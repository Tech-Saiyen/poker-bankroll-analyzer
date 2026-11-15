# poker_bankroll_analyzer/errors.py
from flask import jsonify

def error_response(code, message, status_code):
    """Build a standardized JSON error response matching the API error contract."""
    return jsonify({
        "code": code,
        "message": message,
    }), status_code