import os
import sys
import logging
from datetime import timedelta
from dotenv import load_dotenv
from flask import Flask, send_from_directory, jsonify
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.middleware.proxy_fix import ProxyFix

# Load environment variables
load_dotenv()

# DON'T CHANGE THIS !!!
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.models import db
from src.routes.auth import auth_bp
from src.routes.users import users_bp
from src.routes.payments import payments_bp
from src.routes.learning import learning_bp
from src.routes.forum import forum_bp
from src.routes.gamification import gamification_bp
from src.routes.admin import admin_bp
from src.routes.notifications import notifications_bp
try:
    from src.utils.config import Config
    from src.utils.error_handlers import register_error_handlers
    from src.utils.security import setup_security_headers
except ImportError:
    # Fallback for missing modules
    class Config:
        SECRET_KEY = 'dev-secret-key'
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{os.path.join(os.path.dirname(__file__), 'database', 'app.db')}"
        SQLALCHEMY_TRACK_MODIFICATIONS = False
        CORS_ORIGINS = ['http://localhost:3000']
        VERSION = '1.0.0'
        FLASK_ENV = 'development'

    def register_error_handlers(app):
        pass

    def setup_security_headers(app):
        pass

def create_app(config_class=Config):
    """Application factory pattern"""
    app = Flask(__name__, static_folder=os.path.join(os.path.dirname(__file__), 'static'))

    # Load configuration
    app.config.from_object(config_class)

    # Trust proxy headers for rate limiting
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

    # Setup rate limiting
    limiter = Limiter(
        app,
        key_func=get_remote_address,
        default_limits=["1000 per hour", "100 per minute"],
        storage_uri=app.config.get('REDIS_URL', 'memory://')
    )

    # Configure CORS properly
    CORS(app,
         origins=app.config.get('CORS_ORIGINS', ['http://localhost:3000']),
         allow_headers=["Content-Type", "Authorization", "X-Requested-With"],
         methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
         supports_credentials=True)

    # Initialize database
    db.init_app(app)

    # Setup security headers
    setup_security_headers(app)

    # Register error handlers
    register_error_handlers(app)

    # Register blueprints with rate limiting
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(users_bp, url_prefix='/api/users')
    app.register_blueprint(payments_bp, url_prefix='/api/payments')
    app.register_blueprint(learning_bp, url_prefix='/api/learning')
    app.register_blueprint(forum_bp, url_prefix='/api/forum')
    app.register_blueprint(gamification_bp, url_prefix='/api/gamification')
    app.register_blueprint(admin_bp, url_prefix='/api/admin')
    app.register_blueprint(notifications_bp, url_prefix='/api/notifications')

    # Health check endpoint
    @app.route('/health')
    def health_check():
        return jsonify({
            'status': 'healthy',
            'version': app.config.get('VERSION', '1.0.0'),
            'environment': app.config.get('FLASK_ENV', 'production')
        })

    # API info endpoint
    @app.route('/api')
    def api_info():
        return jsonify({
            'name': 'CriticalMind API',
            'version': app.config.get('VERSION', '1.0.0'),
            'description': 'API for CriticalMind SaaS platform',
            'endpoints': {
                'auth': '/api/auth',
                'users': '/api/users',
                'payments': '/api/payments',
                'learning': '/api/learning',
                'forum': '/api/forum',
                'gamification': '/api/gamification',
                'admin': '/api/admin',
                'notifications': '/api/notifications'
            }
        })

    # Serve frontend static files
    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def serve(path):
        static_folder_path = app.static_folder
        if static_folder_path is None:
            return jsonify({'error': 'Static folder not configured'}), 404

        if path != "" and os.path.exists(os.path.join(static_folder_path, path)):
            return send_from_directory(static_folder_path, path)
        else:
            index_path = os.path.join(static_folder_path, 'index.html')
            if os.path.exists(index_path):
                return send_from_directory(static_folder_path, 'index.html')
            else:
                return jsonify({'error': 'Frontend not found'}), 404

    # Create tables in application context
    with app.app_context():
        db.create_all()

    return app

# Create app instance
app = create_app()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') == 'development'
    app.run(host='0.0.0.0', port=port, debug=debug)
