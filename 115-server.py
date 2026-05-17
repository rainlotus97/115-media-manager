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
import time
from pathlib import Path
from urllib.parse import urlparse, parse_qs

try:
    from flask import Flask, request, jsonify, send_from_directory
except ImportError:
    print("❌ 需要安装 flask: pip3 install flask")
    sys.exit(1)

from server import auth, db as database, tmdb_api, media, sync

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
API_DIR_ADD = "https://webapi.115.com/files/add"
API_SAVE_TO_PAN = "https://115cdn.com/webapi/share/receive"


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
            return False
        except:
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
                    break

                d = data.get("data", {})
                if offset == 0:
                    shareinfo = d.get("shareinfo", {})
                    total_count = d.get("count", 0)
                    expire_time = shareinfo.get("expire_time", 0)
                    is_expired = expire_time > 0 and expire_time < time.time()

                page_files = d.get("list", [])
                if not page_files:
                    break

                for f in page_files:
                    all_files.append({
                        "name": f.get("n", "?"),
                        "is_dir": f.get("fc", 1) == 0,
                        "size": f.get("s", 0),
                    })
                    fc = f.get("fc", 0)
                    fid = str(f.get("fid", "") or f.get("cid", "")) if fc == 1 else str(f.get("cid", ""))
                    all_id_map[fid] = f.get("n", "?")

                offset += page_size
                if offset >= total_count:
                    break
                time.sleep(0.3)

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
                    "user_name": d.get("userinfo", {}).get("user_name", ""),
                }
            return {"state": False, "error": data.get("error", "未知错误")}
        except Exception as e:
            return {"state": False, "error": str(e)}

    def browse_share(self, share_code, receive_code, cid):
        """获取分享链接中某个子目录的全部内容（分页取完）"""
        try:
            referer = f"https://115cdn.com/s/{share_code}?password={receive_code}&"
            all_files = []
            all_id_map = {}
            total_count = 0
            page_size = 200
            offset = 0

            # 获取根目录的元信息（标题、过期状态等）
            root_info = self.get_share_info(share_code, receive_code)
            share_title = (root_info or {}).get("title", "")
            share_size = (root_info or {}).get("size", 0)
            is_expired = (root_info or {}).get("is_expired", False)
            expire_time = (root_info or {}).get("expire_time", "")
            user_name = (root_info or {}).get("user_name", "")

            while True:
                r = self.session.get(
                    API_SHARE_SNAP,
                    params={
                        "share_code": share_code,
                        "receive_code": receive_code,
                        "cid": cid,
                        "limit": str(page_size),
                        "offset": str(offset),
                        "format": "json",
                    },
                    headers={"Referer": referer},
                    timeout=10,
                )
                data = r.json()
                if not (isinstance(data, dict) and data.get("state")):
                    break

                d = data.get("data", {})
                if offset == 0:
                    total_count = d.get("count", 0)

                page_files = d.get("list", [])
                if not page_files:
                    break

                for f in page_files:
                    all_files.append({
                        "name": f.get("n", "?"),
                        "is_dir": f.get("fc", 1) == 0,
                        "size": f.get("s", 0),
                    })
                    fc = f.get("fc", 0)
                    fid = str(f.get("fid", "") or f.get("cid", "")) if fc == 1 else str(f.get("cid", ""))
                    all_id_map[fid] = f.get("n", "?")

                offset += page_size
                if offset >= total_count:
                    break
                time.sleep(0.3)

            return {
                    "state": True,
                    "title": share_title,
                    "file_count": total_count,
                    "size": share_size,
                    "files": all_files,
                    "file_id_map": all_id_map,
                    "browse_cid": cid,
                    "is_expired": is_expired,
                    "expire_time": expire_time,
                    "user_name": user_name,
                }
            return {"state": False, "error": data.get("error", "未知错误")}
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
                data = r.json()
                if not isinstance(data, dict) or not data.get("state"):
                    break
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
                break
        return all_files

    def add_cloud_download(self, url, target_cid="0"):
        """添加离线下载任务（115闪推兼容方式）。
        1. 获取 sign + time
        2. 提交离线任务
        """
        try:
            # 1. 获取用户 uid（优先从 Cookie 提取，省一次 API 调用）
            uid = ""
            cookie = self.session.headers.get("Cookie", "")
            m = re.search(r'UID=([^;]+)', cookie)
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

    def save_to_pan(self, share_code, receive_code, cid):
        try:
            data = {
                "share_code": share_code,
                "receive_code": receive_code,
                "file_id": "0",
                "cid": cid,
            }
            r = self.session.post(API_SAVE_TO_PAN, data=data, timeout=30)
            return r.json()
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


# ============================================================
#  Flask Web 服务
# ============================================================
app = Flask(__name__, static_folder=None)

# 加载配置
config = {}
if CONFIG_FILE.exists():
    with open(CONFIG_FILE) as f:
        config = json.load(f)

def save_config():
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

def get_pan():
    cookie = config.get("cookie", "")
    if not cookie:
        return None
    return Pan115(cookie)


def get_user_cookie(user_id: int) -> str:
    """获取用户 cookie：优先查 user_115_config 表，回退到全局 config。"""
    conn = database.get_db()
    try:
        row = conn.execute(
            "SELECT cookie FROM user_115_config WHERE user_id = ?", (user_id,)
        ).fetchone()
        if row and row["cookie"]:
            return row["cookie"]
    finally:
        conn.close()
    return config.get("cookie", "")

def parse_share_url(url):
    """从 URL 中提取分享码和密码"""
    m = re.search(r'/s/([a-zA-Z0-9]+)', url)
    share_code = m.group(1) if m else None
    # 从 query 中提取 password
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    password = qs.get("password", [""])[0]
    return share_code, password


# ============================================================
#  API 路由
# ============================================================

@app.route("/api/check-cookie", methods=["GET", "POST"])
def api_check_cookie():
    pan = get_pan()
    if not pan:
        return jsonify({"ok": False, "error": "未设置 Cookie"})
    valid = pan.check_cookie()
    return jsonify({"ok": valid})


@app.route("/api/cookie", methods=["GET", "POST"])
def api_cookie():
    """获取或更新 Cookie"""
    if request.method == "GET":
        has = bool(config.get("cookie"))
        return jsonify({"ok": True, "has_cookie": has})
    
    data = request.get_json() or {}
    cookie = (data.get("cookie") or "").strip()
    if not cookie:
        return jsonify({"ok": False, "error": "Cookie 不能为空"})
    
    # 验证
    pan = Pan115(cookie)
    if not pan.check_cookie():
        return jsonify({"ok": False, "error": "Cookie 无效，请重新获取"})
    
    config.clear()
    config["cookie"] = cookie
    save_config()
    return jsonify({"ok": True})


@app.route("/api/info", methods=["POST"])
def api_info():
    pan = get_pan()
    if not pan:
        return jsonify({"ok": False, "error": "未配置 Cookie，请先 login"})

    data = request.get_json() or {}
    url = data.get("url", "")
    password = data.get("password", "")
    cid = data.get("cid", "0")

    share_code, pw_from_url = parse_share_url(url)
    if not share_code and not cid:
        return jsonify({"ok": False, "error": "无法解析分享链接"})
    if not password and pw_from_url:
        password = pw_from_url

    # 如果传了 cid 就是浏览子目录，否则从根目录获取
    if cid and cid != "0":
        info = pan.browse_share(share_code, password, cid)
    else:
        info = pan.get_share_info(share_code, password)
    if info.get("state"):
        resp = {
            "ok": True,
            "share_code": share_code,
            "file_count": info["file_count"],
            "files": info["files"],
            "file_id_map": info.get("file_id_map", {}),
            "browse_cid": info.get("browse_cid", "0"),
        }
        # browse 模式不一定有这些字段
        if "title" in info:
            resp["title"] = info["title"]
        if "size" in info:
            resp["size"] = info["size"]
            resp["size_str"] = _fmt_size(info["size"])
        if "is_expired" in info:
            resp["is_expired"] = info["is_expired"]
        if "user_name" in info:
            resp["user_name"] = info["user_name"]
        return jsonify(resp)
    else:
        err = info.get("error", "未知错误")
        expired_hint = "该链接可能已过期" if "小差" in err else ""
        return jsonify({"ok": False, "error": err, "hint": expired_hint})


@app.route("/api/save", methods=["POST"])
def api_save():
    pan = get_pan()
    if not pan:
        return jsonify({"ok": False, "error": "未配置 Cookie"})

    data = request.get_json() or {}
    url = data.get("url", "")
    password = data.get("password", "")
    target_path = data.get("target_path", "资源库/115转存")

    share_code, pw_from_url = parse_share_url(url)
    if not share_code:
        return jsonify({"ok": False, "error": "无法解析分享链接"})
    if not password and pw_from_url:
        password = pw_from_url

    # 1. 先获取分享信息（验证链接有效性）
    info = pan.get_share_info(share_code, password)
    if not info.get("state"):
        return jsonify({"ok": False, "error": f"链接无效: {info.get('error', '')}"})
    if info.get("is_expired"):
        return jsonify({"ok": False, "error": "该链接已过期，无法转存"})

    # 2. 确保目录存在（直接用前端传的完整路径）
    cid = pan.ensure_path(target_path)
    if not cid:
        return jsonify({"ok": False, "error": "无法创建目标目录"})

    # 3. 转存（支持自选文件）
    file_ids = (data.get("file_ids") or "").strip()
    if file_ids:
        result = pan.save_files_to_pan(share_code, password, cid, file_ids)
    else:
        result = pan.save_to_pan(share_code, password, cid)
    if isinstance(result, dict) and result.get("state"):
        return jsonify({
            "ok": True,
            "target_path": target_path,
        })
    else:
        msg = result.get("error", result.get("message", "失败"))
        return jsonify({"ok": False, "error": msg})



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
#  认证 API
# ============================================================

@app.route("/api/auth/register", methods=["POST"])
def api_register():
    data = request.get_json() or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    result = auth.register(username, password)
    return jsonify(result)


@app.route("/api/auth/login", methods=["POST"])
def api_login():
    data = request.get_json() or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    result = auth.login(username, password)
    return jsonify(result)


@app.route("/api/auth/session", methods=["GET"])
def api_session():
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return jsonify({"ok": False, "error": "未登录"}), 401
    token = auth_header[7:]
    user = auth.get_session(token)
    if not user:
        return jsonify({"ok": False, "error": "登录已过期"}), 401
    return jsonify({"ok": True, "user": user})


@app.route("/api/auth/logout", methods=["POST"])
def api_logout():
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        auth.logout(auth_header[7:])
    return jsonify({"ok": True})


# ============================================================
#  TMDB API
# ============================================================

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
#  媒体库 API（需要登录）
# ============================================================

from server.decorators import login_required


@app.route("/api/media/list")
@login_required
def api_media_list(user):
    media_type = request.args.get("type")
    region = request.args.get("region")
    status = request.args.get("status")
    result = media.get_watchlist(user["id"], media_type, region, status)
    return jsonify(result)


@app.route("/api/media/add", methods=["POST"])
@login_required
def api_media_add(user):
    data = request.get_json() or {}
    result = media.add_watchlist(user["id"], data)
    return jsonify(result)


@app.route("/api/media/<int:media_id>", methods=["GET", "PUT", "DELETE"])
@login_required
def api_media_item(user, media_id):
    if request.method == "GET":
        result = media.get_watchlist_detail(media_id, user["id"])
        return jsonify(result)
    elif request.method == "PUT":
        data = request.get_json() or {}
        result = media.update_watchlist(media_id, user["id"], data)
        return jsonify(result)
    elif request.method == "DELETE":
        result = media.delete_watchlist(media_id, user["id"])
        return jsonify(result)


@app.route("/api/media/<int:media_id>/episodes")
@login_required
def api_media_episodes(user, media_id):
    """从缓存表读取剧集数据，合并文件缓存。不调 TMDB。"""
    season = request.args.get("season", type=int)
    conn = database.get_db()
    try:
        # 获取 watchlist 的 tmdb_id
        wl = conn.execute(
            "SELECT tmdb_id FROM watchlist WHERE id = ? AND user_id = ?",
            (media_id, user["id"]),
        ).fetchone()
        if not wl:
            return jsonify({"ok": False, "error": "记录不存在"})

        tmdb_id = wl["tmdb_id"]

        # 从缓存读 TMDB 剧集
        sql = "SELECT * FROM tmdb_episode_cache WHERE tmdb_id = ?"
        params = [tmdb_id]
        if season:
            sql += " AND season_number = ?"
            params.append(season)
        sql += " ORDER BY season_number, episode_number"
        trows = conn.execute(sql, params).fetchall()

        # 从缓存读文件
        fsql = "SELECT * FROM media_file_cache WHERE watchlist_id = ?"
        fparams = [media_id]
        if season:
            fsql += " AND season_number = ?"
            fparams.append(season)
        frows = conn.execute(fsql, fparams).fetchall()

        # 构建文件查找表
        file_map = {}
        for f in frows:
            sn = f["season_number"] if "season_number" in f.keys() else 1
            key = f"S{sn}E{f['episode_number']}"
            file_map[key] = {
                "id": f["id"], "fid": f["fid"], "filename": f["filename"],
                "file_size": f["file_size"], "episode_number": f["episode_number"],
                "season_number": sn,
            }

        TMDB_IMAGE = "https://image.tmdb.org/t/p"
        # 获取各季的海报（从 TMDB details）
        season_posters = {}
        if tmdb_id:
            try:
                detail = tmdb_api.get_details(tmdb_id, "tv")
                if detail.get("ok"):
                    for s in detail.get("seasons", []):
                        sn = s["season_number"]
                        if s.get("poster_path"):
                            season_posters[sn] = f"{TMDB_IMAGE}/w500{s['poster_path']}"
            except Exception:
                pass

        episodes = []
        for r in trows:
            key = f"S{r['season_number']}E{r['episode_number']}"
            still = r["still_path"] or ""
            if still and not still.startswith("http"):
                still = f"{TMDB_IMAGE}/w780{still}"
            episodes.append({
                "season_number": r["season_number"],
                "episode_number": r["episode_number"],
                "name": r["name"],
                "still_path": still,
                "air_date": r["air_date"],
                "overview": r["overview"],
                "cached_file": file_map.get(key),
            })

        return jsonify({
            "ok": True,
            "episodes": episodes,
            "season_posters": season_posters,
        })
    finally:
        conn.close()


@app.route("/api/media/<int:media_id>/sync", methods=["POST"])
@login_required
def api_media_sync(user, media_id):
    cookie = get_user_cookie(user["id"])
    if not cookie:
        return jsonify({"ok": False, "error": "未配置 115 Cookie，请先在设置页配置"})

    pan = Pan115(cookie)
    result = sync.sync_watchlist_item(media_id, user["id"], pan)
    return jsonify(result)


# ============================================================
#  云下载 API
# ============================================================

@app.route("/api/download/cloud", methods=["POST"])
@login_required
def api_cloud_download(user):
    data = request.get_json() or {}
    magnet_url = (data.get("magnet_url") or data.get("url") or "").strip()
    target_path = (data.get("target_path") or "").strip()

    if not magnet_url:
        return jsonify({"ok": False, "error": "请输入磁力链接或下载地址"})

    cookie = get_user_cookie(user["id"])
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
@login_required
def api_download_tasks(user):
    cookie = get_user_cookie(user["id"])
    if not cookie:
        return jsonify({"ok": False, "error": "未配置 115 Cookie"})

    pan = Pan115(cookie)
    page = request.args.get("page", 1, type=int)
    result = pan.get_offline_tasks(page=page)
    return jsonify(result)


# ============================================================
#  辅助函数
# ============================================================
def _fmt_size(size_bytes):
    if not size_bytes:
        return "?"
    gb = size_bytes / (1024**3)
    if gb >= 1:
        return f"{gb:.2f} GB"
    mb = size_bytes / (1024**2)
    return f"{mb:.1f} MB"


# ============================================================
#  启动
# ============================================================
if __name__ == "__main__":
    print("=" * 50)
    print("  115 管家 Web 服务")
    print("=" * 50)
    print(f"  打开 http://localhost:8767")
    print(f"  Cookie 状态: {'✅ 已配置' if config.get('cookie') else '⚠️ 未配置（请通过网页设置页配置）'}")
    print("=" * 50)
    app.run(host="0.0.0.0", port=8767, debug=False)
