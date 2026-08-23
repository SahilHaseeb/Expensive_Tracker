from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from config import Config
from datetime import timedelta
import os

db = SQLAlchemy()
login_manager = LoginManager()

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # 30-Day Permanent Session & Remember Me Cookie
    app.config['REMEMBER_COOKIE_DURATION'] = timedelta(days=30)
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)

    # Ensure instance directory exists for SQLite
    os.makedirs(app.instance_path, exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'

    from app.models import User, Expense, Budget, Subscription
    from app.db_sync import restore_db_from_backup

    with app.app_context():
        db.create_all()
        
        # Auto-migrate existing SQLite database if currency column is missing
        try:
            from sqlalchemy import text, inspect
            inspector = inspect(db.engine)
            if 'users' in inspector.get_table_names():
                columns = [c['name'] for c in inspector.get_columns('users')]
                if 'currency' not in columns:
                    with db.engine.connect() as conn:
                        conn.execute(text("ALTER TABLE users ADD COLUMN currency VARCHAR(10) DEFAULT '₹'"))
                        conn.commit()
        except Exception as e:
            print(f"Auto-migration check: {e}")

        # Restore from persistent backup storage if container woke up empty
        try:
            restore_db_from_backup(db, User, Expense, Budget, Subscription)
        except Exception as e:
            print(f"Backup restoration check: {e}")

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