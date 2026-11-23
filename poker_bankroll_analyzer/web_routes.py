# poker_bankroll_analyzer/web_routes.py
from flask import Blueprint, jsonify, render_template

web_blueprint = Blueprint("web", __name__)


@web_blueprint.route("/", methods=["GET"])
def home_page():
    """Serves the mobile-first DFW Poker Life & Live Floor web application."""
    return render_template("index.html")


@web_blueprint.route("/manifest.json", methods=["GET"])
def pwa_manifest():
    """Progressive Web App manifest enabling 'Add to Home Screen' on iOS & Android."""
    return jsonify({
        "name": "DFW Poker Life & Live Floor",
        "short_name": "DFW Poker",
        "description": "Live DFW poker waitlists, streams, bankroll analytics, and player spotlights.",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#0b1116",
        "theme_color": "#0b1116",
        "orientation": "portrait",
    }), 200

