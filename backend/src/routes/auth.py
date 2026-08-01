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
    """Register a new user"""
    data = request.get_json()
    
    # Validate the data
    email = sanitize_input(data['email'].lower())
    if not validate_email(email):
        return jsonify({'error': 'Invalid email format'}), 400
    
    password = data['password']
    is_valid, message = validate_password(password)
    if not is_valid:
        return jsonify({'error': message}), 400
    
    first_name = sanitize_input(data['first_name'], 100)
    last_name = sanitize_input(data['last_name'], 100)
    
    # Check if the user already exists
    if User.query.filter_by(email=email).first():
        return jsonify({'error': 'User with this email already exists'}), 409
    
    # Create the user
    user = User(
        email=email,
        first_name=first_name,
        last_name=last_name,
        role='student'  # Default role
    )
    user.set_password(password)
    
    # Handle the organization if provided
    organization_name = data.get('organization_name')
    if organization_name:
        organization_name = sanitize_input(organization_name, 255)
        is_valid, message = validate_organization_name(organization_name)
        if not is_valid:
            return jsonify({'error': message}), 400
        
        # Create a new organization
        organization = Organization(name=organization_name)
        db.session.add(organization)
        db.session.flush()  # To get the ID
        
        user.organization_id = organization.id
        user.role = 'admin'  # First user becomes admin
    
    db.session.add(user)
    db.session.commit()
    
    # Generate the tokens
    tokens = AuthManager.generate_tokens(user.id)
    
    return jsonify({
        'message': 'User registered successfully',
        'user': user.to_dict(),
        'tokens': tokens
    }), 201

@auth_bp.route('/login', methods=['POST'])
@validate_json('email', 'password')
def login():
    """Log in a user"""
    data = request.get_json()
    
    email = sanitize_input(data['email'].lower())
    password = data['password']
    
    # Find the user
    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(password):
        return jsonify({'error': 'Invalid email or password'}), 401
    
    if not user.is_active:
        return jsonify({'error': 'Account is deactivated'}), 401
    
    # Update the last login
    from datetime import datetime
    user.last_login = datetime.utcnow()
    db.session.commit()
    
    # Generate the tokens
    tokens = AuthManager.generate_tokens(user.id)
    
    return jsonify({
        'message': 'Login successful',
        'user': user.to_dict(),
        'tokens': tokens
    }), 200

@auth_bp.route('/refresh', methods=['POST'])
@validate_json('refresh_token')
def refresh_token():
    """Refresh the access token"""
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
    """Log out the user"""
    # Revoke the current token
    auth_header = request.headers.get('Authorization')
    if auth_header:
        token = auth_header.split(' ')[1]
        AuthManager.revoke_token(token)
    
    return jsonify({'message': 'Logout successful'}), 200

@auth_bp.route('/logout-all', methods=['POST'])
@token_required
def logout_all():
    """Log out from all devices"""
    AuthManager.revoke_all_user_tokens(g.current_user.id)
    
    return jsonify({'message': 'Logged out from all devices'}), 200

@auth_bp.route('/me', methods=['GET'])
@token_required
def get_current_user():
    """Get the current user's information"""
    user_data = g.current_user.to_dict()
    
    # Add the organization information if applicable
    if g.current_user.organization:
        user_data['organization'] = g.current_user.organization.to_dict()
    
    return jsonify({
        'user': user_data
    }), 200

@auth_bp.route('/change-password', methods=['POST'])
@token_required
@validate_json('current_password', 'new_password')
def change_password():
    """Change the user's password"""
    data = request.get_json()
    
    current_password = data['current_password']
    new_password = data['new_password']
    
    # Check the current password
    if not g.current_user.check_password(current_password):
        return jsonify({'error': 'Current password is incorrect'}), 400
    
    # Validate the new password
    is_valid, message = validate_password(new_password)
    if not is_valid:
        return jsonify({'error': message}), 400
    
    # Update the password
    g.current_user.set_password(new_password)
    db.session.commit()
    
    # Revoke all existing tokens to force a new login
    AuthManager.revoke_all_user_tokens(g.current_user.id)
    
    return jsonify({'message': 'Password changed successfully'}), 200

@auth_bp.route('/verify-email', methods=['POST'])
@token_required
def verify_email():
    """Mark the email as verified (simplified for the demo)"""
    g.current_user.email_verified = True
    db.session.commit()
    
    return jsonify({'message': 'Email verified successfully'}), 200

@auth_bp.route('/reset-password', methods=['POST'])
@validate_json('email')
def reset_password():
    """Password reset request (simplified for the demo)"""
    data = request.get_json()
    email = sanitize_input(data['email'].lower())
    
    user = User.query.filter_by(email=email).first()
    if not user:
        # Do not reveal whether the email exists or not
        return jsonify({'message': 'If the email exists, a reset link has been sent'}), 200
    
    # In a real application, an email with a reset token would be sent
    # For the demo, we just return a success message
    
    return jsonify({'message': 'If the email exists, a reset link has been sent'}), 200

