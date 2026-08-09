#!/usr/bin/env python3
"""
115 管家 - Web 服务
====================
提供 Web 界面管理 115 分享链接：查看信息、转存。
运行: python3 115-server.py
然后打开 http://localhost:8767

依赖: flask, requests (pip3 install flask requests)
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import json
import re
import random
import time
import base64
import threading
import uuid
import unicodedata
from collections import Counter
from datetime import date
from pathlib import Path
from urllib.parse import urlparse, parse_qs

try:
    from flask import Flask, request, jsonify, send_from_directory, Response
except ImportError:
    print("❌ 需要安装 flask: pip3 install flask")
    sys.exit(1)

from server import db as database, tmdb_api, sync

# ============================================================
#  导入 115-transfer 的 API 类
# ============================================================
from pathlib import Path
import requests as req_lib

SCRIPT_DIR = Path(__file__).parent
CONFIG_FILE = SCRIPT_DIR / "115-config.json"
FRONTEND_DIST = SCRIPT_DIR / "frontend" / "dist"

# 115 API 端点
API_SHARE_SNAP = "https://115cdn.com/webapi/share/snap"
API_FILE_LIST = "https://webapi.115.com/files"
API_FILE_LIST_APP = "https://proapi.115.com/android/2.0/ufile/files"
API_DIR_ADD = "https://webapi.115.com/files/add"
API_SAVE_TO_PAN = "https://115cdn.com/webapi/share/receive"
API_SAVE_TO_PAN_APP = "https://proapi.115.com/android/2.0/share/receive"
API_FILE_UPDATE = "https://webapi.115.com/files/edit"
API_HISTORY_RECEIVE_LIST = "https://webapi.115.com/history/receive_list"
API_HISTORY_DELETE = "https://webapi.115.com/history/delete"
API_QRCODE_TOKEN = "/api/1.0/web/1.0/token/"
API_QRCODE_IMAGE = "/api/1.0/web/1.0/qrcode"
API_QRCODE_STATUS = "/get/status/"
API_QRCODE_RESULT = "/app/1.0/alipaymini/1.0/login/qrcode/"
QRCODE_BASES = [
    "https://qrcodeapi.115.com",
    "https://hnqrcodeapi.115.com",
    "https://passportapi.115.com",
    "https://hnpassportapi.115.com",
]

QR_LOGIN_TTL_SECONDS = 300
SESSION_VERIFY_TTL_SECONDS = 15 * 60
SCAN_REQUEST_DELAY = float(os.environ.get("PAN115_SCAN_DELAY", "0.3"))
qr_logins = {}
qr_login_lock = threading.Lock()
background_tasks = {}
background_tasks_lock = threading.Lock()


# ============================================================
#  115 API 封装
# ============================================================
class Pan115:
    def __init__(self, cookie_str=""):
        self.session = req_lib.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
        })
        if cookie_str:
            self.session.headers["Cookie"] = cookie_str.strip()

    def check_cookie(self):
        try:
            r = self.session.get("https://webapi.115.com/user/info", timeout=10)
            data = r.json()
            if isinstance(data, dict) and data.get("state"):
                return True
        except Exception:
            pass
        try:
            r = self.session.get("https://proapi.115.com/android/2.0/user/info", timeout=10)
            data = r.json()
            return bool(isinstance(data, dict) and data.get("state"))
        except Exception:
            return False

    def get_share_info(self, share_code, receive_code=""):
        try:
            referer = f"https://115cdn.com/s/{share_code}"
            if receive_code:
                referer += f"?password={receive_code}&"
            else:
                referer += "?"
            # 分页获取所有文件（每页最多 200 个）
            all_files = []
            all_id_map = {}
            total_count = 0
            page_size = 200
            offset = 0
            shareinfo = {}
            expire_time = 0
            is_expired = False
            user_name = ""
            last_data = None

            while True:
                r = self.session.get(
                    API_SHARE_SNAP,
                    params={
                        "share_code": share_code,
                        "receive_code": receive_code,
                        "cid": "0",
                        "limit": str(page_size),
                        "offset": str(offset),
                        "format": "json",
                    },
                    headers={"Referer": referer},
                    timeout=10,
                )
                data = r.json()
                if not (isinstance(data, dict) and data.get("state")):
                    last_data = data if isinstance(data, dict) else None
                    break

                d = data.get("data", {})
                last_data = d
                if offset == 0:
                    shareinfo = d.get("shareinfo", {})
                    total_count = d.get("count", 0)
                    expire_time = shareinfo.get("expire_time", 0)
                    is_expired = expire_time > 0 and expire_time < time.time()
                    user_name = d.get("userinfo", {}).get("user_name", "")

                page_files = d.get("list", [])
                if not page_files:
                    break

                for f in page_files:
                    fc = f.get("fc", 0)
                    fid = str(f.get("fid", "") or f.get("cid", "")) if fc == 1 else str(f.get("cid", ""))
                    all_files.append({
                        "fid": fid,
                        "name": f.get("n", "?"),
                        "is_dir": f.get("fc", 1) == 0,
                        "size": int(f.get("s", 0)),
                    })
                    all_id_map[fid] = f.get("n", "?")

                offset += page_size
                if offset >= total_count:
                    break
                time.sleep(0.3)

            if not all_files and not total_count:
                return {"state": False, "error": (last_data or {}).get("error", "链接无效")}
            return {
                    "state": True,
                    "title": shareinfo.get("share_title", "未知"),
                    "file_count": total_count,
                    "size": shareinfo.get("file_size", 0),
                    "is_expired": is_expired,
                    "expire_time": expire_time,
                    "files": all_files,
                    "file_id_map": all_id_map,
                    "browse_cid": "0",
                    "user_name": user_name,
                }
        except Exception as e:
            return {"state": False, "error": str(e)}

    def _find_subfolder(self, parent_cid, name):
        """在 parent_cid 下查找名为 name 的子目录（分页）。"""
        offset = 0
        limit = 200
        while True:
            try:
                r = self.session.get(
                    API_FILE_LIST,
                    params={"cid": parent_cid, "offset": offset, "limit": limit, "show_dir": 1},
                    timeout=10,
                )
                data = r.json()
                if not isinstance(data, dict) or not data.get("state"):
                    break
                items = data.get("data", [])
                if not items:
                    break
                for item in items:
                    if item.get("n") == name and not bool(item.get("f", 0)):
                        return item.get("cid", "")
                count = data.get("count", 0)
                offset += limit
                if offset >= count:
                    break
            except Exception:
                break
        return None

    def _create_folder(self, parent_cid, name):
        try:
            r = self.session.post(
                API_DIR_ADD,
                data={"pid": parent_cid, "cname": name},
                timeout=10,
            )
            data = r.json()
            if isinstance(data, dict) and data.get("state"):
                return data.get("cid", data.get("file_id", ""))
        except:
            pass
        return None

    def ensure_path(self, path):
        parts = [p for p in path.split("/") if p.strip()]
        if not parts:
            return "0"
        current_cid = "0"
        for part in parts:
            found = self._find_subfolder(current_cid, part)
            if found:
                current_cid = found
            else:
                created = self._create_folder(current_cid, part)
                if created:
                    current_cid = created
                else:
                    return None
            time.sleep(0.3)
        return current_cid

    def find_cid_by_path(self, path):
        """根据路径找到目录 cid，不自动创建。
        返回 cid 或 None。
        """
        parts = [p for p in path.split("/") if p.strip()]
        if not parts:
            return "0"
        current_cid = "0"
        for part in parts:
            found = self._find_subfolder(current_cid, part)
            if found:
                current_cid = found
            else:
                return None
            time.sleep(0.2)
        return current_cid

    def list_dir(self, cid, limit=200):
        """列出指定 cid 目录下的所有文件（分页取完）。
        返回 [{"fid": str, "name": str, "size": int, "is_dir": bool}, ...]
        """
        all_files = []
        offset = 0
        page_size = min(limit, 200)
        fallback = False
        while True:
            try:
                r = self.session.get(
                    API_FILE_LIST,
                    params={
                        "cid": cid,
                        "offset": offset,
                        "limit": page_size,
                        "show_dir": 1,
                    },
                    timeout=15,
                )
                if r.status_code != 200:
                    raise RuntimeError(f"webapi files HTTP {r.status_code}")
                data = r.json()
                if not isinstance(data, dict) or not data.get("state"):
                    raise RuntimeError("webapi files 不可用，切换到 App 端接口")
                page_files = data.get("data", [])
                if not page_files:
                    break
                for f in page_files:
                    # 稳健判断：有 cid 无 fid → 目录；f 字段 0→目录 1→文件
                    has_cid = bool(f.get("cid"))
                    has_fid = bool(f.get("fid"))
                    f_val = f.get("f", None)
                    if f_val is not None:
                        is_dir = not bool(f_val)
                    elif has_cid and not has_fid:
                        is_dir = True
                    else:
                        is_dir = False
                    fid = str(f.get("cid") if is_dir else f.get("fid", ""))
                    all_files.append({
                        "fid": fid,
                        "name": f.get("n", "?"),
                        "size": int(f.get("s", 0)),
                        "is_dir": is_dir,
                    })
                count = data.get("count", 0)
                offset += page_size
                if offset >= count:
                    break
                time.sleep(0.3)
            except Exception:
                fallback = True
                break
        if fallback:
            # webapi 被风控时退回 115 App 端接口，接口字段不同（fn/fs/fc/fid）
            all_files = []
            offset = 0
            while True:
                try:
                    r = self.session.get(
                        API_FILE_LIST_APP,
                        params={
                            "cid": cid,
                            "offset": offset,
                            "limit": page_size,
                            "show_dir": 1,
                            "record_open_time": 0,
                        },
                        timeout=15,
                    )
                    data = r.json()
                    if not isinstance(data, dict) or not data.get("state"):
                        break
                    page_files = data.get("data", [])
                    if not page_files:
                        break
                    for f in page_files:
                        is_dir = str(f.get("fc", "1")) == "0"
                        fid = str(f.get("fid", ""))
                        all_files.append({
                            "fid": fid,
                            "name": f.get("fn", "?"),
                            "size": int(f.get("fs") or 0),
                            "is_dir": is_dir,
                        })
                    count = data.get("count", 0)
                    offset += page_size
                    if offset >= count:
                        break
                    time.sleep(0.3)
                except Exception:
                    break
        return all_files

    def list_tree_files(self, cid, max_files=20000, progress=None):
        """Bounded breadth-first scan used to refresh a resource index."""
        files, pending = [], [cid]
        while pending and len(files) < max_files:
            current = pending.pop(0)
            for item in self.list_dir(current):
                if item["is_dir"]:
                    pending.append(item["fid"])
                else:
                    files.append(item)
                    if len(files) >= max_files:
                        break
            if progress:
                progress(len(files))
            time.sleep(SCAN_REQUEST_DELAY)
        return files, bool(pending)

    def add_cloud_download(self, url, target_cid="0"):
        """添加离线下载任务（115闪推兼容方式）。
        1. 获取 sign + time
        2. 提交离线任务
        """
        try:
            # 1. 获取用户 uid（优先从 Cookie 提取，省一次 API 调用）
            uid = ""
            cookie = self.session.headers.get("Cookie", "")
            m = re.search(r'\bUID=([^;]+)', cookie, re.IGNORECASE)
            if m:
                uid = m.group(1)
            if not uid:
                try:
                    ur = self.session.get("https://webapi.115.com/user/info", timeout=10)
                    uinfo = ur.json()
                    if isinstance(uinfo, dict) and uinfo.get("state"):
                        uid = str(uinfo.get("data", {}).get("user_id", ""))
                except Exception:
                    pass

            # 2. 获取 sign 和 time
            sign = ""
            signtime = ""
            try:
                sr = self.session.get(
                    "https://115.com/?ct=offline&ac=space",
                    timeout=10,
                )
                sdata = sr.json()
                if isinstance(sdata, dict):
                    sign = str(sdata.get("sign", ""))
                    signtime = str(sdata.get("time", ""))
            except Exception:
                pass

            if not sign:
                return {"state": False, "error": "获取签名失败，Cookie 可能已过期"}

            # 3. 提交离线任务
            post_data = {
                "url": url,
                "sign": sign,
                "time": signtime,
            }
            if uid:
                post_data["uid"] = uid
            if target_cid and target_cid != "0":
                post_data["wp_path_id"] = target_cid

            r = self.session.post(
                "https://115.com/web/lixian/?ct=lixian&ac=add_task_url",
                data=post_data,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                    "Accept": "application/json, text/javascript, */*; q=0.01",
                    "Origin": "https://115.com",
                    "Referer": "https://115.com/",
                },
                timeout=30,
            )
            try:
                result = r.json()
            except Exception:
                snippet = (r.text or "")[:300]
                return {
                    "state": False,
                    "error": f"115 返回异常: {snippet}" if snippet else "115 无响应",
                }
            if isinstance(result, dict):
                err = result.get("error", result.get("message", ""))
                if not err and not result.get("state"):
                    err = result.get("msg", str(result)[:200])
                return {
                    "state": result.get("state", False),
                    "task_id": result.get("task_id", result.get("info_hash", "")),
                    "error": err,
                }
            return {"state": False, "error": "请求失败: " + str(r.text)[:200]}
        except Exception as e:
            return {"state": False, "error": str(e)}

    def get_offline_tasks(self, page=1, limit=20):
        """查询离线下载任务列表。"""
        try:
            r = self.session.get(
                "https://115.com/web/lixian/?ct=lixian&ac=task_lists",
                params={"page": page, "limit": limit},
                headers={
                    "Accept": "application/json, text/javascript, */*; q=0.01",
                    "Referer": "https://115.com/",
                },
                timeout=15,
            )
            try:
                data = r.json()
            except Exception:
                return {"state": False, "error": "获取任务列表失败"}
            if isinstance(data, dict) and data.get("state"):
                tasks = data.get("data", []) if isinstance(data.get("data"), list) else data.get("data", {}).get("list", [])
                return {
                    "state": True,
                    "tasks": [
                        {
                            "task_id": t.get("info_hash", ""),
                            "name": t.get("name", ""),
                            "status": t.get("status", 0),
                            "percent": t.get("percent", t.get("percentDone", 0)),
                            "size": t.get("size", ""),
                        }
                        for t in tasks
                    ],
                }
            return {"state": False, "error": data.get("error", "获取失败")}
        except Exception as e:
            return {"state": False, "error": str(e)}

    def save_files_to_pan(self, share_code, receive_code, cid, file_ids=""):
        """
        转存指定文件到目录
        file_ids: 逗号分隔的文件ID，空字符串=全部
        """
        try:
            data = {
                "share_code": share_code,
                "receive_code": receive_code,
                "cid": cid,
                "file_id": file_ids or "",
            }
            r = self.session.post(API_SAVE_TO_PAN, data=data, timeout=30)
            return r.json()
        except Exception as e:
            return {"state": False, "error": str(e)}

    def save_files_to_pan_app(self, share_code, receive_code, cid, file_ids=""):
        """通过 115 App 端接口转存（部分场景可绕过网页端“已接收”限制）。"""
        try:
            data = {
                "share_code": share_code,
                "receive_code": receive_code,
                "cid": cid,
                "file_id": file_ids or "",
            }
            r = self.session.post(
                API_SAVE_TO_PAN_APP,
                data=data,
                headers={"Referer": "https://115.com/"},
                timeout=30,
            )
            return r.json()
        except Exception as e:
            return {"state": False, "error": str(e)}

    def get_receive_history(self, limit=1150, offset=0):
        """获取 115 接收记录（最近接收/我的接收历史）。"""
        try:
            r = self.session.get(
                API_HISTORY_RECEIVE_LIST,
                params={"limit": limit, "offset": offset},
                timeout=15,
            )
            data = r.json()
            if not isinstance(data, dict) or not data.get("state"):
                return {"state": False, "error": data.get("message") or data.get("error") or "获取接收记录失败"}
            d = data.get("data") or {}
            records = d.get("list") or []
            return {"state": True, "total": int(d.get("total") or len(records)), "records": records}
        except Exception as e:
            return {"state": False, "error": str(e)}

    def delete_receive_history(self, ids, with_file=0):
        """删除 115 接收记录（with_file=0 时不会删除任何网盘文件）。"""
        try:
            if isinstance(ids, (list, tuple)):
                ids = ",".join(str(x) for x in ids)
            r = self.session.post(
                API_HISTORY_DELETE,
                data={"id": str(ids), "with_file": str(with_file)},
                headers={"Referer": "https://115.com/"},
                timeout=15,
            )
            data = r.json()
            if isinstance(data, dict) and data.get("state"):
                return {"state": True, "deleted": len(str(ids).split(","))}
            return {"state": False, "error": data.get("message") or data.get("error") or "清理接收记录失败"}
        except Exception as e:
            return {"state": False, "error": str(e)}

    def rename_file(self, file_id, new_name):
        """重命名 115 中的文件（扩展名必须保持不变）。"""
        try:
            r = self.session.post(
                API_FILE_UPDATE,
                data={"fid": str(file_id), "file_name": new_name},
                headers={"Referer": "https://115.com/"},
                timeout=15,
            )
            data = r.json()
            if isinstance(data, dict) and data.get("state"):
                return True, ""
            return False, data.get("error") or data.get("msg") or "重命名失败"
        except Exception as e:
            return False, str(e)


# ============================================================
#  Flask Web 服务
# ============================================================
app = Flask(__name__, static_folder=None)

@app.after_request
def add_cors_headers(response):
    """允许 Web/PWA 跨源访问同一 Flask 网关。"""
    response.headers["Access-Control-Allow-Origin"] = request.headers.get("Origin", "*")
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    return response

# 加载配置
config = {}
if CONFIG_FILE.exists():
    with open(CONFIG_FILE) as f:
        config = json.load(f)

def save_config():
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    try:
        os.chmod(CONFIG_FILE, 0o600)
    except OSError:
        pass

def get_pan():
    cookie = config.get("cookie", "")
    if not cookie:
        return None
    return Pan115(cookie)


def get_user_cookie(user_id: int = None) -> str:
    """获取 115 cookie：多端共享同一份，走全局 config。"""
    return config.get("cookie", "")


def _save_pan_session(cookie):
    """Persist only the issued session credential, never login credentials."""
    config["cookie"] = cookie
    config["cookie_status"] = "valid"
    config["last_verified_at"] = time.time()
    save_config()


def _pan_session_status():
    """Use a bounded local validity cache to avoid unnecessary 115 checks."""
    cookie = config.get("cookie", "")
    if not cookie:
        return False, False
    last_verified = float(config.get("last_verified_at", 0) or 0)
    if config.get("cookie_status") == "valid" and time.time() - last_verified < SESSION_VERIFY_TTL_SECONDS:
        return True, True
    valid = Pan115(cookie).check_cookie()
    config["cookie_status"] = "valid" if valid else "expired"
    config["last_verified_at"] = time.time()
    save_config()
    return valid, False


def _clean_qr_logins():
    cutoff = time.time() - QR_LOGIN_TTL_SECONDS
    with qr_login_lock:
        for uid, entry in list(qr_logins.items()):
            if entry["created_at"] < cutoff:
                qr_logins.pop(uid, None)


def _serialize_cookie(cookie):
    if isinstance(cookie, dict):
        return "; ".join(f"{str(key).upper()}={value}" for key, value in cookie.items() if value)
    return str(cookie or "").strip()

def parse_share_url(url):
    """从 URL 中提取分享码和密码"""
    m = re.search(r'/s/([a-zA-Z0-9]+)', url)
    share_code = m.group(1) if m else None
    # 从 query 中提取 password
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    password = qs.get("password", [""])[0]
    return share_code, password


def _match_key(value):
    """A stable, conservative grouping key for release-style filenames."""
    value = re.sub(r'\.[^.]+$', '', (value or '').lower())
    value = re.sub(r'(s\d{1,2}\s*e\d{1,4}|ep?\s*\d{1,4}|第\s*\d{1,4}\s*[集话話])', ' ', value)
    value = re.sub(r'[\[\](){}._\-]+', ' ', value)
    return re.sub(r'\s+', ' ', value).strip()[:160]


def build_pattern_name(prefix, name):
    """按目标前缀把文件名统一为「前缀.SxxExx.扩展名」，无法识别集数时返回 None。"""
    prefix = re.sub(r"\s+\.+$", "", (prefix or "").strip())
    if not prefix:
        return None
    parsed = sync.parse_episode(name or "")
    if not parsed:
        return None
    ext = (name or "").rpartition(".")[2]
    if not ext:
        return None
    season = max(1, int(parsed["season"] or 1))
    episode = int(parsed["episode"] or 0)
    if episode <= 0:
        return None
    return f"{prefix}.S{season:02d}E{episode:02d}.{ext}"


def _file_episode_prefix(name):
    """取文件名里 SxxExx 之前的部分，作为目标前缀判断依据；无集数时返回 None。"""
    m = re.search(r"[sS]\d{1,2}\s*[eE]\d{1,4}", name or "")
    if not m:
        return None
    return re.sub(r"[\s._\-]+$", "", (name or "")[:m.start()])


def _prefixes_match(a, b):
    return _normalize_prefix(a) == _normalize_prefix(b)


def _normalize_prefix(value):
    """归一化前缀用于比较：忽略大小写、全角/半角、罗马数字写法、常见分隔符。"""
    if not value:
        return ""
    text = unicodedata.normalize("NFKC", str(value).strip().lower())
    return re.sub(r"[\s._\-:：·,，、()\[\]【】{}]+", "", text)


def _resource_files(files):
    return [f for f in files if not f.get("is_dir") and f.get("name")]


def _resource_matches(files):
    """Return exact filename-and-size matches, grouped by cached resource."""
    candidates = _resource_files(files)
    if not candidates:
        return {}
    conn = database.get_db()
    try:
        rows = conn.execute(
            """SELECT rf.resource_id, rf.display_name, rf.filename, rf.file_size, rf.tmdb_valid, r.title, r.path_115
               FROM resource_files rf JOIN resources r ON r.id = rf.resource_id"""
        ).fetchall()
    finally:
        conn.close()
    lookup = {(r["filename"], int(r["file_size"] or 0)): r for r in rows}
    result = {}
    for item in candidates:
        row = lookup.get((item.get("name", ""), int(item.get("size") or 0)))
        if row and row.get("tmdb_valid", 1) != 0:
            entry = result.setdefault(row["resource_id"], {
                "resource_id": row["resource_id"], "title": row["title"],
                "path_115": row["path_115"], "matched_file_ids": [],
            })
            entry["matched_file_ids"].append(item.get("fid", ""))
    return result


def _receive_record_matches(rec, files, target_title):
    """判断一条 115 接收记录是否与本次保存的文件属于同一资源。"""
    rec_name = str(rec.get("file_name") or "")
    parent = str(rec.get("parent_name") or "")
    base = re.sub(r"等\d+个文件\s*$", "", rec_name).strip()
    if not base:
        return False
    for f in files:
        name = str(f.get("name") or "")
        if not name:
            continue
        if base.startswith(name) or name.startswith(base):
            return True
        m1 = re.match(r"^(.*?[sS]\d{1,2})\s*[eE]\d{1,4}", base)
        m2 = re.match(r"^(.*?[sS]\d{1,2})\s*[eE]\d{1,4}", name)
        if m1 and m2 and m1.group(1).lower() == m2.group(1).lower():
            return True
    # 记录可能只保留了目录名（例如整个文件夹被接收），此时用目标目录名兜底
    if target_title and parent == target_title:
        return True
    return False


def _log_receive(share_code, cid, file_ids, endpoint, result):
    """把转存请求与 115 原文响应写入本地日志，便于排查。"""
    try:
        line = json.dumps({
            "ts": time.time(),
            "share_code": share_code,
            "cid": str(cid),
            "file_count": len(file_ids.split(",")) if file_ids else 0,
            "endpoint": endpoint,
            "ok": bool(result.get("state")) if isinstance(result, dict) else False,
            "error": str(result.get("error") or result.get("message") or "")[:500] if isinstance(result, dict) else str(result)[:500],
        }, ensure_ascii=False)
        with open(SCRIPT_DIR / "115-receive.log", "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def _store_resource(title, path_115, folder_id, files, existing_id=None,
                    tmdb_id=None, media_type="tv", poster_url="", overview="",
                    total_episodes=0, parse_episodes=False):
    files = _resource_files(files)
    total_size = sum(int(f.get("size") or 0) for f in files)
    episodes_by_season = {}
    prepared = []
    for item in files:
        display_name = item.get("name", "")
        parsed = sync.parse_episode(display_name) if parse_episodes else None
        season = parsed["season"] if parsed else None
        episode = parsed["episode"] if parsed else None
        if season is not None and episode:
            episodes_by_season.setdefault(season, set()).add(episode)
        prepared.append((item.get("fid", ""), item["name"], display_name,
                         int(item.get("size") or 0), _match_key(display_name), season, episode))
    cached = sum(len(v) for v in episodes_by_season.values())
    seasons_json = json.dumps([
        {"season": s, "cached": len(sorted(episodes_by_season[s])), "total": 0}
        for s in sorted(episodes_by_season)
    ], ensure_ascii=False)
    conn = database.get_db()
    rules_json = "[]"
    try:
        resource_id = existing_id
        if resource_id:
            conn.execute(
                """UPDATE resources SET title = ?, path_115 = ?, folder_id_115 = ?,
                   tmdb_id = ?, media_type = ?, poster_url = ?, overview = ?,
                   total_episodes = ?, cached_episodes = ?, seasons_json = ?,
                   replace_rules_json = ?,
                   file_count = ?, total_size = ?, last_synced_at = CURRENT_TIMESTAMP,
                   updated_at = CURRENT_TIMESTAMP WHERE id = ?""",
                (title, path_115, folder_id, tmdb_id, media_type, poster_url, overview,
                 total_episodes, cached, seasons_json, rules_json,
                 len(files), total_size, resource_id),
            )
            conn.execute("DELETE FROM resource_files WHERE resource_id = ?", (resource_id,))
        else:
            cur = conn.execute(
                """INSERT INTO resources
                   (title, match_key, path_115, folder_id_115, tmdb_id, media_type,
                    poster_url, overview, total_episodes, cached_episodes, seasons_json,
                    replace_rules_json, file_count, total_size)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (title, _match_key(title), path_115, folder_id, tmdb_id, media_type,
                 poster_url, overview, total_episodes, cached, seasons_json,
                 rules_json, len(files), total_size),
            )
            resource_id = cur.lastrowid
        for fid, filename, display_name, size, key, season, episode in prepared:
            conn.execute(
                """INSERT OR REPLACE INTO resource_files
                   (resource_id, fid, filename, display_name, file_size, match_key,
                    season_number, episode_number, cached_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
                (resource_id, fid, filename, display_name, size, key, season, episode),
            )
        conn.commit()
        return resource_id
    finally:
        conn.close()


# ============================================================
#  API 路由
# ============================================================

@app.route("/api/pan/dir", methods=["GET"])
def api_pan_dir():
    """浏览 115 网盘目录，用于把已有资源加入资源库。"""
    pan = get_pan()
    if not pan:
        return jsonify({"ok": False, "error": "115 授权已失效，请重新登录"}), 401
    cid = request.args.get("cid", "0") or "0"
    items = pan.list_dir(cid)
    return jsonify({"ok": True, "items": items, "cid": cid})


@app.route("/api/pan/receive-history", methods=["GET"])
def api_pan_receive_history():
    """读取 115 接收记录（最近接收/我的接收历史）。"""
    pan = get_pan()
    if not pan:
        return jsonify({"ok": False, "error": "115 授权已失效，请重新登录"}), 401
    result = pan.get_receive_history()
    if not result.get("state"):
        return jsonify({"ok": False, "error": result.get("error", "获取接收记录失败")}), 502
    records = []
    for rec in result.get("records", []):
        records.append({
            "id": str(rec.get("id") or ""),
            "name": str(rec.get("file_name") or ""),
            "parent_name": str(rec.get("parent_name") or ""),
            "file_size": int(rec.get("file_size") or 0),
            "create_time": int(rec.get("create_time") or 0),
            "update_time": int(rec.get("update_time") or 0),
        })
    return jsonify({"ok": True, "total": result.get("total", len(records)), "records": records})


@app.route("/api/pan/receive-history/clear", methods=["POST"])
def api_pan_receive_history_clear():
    """清理指定 115 接收记录（with_file=0，只删记录、不删文件）。"""
    pan = get_pan()
    if not pan:
        return jsonify({"ok": False, "error": "115 授权已失效，请重新登录"}), 401
    data = request.get_json() or {}
    ids = data.get("ids") or []
    if isinstance(ids, str):
        ids = ids.split(",")
    ids = [str(x).strip() for x in ids if str(x).strip()]
    if not ids:
        return jsonify({"ok": False, "error": "请指定要清理的接收记录"}), 400
    result = pan.delete_receive_history(ids)
    if not result.get("state"):
        return jsonify({"ok": False, "error": result.get("error", "清理接收记录失败")}), 502
    return jsonify({"ok": True, "deleted": result.get("deleted", len(ids))})


# ============================================================
#  Single-user resource library API
# ============================================================

@app.route("/api/pan/session", methods=["GET", "DELETE"])
def api_pan_session():
    if request.method == "DELETE":
        config.pop("cookie", None)
        config.pop("cookie_status", None)
        config.pop("last_verified_at", None)
        save_config()
        return jsonify({"ok": True})
    valid, cached = _pan_session_status()
    return jsonify({"ok": valid, "cached": cached})


@app.route("/api/pan/qrcode", methods=["POST"])
def api_pan_qrcode():
    """Create a browser/mobile-friendly 115 QR login session."""
    _clean_qr_logins()
    last_error = "无法创建 115 登录二维码"
    for base in QRCODE_BASES:
        try:
            response = req_lib.get(base + API_QRCODE_TOKEN, timeout=12).json()
            token = response.get("data", response) if isinstance(response, dict) else {}
            uid = str(token.get("uid", ""))
            if not uid:
                continue
            image = req_lib.get(base + API_QRCODE_IMAGE, params={"uid": uid}, timeout=12)
            image.raise_for_status()
            with qr_login_lock:
                qr_logins[uid] = {"created_at": time.time(), "token": token, "base": base}
            return jsonify({
                "ok": True,
                "uid": uid,
                "qr_url": "data:image/png;base64," + base64.b64encode(image.content).decode("ascii"),
                "expires_in": QR_LOGIN_TTL_SECONDS,
            })
        except Exception as exc:
            last_error = f"二维码服务不可用: {exc}"
    return jsonify({"ok": False, "error": last_error}), 502


@app.route("/api/pan/qrcode/<uid>", methods=["GET", "DELETE"])
def api_pan_qrcode_status(uid):
    with qr_login_lock:
        entry = qr_logins.get(uid)
    if not entry:
        return jsonify({"ok": False, "status": "expired", "error": "二维码已过期，请重新生成"}), 404
    if request.method == "DELETE":
        with qr_login_lock:
            qr_logins.pop(uid, None)
        return jsonify({"ok": True})
    try:
        base = entry.get("base", QRCODE_BASES[0])
        token = entry["token"]
        state = req_lib.get(base + API_QRCODE_STATUS, params={
            "uid": token.get("uid"), "time": token.get("time"), "sign": token.get("sign"),
        }, timeout=12).json()
        status = int(state.get("status", (state.get("data") or {}).get("status", 0)))
        if status != 2:
            labels = {0: "waiting", 1: "scanned", -1: "expired", -2: "canceled"}
            return jsonify({"ok": True, "status": labels.get(status, "waiting")})

        result = req_lib.post(base + API_QRCODE_RESULT, data={"account": uid}, timeout=20).json()
        cookie = _serialize_cookie(result.get("cookie") or (result.get("data") or {}).get("cookie"))
        if not cookie:
            return jsonify({"ok": True, "status": "confirmed", "error": "扫码已确认，正在获取授权凭据"})
        if not re.search(r'(?:^|;)\s*UID=', cookie, re.IGNORECASE):
            cookie = f"{cookie}; uid={uid}"
        pan = Pan115(cookie)
        if not pan.check_cookie():
            return jsonify({"ok": False, "status": "error", "error": "115 授权凭据验证失败"}), 502
        _save_pan_session(cookie)
        with qr_login_lock:
            qr_logins.pop(uid, None)
        return jsonify({"ok": True, "status": "authorized"})
    except Exception as exc:
        # 轮询阶段的瞬时失败不应让整页 502；前端会继续等待下一次轮询。
        return jsonify({"ok": False, "status": "waiting", "error": f"授权检查暂时失败: {exc}"})

@app.route("/api/resources", methods=["GET"])
def api_resources():
    query = (request.args.get("q") or "").strip().lower()
    conn = database.get_db()
    try:
        sql = "SELECT * FROM resources"
        params = []
        if query:
            sql += " WHERE lower(title) LIKE ? OR lower(path_115) LIKE ?"
            params = [f"%{query}%", f"%{query}%"]
        rows = conn.execute(sql + " ORDER BY updated_at DESC", params).fetchall()
        return jsonify({"ok": True, "items": [dict(r) for r in rows]})
    finally:
        conn.close()


@app.route("/api/resources/<int:resource_id>", methods=["GET", "DELETE"])
def api_resource_item(resource_id):
    conn = database.get_db()
    try:
        if request.method == "DELETE":
            conn.execute("DELETE FROM resource_files WHERE resource_id = ?", (resource_id,))
            cur = conn.execute("DELETE FROM resources WHERE id = ?", (resource_id,))
            conn.commit()
            return jsonify({"ok": bool(cur.rowcount)})
        resource = conn.execute("SELECT * FROM resources WHERE id = ?", (resource_id,)).fetchone()
        if not resource:
            return jsonify({"ok": False, "error": "资源不存在"}), 404
        files = conn.execute(
            """SELECT * FROM resource_files WHERE resource_id = ?
               ORDER BY (season_number IS NULL), season_number,
                        (episode_number IS NULL), episode_number, filename""",
            (resource_id,),
        ).fetchall()
        return jsonify({"ok": True, "item": dict(resource), "files": [dict(r) for r in files]})
    finally:
        conn.close()


@app.route("/api/resources/preview", methods=["POST"])
def api_resource_preview():
    data = request.get_json() or {}
    share_code, password_from_url = parse_share_url(data.get("url", ""))
    password = (data.get("password") or password_from_url or "").strip()
    if not share_code:
        return jsonify({"ok": False, "error": "无法解析 115 分享链接"}), 400
    pan = Pan115()
    info = pan.get_share_info(share_code, password)
    if not info.get("state") or info.get("is_expired"):
        return jsonify({"ok": False, "error": info.get("error", "分享链接不可用")}), 400
    files = info.get("files", [])
    matches = list(_resource_matches(files).values())
    return jsonify({"ok": True, "share_code": share_code, "title": info.get("title", "未命名资源"),
                    "files": files, "matches": matches})


@app.route("/api/resources/import", methods=["POST"])
def api_resource_import():
    pan = get_pan()
    if not pan:
        return jsonify({"ok": False, "error": "115 授权已失效，请重新登录"}), 401
    data = request.get_json() or {}
    share_code, password_from_url = parse_share_url(data.get("url", ""))
    password = (data.get("password") or password_from_url or "").strip()
    if not share_code:
        return jsonify({"ok": False, "error": "无法解析 115 分享链接"}), 400
    files = data.get("files") or []
    selected_ids = set(data.get("file_ids") or [])
    files = [f for f in files if not selected_ids or f.get("fid") in selected_ids]
    if not files:
        return jsonify({"ok": False, "error": "请选择至少一个文件"}), 400
    resource_id = data.get("resource_id")
    path_115 = (data.get("target_path") or "").strip()
    existing = None
    if resource_id:
        conn = database.get_db()
        try:
            row = conn.execute("SELECT * FROM resources WHERE id = ?", (resource_id,)).fetchone()
            existing = dict(row) if row else None
            if existing and not path_115:
                path_115 = existing.get("path_115") or ""
        finally:
            conn.close()
    if not path_115:
        return jsonify({"ok": False, "error": "请选择或新建保存目录"}), 400
    cid = pan.ensure_path(path_115)
    if not cid:
        return jsonify({"ok": False, "error": "无法创建或访问目标目录"}), 400
    dir_index = {}
    try:
        for item in pan.list_dir(cid):
            dir_index[(item["name"], int(item.get("size") or 0))] = True
    except Exception:
        pass
    duplicates = []
    to_save = []
    for f in files:
        effective_name = f.get("name", "")
        if (effective_name, int(f.get("size") or 0)) in dir_index:
            duplicates.append(effective_name)
        else:
            to_save.append(f.get("fid", ""))
    if duplicates:
        return jsonify({
            "ok": False,
            "error": "以下文件已存在于 115 目标目录，已阻止重复保存：" + "、".join(duplicates[:10]),
        }), 409
    if not to_save:
        return jsonify({"ok": False, "error": "没有需要保存的文件"}), 400
    file_ids_param = ",".join(to_save)
    result = pan.save_files_to_pan(share_code, password, cid, file_ids_param)
    _log_receive(share_code, cid, file_ids_param, "webapi/share/receive", result)
    already_received = False
    if not isinstance(result, dict) or not result.get("state"):
        err_text = str(result.get("error") or result.get("message") or "转存失败")
        if "已接收" in err_text or "无需重复接收" in err_text:
            already_received = True
            # 网页端被“已接收”拦截时，尝试 115 App 端接口（部分场景不受同一限制）
            app_result = pan.save_files_to_pan_app(share_code, password, cid, file_ids_param)
            _log_receive(share_code, cid, file_ids_param, "proapi/android/2.0/share/receive", app_result)
            if isinstance(app_result, dict) and app_result.get("state"):
                result = app_result
            else:
                app_err = str(app_result.get("error") or app_result.get("message") or "") if isinstance(app_result, dict) else ""
                if "已接收" not in app_err and "无需重复接收" not in app_err:
                    # App 端报的是别的错误，就按普通失败展示，避免误导
                    already_received = False
                    result = app_result
                err_text = app_err or err_text
    if not (isinstance(result, dict) and result.get("state")):
        if already_received:
            target_title = path_115.rstrip("/").split("/")[-1]
            matched = []
            try:
                hist = pan.get_receive_history()
                if hist.get("state"):
                    for rec in hist.get("records", []):
                        if _receive_record_matches(rec, files, target_title):
                            matched.append({
                                "id": str(rec.get("id") or ""),
                                "name": str(rec.get("file_name") or ""),
                                "parent_name": str(rec.get("parent_name") or ""),
                                "file_size": int(rec.get("file_size") or 0),
                                "create_time": int(rec.get("create_time") or 0),
                            })
            except Exception:
                pass
            return jsonify({
                "ok": False,
                "code": "ALREADY_RECEIVED",
                "error": "115 提示这些文件已接收过（网页端与 App 端接口均被拦截）：即使目标目录里已删除，115 侧仍认为该分享已接收。清理接收记录不一定能解除限制，可能需要分享者重新生成一个新分享链接。",
                "receive_raw": err_text,
                "receive_records": matched,
                "receive_count": len(matched),
            }), 409
        return jsonify({"ok": False, "error": err_text})
    title = (existing or {}).get("title") or path_115.rstrip("/").split("/")[-1]
    indexed_files, truncated = pan.list_tree_files(cid)
    stored_id = _store_resource(
        title, path_115, cid, indexed_files, resource_id,
        tmdb_id=(existing or {}).get("tmdb_id") or None,
        media_type=(existing or {}).get("media_type") or "tv",
        poster_url=(existing or {}).get("poster_url") or "",
        overview=(existing or {}).get("overview") or "",
        total_episodes=int((existing or {}).get("total_episodes") or 0),
        parse_episodes=True,
    )
    return jsonify({"ok": True, "resource_id": stored_id, "target_path": path_115,
                    "index_truncated": truncated})
@app.route("/api/resources/<int:resource_id>/title", methods=["POST"])
def api_resource_title(resource_id):
    """修改资源库中的本地显示名称（不影响 115 网盘目录名）。"""
    data = request.get_json() or {}
    title = (data.get("title") or "").strip()
    if not title:
        return jsonify({"ok": False, "error": "标题不能为空"}), 400
    conn = database.get_db()
    try:
        cur = conn.execute(
            """UPDATE resources SET title = ?, match_key = ?, updated_at = CURRENT_TIMESTAMP
               WHERE id = ?""",
            (title, _match_key(title), resource_id),
        )
        conn.commit()
        if not cur.rowcount:
            return jsonify({"ok": False, "error": "资源不存在"}), 404
        row = conn.execute("SELECT * FROM resources WHERE id = ?", (resource_id,)).fetchone()
        return jsonify({"ok": True, "item": dict(row) if row else None})
    finally:
        conn.close()








@app.route("/api/resources/<int:resource_id>/tmdb-refresh", methods=["POST"])
def api_resource_tmdb_refresh(resource_id):
    """只同步 TMDB 元数据与剧集缓存，不扫描 115 目录。"""
    conn = database.get_db()
    try:
        row = conn.execute("SELECT * FROM resources WHERE id = ?", (resource_id,)).fetchone()
        if not row:
            return jsonify({"ok": False, "error": "资源不存在"}), 404
        if not row["tmdb_id"]:
            return jsonify({"ok": False, "error": "该资源尚未关联 TMDB"}), 400
        media_type = row["media_type"] or "tv"
        detail = tmdb_api.get_details(row["tmdb_id"], media_type)
        if not detail.get("ok"):
            return jsonify({"ok": False, "error": detail.get("error", "TMDB 请求失败")}), 502
        try:
            sync._fetch_tmdb_episodes(row["tmdb_id"], conn)
        except Exception:
            pass
        total_episodes = int(detail.get("total_episodes") or row["total_episodes"] or 0)
        aired = conn.execute(
            """SELECT MAX(episode_number) AS latest FROM tmdb_episode_cache
               WHERE tmdb_id = ? AND air_date != '' AND air_date <= ?""",
            (row["tmdb_id"], date.today().isoformat()),
        ).fetchone()
        latest_episode = int(aired["latest"] or 0) if aired else 0
        conn.execute(
            """UPDATE resources
               SET poster_url = ?, overview = ?, total_episodes = ?, latest_episode = ?, media_type = ?,
                   updated_at = CURRENT_TIMESTAMP
               WHERE id = ?""",
            (detail.get("poster_url") or row["poster_url"] or "",
             detail.get("overview") or row["overview"] or "",
             total_episodes, latest_episode, media_type, resource_id),
        )
        conn.commit()
        item = dict(conn.execute("SELECT * FROM resources WHERE id = ?", (resource_id,)).fetchone())
        return jsonify({"ok": True, "item": item})
    finally:
        conn.close()

def _update_task(task_id, **fields):
    with background_tasks_lock:
        if task_id in background_tasks:
            background_tasks[task_id].update(fields)


def _run_add_folder(task_id, data):
    pan = get_pan()
    try:
        if not pan:
            raise RuntimeError("115 授权已失效，请重新登录")
        path_115 = (data.get("path_115") or "").strip().strip("/")
        if not path_115:
            raise RuntimeError("请输入 115 网盘目录路径")
        _update_task(task_id, stage="正在验证目录")
        cid = pan.find_cid_by_path(path_115)
        if not cid:
            raise RuntimeError("在 115 网盘中找不到该目录，请确认路径")

        title = (data.get("title") or "").strip() or path_115.rstrip("/").split("/")[-1]
        tmdb_id = data.get("tmdb_id") or None
        media_type = (data.get("media_type") or "tv").strip()

        _update_task(task_id, stage="正在扫描目录", total=0, current=0)
        files, truncated = pan.list_tree_files(
            cid, progress=lambda n: _update_task(task_id, current=n))
        _update_task(task_id, stage="正在建立索引", current=len(files), total=len(files))
        resource_id = _store_resource(
            title, path_115, cid, files,
            tmdb_id=tmdb_id,
            media_type=media_type,
            poster_url=(data.get("poster_url") or "").strip(),
            overview=(data.get("overview") or "").strip(),
            total_episodes=int(data.get("total_episodes") or 0),
        )
        _update_task(task_id, stage="正在同步集数与 TMDB", total=0, current=0)
        sync_result = sync.sync_resource_item(
            resource_id, pan, progress=lambda n: _update_task(task_id, current=n, total=n))
        conn = database.get_db()
        try:
            row = conn.execute("SELECT * FROM resources WHERE id = ?", (resource_id,)).fetchone()
            item = dict(row) if row else None
        finally:
            conn.close()
        _update_task(task_id, done=True, result={
            "item": item,
            "sync": sync_result,
            "index_truncated": truncated,
        })
    except Exception as exc:
        _update_task(task_id, done=True, error=str(exc))


def _run_rename_files(task_id, resource_id, prefix, renames=None, concurrency=1, interval_ms=300):
    pan = get_pan()
    try:
        if not pan:
            raise RuntimeError("115 授权已失效，请重新登录")
        conn = database.get_db()
        try:
            row = conn.execute("SELECT * FROM resources WHERE id = ?", (resource_id,)).fetchone()
        finally:
            conn.close()
        if not row:
            raise RuntimeError("资源不存在")
        cid = row["folder_id_115"] or ""
        if not cid:
            cid = pan.find_cid_by_path(row["path_115"])
        if not cid:
            raise RuntimeError(f"在 115 网盘中找不到目录: {row['path_115']}")

        skipped = 0
        skipped_samples = []
        truncated = False
        tasks = []
        if renames:
            for r in renames:
                fid = str(r.get("fid") or "").strip()
                old = str(r.get("old_name") or "").strip()
                new_name = str(r.get("new_name") or "").strip()
                if not fid or not old or not new_name or new_name == old:
                    continue
                if new_name.rpartition(".")[-1].lower() != old.rpartition(".")[-1].lower():
                    skipped += 1
                    if len(skipped_samples) < 10:
                        skipped_samples.append(f"{old}：扩展名不一致，已跳过")
                    continue
                tasks.append((fid, old, new_name))
        else:
            prefix = re.sub(r"\s+\.+$", "", (prefix or row["title"] or "").strip())
            if not prefix:
                raise RuntimeError("请输入目标前缀")
            _update_task(task_id, stage="正在扫描目录", total=0, current=0)
            files, truncated = pan.list_tree_files(
                cid, progress=lambda n: _update_task(task_id, current=n))
            for item in files:
                old = item.get("name", "")
                current_prefix = _file_episode_prefix(old)
                new_name = build_pattern_name(prefix, old)
                if current_prefix and _prefixes_match(current_prefix, prefix):
                    # 目标前缀与原名一致，无需修改
                    continue
                if not new_name:
                    skipped += 1
                    if len(skipped_samples) < 10:
                        skipped_samples.append(old)
                elif new_name != old:
                    tasks.append((str(item.get("fid", "")), old, new_name))

        total = len(tasks)
        if total == 0:
            _update_task(task_id, done=True, result={
                "item": dict(row),
                "renamed": 0,
                "skipped": skipped,
                "skipped_samples": skipped_samples,
                "errors": [],
                "index_truncated": False,
            })
            return

        concurrency = max(1, min(int(concurrency or 1), 5))
        interval = max(0.0, float(interval_ms or 300)) / 1000.0
        cookie = config.get("cookie", "")
        renamed = [0]
        errors = []
        state_lock = threading.Lock()
        done = [0]

        def worker(items):
            local_pan = Pan115(cookie)
            for fid, old, new_name in items:
                try:
                    ok, err = local_pan.rename_file(fid, new_name)
                except Exception as exc:
                    ok, err = False, str(exc)
                with state_lock:
                    if ok:
                        renamed[0] += 1
                    else:
                        errors.append(f"{old} → {new_name}：{err}")
                    done[0] += 1
                    _update_task(task_id, stage=f"正在重命名 {done[0]}/{total}",
                                 current=done[0], total=total)
                if interval > 0:
                    time.sleep(interval * random.uniform(0.7, 1.3))

        chunks = [tasks[i::concurrency] for i in range(concurrency)]
        threads = [threading.Thread(target=worker, args=(chunk,), daemon=True)
                   for chunk in chunks if chunk]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        if done[0] < total:
            # 保险：若有 worker 意外中断，把未执行完的数量补报为失败，避免“悄悄只改了一个”
            missing = total - done[0]
            with state_lock:
                errors.append(f"有 {missing} 个文件未执行完成，请重新勾选后再试")
                done[0] = total
            _update_task(task_id, current=total)

        conn = database.get_db()
        try:
            conn.execute(
                "UPDATE resources SET replace_rules_json = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                ("[]", resource_id),
            )
            conn.commit()
        finally:
            conn.close()

        _update_task(task_id, stage="正在重建索引", total=0, current=0)
        sync_result = sync.sync_resource_item(
            resource_id, pan, progress=lambda n: _update_task(task_id, current=n, total=n))
        conn = database.get_db()
        try:
            row = conn.execute("SELECT * FROM resources WHERE id = ?", (resource_id,)).fetchone()
            item = dict(row) if row else None
        finally:
            conn.close()
        _update_task(task_id, done=True, result={
            "item": item,
            "renamed": renamed[0],
            "skipped": skipped,
            "skipped_samples": skipped_samples,
            "errors": errors[:30],
            "index_truncated": truncated,
            "sync": sync_result,
        })
    except Exception as exc:
        _update_task(task_id, done=True, error=str(exc))


def _run_sync_all(task_id):
    pan = get_pan()
    try:
        if not pan:
            raise RuntimeError("115 授权已失效，请重新登录")
        conn = database.get_db()
        try:
            rows = conn.execute("SELECT id, title FROM resources ORDER BY updated_at DESC").fetchall()
        finally:
            conn.close()
        total = len(rows)
        if total == 0:
            _update_task(task_id, done=True, result={"synced": 0, "errors": []})
            return
        synced = 0
        errors = []
        for idx, row in enumerate(rows):
            _update_task(task_id, stage=f"正在同步 {idx + 1}/{total}：{row['title']}",
                         current=idx, total=total)
            result = sync.sync_resource_item(row["id"], pan)
            if result.get("ok"):
                synced += 1
            else:
                errors.append(f"{row['title']}：{result.get('error', '同步失败')}")
            _update_task(task_id, current=idx + 1)
        _update_task(task_id, done=True, result={"synced": synced, "errors": errors[:30]})
    except Exception as exc:
        _update_task(task_id, done=True, error=str(exc))


@app.route("/api/resources/sync-all", methods=["POST"])
def api_resource_sync_all():
    """后台全量从 115 同步所有资源，首页刷新后本地与网盘保持一致。"""
    task_id = uuid.uuid4().hex
    with background_tasks_lock:
        background_tasks[task_id] = {
            "done": False,
            "stage": "准备中",
            "current": 0,
            "total": 0,
            "error": None,
            "result": None,
            "created_at": time.time(),
        }
    threading.Thread(target=_run_sync_all, args=(task_id,), daemon=True).start()
    return jsonify({"ok": True, "task_id": task_id})


@app.route("/api/resources/folder", methods=["POST"])
def api_resource_add_folder():
    """异步把 115 网盘已有目录加入资源库；前端轮询任务进度。"""
    data = request.get_json() or {}
    if not (data.get("path_115") or "").strip():
        return jsonify({"ok": False, "error": "请输入 115 网盘目录路径"}), 400
    task_id = uuid.uuid4().hex
    with background_tasks_lock:
        background_tasks[task_id] = {
            "done": False,
            "stage": "准备中",
            "current": 0,
            "total": 0,
            "error": None,
            "result": None,
            "created_at": time.time(),
        }
    threading.Thread(target=_run_add_folder, args=(task_id, data), daemon=True).start()
    return jsonify({"ok": True, "task_id": task_id})


@app.route("/api/resources/<int:resource_id>/rename-files", methods=["POST"])
def api_resource_rename_files(resource_id):
    """批量重命名：支持按前缀自动生成，或传入明确的 renames 列表；可调并发与间隔防风控。"""
    data = request.get_json() or {}
    prefix = (data.get("prefix") or "").strip()
    renames = data.get("renames")
    if not renames and not prefix:
        conn = database.get_db()
        try:
            row = conn.execute("SELECT title FROM resources WHERE id = ?", (resource_id,)).fetchone()
            prefix = row["title"] if row else ""
        finally:
            conn.close()
    prefix = prefix or ""
    concurrency = max(1, min(int(data.get("concurrency") or 1), 5))
    interval_ms = max(0, int(data.get("interval_ms") or 300))
    task_id = uuid.uuid4().hex
    with background_tasks_lock:
        background_tasks[task_id] = {
            "done": False,
            "stage": "准备中",
            "current": 0,
            "total": 0,
            "error": None,
            "result": None,
            "created_at": time.time(),
        }
    threading.Thread(
        target=_run_rename_files,
        args=(task_id, resource_id, prefix),
        kwargs={"renames": renames, "concurrency": concurrency, "interval_ms": interval_ms},
        daemon=True,
    ).start()
    return jsonify({"ok": True, "task_id": task_id})


@app.route("/api/resources/<int:resource_id>/rename-preview", methods=["POST"])
def api_resource_rename_preview(resource_id):
    """预览批量重命名结果（实时扫描 115 目录，不修改任何文件）。"""
    data = request.get_json() or {}
    prefix = (data.get("prefix") or "").strip()
    requested_prefix = prefix
    conn = database.get_db()
    try:
        row = conn.execute(
            "SELECT title, folder_id_115, path_115 FROM resources WHERE id = ?",
            (resource_id,),
        ).fetchone()
        if not row:
            return jsonify({"ok": False, "error": "资源不存在"}), 404
    finally:
        conn.close()
    pan = get_pan()
    if not pan:
        return jsonify({"ok": False, "error": "115 授权已失效，请重新登录"}), 401
    cid = row["folder_id_115"] or ""
    if not cid:
        cid = pan.find_cid_by_path(row["path_115"])
    if not cid:
        return jsonify({"ok": False, "error": f"在 115 网盘中找不到目录: {row['path_115']}"}), 400
    try:
        files, _ = pan.list_tree_files(cid, max_files=20000)
    except Exception as exc:
        return jsonify({"ok": False, "error": f"扫描目录失败：{exc}"}), 502
    # 自动识别目标前缀：取文件里 SxxExx 之前出现次数最多的部分
    prefix_counter = Counter()
    for f in files:
        p = _file_episode_prefix(f.get("name", ""))
        if p:
            prefix_counter[p] += 1
    suggested_prefix = (prefix_counter.most_common(1) or [(None, 0)])[0][0]
    if not prefix:
        prefix = suggested_prefix or row["title"] or ""
    if not prefix:
        return jsonify({"ok": False, "error": "无法自动识别目标前缀，请手动输入或使用 TMDB 名称"}), 400
    items = []
    parsed = 0
    for f in files:
        name = f.get("name", "")
        ext = name.rpartition(".")[2]
        current_prefix = _file_episode_prefix(name)
        new_name = build_pattern_name(prefix, name)
        no_episode = not sync.parse_episode(name)
        if not new_name and no_episode and ext:
            # 无集数的文件（例如电影）：给出“纯名称.后缀”的候选，需用户手动勾选
            new_name = f"{prefix}.{ext}"
        same_prefix = bool(current_prefix and _prefixes_match(current_prefix, prefix))
        if new_name:
            parsed += 1
        items.append({"fid": f.get("fid", ""), "name": name, "new_name": new_name,
                      "current_prefix": current_prefix,
                      "same_prefix": same_prefix,
                      "no_episode": bool(no_episode),
                      "will_rename": bool(new_name and new_name != name and not same_prefix and not no_episode)})
    # 与详情页保持一致：先按季，再按集，最后按文件名排序；无法解析集数的排最后
    def _rename_sort_key(i):
        p = sync.parse_episode(i["name"])
        season = p["season"] if p else None
        episode = p["episode"] if p else None
        return (season if season is not None else 10 ** 9,
                episode if episode is not None else 10 ** 9,
                i["name"].lower())
    items.sort(key=_rename_sort_key)
    return jsonify({"ok": True, "prefix": prefix, "suggested_prefix": suggested_prefix,
                    "requested_prefix": requested_prefix, "total": len(items),
                    "parsed": parsed, "items": items})


@app.route("/api/resources/<int:resource_id>/rename-file", methods=["POST"])
def api_resource_rename_file(resource_id):
    """单个文件重命名（修改 115 里的真实文件名，并同步本地索引）。"""
    pan = get_pan()
    if not pan:
        return jsonify({"ok": False, "error": "115 授权已失效，请重新登录"}), 401
    data = request.get_json() or {}
    fid = str(data.get("fid") or "").strip()
    new_name = (data.get("new_name") or "").strip()
    if not fid or not new_name:
        return jsonify({"ok": False, "error": "缺少文件或新文件名"}), 400
    conn = database.get_db()
    try:
        row = conn.execute(
            "SELECT * FROM resource_files WHERE resource_id = ? AND fid = ?",
            (resource_id, fid),
        ).fetchone()
    finally:
        conn.close()
    if not row:
        return jsonify({"ok": False, "error": "文件不在当前资源索引中"}), 404
    old = row["filename"]
    if old == new_name:
        return jsonify({"ok": True, "file": dict(row)})
    if new_name.rpartition(".")[-1].lower() != old.rpartition(".")[-1].lower():
        return jsonify({"ok": False, "error": "新文件名扩展名必须与原来一致"}), 400
    ok, err = pan.rename_file(fid, new_name)
    if not ok:
        return jsonify({"ok": False, "error": err}), 502
    parsed = sync.parse_episode(new_name)
    season = parsed["season"] if parsed else None
    episode = parsed["episode"] if parsed else None
    conn = database.get_db()
    try:
        conn.execute(
            """UPDATE resource_files SET filename = ?, display_name = ?, match_key = ?,
               season_number = ?, episode_number = ?, cached_at = CURRENT_TIMESTAMP
               WHERE resource_id = ? AND fid = ?""",
            (new_name, new_name, _match_key(new_name), season, episode, resource_id, fid),
        )
        conn.execute(
            "UPDATE resources SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (resource_id,),
        )
        conn.commit()
        updated = conn.execute(
            "SELECT * FROM resource_files WHERE resource_id = ? AND fid = ?",
            (resource_id, fid),
        ).fetchone()
        return jsonify({"ok": True, "file": dict(updated) if updated else None})
    finally:
        conn.close()


@app.route("/api/tasks/<task_id>", methods=["GET"])
def api_task_status(task_id):
    with background_tasks_lock:
        task = background_tasks.get(task_id)
    if not task:
        return jsonify({"ok": False, "error": "任务不存在或已过期"}), 404
    return jsonify({"ok": True, **task})


@app.route("/api/resources/<int:resource_id>/sync", methods=["POST"])
def api_resource_sync(resource_id):
    """重新扫描 115 目录，更新已保存集数与 TMDB 总集数。"""
    pan = get_pan()
    if not pan:
        return jsonify({"ok": False, "error": "115 授权已失效，请重新登录"}), 401
    result = sync.sync_resource_item(resource_id, pan)
    if not result.get("ok"):
        return jsonify(result), 400
    conn = database.get_db()
    try:
        row = conn.execute("SELECT * FROM resources WHERE id = ?", (resource_id,)).fetchone()
        if not row:
            return jsonify({"ok": False, "error": "资源不存在"}), 404
        item = dict(row)
    finally:
        conn.close()
    return jsonify({"ok": True, "item": item, "stats": result})


@app.route("/api/resources/<int:resource_id>/tmdb", methods=["POST"])
def api_resource_tmdb(resource_id):
    """关联 TMDB 条目并刷新海报、总集数与已保存集数。"""
    pan = get_pan()
    if not pan:
        return jsonify({"ok": False, "error": "115 授权已失效，请重新登录"}), 401
    data = request.get_json() or {}
    tmdb_id = data.get("tmdb_id")
    if not tmdb_id:
        return jsonify({"ok": False, "error": "请选择 TMDB 条目"}), 400
    conn = database.get_db()
    try:
        row = conn.execute("SELECT * FROM resources WHERE id = ?", (resource_id,)).fetchone()
        if not row:
            return jsonify({"ok": False, "error": "资源不存在"}), 404
        media_type = (data.get("media_type") or row["media_type"] or "tv").strip()
        title = (data.get("title") or "").strip() or row["title"]
        conn.execute(
            """UPDATE resources
               SET tmdb_id = ?, media_type = ?, title = ?,
                   poster_url = ?, overview = ?, total_episodes = ?,
                   updated_at = CURRENT_TIMESTAMP
               WHERE id = ?""",
            (tmdb_id, media_type, title,
             (data.get("poster_url") or "").strip(),
             (data.get("overview") or "").strip(),
             int(data.get("total_episodes") or 0),
             resource_id),
        )
        conn.commit()
    finally:
        conn.close()
    result = sync.sync_resource_item(resource_id, pan)
    if not result.get("ok"):
        return jsonify(result), 400
    conn = database.get_db()
    try:
        row = conn.execute("SELECT * FROM resources WHERE id = ?", (resource_id,)).fetchone()
        item = dict(row) if row else None
    finally:
        conn.close()
    return jsonify({"ok": True, "item": item, "stats": result})


@app.route("/")
def index():
    new_index = FRONTEND_DIST / "index.html"
    if new_index.exists():
        return send_from_directory(str(FRONTEND_DIST), "index.html")
    return send_from_directory(str(SCRIPT_DIR), "index-server.html")


@app.route("/<path:path>")
def static_files(path):
    frontend_file = FRONTEND_DIST / path
    if frontend_file.exists():
        return send_from_directory(str(FRONTEND_DIST), path)
    return send_from_directory(str(SCRIPT_DIR), path)


# ============================================================
#  TMDB API
# ============================================================

@app.route("/api/tmdb/image")
def api_tmdb_image():
    """代理 TMDB 海报图，避免浏览器跨域 fetch 被 CORS 拦截。"""
    url = request.args.get("url", "")
    try:
        parsed = urlparse(url)
    except Exception:
        parsed = None
    if not parsed or parsed.scheme not in ("http", "https") or parsed.hostname != "image.tmdb.org":
        return jsonify({"ok": False, "error": "不支持的图片地址"}), 400
    try:
        r = req_lib.get(url, timeout=15, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
        })
        if r.status_code != 200:
            return jsonify({"ok": False, "error": f"图片获取失败（HTTP {r.status_code}）"}), 502
        return Response(
            r.content,
            mimetype=r.headers.get("Content-Type", "image/jpeg"),
            headers={"Cache-Control": "public, max-age=86400"},
        )
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 502


@app.route("/api/tmdb/config", methods=["GET", "POST"])
def api_tmdb_config():
    if request.method == "GET":
        return jsonify(tmdb_api.get_config())
    data = request.get_json() or {}
    api_key = (data.get("api_key") or "").strip()
    if not api_key:
        return jsonify({"ok": False, "error": "API Key 不能为空"})
    tmdb_api.set_api_key(api_key)
    return jsonify({"ok": True})


@app.route("/api/tmdb/search")
def api_tmdb_search():
    query = request.args.get("query", "")
    media_type = request.args.get("type", "tv")
    page = request.args.get("page", 1, type=int)
    if not query:
        return jsonify({"ok": False, "error": "请输入搜索关键词"})
    result = tmdb_api.search(query, media_type, page)
    return jsonify(result)


@app.route("/api/tmdb/<int:tmdb_id>")
def api_tmdb_detail(tmdb_id):
    media_type = request.args.get("type", "tv")
    result = tmdb_api.get_details(tmdb_id, media_type)
    return jsonify(result)


@app.route("/api/tmdb/<int:tmdb_id>/season/<int:season_number>")
def api_tmdb_season(tmdb_id, season_number):
    result = tmdb_api.get_season(tmdb_id, season_number)
    return jsonify(result)


# ============================================================
#  云下载 API
# ============================================================

@app.route("/api/download/cloud", methods=["POST"])
def api_cloud_download():
    data = request.get_json() or {}
    magnet_url = (data.get("magnet_url") or data.get("url") or "").strip()
    target_path = (data.get("target_path") or "").strip()

    if not magnet_url:
        return jsonify({"ok": False, "error": "请输入磁力链接或下载地址"})

    cookie = get_user_cookie()
    if not cookie:
        return jsonify({"ok": False, "error": "未配置 115 Cookie"})

    pan = Pan115(cookie)
    target_cid = "0"
    if target_path:
        target_cid = pan.find_cid_by_path(target_path) or "0"

    result = pan.add_cloud_download(magnet_url, target_cid)
    return jsonify({
        "ok": bool(result.get("state")),
        "task_id": result.get("task_id", ""),
        "error": result.get("error", ""),
    })


@app.route("/api/download/tasks", methods=["GET"])
def api_download_tasks():
    cookie = get_user_cookie()
    if not cookie:
        return jsonify({"ok": False, "error": "未配置 115 Cookie"})

    pan = Pan115(cookie)
    page = request.args.get("page", 1, type=int)
    result = pan.get_offline_tasks(page=page)
    return jsonify(result)


# ============================================================
#  启动
# ============================================================
if __name__ == "__main__":
    print("=" * 50)
    print("  115 管家 Web 服务")
    print("=" * 50)
    print(f"  打开 http://localhost:8767")
    print(f"  115 授权: {'✅ 已配置（缓存有效期内复用）' if config.get('cookie') else '⚠️ 未授权（请通过网页设置页扫码）'}")
    print("=" * 50)
    app.run(host="0.0.0.0", port=8767, debug=False)
