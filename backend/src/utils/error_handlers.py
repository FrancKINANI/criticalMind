import logging
from flask import jsonify, request
from werkzeug.exceptions import HTTPException
from sqlalchemy.exc import SQLAlchemyError
import traceback

logger = logging.getLogger(__name__)

def register_error_handlers(app):
    """Register error handlers for the Flask app"""
    
    @app.errorhandler(400)
    def bad_request(error):
        """Handle bad request errors"""
        return jsonify({
            'error': 'Bad Request',
            'message': 'The request could not be understood by the server',
            'status_code': 400
        }), 400
    
    @app.errorhandler(401)
    def unauthorized(error):
        """Handle unauthorized errors"""
        return jsonify({
            'error': 'Unauthorized',
            'message': 'Authentication required',
            'status_code': 401
        }), 401
    
    @app.errorhandler(403)
    def forbidden(error):
        """Handle forbidden errors"""
        return jsonify({
            'error': 'Forbidden',
            'message': 'You do not have permission to access this resource',
            'status_code': 403
        }), 403
    
    @app.errorhandler(404)
    def not_found(error):
        """Handle not found errors"""
        return jsonify({
            'error': 'Not Found',
            'message': 'The requested resource was not found',
            'status_code': 404
        }), 404
    
    @app.errorhandler(405)
    def method_not_allowed(error):
        """Handle method not allowed errors"""
        return jsonify({
            'error': 'Method Not Allowed',
            'message': 'The method is not allowed for the requested URL',
            'status_code': 405
        }), 405
    
    @app.errorhandler(422)
    def unprocessable_entity(error):
        """Handle validation errors"""
        return jsonify({
            'error': 'Unprocessable Entity',
            'message': 'The request was well-formed but contains semantic errors',
            'status_code': 422
        }), 422
    
    @app.errorhandler(429)
    def rate_limit_exceeded(error):
        """Handle rate limit exceeded errors"""
        return jsonify({
            'error': 'Rate Limit Exceeded',
            'message': 'Too many requests. Please try again later.',
            'status_code': 429,
            'retry_after': getattr(error, 'retry_after', None)
        }), 429
    
    @app.errorhandler(500)
    def internal_server_error(error):
        """Handle internal server errors"""
        logger.error(f"Internal server error: {str(error)}")
        logger.error(f"Request: {request.method} {request.url}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        
        return jsonify({
            'error': 'Internal Server Error',
            'message': 'An unexpected error occurred',
            'status_code': 500
        }), 500
    
    @app.errorhandler(SQLAlchemyError)
    def database_error(error):
        """Handle database errors"""
        logger.error(f"Database error: {str(error)}")
        logger.error(f"Request: {request.method} {request.url}")
        
        return jsonify({
            'error': 'Database Error',
            'message': 'A database error occurred',
            'status_code': 500
        }), 500
    
    @app.errorhandler(HTTPException)
    def handle_http_exception(error):
        """Handle HTTP exceptions"""
        return jsonify({
            'error': error.name,
            'message': error.description,
            'status_code': error.code
        }), error.code
    
    @app.errorhandler(Exception)
    def handle_unexpected_error(error):
        """Handle unexpected errors"""
        logger.error(f"Unexpected error: {str(error)}")
        logger.error(f"Request: {request.method} {request.url}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        
        # Don't expose internal errors in production
        if app.config.get('FLASK_ENV') == 'production':
            message = 'An unexpected error occurred'
        else:
            message = str(error)
        
        return jsonify({
            'error': 'Unexpected Error',
            'message': message,
            'status_code': 500
        }), 500

class APIError(Exception):
    """Custom API error class"""
    
    def __init__(self, message, status_code=400, payload=None):
        super().__init__()
        self.message = message
        self.status_code = status_code
        self.payload = payload
    
    def to_dict(self):
        result = {'message': self.message}
        if self.payload:
            result.update(self.payload)
        return result

class ValidationError(APIError):
    """Validation error"""
    
    def __init__(self, message, field=None):
        super().__init__(message, 422)
        if field:
            self.payload = {'field': field}

class AuthenticationError(APIError):
    """Authentication error"""
    
    def __init__(self, message='Authentication required'):
        super().__init__(message, 401)

class AuthorizationError(APIError):
    """Authorization error"""
    
    def __init__(self, message='Insufficient permissions'):
        super().__init__(message, 403)

class NotFoundError(APIError):
    """Not found error"""
    
    def __init__(self, message='Resource not found'):
        super().__init__(message, 404)

class ConflictError(APIError):
    """Conflict error"""
    
    def __init__(self, message='Resource conflict'):
        super().__init__(message, 409)

def register_custom_error_handlers(app):
    """Register custom error handlers"""
    
    @app.errorhandler(APIError)
    def handle_api_error(error):
        response = jsonify(error.to_dict())
        response.status_code = error.status_code
        return response
    
    @app.errorhandler(ValidationError)
    def handle_validation_error(error):
        response = jsonify(error.to_dict())
        response.status_code = error.status_code
        return response
    
    @app.errorhandler(AuthenticationError)
    def handle_authentication_error(error):
        response = jsonify(error.to_dict())
        response.status_code = error.status_code
        return response
    
    @app.errorhandler(AuthorizationError)
    def handle_authorization_error(error):
        response = jsonify(error.to_dict())
        response.status_code = error.status_code
        return response
    
    @app.errorhandler(NotFoundError)
    def handle_not_found_error(error):
        response = jsonify(error.to_dict())
        response.status_code = error.status_code
        return response
    
    @app.errorhandler(ConflictError)
    def handle_conflict_error(error):
        response = jsonify(error.to_dict())
        response.status_code = error.status_code
        return response
