import jwt
import uuid
from datetime import datetime, timedelta
from functools import wraps
from flask import request, jsonify, current_app, g
from src.models import db
from src.models.user import User, UserSession

class AuthManager:
    """Gestionnaire d'authentification pour CriticalMind SaaS"""
    
    @staticmethod
    def generate_tokens(user_id):
        """Génère les tokens d'accès et de rafraîchissement pour un utilisateur"""
        now = datetime.utcnow()
        
        # Token d'accès (15 minutes)
        access_payload = {
            'user_id': user_id,
            'type': 'access',
            'iat': now,
            'exp': now + timedelta(minutes=15),
            'jti': str(uuid.uuid4())
        }
        access_token = jwt.encode(access_payload, current_app.config['SECRET_KEY'], algorithm='HS256')
        
        # Token de rafraîchissement (30 jours)
        refresh_payload = {
            'user_id': user_id,
            'type': 'refresh',
            'iat': now,
            'exp': now + timedelta(days=30),
            'jti': str(uuid.uuid4())
        }
        refresh_token = jwt.encode(refresh_payload, current_app.config['SECRET_KEY'], algorithm='HS256')
        
        # Créer une session utilisateur
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
            'expires_in': 900,  # 15 minutes en secondes
            'token_type': 'Bearer'
        }
    
    @staticmethod
    def verify_token(token, token_type='access'):
        """Vérifie et décode un token JWT"""
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
        """Rafraîchit un token d'accès en utilisant le token de rafraîchissement"""
        payload = AuthManager.verify_token(refresh_token, 'refresh')
        if not payload:
            return None
        
        user_id = payload['user_id']
        
        # Vérifier que la session existe et est valide
        session = UserSession.query.filter_by(
            user_id=user_id,
            refresh_token=refresh_token
        ).first()
        
        if not session or session.is_expired():
            return None
        
        # Générer de nouveaux tokens
        new_tokens = AuthManager.generate_tokens(user_id)
        
        # Supprimer l'ancienne session
        db.session.delete(session)
        db.session.commit()
        
        return new_tokens
    
    @staticmethod
    def revoke_token(token):
        """Révoque un token en supprimant la session associée"""
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
        """Révoque tous les tokens d'un utilisateur"""
        UserSession.query.filter_by(user_id=user_id).delete()
        db.session.commit()

def token_required(f):
    """Décorateur pour protéger les routes avec authentification JWT"""
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
        
        # Vérifier que la session existe
        session = UserSession.query.filter_by(
            user_id=payload['user_id'],
            session_token=token
        ).first()
        
        if not session or session.is_expired():
            return jsonify({'error': 'Session is invalid or expired'}), 401
        
        # Charger l'utilisateur
        current_user = User.query.get(payload['user_id'])
        if not current_user or not current_user.is_active:
            return jsonify({'error': 'User not found or inactive'}), 401
        
        g.current_user = current_user
        g.current_session = session
        
        return f(*args, **kwargs)
    
    return decorated

def role_required(*allowed_roles):
    """Décorateur pour vérifier les rôles utilisateur"""
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
    """Décorateur pour vérifier les permissions utilisateur"""
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
    """Décorateur pour s'assurer que l'utilisateur appartient à une organisation"""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not hasattr(g, 'current_user'):
            return jsonify({'error': 'Authentication required'}), 401
        
        if not g.current_user.organization_id:
            return jsonify({'error': 'User must belong to an organization'}), 403
        
        return f(*args, **kwargs)
    
    return decorated

