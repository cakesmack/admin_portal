from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
login_manager.login_view = 'main.login'
login_manager.login_message_category = 'info'

def create_app():
    app = Flask(__name__)
    
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
    from app.admin_routes import admin_bp
    
    app.register_blueprint(main)
    app.register_blueprint(admin_bp)
    
    # Add security headers in production
    if app.config.get('FLASK_ENV') == 'production':
        @app.after_request
        def add_security_headers(response):
            headers = app.config.get('SECURITY_HEADERS', {})
            for header, value in headers.items():
                response.headers[header] = value
            return response
    
    return app