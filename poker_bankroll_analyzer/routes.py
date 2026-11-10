# poker_bankroll_analyzer/routes.py
from flask import Blueprint, jsonify

# Create the department blueprint
# "poker_api" is its name, and __name__ helps my Flask locate its assets.
poker_blueprint = Blueprint("poker_api", __name__)

# simple status route to this blueprint department
@poker_blueprint.route("/status", methods=["GET"])
def get_status():
    # Return a simple JSON response to prove the route works
    return jsonify({
        "status": "online",
        "message": "Poker API blueprint is successfully wired"
    })

# Route 1: A welcome dashboard message
@poker_blueprint.route("/welcome", methods=["GET"])
def get_welcome():
    return jsonify({
        "greeting": "Welcome to your Personal Performance Tracker!",
        "greeting_a": "Here is where you redefine your poker journey",
        "tip": "Rememer to separate your freerolls from your cash buy-ins"
    })

# Route 2: A quick mock summary payload
@poker_blueprint.route("/mock-summary", methods=["GET"])
def get_mock_summary():
    return jsonify({
        "total_sessions": 0,
        "net_profit": 0.00,
        "status": "No games logged yet."
    })