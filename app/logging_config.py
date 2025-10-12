"""
Logging Configuration for Highland Admin Portal

This module provides centralized logging configuration with:
- Rotating file handlers for different log levels
- Console output for development
- Structured logging format
- Separate error and access logs
"""

import logging
import os
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from datetime import datetime


def setup_logging(app):
    """
    Configure comprehensive logging for the Flask application.

    Args:
        app: Flask application instance

    Returns:
        None
    """
    # Create logs directory if it doesn't exist
    log_dir = 'logs'
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
        app.logger.info(f"Created logs directory: {log_dir}")

    # Determine log level based on environment
    if app.config.get('DEBUG'):
        log_level = logging.DEBUG
    elif app.config.get('TESTING'):
        log_level = logging.WARNING
    else:
        log_level = logging.INFO

    # Remove default handlers
    app.logger.handlers.clear()

    # Create formatters
    detailed_formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)s in %(module)s (%(filename)s:%(lineno)d): %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    simple_formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # 1. General Application Log (INFO and above) - Rotating by size
    app_handler = RotatingFileHandler(
        os.path.join(log_dir, 'app.log'),
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=10
    )
    app_handler.setLevel(logging.INFO)
    app_handler.setFormatter(detailed_formatter)
    app.logger.addHandler(app_handler)

    # 2. Error Log (ERROR and above) - Rotating by size
    error_handler = RotatingFileHandler(
        os.path.join(log_dir, 'errors.log'),
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=20
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(detailed_formatter)
    app.logger.addHandler(error_handler)

    # 3. Debug Log (DEBUG and above) - Only in development, daily rotation
    if app.config.get('DEBUG'):
        debug_handler = TimedRotatingFileHandler(
            os.path.join(log_dir, 'debug.log'),
            when='midnight',
            interval=1,
            backupCount=7  # Keep 7 days
        )
        debug_handler.setLevel(logging.DEBUG)
        debug_handler.setFormatter(detailed_formatter)
        app.logger.addHandler(debug_handler)

    # 4. Console Handler - For development
    if app.config.get('DEBUG'):
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(simple_formatter)
        app.logger.addHandler(console_handler)

    # Set the application logger level
    app.logger.setLevel(log_level)

    # Configure SQLAlchemy logging (reduce noise)
    logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
    logging.getLogger('sqlalchemy.pool').setLevel(logging.WARNING)

    # Configure Werkzeug logging (Flask development server)
    werkzeug_logger = logging.getLogger('werkzeug')
    werkzeug_logger.setLevel(logging.INFO)

    # Log startup information
    app.logger.info('=' * 80)
    app.logger.info(f'Highland Admin Portal Starting')
    app.logger.info(f'Environment: {app.config.get("FLASK_ENV", "production")}')
    app.logger.info(f'Debug Mode: {app.config.get("DEBUG", False)}')
    app.logger.info(f'Log Level: {logging.getLevelName(log_level)}')
    app.logger.info(f'Database: {app.config.get("SQLALCHEMY_DATABASE_URI", "Not configured")}')
    app.logger.info('=' * 80)

    # Register request logging
    @app.before_request
    def log_request_info():
        """Log information about each request"""
        from flask import request
        if not request.path.startswith('/static'):
            app.logger.debug(f'Request: {request.method} {request.path} from {request.remote_addr}')

    @app.after_request
    def log_response_info(response):
        """Log information about each response"""
        from flask import request
        if not request.path.startswith('/static'):
            app.logger.debug(f'Response: {response.status_code} for {request.method} {request.path}')
        return response

    @app.errorhandler(Exception)
    def log_exception(error):
        """Log unhandled exceptions"""
        app.logger.error(f'Unhandled exception: {error}', exc_info=True)
        # Re-raise the exception so Flask can handle it normally
        raise error

    app.logger.info('Logging configuration complete')


def get_logger(name):
    """
    Get a logger instance for a specific module.

    Args:
        name: Name of the module (typically __name__)

    Returns:
        logging.Logger: Configured logger instance
    """
    return logging.getLogger(name)
