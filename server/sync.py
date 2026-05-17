"""
同步模块：扫描115网盘目录（支持多季子目录），解析文件名提取集数，
结合 TMDB 播出日期计算"已播出"集数，缓存到数据库。
"""

import re
from typing import Optional
from datetime import datetime, timedelta
from server.db import get_db
from server.tmdb_api import get_details as tmdb_get_details, get_season as tmdb_get_season


def parse_episode(filename: str) -> Optional[dict]:
    """从文件名提取 (season, episode)。
    优先 S01E01 格式（含季号），否则回退到单集数字。
    """
    name = filename.strip()

    # S01E01 / S1E01 / s01e01 (最优先，含季号)
    m = re.search(r'[sS](\d{1,2})\s*[eE](\d{1,4})', name)
    if m:
        return {"season": int(m.group(1)), "episode": int(m.group(2))}

    # EP01 / ep01 / Ep.01
    m = re.search(r'(?:^|[^a-zA-Z])[eE][pP]\.?\s*(\d{1,4})', name)
    if m:
        return {"season": 1, "episode": int(m.group(1))}

    # [01] [12.5]
    m = re.search(r'\[(\d{1,4}(?:\.5)?)\]', name)
    if m:
        return {"season": 1, "episode": int(float(m.group(1)))}

    # 第01集 / 第1话 / 第01話
    m = re.search(r'第\s*(\d{1,4})\s*(?:集|话|話)', name)
    if m:
        return {"season": 1, "episode": int(m.group(1))}

    # 纯数字 (01.mp4 / 标题 01.mkv)
    stem = re.sub(r'\.[^.]+$', '', name)
    m = re.search(r'(?:^|\s)(\d{1,4}(?:\.5)?)(?:\s|$)', stem)
    if m:
        ep = int(float(m.group(1)))
        if 1 <= ep <= 9999:
            return {"season": 1, "episode": ep}

    return None


def parse_season_from_dirname(dirname: str) -> Optional[int]:
    """从目录名提取季号。"""
    name = dirname.strip()
    # Season 01 / Season 1 / season 01
    m = re.search(r'[Ss]eason\s*\.?\s*(\d{1,2})', name)
    if m: return int(m.group(1))
    # S01 / S1 (独立的S+数字，如 "S01" 或 "S1 航海王")
    m = re.search(r'(?:^|\s)[Ss](\d{1,2})(?:\s|$)', name)
    if m: return int(m.group(1))
    # 第1季 / 第01季
    m = re.search(r'第\s*(\d{1,2})\s*季', name)
    if m: return int(m.group(1))
    # Season.01 / Season01
    m = re.search(r'[Ss]eason\.?(\d{1,2})', name)
    if m: return int(m.group(1))
    return None


def _is_video_dir(pan, cid: str) -> bool:
    """判断一个目录是否包含视频文件（避免把纯文档目录当季）。"""
    files = pan.list_dir(cid, limit=10)
    for f in files:
        if not f["is_dir"]:
            ext = f["name"].lower()
            for ve in (".mp4", ".mkv", ".avi", ".mov", ".ts", ".m2ts", ".flv", ".rmvb", ".wmv"):
                if ve in ext:
                    return True
    return False


def _scan_dir(pan, cid: str, season_context: int,
              conn, watchlist_id: int, depth: int = 0) -> list:
    """递归扫描目录。"""
    results = []
    items = pan.list_dir(cid)
    dirs = [i for i in items if i["is_dir"]]
    files = [i for i in items if not i["is_dir"]]
    print(f"  [scan] depth={depth} cid={cid}: {len(dirs)} dirs + {len(files)} files")
    for d in dirs:
        print(f"    DIR: '{d['name']}'")
    for f in files[:5]:
        print(f"    FILE: '{f['name']}'")
    if len(files) > 5:
        print(f"    ... and {len(files)-5} more files")

    for item in items:
        if item["is_dir"]:
            season = parse_season_from_dirname(item["name"])
            if season is None:
                m = re.match(r'^(\d{1,2})$', item["name"].strip())
                if m:
                    season = int(m.group(1))
            sub_season = season if (season and season >= 1) else season_context
            print(f"  [scan]   DIR: {item['name']} → season={sub_season}, cid={item['fid']}")
            sub = _scan_dir(pan, item["fid"], sub_season, conn, watchlist_id, depth + 1)
            results.extend(sub)
        else:
            parsed = parse_episode(item["name"])
            season = parsed["season"] if parsed else season_context
            episode = parsed["episode"] if parsed else 0

            if episode == 0:
                print(f"  [scan]   FILE(noparse) d={depth}: '{item['name']}'")
            else:
                print(f"  [scan]   FILE d={depth}: '{item['name']}' → S{season}E{episode}")

            conn.execute(
                """INSERT INTO media_file_cache
                   (watchlist_id, fid, filename, file_size, episode_number, season_number)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (watchlist_id, item["fid"], item["name"], item["size"], episode, season),
            )
            results.append({
                "fid": item["fid"],
                "name": item["name"],
                "size": item["size"],
                "season": season,
                "episode": episode,
            })
    return results


def _fetch_tmdb_episodes(tmdb_id: int, conn) -> dict:
    """从 TMDB 获取所有季剧集信息并写入 tmdb_episode_cache。
    返回 {season_num: [{episode_num, name, still_path, air_date}]}
    """
    detail = tmdb_get_details(tmdb_id, "tv")
    if not detail.get("ok"):
        return {}

    all_episodes = {}
    for s in detail.get("seasons", []):
        sn = s["season_number"]
        if sn == 0:
            continue
        season_data = tmdb_get_season(tmdb_id, sn)
        if season_data.get("ok"):
            eps = []
            for ep in season_data.get("episodes", []):
                ep_info = {
                    "episode_number": ep["episode_number"],
                    "name": ep.get("name", ""),
                    "still_url": ep.get("still_url"),
                    "air_date": ep.get("air_date", ""),
                    "overview": ep.get("overview", ""),
                }
                eps.append(ep_info)
                # 写入缓存表
                conn.execute(
                    """INSERT OR REPLACE INTO tmdb_episode_cache
                       (tmdb_id, season_number, episode_number, name, still_path, air_date, overview, cached_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
                    (tmdb_id, sn, ep["episode_number"],
                     ep.get("name", ""), ep.get("still_url"),
                     ep.get("air_date", ""), ep.get("overview", "")),
                )
            all_episodes[sn] = eps
    return all_episodes


def sync_watchlist_item(watchlist_id: int, user_id: int, pan) -> dict:
    """同步单个追剧项：扫描115目录（含子目录）、解析集数、结合TMDB播出日期。"""
    conn = get_db()
    try:
        wl = conn.execute(
            "SELECT * FROM watchlist WHERE id = ? AND user_id = ?",
            (watchlist_id, user_id),
        ).fetchone()
        if not wl:
            return {"ok": False, "error": "记录不存在"}

        path_115 = wl["path_115"]
        if not path_115:
            return {"ok": False, "error": "未设置 115 路径"}

        # 找到目录 cid
        cid = wl["folder_id_115"]
        print(f"[sync] watchlist_id={watchlist_id} path={path_115} cached_cid={cid}")
        if not cid:
            cid = pan.find_cid_by_path(path_115)
            print(f"[sync] find_cid_by_path('{path_115}') → {cid}")
            if not cid:
                return {"ok": False, "error": f"在115网盘中找不到目录: {path_115}"}

        # 清旧缓存
        conn.execute("DELETE FROM media_file_cache WHERE watchlist_id = ?", (watchlist_id,))

        # 扫描目录（递归子目录）
        print(f"[sync] scanning cid={cid}...")
        all_files = _scan_dir(pan, cid, 1, conn, watchlist_id)

        # 统计
        episodes_by_season: dict[int, set[int]] = {}
        for f in all_files:
            if f["episode"] > 0:
                s = f["season"]
                if s not in episodes_by_season:
                    episodes_by_season[s] = set()
                episodes_by_season[s].add(f["episode"])

        total_cached = sum(len(eps) for eps in episodes_by_season.values())
        files_cached = len(all_files)
        seasons_found = sorted(episodes_by_season.keys())

        # TMDB 播出日期
        latest_episode = 0
        total_aired = 0
        tmdb_total = wl["total_episodes"] or 0
        tmdb_episodes = {}
        if wl["tmdb_id"]:
            try:
                tmdb_episodes = _fetch_tmdb_episodes(wl["tmdb_id"], conn)
            except Exception:
                pass

        if tmdb_episodes:
            today = datetime.utcnow().date().isoformat()
            for sn, eps in tmdb_episodes.items():
                for ep in eps:
                    air = ep["air_date"]
                    if air and air <= today:
                        total_aired += 1
            if total_aired > 0:
                latest_episode = total_aired

        # 更新 watchlist
        now = datetime.utcnow().isoformat()
        effective_total = latest_episode or tmdb_total
        new_status = wl["status"]
        if effective_total > 0 and total_cached >= effective_total:
            new_status = "completed"
        elif wl["status"] == "completed" and total_cached < effective_total:
            new_status = "tracking"

        conn.execute(
            """UPDATE watchlist
               SET cached_episodes = ?, latest_episode = ?, folder_id_115 = ?,
                   last_synced_at = ?, next_sync_at = ?, updated_at = ?,
                   status = ?
               WHERE id = ?""",
            (
                total_cached,
                effective_total,
                cid,
                now,
                (datetime.utcnow() + timedelta(hours=24)).isoformat(),
                now,
                new_status,
                watchlist_id,
            ),
        )

        # 记录日志
        conn.execute(
            """INSERT INTO sync_log
               (user_id, watchlist_id, action, files_added, details)
               VALUES (?, ?, 'full_scan', ?, ?)""",
            (
                user_id, watchlist_id, files_cached,
                f"共 {len(seasons_found)} 季 (S{min(seasons_found)}-S{max(seasons_found)}), "
                f"{files_cached} 文件, {total_cached} 集已缓存, "
                f"TMDB 已播出 {latest_episode} 集",
            ),
        )
        conn.commit()

        debug_info = (
            f"扫描到 {len(all_files)} 项, {files_cached} 文件, "
            f"{total_cached} 集, {len(seasons_found)} 季(S{min(seasons_found)}-S{max(seasons_found)})"
            if seasons_found else
            f"扫描到 {len(all_files)} 项, {files_cached} 文件, 未识别到剧集"
        )
        print(f"[sync] DONE: {debug_info}")

        return {
            "ok": True,
            "files_found": len(all_files),
            "files_cached": files_cached,
            "episodes_cached": total_cached,
            "total_episodes": tmdb_total,
            "latest_episode": latest_episode or tmdb_total,
            "seasons": seasons_found,
            "season_count": len(seasons_found),
            "debug": debug_info,
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}
    finally:
        conn.close()
