# poker_bankroll_analyzer/decorators.py
from functools import wraps
import jwt
from flask import current_app, g, jsonify, request
from .extensions import db
from .models import User

def require_auth(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        # 1. Read the Authorization header
        auth_header = request.headers.get("Authorization", None)
        if not auth_header:
            return jsonify({
                "code": "UNAUTHORIZED",
                "message": "Authorization header is missing."
            }), 401

        # 2. Check that if follows the exact "Bearer <token>" format
        parts = auth_header.split()
        if len(parts) !=2 or parts[0] != "Bearer":
            return jsonify({
                "code": "UNAUTHORIZED",
                "message": "Authorization header must be in 'Bearer <token>' format."
            }), 401

        token = parts[1]

        # 3 Verify signature and expiration
        try:
            secret_key = current_app.config["JWT_SECRET_KEY"]
            payload = jwt.decode(token, secret_key, algorithms=["HS256"])
        except jwt.ExpiredSignatureError:
            return jsonify({
                "code": "UNAUTHORIZED",
                "message": "Token has expired."
            }), 401
        except (jwt.InvalidTokenError, KeyError, ValueError):
            return jsonify({
                "code": "UNAUTHORIZED",
                "message": "Invalid authentication token."
            }), 401

        # 4. Extract user ID from 'sub' and store as an integer on flask.g
        sub = payload.get("sub")
        if not sub:
            return jsonify({
                "code": "UNAUTHORIZED",
                "message": "Token payload missing subject."
            }), 401

        try:
            g.current_user_id = int(sub)
        except (TypeError, ValueError):
            return jsonify({
                "code": "UNAUTHORIZED",
                "message": "Invalid user subject in token."
            }), 401

        # 5. All checks passed-let the protected route run
        return fn(*args, **kwargs)

    return wrapper

def require_role(required_role):
    """Second security door: verifies the authenticated user holds the required server-side role."""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            # Look up the verified user in SQLite (never trust role from request JSON)
            user = db.session.get(User, getattr(g, "current_user_id", None))
            if not user:
                return jsonify({
                    "code": "UNAUTHORIZED",
                    "mesage": "Authenticated user not found."
                }), 401

            g.current_user_role = user.role

            if user.role != required_role:
                return jsonify({
                    "code": "FORBIDDEN",
                    "message": "Admin privileges are required to access this resource."
                }), 403

            return fn(*args, **kwargs)
        return wrapper
    return decorator