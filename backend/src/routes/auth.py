from flask import Blueprint, request, jsonify, g
from src.models import db
from src.models.user import User, UserSession
from src.models.organization import Organization
from src.utils.auth import AuthManager, token_required
from src.utils.validators import validate_json, validate_email, validate_password, validate_organization_name, sanitize_input

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/register', methods=['POST'])
@validate_json('email', 'password', 'first_name', 'last_name')
def register():
    """Inscription d'un nouvel utilisateur"""
    data = request.get_json()
    
    # Validation des données
    email = sanitize_input(data['email'].lower())
    if not validate_email(email):
        return jsonify({'error': 'Invalid email format'}), 400
    
    password = data['password']
    is_valid, message = validate_password(password)
    if not is_valid:
        return jsonify({'error': message}), 400
    
    first_name = sanitize_input(data['first_name'], 100)
    last_name = sanitize_input(data['last_name'], 100)
    
    # Vérifier si l'utilisateur existe déjà
    if User.query.filter_by(email=email).first():
        return jsonify({'error': 'User with this email already exists'}), 409
    
    # Créer l'utilisateur
    user = User(
        email=email,
        first_name=first_name,
        last_name=last_name,
        role='student'  # Rôle par défaut
    )
    user.set_password(password)
    
    # Gérer l'organisation si fournie
    organization_name = data.get('organization_name')
    if organization_name:
        organization_name = sanitize_input(organization_name, 255)
        is_valid, message = validate_organization_name(organization_name)
        if not is_valid:
            return jsonify({'error': message}), 400
        
        # Créer une nouvelle organisation
        organization = Organization(name=organization_name)
        db.session.add(organization)
        db.session.flush()  # Pour obtenir l'ID
        
        user.organization_id = organization.id
        user.role = 'admin'  # Premier utilisateur devient admin
    
    db.session.add(user)
    db.session.commit()
    
    # Générer les tokens
    tokens = AuthManager.generate_tokens(user.id)
    
    return jsonify({
        'message': 'User registered successfully',
        'user': user.to_dict(),
        'tokens': tokens
    }), 201

@auth_bp.route('/login', methods=['POST'])
@validate_json('email', 'password')
def login():
    """Connexion d'un utilisateur"""
    data = request.get_json()
    
    email = sanitize_input(data['email'].lower())
    password = data['password']
    
    # Trouver l'utilisateur
    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(password):
        return jsonify({'error': 'Invalid email or password'}), 401
    
    if not user.is_active:
        return jsonify({'error': 'Account is deactivated'}), 401
    
    # Mettre à jour la dernière connexion
    from datetime import datetime
    user.last_login = datetime.utcnow()
    db.session.commit()
    
    # Générer les tokens
    tokens = AuthManager.generate_tokens(user.id)
    
    return jsonify({
        'message': 'Login successful',
        'user': user.to_dict(),
        'tokens': tokens
    }), 200

@auth_bp.route('/refresh', methods=['POST'])
@validate_json('refresh_token')
def refresh_token():
    """Rafraîchissement du token d'accès"""
    data = request.get_json()
    refresh_token = data['refresh_token']
    
    new_tokens = AuthManager.refresh_access_token(refresh_token)
    if not new_tokens:
        return jsonify({'error': 'Invalid or expired refresh token'}), 401
    
    return jsonify({
        'message': 'Token refreshed successfully',
        'tokens': new_tokens
    }), 200

@auth_bp.route('/logout', methods=['POST'])
@token_required
def logout():
    """Déconnexion de l'utilisateur"""
    # Révoquer le token actuel
    auth_header = request.headers.get('Authorization')
    if auth_header:
        token = auth_header.split(' ')[1]
        AuthManager.revoke_token(token)
    
    return jsonify({'message': 'Logout successful'}), 200

@auth_bp.route('/logout-all', methods=['POST'])
@token_required
def logout_all():
    """Déconnexion de tous les appareils"""
    AuthManager.revoke_all_user_tokens(g.current_user.id)
    
    return jsonify({'message': 'Logged out from all devices'}), 200

@auth_bp.route('/me', methods=['GET'])
@token_required
def get_current_user():
    """Obtenir les informations de l'utilisateur actuel"""
    user_data = g.current_user.to_dict()
    
    # Ajouter les informations de l'organisation si applicable
    if g.current_user.organization:
        user_data['organization'] = g.current_user.organization.to_dict()
    
    return jsonify({
        'user': user_data
    }), 200

@auth_bp.route('/change-password', methods=['POST'])
@token_required
@validate_json('current_password', 'new_password')
def change_password():
    """Changer le mot de passe de l'utilisateur"""
    data = request.get_json()
    
    current_password = data['current_password']
    new_password = data['new_password']
    
    # Vérifier le mot de passe actuel
    if not g.current_user.check_password(current_password):
        return jsonify({'error': 'Current password is incorrect'}), 400
    
    # Valider le nouveau mot de passe
    is_valid, message = validate_password(new_password)
    if not is_valid:
        return jsonify({'error': message}), 400
    
    # Mettre à jour le mot de passe
    g.current_user.set_password(new_password)
    db.session.commit()
    
    # Révoquer tous les tokens existants pour forcer une nouvelle connexion
    AuthManager.revoke_all_user_tokens(g.current_user.id)
    
    return jsonify({'message': 'Password changed successfully'}), 200

@auth_bp.route('/verify-email', methods=['POST'])
@token_required
def verify_email():
    """Marquer l'email comme vérifié (simplifié pour la démo)"""
    g.current_user.email_verified = True
    db.session.commit()
    
    return jsonify({'message': 'Email verified successfully'}), 200

@auth_bp.route('/reset-password', methods=['POST'])
@validate_json('email')
def reset_password():
    """Demande de réinitialisation de mot de passe (simplifié pour la démo)"""
    data = request.get_json()
    email = sanitize_input(data['email'].lower())
    
    user = User.query.filter_by(email=email).first()
    if not user:
        # Ne pas révéler si l'email existe ou non
        return jsonify({'message': 'If the email exists, a reset link has been sent'}), 200
    
    # Dans une vraie application, on enverrait un email avec un token de réinitialisation
    # Pour la démo, on retourne juste un message de succès
    
    return jsonify({'message': 'If the email exists, a reset link has been sent'}), 200

