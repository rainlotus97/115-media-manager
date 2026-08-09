"""
数据库模块：初始化 SQLite，提供连接和基础操作。
"""

import sqlite3
import os
from pathlib import Path

DB_FILE = Path(__file__).parent.parent / "115-media.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS user_sessions (
    token TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS user_115_config (
    user_id INTEGER PRIMARY KEY REFERENCES users(id),
    cookie TEXT,
    cookie_status TEXT DEFAULT 'unknown',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tmdb_config (
    id INTEGER PRIMARY KEY DEFAULT 1,
    api_key TEXT,
    enabled INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS watchlist (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    tmdb_id INTEGER,
    title TEXT NOT NULL,
    original_title TEXT,
    media_type TEXT NOT NULL,
    region TEXT,
    genre TEXT,
    poster_path TEXT,
    backdrop_path TEXT,
    overview TEXT,
    total_episodes INTEGER DEFAULT 0,
    cached_episodes INTEGER DEFAULT 0,
    latest_episode INTEGER DEFAULT 0,
    status TEXT DEFAULT 'tracking',
    path_115 TEXT,
    folder_id_115 TEXT,
    last_synced_at TIMESTAMP,
    next_sync_at TIMESTAMP,
    auto_sync_days TEXT DEFAULT '1,2,3,4,5,6,7',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, tmdb_id, path_115)
);

CREATE TABLE IF NOT EXISTS media_file_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    watchlist_id INTEGER REFERENCES watchlist(id),
    fid TEXT,
    filename TEXT NOT NULL,
    file_size INTEGER,
    episode_number INTEGER,
    season_number INTEGER DEFAULT 1,
    cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS dir_index_files (
    watchlist_id INTEGER REFERENCES watchlist(id),
    index_fid TEXT,
    index_name TEXT DEFAULT '.media_index.json',
    last_verified_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sync_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER REFERENCES users(id),
    watchlist_id INTEGER REFERENCES watchlist(id),
    action TEXT,
    files_added INTEGER DEFAULT 0,
    files_removed INTEGER DEFAULT 0,
    details TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tmdb_episode_cache (
    tmdb_id INTEGER NOT NULL,
    season_number INTEGER NOT NULL,
    episode_number INTEGER NOT NULL,
    name TEXT,
    still_path TEXT,
    air_date TEXT,
    overview TEXT,
    cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (tmdb_id, season_number, episode_number)
);

-- Single-user resource index.  This is deliberately independent from the
-- legacy watchlist tables so an upgrade never mutates a user's 115 files.
CREATE TABLE IF NOT EXISTS resources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    match_key TEXT NOT NULL,
    path_115 TEXT NOT NULL,
    folder_id_115 TEXT,
    tmdb_id INTEGER,
    media_type TEXT DEFAULT 'tv',
    poster_url TEXT,
    overview TEXT,
    total_episodes INTEGER DEFAULT 0,
    cached_episodes INTEGER DEFAULT 0,
    latest_episode INTEGER DEFAULT 0,
    seasons_json TEXT DEFAULT '[]',
    replace_rules_json TEXT DEFAULT '[]',
    file_count INTEGER DEFAULT 0,
    total_size INTEGER DEFAULT 0,
    last_synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS resource_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    resource_id INTEGER NOT NULL REFERENCES resources(id) ON DELETE CASCADE,
    fid TEXT,
    filename TEXT NOT NULL,
    file_size INTEGER NOT NULL DEFAULT 0,
    match_key TEXT,
    season_number INTEGER,
    episode_number INTEGER,
    display_name TEXT,
    tmdb_valid INTEGER DEFAULT 1,
    cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(resource_id, filename, file_size)
);

CREATE INDEX IF NOT EXISTS idx_resource_files_match
ON resource_files(filename, file_size);

CREATE INDEX IF NOT EXISTS idx_resources_match_key
ON resources(match_key);
"""


def get_db():
    """获取数据库连接（每线程独立）。"""
    conn = sqlite3.connect(str(DB_FILE))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


MIGRATIONS = [
    "ALTER TABLE media_file_cache ADD COLUMN season_number INTEGER DEFAULT 1",
    "ALTER TABLE watchlist ADD COLUMN latest_episode INTEGER DEFAULT 0",
    "ALTER TABLE resources ADD COLUMN tmdb_id INTEGER",
    "ALTER TABLE resources ADD COLUMN media_type TEXT DEFAULT 'tv'",
    "ALTER TABLE resources ADD COLUMN poster_url TEXT",
    "ALTER TABLE resources ADD COLUMN overview TEXT",
    "ALTER TABLE resources ADD COLUMN total_episodes INTEGER DEFAULT 0",
    "ALTER TABLE resources ADD COLUMN cached_episodes INTEGER DEFAULT 0",
    "ALTER TABLE resources ADD COLUMN latest_episode INTEGER DEFAULT 0",
    "ALTER TABLE resources ADD COLUMN seasons_json TEXT DEFAULT '[]'",
    "ALTER TABLE resources ADD COLUMN replace_rules_json TEXT DEFAULT '[]'",
    "ALTER TABLE resource_files ADD COLUMN season_number INTEGER",
    "ALTER TABLE resource_files ADD COLUMN episode_number INTEGER",
    "ALTER TABLE resource_files ADD COLUMN display_name TEXT",
    "ALTER TABLE resource_files ADD COLUMN tmdb_valid INTEGER DEFAULT 1",
]


def init_db():
    """初始化数据库表。"""
    conn = get_db()
    conn.executescript(SCHEMA)
    # 增量迁移
    for sql in MIGRATIONS:
        try:
            conn.execute(sql)
        except sqlite3.OperationalError:
            pass  # 列已存在
    conn.commit()
    conn.close()


# 应用启动时自动初始化
if not DB_FILE.exists():
    init_db()
else:
    # 确保表存在（增量迁移）
    init_db()
