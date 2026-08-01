import jwt
import uuid
from datetime import datetime, timedelta
from functools import wraps
from flask import request, jsonify, current_app, g
from src.models import db
from src.models.user import User, UserSession

class AuthManager:
    """Authentication manager for CriticalMind SaaS"""
    
    @staticmethod
    def generate_tokens(user_id):
        """Generate access and refresh tokens for a user"""
        now = datetime.utcnow()
        
        # Access token (15 minutes)
        access_payload = {
            'user_id': user_id,
            'type': 'access',
            'iat': now,
            'exp': now + timedelta(minutes=15),
            'jti': str(uuid.uuid4())
        }
        access_token = jwt.encode(access_payload, current_app.config['SECRET_KEY'], algorithm='HS256')
        
        # Refresh token (30 days)
        refresh_payload = {
            'user_id': user_id,
            'type': 'refresh',
            'iat': now,
            'exp': now + timedelta(days=30),
            'jti': str(uuid.uuid4())
        }
        refresh_token = jwt.encode(refresh_payload, current_app.config['SECRET_KEY'], algorithm='HS256')
        
        # Create a user session
        session = UserSession(
            user_id=user_id,
            session_token=access_token,
            refresh_token=refresh_token,
            expires_at=now + timedelta(days=30)
        )
        db.session.add(session)
        db.session.commit()
        
        return {
            'access_token': access_token,
            'refresh_token': refresh_token,
            'expires_in': 900,  # 15 minutes in seconds
            'token_type': 'Bearer'
        }
    
    @staticmethod
    def verify_token(token, token_type='access'):
        """Verify and decode a JWT token"""
        try:
            payload = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=['HS256'])
            
            if payload.get('type') != token_type:
                return None
                
            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None
    
    @staticmethod
    def refresh_access_token(refresh_token):
        """Refresh an access token using the refresh token"""
        payload = AuthManager.verify_token(refresh_token, 'refresh')
        if not payload:
            return None
        
        user_id = payload['user_id']
        
        # Check that the session exists and is valid
        session = UserSession.query.filter_by(
            user_id=user_id,
            refresh_token=refresh_token
        ).first()
        
        if not session or session.is_expired():
            return None
        
        # Generate new tokens
        new_tokens = AuthManager.generate_tokens(user_id)
        
        # Delete the old session
        db.session.delete(session)
        db.session.commit()
        
        return new_tokens
    
    @staticmethod
    def revoke_token(token):
        """Revoke a token by deleting the associated session"""
        payload = AuthManager.verify_token(token)
        if not payload:
            return False
        
        session = UserSession.query.filter_by(
            user_id=payload['user_id'],
            session_token=token
        ).first()
        
        if session:
            db.session.delete(session)
            db.session.commit()
            return True
        
        return False
    
    @staticmethod
    def revoke_all_user_tokens(user_id):
        """Revoke all tokens of a user"""
        UserSession.query.filter_by(user_id=user_id).delete()
        db.session.commit()

def token_required(f):
    """Decorator to protect routes with JWT authentication"""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        auth_header = request.headers.get('Authorization')
        
        if auth_header:
            try:
                token = auth_header.split(' ')[1]  # Bearer <token>
            except IndexError:
                return jsonify({'error': 'Invalid authorization header format'}), 401
        
        if not token:
            return jsonify({'error': 'Token is missing'}), 401
        
        payload = AuthManager.verify_token(token)
        if not payload:
            return jsonify({'error': 'Token is invalid or expired'}), 401
        
        # Check that the session exists
        session = UserSession.query.filter_by(
            user_id=payload['user_id'],
            session_token=token
        ).first()
        
        if not session or session.is_expired():
            return jsonify({'error': 'Session is invalid or expired'}), 401
        
        # Load the user
        current_user = User.query.get(payload['user_id'])
        if not current_user or not current_user.is_active:
            return jsonify({'error': 'User not found or inactive'}), 401
        
        g.current_user = current_user
        g.current_session = session
        
        return f(*args, **kwargs)
    
    return decorated

def role_required(*allowed_roles):
    """Decorator to check user roles"""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if not hasattr(g, 'current_user'):
                return jsonify({'error': 'Authentication required'}), 401
            
            if g.current_user.role not in allowed_roles:
                return jsonify({'error': 'Insufficient permissions'}), 403
            
            return f(*args, **kwargs)
        
        return decorated
    return decorator

def permission_required(permission):
    """Decorator to check user permissions"""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if not hasattr(g, 'current_user'):
                return jsonify({'error': 'Authentication required'}), 401
            
            if not g.current_user.has_permission(permission):
                return jsonify({'error': f'Permission "{permission}" required'}), 403
            
            return f(*args, **kwargs)
        
        return decorated
    return decorator

def organization_required(f):
    """Decorator to ensure the user belongs to an organization"""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not hasattr(g, 'current_user'):
            return jsonify({'error': 'Authentication required'}), 401
        
        if not g.current_user.organization_id:
            return jsonify({'error': 'User must belong to an organization'}), 403
        
        return f(*args, **kwargs)
    
    return decorated

