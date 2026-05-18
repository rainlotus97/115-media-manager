"""
认证模块：注册、登录、session 管理。
"""

import hashlib
import secrets
from typing import Optional
from datetime import datetime, timedelta
from server.db import get_db


def _hash_password(password: str) -> str:
    """SHA-256 哈希密码（简单方案，避免 bcrypt 额外依赖）。"""
    salt = "115-media-mgr"
    return hashlib.sha256(f"{salt}:{password}".encode()).hexdigest()


def _generate_token() -> str:
    return secrets.token_hex(32)


def register(username: str, password: str) -> dict:
    """注册新用户，返回 {ok, token, user} 或 {ok: false, error}。"""
    if not username or not password:
        return {"ok": False, "error": "用户名和密码不能为空"}
    if len(username) < 2:
        return {"ok": False, "error": "用户名至少 2 个字符"}
    if len(password) < 4:
        return {"ok": False, "error": "密码至少 4 个字符"}

    conn = get_db()
    try:
        existing = conn.execute(
            "SELECT id FROM users WHERE username = ?", (username,)
        ).fetchone()
        if existing:
            return {"ok": False, "error": "用户名已存在"}

        pw_hash = _hash_password(password)
        cur = conn.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (username, pw_hash),
        )
        user_id = cur.lastrowid

        # 创建 session
        token = _generate_token()
        expires = datetime.utcnow() + timedelta(days=30)
        conn.execute(
            "INSERT INTO user_sessions (token, user_id, expires_at) VALUES (?, ?, ?)",
            (token, user_id, expires),
        )
        conn.commit()

        return {
            "ok": True,
            "token": token,
            "user": {"id": user_id, "username": username},
        }
    finally:
        conn.close()


def login(username: str, password: str) -> dict:
    """登录，返回 {ok, token, user} 或 {ok: false, error}。"""
    if not username or not password:
        return {"ok": False, "error": "用户名和密码不能为空"}

    conn = get_db()
    try:
        user = conn.execute(
            "SELECT id, username, password_hash FROM users WHERE username = ?",
            (username,),
        ).fetchone()
        if not user:
            return {"ok": False, "error": "用户名不存在"}

        if user["password_hash"] != _hash_password(password):
            return {"ok": False, "error": "密码错误"}

        # 创建新 session（不踢其他设备）
        token = _generate_token()
        expires = datetime.utcnow() + timedelta(days=30)
        conn.execute(
            "INSERT INTO user_sessions (token, user_id, expires_at) VALUES (?, ?, ?)",
            (token, user["id"], expires),
        )
        conn.commit()

        return {
            "ok": True,
            "token": token,
            "user": {"id": user["id"], "username": user["username"]},
        }
    finally:
        conn.close()


def get_session(token: str) -> Optional[dict]:
    """验证 token，返回 user info 或 None。"""
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT u.id, u.username FROM user_sessions s "
            "JOIN users u ON s.user_id = u.id "
            "WHERE s.token = ? AND s.expires_at > ?",
            (token, datetime.utcnow()),
        ).fetchone()
        if row:
            return {"id": row["id"], "username": row["username"]}
        return None
    finally:
        conn.close()


def logout(token: str):
    """登出，删除 session。"""
    conn = get_db()
    try:
        conn.execute("DELETE FROM user_sessions WHERE token = ?", (token,))
        conn.commit()
    finally:
        conn.close()
