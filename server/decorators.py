"""
装饰器：login_required。
"""

from functools import wraps
from flask import request, jsonify
from server.auth import get_session


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"ok": False, "error": "未登录"}), 401
        token = auth_header[7:]
        user = get_session(token)
        if not user:
            return jsonify({"ok": False, "error": "登录已过期，请重新登录"}), 401
        return f(user=user, *args, **kwargs)

    return decorated
