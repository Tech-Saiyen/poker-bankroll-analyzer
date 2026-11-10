# poker_bankroll_analyzer/config.py
import os

class Config:
    """Base config class with settings common to all environments."""
    # This is the fallback security secret. os.environ.get reads from the computer's system variables.
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET", "super-secret-fallback-key-for-local-dev")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

class DevelopmentConfig(Config):
    """Settings used while coding on my local MacBook."""
    DEBUG = True
    # Look for a system DATABASE_URL note; if it's missing, fall back to our local dev.db file
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///dev.db")

class TestingConfig(Config):
    """Settings used when running automated tests."""
    TESTING = True
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"  

class ProductionConfig(Config):
    """Settings used when live on the real internet for real users."""
    DEBUG = False
    # On a live server, DATABASE_URL MUST be provided, so no default fallback included. 
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL")

# The mapping dictionary that lets the factory select a setting team by its text name. 
config_by_name = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig
}
