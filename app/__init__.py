from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message_category = 'info'

def create_app():
    app = Flask(__name__)
    app.config['TEMPLATES_AUTO_RELOAD'] = True
    # Load configuration
    try:
        from config import get_config
        config_class = get_config()
        app.config.from_object(config_class)

        print(f"[SUCCESS] Configuration loaded successfully")
        print(f"   SECRET_KEY length: {len(app.config['SECRET_KEY'])} characters")

    except ValueError as e:
        print(f"[ERROR] Configuration Error: {e}")
        print("Please run: python generate_secret_key.py")
        raise
    except Exception as e:
        print(f"[ERROR] Failed to load configuration: {e}")
        raise

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)

    # Setup comprehensive logging
    from app.logging_config import setup_logging
    setup_logging(app)

    # Register blueprints
    from app.routes import main
    from app.blueprints.auth import auth_bp
    from app.blueprints.standing_orders import standing_orders_bp
    from app.blueprints.callsheets import callsheets_bp
    from app.blueprints.customer_stock import customer_stock_bp
    from app.blueprints.admin import admin_bp
    from app.blueprints.clearance_stock import clearance_stock_bp
    from app.blueprints.forms import forms_bp
    from app.blueprints.customers import customers_bp
    from app.blueprints.company_updates import company_updates_bp

    app.register_blueprint(main)
    app.register_blueprint(auth_bp)
    app.register_blueprint(standing_orders_bp)
    app.register_blueprint(callsheets_bp)
    app.register_blueprint(customer_stock_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(clearance_stock_bp)
    app.register_blueprint(forms_bp)
    app.register_blueprint(customers_bp)
    app.register_blueprint(company_updates_bp)

    # Add security headers in production
    if app.config.get('FLASK_ENV') == 'production':
        @app.after_request
        def add_security_headers(response):
            headers = app.config.get('SECURITY_HEADERS', {})
            for header, value in headers.items():
                response.headers[header] = value
            return response

    return app