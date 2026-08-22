from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from config import Config
import os

db = SQLAlchemy()
login_manager = LoginManager()

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Ensure instance directory exists for SQLite
    os.makedirs(app.instance_path, exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'

    from app.models import User, Expense, Budget, Subscription

    with app.app_context():
        db.create_all()

    # Blueprints registration
    from app.auth import auth as auth_blueprint
    app.register_blueprint(auth_blueprint)

    from app.routes import main as main_blueprint
    app.register_blueprint(main_blueprint)

    from app.chatbot_routes import chatbot_bp
    app.register_blueprint(chatbot_bp)

    from app.shopping_routes import shopping_bp
    app.register_blueprint(shopping_bp)

    from app.feature_routes import features_bp
    app.register_blueprint(features_bp)

    return app

# Expose 'app' directly for gunicorn
app = create_app()