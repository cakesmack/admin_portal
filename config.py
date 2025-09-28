# config.py
# Updated secure configuration that properly loads from .env

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    # Get SECRET_KEY from environment, with fallback warning
    SECRET_KEY = os.environ.get('SECRET_KEY')
    
    # Validate SECRET_KEY exists and is secure
    if not SECRET_KEY:
        raise ValueError(
            "SECRET_KEY not found! Please run 'python generate_secret_key.py' "
            "to create a secure .env file with SECRET_KEY"
        )
    
    # Warn if using a weak SECRET_KEY
    if SECRET_KEY in ['dev-key-change-in-production', 'your-secret-key-here']:
        raise ValueError(
            "Insecure SECRET_KEY detected! Please run 'python generate_secret_key.py' "
            "to generate a secure SECRET_KEY"
        )
    
    # Ensure SECRET_KEY is long enough
    if len(SECRET_KEY) < 32:
        print("⚠️  WARNING: SECRET_KEY is shorter than recommended (32+ characters)")
    
    # Database configuration
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///admin_portal.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Security settings
    SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'false').lower() == 'true'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # CSRF Protection
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = 3600  # 1 hour
    
    # Upload settings
    MAX_CONTENT_LENGTH = int(os.environ.get('MAX_CONTENT_LENGTH', 16 * 1024 * 1024))  # 16MB
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', 'uploads')
    
    # Application settings
    PERMANENT_SESSION_LIFETIME = 86400  # 24 hours in seconds

class DevelopmentConfig(Config):
    """Development-specific configuration"""
    DEBUG = True
    FLASK_ENV = 'development'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DEV_DATABASE_URL') or 'sqlite:///admin_portal_dev.db'
    SESSION_COOKIE_SECURE = False  # Allow HTTP in development

class ProductionConfig(Config):
    """Production-specific configuration"""
    DEBUG = False
    TESTING = False
    FLASK_ENV = 'production'
    
    # Force secure cookies in production
    SESSION_COOKIE_SECURE = True
    
    # Additional production settings
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_recycle': 300,
        'pool_pre_ping': True
    }
    
    # Enhanced security headers (you can add these to your app later)
    SECURITY_HEADERS = {
        'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',
        'X-Content-Type-Options': 'nosniff',
        'X-Frame-Options': 'DENY',
        'X-XSS-Protection': '1; mode=block'
    }

class TestingConfig(Config):
    """Testing-specific configuration"""
    TESTING = True
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    SECRET_KEY = 'test-secret-key-not-secure'  # OK for testing only

# Configuration selection based on environment
def get_config():
    """Get configuration based on FLASK_ENV environment variable"""
    env = os.environ.get('FLASK_ENV', 'development').lower()
    
    config_map = {
        'development': DevelopmentConfig,
        'production': ProductionConfig,
        'testing': TestingConfig
    }
    
    config_class = config_map.get(env, DevelopmentConfig)
    
    # Print configuration info (but not the actual SECRET_KEY!)
    print(f"🔧 Loading {config_class.__name__}")
    print(f"   Environment: {env}")
    print(f"   Debug: {config_class.DEBUG}")
    print(f"   Database: {config_class.SQLALCHEMY_DATABASE_URI}")
    print(f"   Secure Cookies: {config_class.SESSION_COOKIE_SECURE}")
    
    return config_class

# For backwards compatibility
Config = get_config()