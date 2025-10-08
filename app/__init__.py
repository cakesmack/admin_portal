from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
import logging
from logging.handlers import RotatingFileHandler
import os

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
        
        print(f"✅ Configuration loaded successfully")
        print(f"   SECRET_KEY length: {len(app.config['SECRET_KEY'])} characters")
        
    except ValueError as e:
        print(f"❌ Configuration Error: {e}")
        print("Please run: python generate_secret_key.py")
        raise
    except Exception as e:
        print(f"❌ Failed to load configuration: {e}")
        raise
    
    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    
    # Register blueprints
    from app.routes import main
    from app.blueprints.auth import auth_bp
    from app.blueprints.standing_orders import standing_orders_bp
    from app.blueprints.callsheets import callsheets_bp
    from app.blueprints.customer_stock import customer_stock_bp
    from app.blueprints.admin import admin_bp
    from app.blueprints.clearance_stock import clearance_stock_bp
    
    app.register_blueprint(main)
    app.register_blueprint(auth_bp)
    app.register_blueprint(standing_orders_bp)
    app.register_blueprint(callsheets_bp)
    app.register_blueprint(customer_stock_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(clearance_stock_bp)



    # Add security headers in production
    if app.config.get('FLASK_ENV') == 'production':
        @app.after_request
        def add_security_headers(response):
            headers = app.config.get('SECURITY_HEADERS', {})
            for header, value in headers.items():
                response.headers[header] = value
            return response
    
    # ADD THIS SECTION - Logging Setup
    if not app.debug:
        # Create logs directory if it doesn't exist
        if not os.path.exists('logs'):
            os.mkdir('logs')
        
        # Set up file handler with rotation
        file_handler = RotatingFileHandler(
            'logs/app.log', 
            maxBytes=10485760,  # 10MB
            backupCount=10
        )
        
        # Set logging format
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        
        # Set logging level
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        app.logger.setLevel(logging.INFO)
        app.logger.info('Application startup')
    
    return app