from flask import request, g
from functools import wraps
import logging

logger = logging.getLogger(__name__)

def setup_security_headers(app):
    """Setup security headers for the Flask app"""
    
    @app.after_request
    def add_security_headers(response):
        """Add security headers to all responses"""
        headers = app.config.get('SECURITY_HEADERS', {})
        
        for header, value in headers.items():
            response.headers[header] = value
        
        # Add CORS headers if not already set
        if 'Access-Control-Allow-Origin' not in response.headers:
            origin = request.headers.get('Origin')
            allowed_origins = app.config.get('CORS_ORIGINS', [])
            
            if origin in allowed_origins or '*' in allowed_origins:
                response.headers['Access-Control-Allow-Origin'] = origin
                response.headers['Access-Control-Allow-Credentials'] = 'true'
        
        return response
    
    @app.before_request
    def log_request_info():
        """Log request information for security monitoring"""
        if app.config.get('FLASK_ENV') != 'production':
            logger.info(f"Request: {request.method} {request.url}")
            logger.info(f"Headers: {dict(request.headers)}")
            logger.info(f"Remote Address: {request.remote_addr}")
            logger.info(f"User Agent: {request.headers.get('User-Agent')}")

def require_https(f):
    """Decorator to require HTTPS in production"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if request.environ.get('wsgi.url_scheme') != 'https' and \
           request.headers.get('X-Forwarded-Proto') != 'https':
            from flask import current_app
            if current_app.config.get('FLASK_ENV') == 'production':
                return {'error': 'HTTPS required'}, 400
        return f(*args, **kwargs)
    return decorated_function

def validate_content_type(content_type='application/json'):
    """Decorator to validate request content type"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if request.method in ['POST', 'PUT', 'PATCH']:
                if not request.content_type or not request.content_type.startswith(content_type):
                    return {'error': f'Content-Type must be {content_type}'}, 400
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def sanitize_filename(filename):
    """Sanitize filename for safe file operations"""
    import re
    import os
    
    # Remove path separators and dangerous characters
    filename = re.sub(r'[<>:"/\\|?*]', '', filename)
    filename = re.sub(r'\.\.', '', filename)  # Remove directory traversal
    filename = filename.strip('. ')  # Remove leading/trailing dots and spaces
    
    # Limit length
    if len(filename) > 255:
        name, ext = os.path.splitext(filename)
        filename = name[:255-len(ext)] + ext
    
    return filename

def validate_file_upload(file, allowed_extensions=None, max_size=None):
    """Validate file upload"""
    if not file or not file.filename:
        return False, "No file provided"
    
    # Check file extension
    if allowed_extensions:
        ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''
        if ext not in allowed_extensions:
            return False, f"File type not allowed. Allowed types: {', '.join(allowed_extensions)}"
    
    # Check file size
    if max_size:
        file.seek(0, 2)  # Seek to end
        size = file.tell()
        file.seek(0)  # Reset to beginning
        
        if size > max_size:
            return False, f"File too large. Maximum size: {max_size} bytes"
    
    return True, "Valid file"

def check_password_strength(password):
    """Check password strength"""
    import re
    
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    
    if not re.search(r'[A-Z]', password):
        return False, "Password must contain at least one uppercase letter"
    
    if not re.search(r'[a-z]', password):
        return False, "Password must contain at least one lowercase letter"
    
    if not re.search(r'\d', password):
        return False, "Password must contain at least one digit"
    
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        return False, "Password must contain at least one special character"
    
    # Check for common weak passwords
    weak_passwords = [
        'password', '12345678', 'qwerty', 'abc123', 'password123',
        'admin', 'letmein', 'welcome', '123456789', 'password1'
    ]
    
    if password.lower() in weak_passwords:
        return False, "Password is too common"
    
    return True, "Strong password"

def generate_csrf_token():
    """Generate CSRF token"""
    import secrets
    return secrets.token_urlsafe(32)

def validate_csrf_token(token):
    """Validate CSRF token"""
    # In a real implementation, you would store and validate against a session token
    # This is a simplified version
    return token and len(token) == 43  # URL-safe base64 token length

def rate_limit_key_func():
    """Generate rate limit key based on user or IP"""
    if hasattr(g, 'current_user') and g.current_user:
        return f"user:{g.current_user.id}"
    return f"ip:{request.remote_addr}"

def is_safe_url(target):
    """Check if URL is safe for redirects"""
    from urllib.parse import urlparse, urljoin
    from flask import request, url_for
    
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    
    return test_url.scheme in ('http', 'https') and \
           ref_url.netloc == test_url.netloc

def mask_sensitive_data(data, fields=None):
    """Mask sensitive data in logs"""
    if fields is None:
        fields = ['password', 'token', 'secret', 'key', 'authorization']
    
    if isinstance(data, dict):
        masked = {}
        for key, value in data.items():
            if any(field in key.lower() for field in fields):
                masked[key] = '***MASKED***'
            elif isinstance(value, (dict, list)):
                masked[key] = mask_sensitive_data(value, fields)
            else:
                masked[key] = value
        return masked
    elif isinstance(data, list):
        return [mask_sensitive_data(item, fields) for item in data]
    else:
        return data

class SecurityMiddleware:
    """Security middleware for additional protection"""
    
    def __init__(self, app):
        self.app = app
        self.init_app(app)
    
    def init_app(self, app):
        """Initialize security middleware"""
        app.before_request(self.before_request)
        app.after_request(self.after_request)
    
    def before_request(self):
        """Process request before handling"""
        # Block requests with suspicious patterns
        suspicious_patterns = [
            '../', '..\\', '<script', 'javascript:', 'vbscript:',
            'onload=', 'onerror=', 'eval(', 'expression('
        ]
        
        request_data = str(request.url) + str(request.get_data())
        for pattern in suspicious_patterns:
            if pattern in request_data.lower():
                logger.warning(f"Suspicious request blocked: {request.url}")
                return {'error': 'Suspicious request blocked'}, 400
    
    def after_request(self, response):
        """Process response after handling"""
        # Remove server information
        response.headers.pop('Server', None)
        return response
