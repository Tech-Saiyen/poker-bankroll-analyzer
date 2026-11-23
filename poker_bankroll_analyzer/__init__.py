# poker_bankroll_analyzer/__init__.py
import click
from flask import Flask
from dotenv import load_dotenv

# I load the .env file at the absolute top of the file.
# This ensures that when .config imports below, the secret variables are already loaded! Prime the engine with secret keys before any config classes execute.
load_dotenv()

from .extensions import db, migrate
from .routes import poker_blueprint
from .venue_routes import venue_blueprint, seed_dfw_venues_data
from .config import config_by_name
# 🧠 I pull the models here so Flask-SQLAlchemy detects them on boot!
from . import models

def create_app(config_name="development"):
   # Create the Flask application instance
    app = Flask(__name__, instance_relative_config=True)
    selected_config = config_by_name[config_name]
  
 # Feed that configuration class directly into the Flask's configuration manager from our configuration object
    app.config.from_object(selected_config)
  
 # Call init_app to connect/bind the database and migration plumbing to this specific app instance
    db.init_app(app)
    migrate.init_app(app, db)
   # Officially sign off and register the blueprint department.
    app.register_blueprint(poker_blueprint, url_prefix="/api")
    app.register_blueprint(venue_blueprint, url_prefix="/api")

    @app.cli.command("seed-dfw")
    def seed_dfw_command():
        """Prepopulate starter Dallas-Fort Worth poker venues and live games."""
        added = seed_dfw_venues_data()
        click.echo(f"Seeded {added} new DFW poker venue(s).")

    print("🔑 JWT_SECRET_KEY configured:", bool(app.config.get("JWT_SECRET_KEY")))
   # Hand the fully configured application back to the server. 
    return app