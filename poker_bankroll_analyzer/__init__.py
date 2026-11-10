# poker_bankroll_analyzer/__init__.py
from flask import Flask
from dotenv import load_dotenv

# We load the .env file at the absolute top of the file.
# This ensures that when .config imports below, the secret variables are already loaded! Prime the engine with secret keys before any config classes execute. 
load_dotenv()

from .extensions import db, migrate
from .routes import poker_blueprint # Grab department blueprint
from .config import config_by_name 

def create_app(config_name="development"):
    # Create the Flask applicaton instance
    app = Flask(__name__, instance_relative_config=True)
    # Look up the correct config class using the mapping dict (config_by_name["?"])
    selected_config = config_by_name[config_name]
    # Feed that configuration class directly into the Flask's configuration manager from our configuration object
    app.config.from_object(selected_config)

    # Call init_app to connect/bind the database and migration plumbing to this specific app instance
    db.init_app(app)
    migrate.init_app(app, db)

    # Officially sign off and reister the blueprint department.
    app.register_blueprint(poker_blueprint, url_prefix="/api")

    # temp log for experiment
    print(f"\n 🔑ACTIVE JWT SECRET KEY IN SYSTEM: {app.config['JWT_SECRET_KEY']}\n")

    # Hand the fully configured application back to the server. 
    return app