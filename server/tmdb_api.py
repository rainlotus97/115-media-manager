"""
TMDB API 封装。
API Key 从 tmdb_config 表读取，未配置时返回错误。
"""

from typing import Optional
import requests
from server.db import get_db

TMDB_BASE = "https://api.themoviedb.org/3"
IMAGE_BASE = "https://image.tmdb.org/t/p"

# media_type 到 TMDB 类型的映射
TYPE_MAP = {
    "anime": "tv",
    "movie": "movie",
    "tv": "tv",
}


def _get_api_key() -> Optional[str]:
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT api_key, enabled FROM tmdb_config WHERE id = 1"
        ).fetchone()
        if row and row["enabled"] and row["api_key"]:
            return row["api_key"]
        return None
    finally:
        conn.close()


def _tmdb_get(path: str, params: dict = None) -> Optional[dict]:
    api_key = _get_api_key()
    if not api_key:
        return None
    if params is None:
        params = {}
    params["api_key"] = api_key
    params["language"] = params.get("language", "zh-CN")
    try:
        r = requests.get(f"{TMDB_BASE}{path}", params=params, timeout=10)
        if r.status_code == 200:
            return r.json()
        return None
    except Exception:
        return None


def set_api_key(api_key: str, enabled: bool = True) -> bool:
    conn = get_db()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO tmdb_config (id, api_key, enabled) VALUES (1, ?, ?)",
            (api_key, 1 if enabled else 0),
        )
        conn.commit()
        return True
    finally:
        conn.close()


def get_config() -> dict:
    conn = get_db()
    try:
        row = conn.execute("SELECT * FROM tmdb_config WHERE id = 1").fetchone()
        if row:
            return {
                "configured": bool(row["enabled"] and row["api_key"]),
                "enabled": bool(row["enabled"]),
            }
        return {"configured": False, "enabled": False}
    finally:
        conn.close()


def search(query: str, media_type: str = "tv", page: int = 1) -> dict:
    """
    搜索 TMDB。
    media_type: 'anime' → 搜 tv + 动画关键词, 'movie' → 搜 movie, 'tv' → 搜 tv
    """
    tmdb_type = TYPE_MAP.get(media_type, "tv")
    params = {"query": query, "page": page}

    if media_type == "anime":
        # 动漫搜索：用 tv 类型 + 动画关键词
        # 不使用 with_keywords 以减少结果限制
        pass

    result = _tmdb_get(f"/search/{tmdb_type}", params)
    if result is None:
        if not _get_api_key():
            return {"ok": False, "error": "TMDB API Key 未配置，请在设置页配置"}
        return {"ok": False, "error": "TMDB API 请求失败"}

    # 精简结果
    items = []
    for item in result.get("results", [])[:20]:
        poster = None
        if item.get("poster_path"):
            poster = f"{IMAGE_BASE}/w342{item['poster_path']}"
        backdrop = None
        if item.get("backdrop_path"):
            backdrop = f"{IMAGE_BASE}/w780{item['backdrop_path']}"

        # 对于 tv 类型，提取年份和原名
        first_air = item.get("first_air_date", "")
        release_date = item.get("release_date", "")
        date_str = first_air or release_date

        items.append({
            "tmdb_id": item["id"],
            "title": item.get("name") or item.get("title", "未知"),
            "original_title": item.get("original_name") or item.get("original_title", ""),
            "year": date_str[:4] if date_str else "",
            "overview": (item.get("overview") or "")[:200],
            "poster_url": poster,
            "backdrop_url": backdrop,
            "media_type": media_type,
            "vote_average": item.get("vote_average", 0),
        })

    return {
        "ok": True,
        "items": items,
        "total_results": result.get("total_results", 0),
        "page": result.get("page", page),
        "total_pages": result.get("total_pages", 1),
    }


def get_details(tmdb_id: int, media_type: str = "tv") -> dict:
    """获取节目详情，包括季/集数、海报等。"""
    tmdb_type = TYPE_MAP.get(media_type, "tv")
    params = {"append_to_response": "external_ids"}

    result = _tmdb_get(f"/{tmdb_type}/{tmdb_id}", params)
    if result is None:
        return {"ok": False, "error": "获取详情失败"}

    # 提取季和集
    seasons = []
    total_episodes = 0
    if tmdb_type == "tv":
        for s in result.get("seasons", []):
            if s.get("season_number", 0) == 0:
                continue  # 跳过特辑季
            seasons.append({
                "season_number": s["season_number"],
                "name": s.get("name", f"第{s['season_number']}季"),
                "episode_count": s.get("episode_count", 0),
                "poster_path": f"{IMAGE_BASE}/w342{s['poster_path']}" if s.get("poster_path") else None,
            })
            total_episodes += s.get("episode_count", 0)

    poster = None
    if result.get("poster_path"):
        poster = f"{IMAGE_BASE}/w500{result['poster_path']}"
    backdrop = None
    if result.get("backdrop_path"):
        backdrop = f"{IMAGE_BASE}/w1280{result['backdrop_path']}"

    # 题材标签
    genres = [g["name"] for g in result.get("genres", [])]

    # 地区
    region = ""
    if result.get("origin_country"):
        country = result["origin_country"][0] if result["origin_country"] else ""
        if country in ("CN", "TW", "HK"):
            region = "cn"
        elif country == "JP":
            region = "jp"
        elif country in ("US", "GB", "FR", "DE", "IT", "ES"):
            region = "west"
        else:
            region = country.lower()

    first_air = result.get("first_air_date", "")
    release_date = result.get("release_date", "")
    date_str = first_air or release_date

    return {
        "ok": True,
        "tmdb_id": result["id"],
        "title": result.get("name") or result.get("title", "未知"),
        "original_title": result.get("original_name") or result.get("original_title", ""),
        "year": date_str[:4] if date_str else "",
        "overview": result.get("overview", ""),
        "poster_url": poster,
        "backdrop_url": backdrop,
        "genres": genres,
        "region": region,
        "vote_average": result.get("vote_average", 0),
        "total_episodes": total_episodes,
        "number_of_seasons": result.get("number_of_seasons", 1) if tmdb_type == "tv" else 1,
        "seasons": seasons,
        "status": result.get("status", ""),
    }


def get_season(tmdb_id: int, season_number: int) -> dict:
    """获取单季的剧集列表。"""
    result = _tmdb_get(f"/tv/{tmdb_id}/season/{season_number}")
    if result is None:
        return {"ok": False, "error": "获取剧集列表失败"}

    episodes = []
    for ep in result.get("episodes", []):
        still = None
        if ep.get("still_path"):
            still = f"{IMAGE_BASE}/w300{ep['still_path']}"
        episodes.append({
            "episode_number": ep["episode_number"],
            "name": ep.get("name", ""),
            "overview": ep.get("overview", "")[:150],
            "still_url": still,
            "air_date": ep.get("air_date", ""),
        })

    return {
        "ok": True,
        "season_number": result.get("season_number", season_number),
        "name": result.get("name", ""),
        "episodes": episodes,
    }
