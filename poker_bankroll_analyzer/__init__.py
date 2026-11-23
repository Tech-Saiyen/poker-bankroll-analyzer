# poker_bankroll_analyzer/__init__.py
import click
from flask import Flask
from dotenv import load_dotenv

load_dotenv()

from .extensions import db, migrate
from .routes import poker_blueprint
from .venue_routes import venue_blueprint, seed_dfw_venues_data
from .editorial_routes import editorial_blueprint
from .config import config_by_name
from . import models


def create_app(config_name="development"):
    app = Flask(__name__, instance_relative_config=True)
    selected_config = config_by_name[config_name]
    app.config.from_object(selected_config)

    db.init_app(app)
    migrate.init_app(app, db)

    app.register_blueprint(poker_blueprint, url_prefix="/api")
    app.register_blueprint(venue_blueprint, url_prefix="/api")
    app.register_blueprint(editorial_blueprint, url_prefix="/api")

    @app.cli.command("seed-dfw")
    def seed_dfw_command():
        """Prepopulate starter Dallas-Fort Worth poker venues and live games."""
        added = seed_dfw_venues_data()
        click.echo(f"Seeded {added} new DFW poker venue(s).")

    print("🔑 JWT_SECRET_KEY configured:", bool(app.config.get("JWT_SECRET_KEY")))

    return app
