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
    from src.utils.config import config
    from src.utils.error_handlers import register_error_handlers
    from src.utils.security import setup_security_headers, SecurityMiddleware
    from src.utils.monitoring import init_monitoring
    from src.utils.input_validation import ValidationError
    from flask_talisman import Talisman
    from flask_wtf.csrf import CSRFProtect
    from flask_caching import Cache
    from flask_migrate import Migrate
except ImportError as e:
    print(f"Warning: Could not import enhanced modules: {e}")
    # Fallback for missing modules
    from src.utils.config import Config as config

    def register_error_handlers(app):
        pass

    def setup_security_headers(app):
        pass

    def init_monitoring(app):
        return app

    class SecurityMiddleware:
        def __init__(self, app):
            pass

    class Talisman:
        def __init__(self, app, **kwargs):
            pass

    class CSRFProtect:
        def __init__(self, app=None):
            pass

    class Cache:
        def __init__(self, app=None, config=None):
            pass

    class Migrate:
        def __init__(self, app=None, db=None):
            pass

def create_app(config_name=None):
    """Application factory pattern with enhanced security and monitoring"""
    app = Flask(__name__, static_folder=os.path.join(os.path.dirname(__file__), 'static'))

    # Load configuration based on environment
    config_name = config_name or os.environ.get('FLASK_ENV', 'development')
    app.config.from_object(config[config_name])

    # Trust proxy headers for rate limiting
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

    # Initialize security middleware
    SecurityMiddleware(app)

    # Setup CSRF protection
    csrf = CSRFProtect(app)

    # Setup security headers with Talisman
    if app.config.get('FLASK_ENV') == 'production':
        Talisman(
            app,
            force_https=True,
            strict_transport_security=True,
            strict_transport_security_max_age=31536000,
            content_security_policy={
                'default-src': "'self'",
                'script-src': "'self' 'unsafe-inline' https://js.stripe.com",
                'style-src': "'self' 'unsafe-inline'",
                'img-src': "'self' data: https:",
                'font-src': "'self' https:",
                'connect-src': "'self' https://api.stripe.com"
            }
        )

    # Setup rate limiting
    limiter = Limiter(
        app=app,
        key_func=get_remote_address,
        default_limits=[app.config.get('RATELIMIT_DEFAULT', "1000 per hour, 100 per minute")],
        storage_uri=app.config.get('REDIS_URL', 'memory://'),
        # Degradation gracieuse si Redis est indisponible (fallback mémoire)
        # au lieu de 500 sur chaque requête.
        in_memory_fallback_enabled=True,
        swallow_errors=True
    )

    # Initialize caching
    cache = Cache(app, config={
        'CACHE_TYPE': 'redis',
        'CACHE_REDIS_URL': app.config.get('REDIS_URL'),
        'CACHE_DEFAULT_TIMEOUT': 300
    })

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
        # S'assurer que le répertoire de la base SQLite existe (absent sur un
        # clone frais : git ne tracke pas les dossiers vides)
        db_uri = app.config.get('SQLALCHEMY_DATABASE_URI', '')
        if db_uri.startswith('sqlite:///'):
            db_dir = os.path.dirname(db_uri.removeprefix('sqlite:///'))
            if db_dir:
                os.makedirs(db_dir, exist_ok=True)
        db.create_all()

    return app

# Create app instance
app = create_app()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') == 'development'
    app.run(host='0.0.0.0', port=port, debug=debug)
