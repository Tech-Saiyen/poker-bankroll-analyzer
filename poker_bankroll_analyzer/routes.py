# poker_bankroll_analyzer/routes.py
from flask import Blueprint, jsonify, request
from werkzeug.security import generate_password_hash
from .extensions import db
from .models import User

# Creates the department blueprint
# "poker_api" is its name, and __name__ helps my Flask locate its assets.
poker_blueprint = Blueprint("poker_api", __name__)

# Route 1: simple status route to this blueprint department
@poker_blueprint.route("/status", methods=["GET"])
def get_status():
    # Return a simple JSON response to prove the route works
    return jsonify({
        "status": "online",
        "message": "Poker API blueprint is successfully wired"
    })

# Route 2: A welcome dashboard message
@poker_blueprint.route("/welcome", methods=["GET"])
def get_welcome():
    return jsonify({
        "greeting": "Welcome to your Personal Performance Tracker!",
        "greeting_a": "Here is where you redefine your poker journey",
        "tip": "Rememer to separate your freerolls from your cash buy-ins"
    })

# Route 3: A quick mock summary payload
@poker_blueprint.route("/mock-summary", methods=["GET"])
def get_mock_summary():
    return jsonify({
        "total_sessions": 0,
        "net_profit": 0.00,
        "status": "No games logged yet."
    })

# Route 4: My official health check
@poker_blueprint.route("/health", methods=["GET"])
def get_health():
    #Returns a crisp JSON object and an explicit HTTP 200 success code
    return jsonify({
        "status": "healthy",
        "database_fallback": "active",
        "environment": "operational"
    }), 200

# 5. USER REGISTRATION ROUTE (WITH VALIDATION BOUNCER)
@poker_blueprint.route("/auth/register", methods=["POST"])
def register_user():
    # Open the incoming JSON envelope safely (silent=True prevents ugly HTML crashes with bad JSON)
    data = request.get_json(silent=True) or {}
    
    username = data.get("username")
    password = data.get("password")
    
    # --- BOUNCER CHECK 1: Validate Username ---
    if not username or not isinstance(username, str):
        return jsonify({
            "code": "VALIDATION_ERROR",
            "message": "Username is required."
        }), 400
    
    # Strips all accidental leading/trailing spaces before checking the length
    username = username.strip()
    if len(username) < 3 or len(username) > 30:
        return jsonify({
            "code": "VALIDATION_ERROR",
            "message": "Username must be between 3 and 30 characters long."
        }), 400

    # --- BOUNCER CHECK 2: Validate Password ---
    if not password or not isinstance(password, str):
        return jsonify({
            "code": "VALIDATION_ERROR",
            "message": "Password is required."
        }), 400
        
    if len(password) < 8 or len(password) > 128:
        return jsonify({
            "code": "VALIDATION_ERROR",
            "message": "Password must be between 8 and 128 characters long."
        }), 400

    # --- BOUNCER CHECK 3: Check For Duplicate Username ---
    existing_user = User.query.filter_by(username=username).first()
    if existing_user:
        return jsonify({
            "code": "VALIDATION_ERROR",
            "message": "Username is already taken."
        }), 409

    # Hash Password and Create User
    hashed_pw = generate_password_hash(password)
    new_user = User(username=username, password_hash=hashed_pw)

    db.session.add(new_user)
    db.session.commit()
    
    # If both pass the bouncer, return safe public field (201 Created)
    return jsonify({
        "id": new_user.id,
        "username": new_user.username,
        "created_at": new_user.created_at.isoformat()
    }), 201
