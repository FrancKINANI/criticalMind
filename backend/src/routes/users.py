from flask import Blueprint, request, jsonify, g
from src.models import db
from src.models.user import User
from src.models.organization import Organization
from src.utils.auth import token_required, role_required, permission_required, organization_required
from src.utils.validators import validate_json, validate_email, validate_user_role, validate_pagination_params, sanitize_input

users_bp = Blueprint('users', __name__)

@users_bp.route('/profile', methods=['GET'])
@token_required
def get_profile():
    """Obtenir le profil de l'utilisateur actuel"""
    user_data = g.current_user.to_dict()
    
    # Ajouter les statistiques utilisateur
    from src.models.gamification import UserPoints, UserBadge
    from src.models.learning import UserProgress
    
    total_points = db.session.query(db.func.sum(UserPoints.points)).filter_by(user_id=g.current_user.id).scalar() or 0
    badges_count = UserBadge.query.filter_by(user_id=g.current_user.id).count()
    modules_completed = UserProgress.query.filter_by(user_id=g.current_user.id).filter(UserProgress.completion_percentage >= 100).count()
    
    user_data['stats'] = {
        'total_points': int(total_points),
        'badges_count': badges_count,
        'modules_completed': modules_completed
    }
    
    return jsonify({'user': user_data}), 200

@users_bp.route('/profile', methods=['PUT'])
@token_required
@validate_json('first_name', 'last_name')
def update_profile():
    """Mettre à jour le profil de l'utilisateur"""
    data = request.get_json()
    
    g.current_user.first_name = sanitize_input(data['first_name'], 100)
    g.current_user.last_name = sanitize_input(data['last_name'], 100)
    
    # Mettre à jour l'email si fourni et différent
    if 'email' in data and data['email'] != g.current_user.email:
        new_email = sanitize_input(data['email'].lower())
        if not validate_email(new_email):
            return jsonify({'error': 'Invalid email format'}), 400
        
        # Vérifier que l'email n'est pas déjà utilisé
        if User.query.filter_by(email=new_email).first():
            return jsonify({'error': 'Email already in use'}), 409
        
        g.current_user.email = new_email
        g.current_user.email_verified = False  # Nécessite une nouvelle vérification
    
    db.session.commit()
    
    return jsonify({
        'message': 'Profile updated successfully',
        'user': g.current_user.to_dict()
    }), 200

@users_bp.route('/', methods=['GET'])
@token_required
@organization_required
@permission_required('manage_users')
def list_users():
    """Lister les utilisateurs de l'organisation"""
    page = request.args.get('page', 1)
    per_page = request.args.get('per_page', 20)
    search = request.args.get('search', '')
    role_filter = request.args.get('role', '')
    
    page, per_page = validate_pagination_params(page, per_page)
    
    # Construire la requête
    query = User.query.filter_by(organization_id=g.current_user.organization_id)
    
    # Filtrer par recherche
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            db.or_(
                User.first_name.ilike(search_term),
                User.last_name.ilike(search_term),
                User.email.ilike(search_term)
            )
        )
    
    # Filtrer par rôle
    if role_filter:
        query = query.filter_by(role=role_filter)
    
    # Paginer les résultats
    pagination = query.paginate(
        page=page,
        per_page=per_page,
        error_out=False
    )
    
    users = [user.to_dict() for user in pagination.items]
    
    return jsonify({
        'users': users,
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total': pagination.total,
            'pages': pagination.pages,
            'has_next': pagination.has_next,
            'has_prev': pagination.has_prev
        }
    }), 200

@users_bp.route('/<user_id>', methods=['GET'])
@token_required
@organization_required
@permission_required('manage_users')
def get_user(user_id):
    """Obtenir les détails d'un utilisateur"""
    user = User.query.filter_by(
        id=user_id,
        organization_id=g.current_user.organization_id
    ).first()
    
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    # Ajouter les statistiques détaillées
    from src.models.gamification import UserPoints, UserBadge
    from src.models.learning import UserProgress
    
    user_data = user.to_dict()
    
    # Points par source
    points_by_source = db.session.query(
        UserPoints.source,
        db.func.sum(UserPoints.points)
    ).filter_by(user_id=user.id).group_by(UserPoints.source).all()
    
    user_data['detailed_stats'] = {
        'points_by_source': {source: int(points) for source, points in points_by_source},
        'recent_badges': [
            badge.to_dict() for badge in UserBadge.query.filter_by(user_id=user.id)
            .order_by(UserBadge.earned_at.desc()).limit(5).all()
        ],
        'progress_summary': [
            progress.to_dict() for progress in UserProgress.query.filter_by(user_id=user.id)
            .order_by(UserProgress.last_accessed.desc()).limit(10).all()
        ]
    }
    
    return jsonify({'user': user_data}), 200

@users_bp.route('/<user_id>', methods=['PUT'])
@token_required
@organization_required
@permission_required('manage_users')
@validate_json('first_name', 'last_name', 'role')
def update_user(user_id):
    """Mettre à jour un utilisateur"""
    data = request.get_json()
    
    user = User.query.filter_by(
        id=user_id,
        organization_id=g.current_user.organization_id
    ).first()
    
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    # Empêcher la modification de son propre rôle
    if user.id == g.current_user.id and 'role' in data:
        return jsonify({'error': 'Cannot modify your own role'}), 403
    
    # Valider le rôle
    if 'role' in data:
        is_valid, message = validate_user_role(data['role'])
        if not is_valid:
            return jsonify({'error': message}), 400
        user.role = data['role']
    
    # Mettre à jour les autres champs
    user.first_name = sanitize_input(data['first_name'], 100)
    user.last_name = sanitize_input(data['last_name'], 100)
    
    if 'is_active' in data and isinstance(data['is_active'], bool):
        user.is_active = data['is_active']
    
    db.session.commit()
    
    return jsonify({
        'message': 'User updated successfully',
        'user': user.to_dict()
    }), 200

@users_bp.route('/<user_id>', methods=['DELETE'])
@token_required
@organization_required
@permission_required('manage_users')
def delete_user(user_id):
    """Supprimer un utilisateur (désactivation)"""
    user = User.query.filter_by(
        id=user_id,
        organization_id=g.current_user.organization_id
    ).first()
    
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    # Empêcher la suppression de son propre compte
    if user.id == g.current_user.id:
        return jsonify({'error': 'Cannot delete your own account'}), 403
    
    # Désactiver l'utilisateur au lieu de le supprimer
    user.is_active = False
    db.session.commit()
    
    return jsonify({'message': 'User deactivated successfully'}), 200

@users_bp.route('/invite', methods=['POST'])
@token_required
@organization_required
@permission_required('manage_users')
@validate_json('email', 'role')
def invite_user():
    """Inviter un nouvel utilisateur à l'organisation"""
    data = request.get_json()
    
    email = sanitize_input(data['email'].lower())
    if not validate_email(email):
        return jsonify({'error': 'Invalid email format'}), 400
    
    role = data['role']
    is_valid, message = validate_user_role(role)
    if not is_valid:
        return jsonify({'error': message}), 400
    
    # Vérifier si l'utilisateur existe déjà
    existing_user = User.query.filter_by(email=email).first()
    if existing_user:
        if existing_user.organization_id == g.current_user.organization_id:
            return jsonify({'error': 'User is already a member of this organization'}), 409
        else:
            return jsonify({'error': 'User already exists in another organization'}), 409
    
    # Dans une vraie application, on enverrait un email d'invitation
    # Pour la démo, on crée directement l'utilisateur avec un mot de passe temporaire
    
    user = User(
        email=email,
        first_name=data.get('first_name', ''),
        last_name=data.get('last_name', ''),
        role=role,
        organization_id=g.current_user.organization_id,
        is_active=True,
        email_verified=False
    )
    
    # Mot de passe temporaire (dans une vraie app, ce serait généré et envoyé par email)
    user.set_password('TempPassword123!')
    
    db.session.add(user)
    db.session.commit()
    
    return jsonify({
        'message': 'User invited successfully',
        'user': user.to_dict(),
        'temporary_password': 'TempPassword123!'  # À supprimer en production
    }), 201

@users_bp.route('/stats', methods=['GET'])
@token_required
@organization_required
def get_user_stats():
    """Obtenir les statistiques de l'utilisateur actuel"""
    from src.models.gamification import UserPoints, UserBadge
    from src.models.learning import UserProgress, UserResponse
    from src.models.forum import ForumTopic, ForumReply
    
    user_id = g.current_user.id
    
    # Points totaux
    total_points = db.session.query(db.func.sum(UserPoints.points)).filter_by(user_id=user_id).scalar() or 0
    
    # Badges
    badges_count = UserBadge.query.filter_by(user_id=user_id).count()
    recent_badges = UserBadge.query.filter_by(user_id=user_id).order_by(UserBadge.earned_at.desc()).limit(3).all()
    
    # Progression d'apprentissage
    modules_started = UserProgress.query.filter_by(user_id=user_id).count()
    modules_completed = UserProgress.query.filter_by(user_id=user_id).filter(UserProgress.completion_percentage >= 100).count()
    avg_score = db.session.query(db.func.avg(UserProgress.score)).filter_by(user_id=user_id).scalar() or 0
    
    # Activité forum
    topics_created = ForumTopic.query.filter_by(user_id=user_id).count()
    replies_posted = ForumReply.query.filter_by(user_id=user_id).count()
    
    # Exercices
    exercises_completed = UserResponse.query.filter_by(user_id=user_id).count()
    correct_answers = UserResponse.query.filter_by(user_id=user_id, is_correct=True).count()
    accuracy = (correct_answers / exercises_completed * 100) if exercises_completed > 0 else 0
    
    return jsonify({
        'stats': {
            'points': {
                'total': int(total_points),
                'recent_badges': [badge.to_dict() for badge in recent_badges]
            },
            'learning': {
                'modules_started': modules_started,
                'modules_completed': modules_completed,
                'completion_rate': (modules_completed / modules_started * 100) if modules_started > 0 else 0,
                'average_score': round(float(avg_score), 2)
            },
            'engagement': {
                'topics_created': topics_created,
                'replies_posted': replies_posted,
                'exercises_completed': exercises_completed,
                'accuracy_percentage': round(accuracy, 2)
            },
            'badges': {
                'total': badges_count,
                'recent': [badge.to_dict() for badge in recent_badges]
            }
        }
    }), 200

