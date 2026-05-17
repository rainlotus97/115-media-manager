"""
媒体库 CRUD：追剧列表增删改查、同步日志。
"""

from datetime import datetime
from server.db import get_db


def add_watchlist(user_id: int, data: dict) -> dict:
    """添加一条追剧记录。"""
    title = (data.get("title") or "").strip()
    if not title:
        return {"ok": False, "error": "标题不能为空"}

    media_type = data.get("media_type", "anime")
    if media_type not in ("anime", "movie", "tv"):
        return {"ok": False, "error": "无效的媒体类型"}

    conn = get_db()
    try:
        cur = conn.execute(
            """INSERT INTO watchlist
               (user_id, tmdb_id, title, original_title, media_type, region, genre,
                poster_path, backdrop_path, overview,
                total_episodes, cached_episodes, status, path_115)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                user_id,
                data.get("tmdb_id"),
                title,
                data.get("original_title", ""),
                media_type,
                data.get("region", ""),
                ",".join(data.get("genres", [])) if isinstance(data.get("genres"), list) else data.get("genre", ""),
                data.get("poster_url") or data.get("poster_path", ""),
                data.get("backdrop_url") or data.get("backdrop_path", ""),
                data.get("overview", ""),
                data.get("total_episodes", 0),
                0,
                data.get("status", "tracking"),
                data.get("path_115", ""),
            ),
        )
        watchlist_id = cur.lastrowid
        conn.commit()
        return {
            "ok": True,
            "id": watchlist_id,
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}
    finally:
        conn.close()


def get_watchlist(user_id: int, media_type: str = None,
                  region: str = None, status: str = None) -> dict:
    """查询用户的追剧列表。"""
    conn = get_db()
    try:
        sql = "SELECT * FROM watchlist WHERE user_id = ?"
        params = [user_id]

        if media_type:
            sql += " AND media_type = ?"
            params.append(media_type)
        if region:
            sql += " AND region = ?"
            params.append(region)
        if status:
            sql += " AND status = ?"
            params.append(status)

        sql += " ORDER BY updated_at DESC"

        rows = conn.execute(sql, params).fetchall()
        items = []
        for r in rows:
            items.append(_row_to_dict(r))
        return {"ok": True, "items": items}
    finally:
        conn.close()


def get_watchlist_detail(watchlist_id: int, user_id: int = None) -> dict:
    """获取单条追剧详情。"""
    conn = get_db()
    try:
        if user_id:
            row = conn.execute(
                "SELECT * FROM watchlist WHERE id = ? AND user_id = ?",
                (watchlist_id, user_id),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT * FROM watchlist WHERE id = ?", (watchlist_id,)
            ).fetchone()

        if not row:
            return {"ok": False, "error": "记录不存在"}

        result = _row_to_dict(row)

        # 附带文件缓存
        files = conn.execute(
            "SELECT * FROM media_file_cache WHERE watchlist_id = ? ORDER BY episode_number",
            (watchlist_id,),
        ).fetchall()
        result["cached_files"] = [_file_row(r) for r in files]

        return {"ok": True, "item": result}
    finally:
        conn.close()


def update_watchlist(watchlist_id: int, user_id: int, data: dict) -> dict:
    """更新追剧记录。"""
    conn = get_db()
    try:
        fields = []
        params = []

        allowed = [
            "title", "original_title", "region", "genre", "poster_path",
            "backdrop_path", "overview", "total_episodes", "cached_episodes",
            "status", "path_115", "folder_id_115", "tmdb_id",
            "last_synced_at", "next_sync_at",
        ]
        for key in allowed:
            if key in data:
                fields.append(f"{key} = ?")
                val = data[key]
                if key == "genre" and isinstance(val, list):
                    val = ",".join(val)
                params.append(val)

        if not fields:
            return {"ok": False, "error": "没有要更新的字段"}

        fields.append("updated_at = ?")
        params.append(datetime.utcnow().isoformat())

        params.extend([watchlist_id, user_id])
        conn.execute(
            f"UPDATE watchlist SET {', '.join(fields)} WHERE id = ? AND user_id = ?",
            params,
        )
        conn.commit()
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}
    finally:
        conn.close()


def delete_watchlist(watchlist_id: int, user_id: int) -> dict:
    """删除追剧记录及其关联缓存。"""
    conn = get_db()
    try:
        conn.execute(
            "DELETE FROM media_file_cache WHERE watchlist_id = ?", (watchlist_id,)
        )
        conn.execute(
            "DELETE FROM sync_log WHERE watchlist_id = ?", (watchlist_id,)
        )
        conn.execute(
            "DELETE FROM dir_index_files WHERE watchlist_id = ?", (watchlist_id,)
        )
        cursor = conn.execute(
            "DELETE FROM watchlist WHERE id = ? AND user_id = ?",
            (watchlist_id, user_id),
        )
        conn.commit()
        if cursor.rowcount == 0:
            return {"ok": False, "error": "记录不存在或无权删除"}
        return {"ok": True}
    finally:
        conn.close()


def record_sync(watchlist_id: int, user_id: int,
                action: str, files_added: int = 0,
                files_removed: int = 0, details: str = "") -> dict:
    """记录同步日志。"""
    conn = get_db()
    try:
        conn.execute(
            """INSERT INTO sync_log
               (user_id, watchlist_id, action, files_added, files_removed, details)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (user_id, watchlist_id, action, files_added, files_removed, details),
        )
        # 更新最后同步时间
        now = datetime.utcnow().isoformat()
        conn.execute(
            "UPDATE watchlist SET last_synced_at = ?, updated_at = ? WHERE id = ?",
            (now, now, watchlist_id),
        )
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


# ---- helpers ----

def _row_to_dict(r) -> dict:
    return {
        "id": r["id"],
        "user_id": r["user_id"],
        "tmdb_id": r["tmdb_id"],
        "title": r["title"],
        "original_title": r["original_title"],
        "media_type": r["media_type"],
        "region": r["region"],
        "genre": r["genre"],
        "poster_path": r["poster_path"],
        "backdrop_path": r["backdrop_path"],
        "overview": r["overview"],
        "total_episodes": r["total_episodes"],
        "cached_episodes": r["cached_episodes"],
        "latest_episode": r["latest_episode"] if "latest_episode" in r.keys() else 0,
        "status": r["status"],
        "path_115": r["path_115"],
        "folder_id_115": r["folder_id_115"],
        "last_synced_at": r["last_synced_at"],
        "next_sync_at": r["next_sync_at"],
        "auto_sync_days": r["auto_sync_days"],
        "created_at": r["created_at"],
        "updated_at": r["updated_at"],
    }


def _file_row(r) -> dict:
    return {
        "id": r["id"],
        "fid": r["fid"],
        "filename": r["filename"],
        "file_size": r["file_size"],
        "episode_number": r["episode_number"],
        "season_number": r["season_number"] if "season_number" in r.keys() else 1,
    }
