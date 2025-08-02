import re
from functools import wraps
from flask import request, jsonify

def validate_email(email):
    """Valide le format d'une adresse email"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def validate_password(password):
    """Valide la force d'un mot de passe"""
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
    
    return True, "Password is valid"

def validate_json(*required_fields):
    """Décorateur pour valider les données JSON requises"""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if not request.is_json:
                return jsonify({'error': 'Content-Type must be application/json'}), 400
            
            data = request.get_json()
            if not data:
                return jsonify({'error': 'No JSON data provided'}), 400
            
            missing_fields = []
            for field in required_fields:
                if field not in data or data[field] is None or data[field] == '':
                    missing_fields.append(field)
            
            if missing_fields:
                return jsonify({
                    'error': 'Missing required fields',
                    'missing_fields': missing_fields
                }), 400
            
            return f(*args, **kwargs)
        
        return decorated
    return decorator

def validate_organization_name(name):
    """Valide le nom d'une organisation"""
    if not name or len(name.strip()) < 2:
        return False, "Organization name must be at least 2 characters long"
    
    if len(name) > 255:
        return False, "Organization name must be less than 255 characters"
    
    return True, "Organization name is valid"

def validate_user_role(role):
    """Valide le rôle d'un utilisateur"""
    valid_roles = ['admin', 'teacher', 'student', 'guest']
    if role not in valid_roles:
        return False, f"Role must be one of: {', '.join(valid_roles)}"
    
    return True, "Role is valid"

def sanitize_input(text, max_length=None):
    """Nettoie et sanitise une entrée de texte"""
    if not text:
        return ""
    
    # Supprimer les espaces en début et fin
    text = text.strip()
    
    # Limiter la longueur si spécifiée
    if max_length and len(text) > max_length:
        text = text[:max_length]
    
    return text

def validate_pagination_params(page=None, per_page=None):
    """Valide les paramètres de pagination"""
    try:
        page = int(page) if page else 1
        per_page = int(per_page) if per_page else 20
        
        if page < 1:
            page = 1
        
        if per_page < 1:
            per_page = 20
        elif per_page > 100:  # Limiter à 100 éléments par page
            per_page = 100
        
        return page, per_page
    except (ValueError, TypeError):
        return 1, 20

