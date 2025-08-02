import os
import sys
# DON'T CHANGE THIS !!!
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from flask import Flask, send_from_directory
from flask_cors import CORS
from src.models import db
from src.routes.auth import auth_bp
from src.routes.users import users_bp
from src.routes.payments import payments_bp
from src.routes.learning import learning_bp
from src.routes.forum import forum_bp
from src.routes.gamification import gamification_bp
from src.routes.admin import admin_bp
from src.routes.notifications import notifications_bp

app = Flask(__name__, static_folder=os.path.join(os.path.dirname(__file__), 'static'))

# Configuration
app.config['SECRET_KEY'] = 'CriticalMind-SaaS-Secret-Key-2024-Production-Ready'
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(os.path.dirname(__file__), 'database', 'app.db')}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Enable CORS for all routes
CORS(app, origins="*", allow_headers=["Content-Type", "Authorization"])

# Initialize database
db.init_app(app)

# Register blueprints
app.register_blueprint(auth_bp, url_prefix='/api/auth')
app.register_blueprint(users_bp, url_prefix='/api/users')
app.register_blueprint(payments_bp, url_prefix='/api/payments')
app.register_blueprint(learning_bp, url_prefix='/api/learning')
app.register_blueprint(forum_bp, url_prefix='/api/forum')
app.register_blueprint(gamification_bp, url_prefix='/api/gamification')
app.register_blueprint(admin_bp, url_prefix='/api/admin')
app.register_blueprint(notifications_bp, url_prefix='/api/notifications')

# Create tables
with app.app_context():
    db.create_all()

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    static_folder_path = app.static_folder
    if static_folder_path is None:
            return "Static folder not configured", 404

    if path != "" and os.path.exists(os.path.join(static_folder_path, path)):
        return send_from_directory(static_folder_path, path)
    else:
        index_path = os.path.join(static_folder_path, 'index.html')
        if os.path.exists(index_path):
            return send_from_directory(static_folder_path, 'index.html')
        else:
            return "index.html not found", 404


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
