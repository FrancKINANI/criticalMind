from flask import Blueprint, request, jsonify, g
from src.models import db
from src.models.user import User
from src.models.organization import Organization
from src.models.subscription import Subscription, SubscriptionPlan
from src.models.learning import LearningModule, Exercise, UserProgress
from src.models.forum import ForumCategory, ForumTopic, ForumReply
from src.models.gamification import Badge, UserBadge, UserPoints
from src.models.analytics import AnalyticsEvent, AnalyticsMetric
from src.utils.auth import token_required, role_required, organization_required
from src.utils.validators import validate_json, validate_pagination_params, sanitize_input
from datetime import datetime, timedelta
from sqlalchemy import func, desc

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/dashboard', methods=['GET'])
@token_required
@organization_required
@role_required('admin')
def get_admin_dashboard():
    """Obtenir les données du tableau de bord administrateur"""
    org_id = g.current_user.organization_id
    
    # Statistiques générales
    total_users = User.query.filter_by(organization_id=org_id, is_active=True).count()
    total_modules = LearningModule.query.filter_by(organization_id=org_id, is_active=True).count()
    total_topics = ForumTopic.query.join(ForumCategory).filter(ForumCategory.organization_id == org_id).count()
    
    # Utilisateurs actifs (connectés dans les 30 derniers jours)
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    active_users = User.query.filter(
        User.organization_id == org_id,
        User.is_active == True,
        User.last_login >= thirty_days_ago
    ).count()
    
    # Progression moyenne
    avg_progress = db.session.query(func.avg(UserProgress.completion_percentage)).join(User).filter(
        User.organization_id == org_id
    ).scalar() or 0
    
    # Modules les plus populaires
    popular_modules = db.session.query(
        LearningModule.title,
        func.count(UserProgress.id).label('enrollments')
    ).join(UserProgress).join(User).filter(
        User.organization_id == org_id,
        LearningModule.is_active == True
    ).group_by(LearningModule.id).order_by(desc('enrollments')).limit(5).all()
    
    # Activité récente (derniers 7 jours)
    seven_days_ago = datetime.utcnow() - timedelta(days=7)
    recent_activity = {
        'new_users': User.query.filter(
            User.organization_id == org_id,
            User.created_at >= seven_days_ago
        ).count(),
        'completed_modules': UserProgress.query.join(User).filter(
            User.organization_id == org_id,
            UserProgress.completed_at >= seven_days_ago
        ).count(),
        'forum_posts': ForumTopic.query.join(ForumCategory).filter(
            ForumCategory.organization_id == org_id,
            ForumTopic.created_at >= seven_days_ago
        ).count() + ForumReply.query.join(ForumTopic).join(ForumCategory).filter(
            ForumCategory.organization_id == org_id,
            ForumReply.created_at >= seven_days_ago
        ).count()
    }
    
    return jsonify({
        'stats': {
            'total_users': total_users,
            'active_users': active_users,
            'total_modules': total_modules,
            'total_topics': total_topics,
            'avg_progress': round(float(avg_progress), 2),
            'user_activity_rate': round((active_users / total_users * 100) if total_users > 0 else 0, 2)
        },
        'popular_modules': [
            {'title': title, 'enrollments': enrollments} 
            for title, enrollments in popular_modules
        ],
        'recent_activity': recent_activity
    }), 200

@admin_bp.route('/users', methods=['GET'])
@token_required
@organization_required
@role_required('admin')
def get_all_users():
    """Obtenir tous les utilisateurs avec des détails administratifs"""
    page = request.args.get('page', 1)
    per_page = request.args.get('per_page', 20)
    search = request.args.get('search', '')
    role_filter = request.args.get('role', '')
    status_filter = request.args.get('status', '')  # 'active', 'inactive'
    
    page, per_page = validate_pagination_params(page, per_page)
    
    query = User.query.filter_by(organization_id=g.current_user.organization_id)
    
    # Filtres
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            db.or_(
                User.first_name.ilike(search_term),
                User.last_name.ilike(search_term),
                User.email.ilike(search_term)
            )
        )
    
    if role_filter:
        query = query.filter_by(role=role_filter)
    
    if status_filter == 'active':
        query = query.filter_by(is_active=True)
    elif status_filter == 'inactive':
        query = query.filter_by(is_active=False)
    
    pagination = query.order_by(User.created_at.desc()).paginate(
        page=page,
        per_page=per_page,
        error_out=False
    )
    
    users = []
    for user in pagination.items:
        user_data = user.to_dict()
        
        # Ajouter des statistiques détaillées
        user_data['stats'] = {
            'modules_completed': UserProgress.query.filter_by(
                user_id=user.id
            ).filter(UserProgress.completion_percentage >= 100).count(),
            
            'total_points': db.session.query(func.sum(UserPoints.points)).filter_by(
                user_id=user.id
            ).scalar() or 0,
            
            'badges_count': UserBadge.query.filter_by(user_id=user.id).count(),
            
            'forum_activity': ForumTopic.query.filter_by(user_id=user.id).count() + 
                            ForumReply.query.filter_by(user_id=user.id).count()
        }
        
        users.append(user_data)
    
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

@admin_bp.route('/users/<user_id>/impersonate', methods=['POST'])
@token_required
@organization_required
@role_required('admin')
def impersonate_user(user_id):
    """Se connecter en tant qu'autre utilisateur (pour le support)"""
    target_user = User.query.filter_by(
        id=user_id,
        organization_id=g.current_user.organization_id
    ).first()
    
    if not target_user:
        return jsonify({'error': 'User not found'}), 404
    
    # Générer des tokens pour l'utilisateur cible
    from src.utils.auth import AuthManager
    tokens = AuthManager.generate_tokens(target_user.id)
    
    # Enregistrer l'action d'impersonation
    AnalyticsEvent.track_event(
        event_type='admin_impersonation',
        organization_id=g.current_user.organization_id,
        user_id=g.current_user.id,
        event_data={
            'target_user_id': user_id,
            'target_user_email': target_user.email
        }
    )
    
    return jsonify({
        'message': 'Impersonation successful',
        'user': target_user.to_dict(),
        'tokens': tokens
    }), 200

@admin_bp.route('/modules', methods=['GET'])
@token_required
@organization_required
@role_required('admin')
def get_all_modules():
    """Obtenir tous les modules avec des statistiques"""
    page = request.args.get('page', 1)
    per_page = request.args.get('per_page', 20)
    
    page, per_page = validate_pagination_params(page, per_page)
    
    pagination = LearningModule.query.filter_by(
        organization_id=g.current_user.organization_id
    ).order_by(LearningModule.created_at.desc()).paginate(
        page=page,
        per_page=per_page,
        error_out=False
    )
    
    modules = []
    for module in pagination.items:
        module_data = module.to_dict()
        
        # Ajouter des statistiques
        module_data['stats'] = {
            'total_enrollments': UserProgress.query.filter_by(module_id=module.id).count(),
            'completions': UserProgress.query.filter_by(module_id=module.id).filter(
                UserProgress.completion_percentage >= 100
            ).count(),
            'avg_score': db.session.query(func.avg(UserProgress.score)).filter_by(
                module_id=module.id
            ).scalar() or 0,
            'exercises_count': Exercise.query.filter_by(module_id=module.id).count()
        }
        
        # Calculer le taux de completion
        if module_data['stats']['total_enrollments'] > 0:
            module_data['stats']['completion_rate'] = round(
                module_data['stats']['completions'] / module_data['stats']['total_enrollments'] * 100, 2
            )
        else:
            module_data['stats']['completion_rate'] = 0
        
        modules.append(module_data)
    
    return jsonify({
        'modules': modules,
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total': pagination.total,
            'pages': pagination.pages,
            'has_next': pagination.has_next,
            'has_prev': pagination.has_prev
        }
    }), 200

@admin_bp.route('/modules/<module_id>/toggle-status', methods=['POST'])
@token_required
@organization_required
@role_required('admin')
def toggle_module_status(module_id):
    """Activer/désactiver un module"""
    module = LearningModule.query.filter_by(
        id=module_id,
        organization_id=g.current_user.organization_id
    ).first()
    
    if not module:
        return jsonify({'error': 'Module not found'}), 404
    
    module.is_active = not module.is_active
    db.session.commit()
    
    return jsonify({
        'message': f'Module {"activated" if module.is_active else "deactivated"} successfully',
        'is_active': module.is_active
    }), 200

@admin_bp.route('/forum/moderation', methods=['GET'])
@token_required
@organization_required
@role_required('admin')
def get_forum_moderation():
    """Obtenir les éléments nécessitant une modération"""
    # Sujets récents
    recent_topics = ForumTopic.query.join(ForumCategory).filter(
        ForumCategory.organization_id == g.current_user.organization_id
    ).order_by(ForumTopic.created_at.desc()).limit(10).all()
    
    # Réponses récentes
    recent_replies = ForumReply.query.join(ForumTopic).join(ForumCategory).filter(
        ForumCategory.organization_id == g.current_user.organization_id
    ).order_by(ForumReply.created_at.desc()).limit(10).all()
    
    # Statistiques du forum
    forum_stats = {
        'total_topics': ForumTopic.query.join(ForumCategory).filter(
            ForumCategory.organization_id == g.current_user.organization_id
        ).count(),
        'total_replies': ForumReply.query.join(ForumTopic).join(ForumCategory).filter(
            ForumCategory.organization_id == g.current_user.organization_id
        ).count(),
        'active_categories': ForumCategory.query.filter_by(
            organization_id=g.current_user.organization_id,
            is_active=True
        ).count()
    }
    
    # Préparer les données
    topics_data = []
    for topic in recent_topics:
        topic_data = topic.to_dict()
        author = User.query.get(topic.user_id)
        if author:
            topic_data['author'] = author.to_dict()
        topics_data.append(topic_data)
    
    replies_data = []
    for reply in recent_replies:
        reply_data = reply.to_dict()
        author = User.query.get(reply.user_id)
        if author:
            reply_data['author'] = author.to_dict()
        reply_data['topic'] = reply.topic.to_dict()
        replies_data.append(reply_data)
    
    return jsonify({
        'recent_topics': topics_data,
        'recent_replies': replies_data,
        'forum_stats': forum_stats
    }), 200

@admin_bp.route('/analytics', methods=['GET'])
@token_required
@organization_required
@role_required('admin')
def get_analytics():
    """Obtenir les analyses détaillées"""
    period = request.args.get('period', '30')  # jours
    try:
        period_days = int(period)
    except ValueError:
        period_days = 30
    
    start_date = datetime.utcnow() - timedelta(days=period_days)
    org_id = g.current_user.organization_id
    
    # Activité des utilisateurs
    user_activity = db.session.query(
        func.date(AnalyticsEvent.created_at).label('date'),
        func.count(func.distinct(AnalyticsEvent.user_id)).label('active_users')
    ).filter(
        AnalyticsEvent.organization_id == org_id,
        AnalyticsEvent.created_at >= start_date
    ).group_by(func.date(AnalyticsEvent.created_at)).all()
    
    # Modules complétés par jour
    module_completions = db.session.query(
        func.date(UserProgress.completed_at).label('date'),
        func.count(UserProgress.id).label('completions')
    ).join(User).filter(
        User.organization_id == org_id,
        UserProgress.completed_at >= start_date,
        UserProgress.completed_at.isnot(None)
    ).group_by(func.date(UserProgress.completed_at)).all()
    
    # Top utilisateurs par points
    top_users = db.session.query(
        User.first_name,
        User.last_name,
        User.email,
        func.sum(UserPoints.points).label('total_points')
    ).join(UserPoints).filter(
        User.organization_id == org_id
    ).group_by(User.id).order_by(desc('total_points')).limit(10).all()
    
    # Modules les plus populaires
    popular_modules = db.session.query(
        LearningModule.title,
        func.count(UserProgress.id).label('enrollments'),
        func.avg(UserProgress.completion_percentage).label('avg_progress')
    ).join(UserProgress).join(User).filter(
        User.organization_id == org_id,
        LearningModule.is_active == True
    ).group_by(LearningModule.id).order_by(desc('enrollments')).limit(10).all()
    
    return jsonify({
        'period_days': period_days,
        'user_activity': [
            {'date': date.isoformat(), 'active_users': active_users}
            for date, active_users in user_activity
        ],
        'module_completions': [
            {'date': date.isoformat(), 'completions': completions}
            for date, completions in module_completions
        ],
        'top_users': [
            {
                'name': f"{first_name} {last_name}",
                'email': email,
                'total_points': int(total_points)
            }
            for first_name, last_name, email, total_points in top_users
        ],
        'popular_modules': [
            {
                'title': title,
                'enrollments': enrollments,
                'avg_progress': round(float(avg_progress), 2)
            }
            for title, enrollments, avg_progress in popular_modules
        ]
    }), 200

@admin_bp.route('/system/health', methods=['GET'])
@token_required
@organization_required
@role_required('admin')
def get_system_health():
    """Obtenir l'état de santé du système"""
    # Vérifications de base
    db_status = 'healthy'
    try:
        db.session.execute('SELECT 1')
    except Exception:
        db_status = 'error'
    
    # Statistiques de la base de données
    table_counts = {
        'users': User.query.filter_by(organization_id=g.current_user.organization_id).count(),
        'modules': LearningModule.query.filter_by(organization_id=g.current_user.organization_id).count(),
        'exercises': Exercise.query.join(LearningModule).filter(
            LearningModule.organization_id == g.current_user.organization_id
        ).count(),
        'forum_topics': ForumTopic.query.join(ForumCategory).filter(
            ForumCategory.organization_id == g.current_user.organization_id
        ).count(),
        'user_progress': UserProgress.query.join(User).filter(
            User.organization_id == g.current_user.organization_id
        ).count()
    }
    
    # Vérifier l'abonnement
    subscription = Subscription.query.filter_by(
        organization_id=g.current_user.organization_id
    ).order_by(Subscription.created_at.desc()).first()
    
    subscription_status = {
        'has_subscription': subscription is not None,
        'status': subscription.status if subscription else 'free',
        'plan': subscription.plan.name if subscription and subscription.plan else 'free',
        'expires_at': subscription.current_period_end.isoformat() if subscription and subscription.current_period_end else None
    }
    
    return jsonify({
        'system_health': {
            'database': db_status,
            'timestamp': datetime.utcnow().isoformat()
        },
        'table_counts': table_counts,
        'subscription_status': subscription_status
    }), 200

@admin_bp.route('/export/users', methods=['GET'])
@token_required
@organization_required
@role_required('admin')
def export_users():
    """Exporter les données des utilisateurs"""
    users = User.query.filter_by(
        organization_id=g.current_user.organization_id
    ).all()
    
    export_data = []
    for user in users:
        # Calculer les statistiques
        modules_completed = UserProgress.query.filter_by(
            user_id=user.id
        ).filter(UserProgress.completion_percentage >= 100).count()
        
        total_points = db.session.query(func.sum(UserPoints.points)).filter_by(
            user_id=user.id
        ).scalar() or 0
        
        export_data.append({
            'id': user.id,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'role': user.role,
            'is_active': user.is_active,
            'created_at': user.created_at.isoformat() if user.created_at else None,
            'last_login': user.last_login.isoformat() if user.last_login else None,
            'modules_completed': modules_completed,
            'total_points': int(total_points)
        })
    
    return jsonify({
        'users': export_data,
        'exported_at': datetime.utcnow().isoformat(),
        'total_count': len(export_data)
    }), 200

@admin_bp.route('/settings', methods=['GET'])
@token_required
@organization_required
@role_required('admin')
def get_organization_settings():
    """Obtenir les paramètres de l'organisation"""
    organization = g.current_user.organization
    
    settings = {
        'organization': organization.to_dict(),
        'features': {
            'forum_enabled': True,
            'gamification_enabled': True,
            'ai_features_enabled': True,
            'analytics_enabled': True
        },
        'limits': {
            'max_users': 50 if organization.subscription_plan != 'free' else 5,
            'max_modules': 100 if organization.subscription_plan != 'free' else 3,
            'storage_limit_mb': 1000 if organization.subscription_plan != 'free' else 100
        }
    }
    
    return jsonify(settings), 200

@admin_bp.route('/settings', methods=['PUT'])
@token_required
@organization_required
@role_required('admin')
@validate_json('name')
def update_organization_settings():
    """Mettre à jour les paramètres de l'organisation"""
    data = request.get_json()
    organization = g.current_user.organization
    
    organization.name = sanitize_input(data['name'], 255)
    
    if 'domain' in data:
        organization.domain = sanitize_input(data.get('domain', ''), 255)
    
    db.session.commit()
    
    return jsonify({
        'message': 'Settings updated successfully',
        'organization': organization.to_dict()
    }), 200

