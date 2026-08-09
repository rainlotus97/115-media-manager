"""
同步模块：扫描 115 网盘目录（含多季子目录），解析文件名提取集数，
结合 TMDB 元数据对比“已保存集数 / 总集数”，写入资源库。
"""

import json
import re
import time
from datetime import datetime
from typing import Optional

from server.db import get_db
from server.tmdb_api import get_details as tmdb_get_details, get_season as tmdb_get_season


def parse_episode(filename: str) -> Optional[dict]:
    """从文件名提取 (season, episode)。优先 S01E01，再回退单集数字。"""
    name = filename.strip()

    # S01E01 / S1E01 / s01e01（最优先，含季号）
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

    # 纯数字（01.mp4 / 标题 01.mkv）
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
    if m:
        return int(m.group(1))
    # S01 / S1（独立 S+数字）
    m = re.search(r'(?:^|\s)[Ss](\d{1,2})(?:\s|$)', name)
    if m:
        return int(m.group(1))
    # 第1季 / 第01季
    m = re.search(r'第\s*(\d{1,2})\s*季', name)
    if m:
        return int(m.group(1))
    # Season.01 / Season01
    m = re.search(r'[Ss]eason\.?(\d{1,2})', name)
    if m:
        return int(m.group(1))
    return None


def _match_key(value):
    """稳定的保守分组键，用于导入时按资源关联。"""
    value = re.sub(r'\.[^.]+$', '', (value or '').lower())
    value = re.sub(r'(s\d{1,2}\s*e\d{1,4}|ep?\s*\d{1,4}|第\s*\d{1,4}\s*[集话話])', ' ', value)
    value = re.sub(r'[\[\](){}._\-]+', ' ', value)
    return re.sub(r'\s+', ' ', value).strip()[:160]


def _fetch_tmdb_episodes(tmdb_id: int, conn) -> dict:
    """从 TMDB 拉取各季剧集并写入 tmdb_episode_cache。"""
    detail = tmdb_get_details(tmdb_id, "tv")
    if not detail.get("ok"):
        return {}
    all_episodes = {}
    for season in detail.get("seasons", []):
        sn = int(season["season_number"])
        season_result = tmdb_get_season(tmdb_id, sn)
        eps = []
        if season_result.get("ok"):
            for ep in season_result.get("episodes", []):
                ep_num = int(ep["episode_number"])
                eps.append(ep_num)
                conn.execute(
                    """INSERT OR REPLACE INTO tmdb_episode_cache
                       (tmdb_id, season_number, episode_number, name, still_path, air_date, overview, cached_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
                    (tmdb_id, sn, ep_num, ep.get("name", ""), ep.get("still_url", ""),
                     ep.get("air_date", ""), ep.get("overview", "")),
                )
        all_episodes[sn] = eps
    return all_episodes


def scan_resource_folder(pan, cid: str, resource_id: int, conn, progress=None):
    """递归扫描 115 目录，索引文件并解析集数。返回 (文件列表, 各季集数集合, 是否截断)。"""
    files = []
    episodes: dict[int, set[int]] = {}
    pending = [(cid, 1)]
    max_files = 20000
    truncated = False

    while pending and len(files) < max_files:
        current_cid, season_context = pending.pop(0)
        try:
            items = pan.list_dir(current_cid)
        except Exception:
            truncated = True
            break
        for item in items:
            if len(files) >= max_files:
                truncated = True
                break
            if item["is_dir"]:
                season = parse_season_from_dirname(item["name"])
                if season is None and item["name"].strip().isdigit():
                    season = int(item["name"].strip())
                pending.append((item["fid"], season or season_context))
            else:
                display_name = item["name"]
                parsed = parse_episode(display_name)
                season = parsed["season"] if parsed else None
                episode = parsed["episode"] if parsed else 0
                size = int(item.get("size") or 0)
                files.append({
                    "fid": item["fid"], "name": item["name"], "size": size,
                    "display_name": display_name,
                    "season": season, "episode": episode,
                })
                conn.execute(
                    """INSERT OR REPLACE INTO resource_files
                       (resource_id, fid, filename, display_name, file_size, match_key, season_number, episode_number, cached_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
                    (resource_id, item["fid"], item["name"], display_name, size, _match_key(display_name),
                     season, episode if episode else None),
                )
                if episode > 0 and season is not None:
                    episodes.setdefault(season, set()).add(episode)
        if progress:
            progress(len(files))
        time.sleep(0.3)
    return files, episodes, truncated


def sync_resource_item(resource_id: int, pan, progress=None) -> dict:
    """同步单个资源：扫描 115 目录，更新文件索引与 TMDB 集数对比。"""
    conn = get_db()
    try:
        row = conn.execute("SELECT * FROM resources WHERE id = ?", (resource_id,)).fetchone()
        if not row:
            return {"ok": False, "error": "资源不存在"}
        cid = row["folder_id_115"] or ""
        if not cid:
            cid = pan.find_cid_by_path(row["path_115"])
        if not cid:
            return {"ok": False, "error": f"在 115 网盘中找不到目录: {row['path_115']}"}

        conn.execute("DELETE FROM resource_files WHERE resource_id = ?", (resource_id,))
        files, episodes, truncated = scan_resource_folder(
            pan, cid, resource_id, conn, progress=progress)

        cached = sum(len(v) for v in episodes.values())
        seasons = sorted(episodes.keys())
        tmdb_total = int(row["total_episodes"] or 0)
        poster = row["poster_url"] or ""
        overview = row["overview"] or ""
        tmdb_season_totals = {}
        latest_episode = 0

        if row["tmdb_id"]:
            try:
                detail = tmdb_get_details(row["tmdb_id"], row["media_type"] or "tv")
                if detail.get("ok"):
                    tmdb_total = int(detail.get("total_episodes") or tmdb_total)
                    poster = detail.get("poster_url") or poster
                    overview = detail.get("overview") or overview
                    for s in detail.get("seasons", []):
                        tmdb_season_totals[int(s["season_number"])] = int(s.get("episode_count") or 0)
                    _fetch_tmdb_episodes(row["tmdb_id"], conn)
                    today = datetime.utcnow().date().isoformat()
                    aired = conn.execute(
                        """SELECT MAX(episode_number) AS latest FROM tmdb_episode_cache
                           WHERE tmdb_id = ? AND air_date != '' AND air_date <= ?""",
                        (row["tmdb_id"], today),
                    ).fetchone()
                    latest_episode = int(aired["latest"] or 0) if aired else 0
            except Exception:
                pass

        if row["tmdb_id"]:
            try:
                valid_rows = conn.execute(
                    "SELECT DISTINCT season_number, episode_number FROM tmdb_episode_cache WHERE tmdb_id = ?",
                    (row["tmdb_id"],),
                ).fetchall()
                valid_episodes = {(int(r["season_number"]), int(r["episode_number"])) for r in valid_rows}
                if valid_episodes:
                    placeholders = ",".join(["(?, ?)"] * len(valid_episodes))
                    params = [resource_id]
                    for season, episode in valid_episodes:
                        params.extend([season, episode])
                    conn.execute(
                        f"""UPDATE resource_files
                            SET tmdb_valid = 0, episode_number = NULL
                            WHERE resource_id = ? AND season_number IS NOT NULL AND episode_number IS NOT NULL
                              AND (season_number, episode_number) NOT IN ({placeholders})""",
                        params,
                    )
                episodes = {}
                for r in conn.execute(
                    """SELECT season_number, episode_number FROM resource_files
                       WHERE resource_id = ? AND tmdb_valid = 1""",
                    (resource_id,),
                ).fetchall():
                    if r["season_number"] is not None and r["episode_number"] is not None:
                        episodes.setdefault(int(r["season_number"]), set()).add(int(r["episode_number"]))
                cached = sum(len(v) for v in episodes.values())
                seasons = sorted(episodes.keys())
            except Exception:
                pass

        seasons_json = json.dumps([
            {"season": s, "cached": len(sorted(episodes[s])), "total": tmdb_season_totals.get(s, 0)}
            for s in seasons
        ], ensure_ascii=False)

        now = datetime.utcnow().isoformat()
        conn.execute(
            """UPDATE resources
               SET folder_id_115 = ?, total_episodes = ?, cached_episodes = ?,
                   latest_episode = ?, seasons_json = ?, poster_url = ?, overview = ?,
                   file_count = ?, total_size = ?, last_synced_at = ?, updated_at = ?
               WHERE id = ?""",
            (cid, tmdb_total, cached, latest_episode, seasons_json, poster, overview,
             len(files), sum(f["size"] for f in files), now, now, resource_id),
        )
        conn.commit()
        return {
            "ok": True,
            "files": len(files),
            "episodes_cached": cached,
            "total_episodes": tmdb_total,
            "latest_episode": latest_episode,
            "seasons": seasons,
            "seasons_json": seasons_json,
            "truncated": truncated,
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    finally:
        conn.close()
