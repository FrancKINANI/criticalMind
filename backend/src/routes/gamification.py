from flask import Blueprint, request, jsonify, g
from src.models import db
from src.models.gamification import Badge, UserBadge, UserPoints, Leaderboard
from src.utils.auth import token_required, role_required, organization_required
from src.utils.validators import validate_json, validate_pagination_params, sanitize_input
from datetime import datetime, date

gamification_bp = Blueprint('gamification', __name__)

@gamification_bp.route('/badges', methods=['GET'])
@token_required
@organization_required
def get_badges():
    """Obtenir tous les badges disponibles"""
    badges = Badge.query.filter(
        db.or_(
            Badge.organization_id == g.current_user.organization_id,
            Badge.organization_id.is_(None)  # Badges globaux
        )
    ).all()
    
    badges_data = []
    for badge in badges:
        badge_data = badge.to_dict()
        
        # Vérifier si l'utilisateur a ce badge
        user_badge = UserBadge.query.filter_by(
            user_id=g.current_user.id,
            badge_id=badge.id
        ).first()
        
        badge_data['earned'] = user_badge is not None
        if user_badge:
            badge_data['earned_at'] = user_badge.earned_at.isoformat()
        
        badges_data.append(badge_data)
    
    return jsonify({
        'badges': badges_data
    }), 200

@gamification_bp.route('/badges', methods=['POST'])
@token_required
@organization_required
@role_required('admin')
@validate_json('name', 'criteria')
def create_badge():
    """Créer un nouveau badge"""
    data = request.get_json()
    
    badge = Badge(
        organization_id=g.current_user.organization_id,
        name=sanitize_input(data['name'], 100),
        description=sanitize_input(data.get('description', ''), 500),
        icon_url=data.get('icon_url'),
        criteria=data['criteria'],
        points_value=data.get('points_value', 0),
        rarity=data.get('rarity', 'common')
    )
    
    db.session.add(badge)
    db.session.commit()
    
    return jsonify({
        'message': 'Badge created successfully',
        'badge': badge.to_dict()
    }), 201

@gamification_bp.route('/my-badges', methods=['GET'])
@token_required
def get_my_badges():
    """Obtenir les badges de l'utilisateur actuel"""
    page = request.args.get('page', 1)
    per_page = request.args.get('per_page', 20)
    
    page, per_page = validate_pagination_params(page, per_page)
    
    pagination = UserBadge.query.filter_by(
        user_id=g.current_user.id
    ).order_by(UserBadge.earned_at.desc()).paginate(
        page=page,
        per_page=per_page,
        error_out=False
    )
    
    badges = []
    for user_badge in pagination.items:
        badge_data = user_badge.badge.to_dict()
        badge_data['earned_at'] = user_badge.earned_at.isoformat()
        badges.append(badge_data)
    
    return jsonify({
        'badges': badges,
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total': pagination.total,
            'pages': pagination.pages,
            'has_next': pagination.has_next,
            'has_prev': pagination.has_prev
        }
    }), 200

@gamification_bp.route('/points', methods=['GET'])
@token_required
def get_my_points():
    """Obtenir l'historique des points de l'utilisateur"""
    page = request.args.get('page', 1)
    per_page = request.args.get('per_page', 20)
    source_filter = request.args.get('source')
    
    page, per_page = validate_pagination_params(page, per_page)
    
    query = UserPoints.query.filter_by(user_id=g.current_user.id)
    
    if source_filter:
        query = query.filter_by(source=source_filter)
    
    pagination = query.order_by(UserPoints.earned_at.desc()).paginate(
        page=page,
        per_page=per_page,
        error_out=False
    )
    
    points = [point.to_dict() for point in pagination.items]
    
    # Calculer le total des points
    total_points = db.session.query(db.func.sum(UserPoints.points)).filter_by(
        user_id=g.current_user.id
    ).scalar() or 0
    
    return jsonify({
        'points': points,
        'total_points': int(total_points),
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total': pagination.total,
            'pages': pagination.pages,
            'has_next': pagination.has_next,
            'has_prev': pagination.has_prev
        }
    }), 200

@gamification_bp.route('/leaderboard', methods=['GET'])
@token_required
@organization_required
def get_leaderboard():
    """Obtenir le classement de l'organisation"""
    leaderboard_type = request.args.get('type', 'all_time')  # 'weekly', 'monthly', 'all_time'
    limit = min(int(request.args.get('limit', 10)), 50)  # Max 50 utilisateurs
    
    # Chercher ou créer le leaderboard
    leaderboard = Leaderboard.query.filter_by(
        organization_id=g.current_user.organization_id,
        type=leaderboard_type,
        is_active=True
    ).first()
    
    if not leaderboard:
        # Créer un nouveau leaderboard
        start_date = None
        end_date = None
        
        if leaderboard_type == 'weekly':
            today = date.today()
            start_date = today - timedelta(days=today.weekday())
            end_date = start_date + timedelta(days=6)
        elif leaderboard_type == 'monthly':
            today = date.today()
            start_date = today.replace(day=1)
            if today.month == 12:
                end_date = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
            else:
                end_date = today.replace(month=today.month + 1, day=1) - timedelta(days=1)
        
        leaderboard = Leaderboard(
            organization_id=g.current_user.organization_id,
            name=f'{leaderboard_type.title()} Leaderboard',
            type=leaderboard_type,
            start_date=start_date,
            end_date=end_date
        )
        db.session.add(leaderboard)
        db.session.commit()
    
    # Obtenir les classements
    rankings = leaderboard.get_rankings(limit=limit)
    
    # Trouver la position de l'utilisateur actuel
    user_rank = None
    user_points = 0
    for rank in rankings:
        if rank['user_id'] == g.current_user.id:
            user_rank = rank['rank']
            user_points = rank['total_points']
            break
    
    return jsonify({
        'leaderboard': leaderboard.to_dict(),
        'rankings': rankings,
        'user_position': {
            'rank': user_rank,
            'points': user_points
        }
    }), 200

@gamification_bp.route('/achievements', methods=['GET'])
@token_required
def get_achievements_progress():
    """Obtenir la progression vers les achievements"""
    from src.models.learning import UserProgress, UserResponse
    from src.models.forum import ForumTopic, ForumReply
    
    user_id = g.current_user.id
    
    # Calculer les statistiques pour les achievements
    stats = {
        'modules_completed': UserProgress.query.filter_by(
            user_id=user_id
        ).filter(UserProgress.completion_percentage >= 100).count(),
        
        'exercises_completed': UserResponse.query.filter_by(
            user_id=user_id
        ).count(),
        
        'correct_answers': UserResponse.query.filter_by(
            user_id=user_id,
            is_correct=True
        ).count(),
        
        'forum_topics': ForumTopic.query.filter_by(
            user_id=user_id
        ).count(),
        
        'forum_replies': ForumReply.query.filter_by(
            user_id=user_id
        ).count(),
        
        'total_points': db.session.query(db.func.sum(UserPoints.points)).filter_by(
            user_id=user_id
        ).scalar() or 0,
        
        'badges_earned': UserBadge.query.filter_by(
            user_id=user_id
        ).count()
    }
    
    # Définir les achievements et leur progression
    achievements = [
        {
            'id': 'first_steps',
            'name': 'Premiers pas',
            'description': 'Terminer votre premier module',
            'target': 1,
            'current': stats['modules_completed'],
            'completed': stats['modules_completed'] >= 1,
            'category': 'learning'
        },
        {
            'id': 'dedicated_learner',
            'name': 'Apprenant dévoué',
            'description': 'Terminer 5 modules',
            'target': 5,
            'current': stats['modules_completed'],
            'completed': stats['modules_completed'] >= 5,
            'category': 'learning'
        },
        {
            'id': 'expert_learner',
            'name': 'Expert en apprentissage',
            'description': 'Terminer 20 modules',
            'target': 20,
            'current': stats['modules_completed'],
            'completed': stats['modules_completed'] >= 20,
            'category': 'learning'
        },
        {
            'id': 'accuracy_master',
            'name': 'Maître de la précision',
            'description': 'Obtenir 90% de bonnes réponses sur 50 exercices',
            'target': 45,  # 90% de 50
            'current': min(stats['correct_answers'], 45),
            'completed': stats['exercises_completed'] >= 50 and stats['correct_answers'] >= 45,
            'category': 'performance'
        },
        {
            'id': 'community_helper',
            'name': 'Aide communautaire',
            'description': 'Créer 10 réponses dans le forum',
            'target': 10,
            'current': stats['forum_replies'],
            'completed': stats['forum_replies'] >= 10,
            'category': 'community'
        },
        {
            'id': 'discussion_starter',
            'name': 'Lanceur de discussions',
            'description': 'Créer 5 sujets dans le forum',
            'target': 5,
            'current': stats['forum_topics'],
            'completed': stats['forum_topics'] >= 5,
            'category': 'community'
        },
        {
            'id': 'point_collector',
            'name': 'Collectionneur de points',
            'description': 'Accumuler 1000 points',
            'target': 1000,
            'current': min(int(stats['total_points']), 1000),
            'completed': stats['total_points'] >= 1000,
            'category': 'points'
        },
        {
            'id': 'badge_hunter',
            'name': 'Chasseur de badges',
            'description': 'Obtenir 10 badges',
            'target': 10,
            'current': stats['badges_earned'],
            'completed': stats['badges_earned'] >= 10,
            'category': 'badges'
        }
    ]
    
    return jsonify({
        'achievements': achievements,
        'stats': stats,
        'completion_rate': len([a for a in achievements if a['completed']]) / len(achievements) * 100
    }), 200

@gamification_bp.route('/daily-challenge', methods=['GET'])
@token_required
def get_daily_challenge():
    """Obtenir le défi quotidien"""
    today = date.today()
    
    # Générer un défi basé sur la date (pour la cohérence)
    import hashlib
    seed = hashlib.md5(f"{today.isoformat()}{g.current_user.id}".encode()).hexdigest()
    challenge_type = int(seed[:2], 16) % 4
    
    challenges = [
        {
            'type': 'exercises',
            'title': 'Maître des exercices',
            'description': 'Complétez 5 exercices aujourd\'hui',
            'target': 5,
            'reward_points': 20
        },
        {
            'type': 'accuracy',
            'title': 'Précision parfaite',
            'description': 'Obtenez 100% de bonnes réponses sur 3 exercices',
            'target': 3,
            'reward_points': 25
        },
        {
            'type': 'forum',
            'title': 'Contributeur communautaire',
            'description': 'Créez 2 réponses utiles dans le forum',
            'target': 2,
            'reward_points': 15
        },
        {
            'type': 'learning_time',
            'title': 'Session d\'apprentissage',
            'description': 'Passez 30 minutes sur la plateforme',
            'target': 30,
            'reward_points': 10
        }
    ]
    
    daily_challenge = challenges[challenge_type]
    
    # Calculer la progression actuelle
    from src.models.analytics import AnalyticsEvent
    today_start = datetime.combine(today, datetime.min.time())
    today_end = datetime.combine(today, datetime.max.time())
    
    current_progress = 0
    
    if daily_challenge['type'] == 'exercises':
        current_progress = UserResponse.query.filter(
            UserResponse.user_id == g.current_user.id,
            UserResponse.submitted_at >= today_start,
            UserResponse.submitted_at <= today_end
        ).count()
    
    elif daily_challenge['type'] == 'accuracy':
        current_progress = UserResponse.query.filter(
            UserResponse.user_id == g.current_user.id,
            UserResponse.submitted_at >= today_start,
            UserResponse.submitted_at <= today_end,
            UserResponse.is_correct == True
        ).count()
    
    elif daily_challenge['type'] == 'forum':
        current_progress = ForumReply.query.filter(
            ForumReply.user_id == g.current_user.id,
            ForumReply.created_at >= today_start,
            ForumReply.created_at <= today_end
        ).count()
    
    elif daily_challenge['type'] == 'learning_time':
        # Simuler le temps passé basé sur les événements
        events = AnalyticsEvent.query.filter(
            AnalyticsEvent.user_id == g.current_user.id,
            AnalyticsEvent.created_at >= today_start,
            AnalyticsEvent.created_at <= today_end
        ).count()
        current_progress = min(events * 2, daily_challenge['target'])  # 2 minutes par événement
    
    daily_challenge['current'] = current_progress
    daily_challenge['completed'] = current_progress >= daily_challenge['target']
    daily_challenge['date'] = today.isoformat()
    
    return jsonify({
        'daily_challenge': daily_challenge
    }), 200

@gamification_bp.route('/stats/summary', methods=['GET'])
@token_required
def get_gamification_summary():
    """Obtenir un résumé des statistiques de gamification"""
    user_id = g.current_user.id
    
    # Points totaux
    total_points = db.session.query(db.func.sum(UserPoints.points)).filter_by(
        user_id=user_id
    ).scalar() or 0
    
    # Badges
    badges_count = UserBadge.query.filter_by(user_id=user_id).count()
    recent_badges = UserBadge.query.filter_by(user_id=user_id).order_by(
        UserBadge.earned_at.desc()
    ).limit(3).all()
    
    # Position dans le classement
    if g.current_user.organization_id:
        leaderboard = Leaderboard.query.filter_by(
            organization_id=g.current_user.organization_id,
            type='all_time',
            is_active=True
        ).first()
        
        user_rank = None
        if leaderboard:
            rankings = leaderboard.get_rankings(limit=100)
            for rank in rankings:
                if rank['user_id'] == user_id:
                    user_rank = rank['rank']
                    break
    else:
        user_rank = None
    
    # Streak (jours consécutifs d'activité)
    # Simplifié pour la démo
    streak_days = 1  # À implémenter avec la logique réelle
    
    return jsonify({
        'summary': {
            'total_points': int(total_points),
            'badges_count': badges_count,
            'leaderboard_rank': user_rank,
            'streak_days': streak_days,
            'recent_badges': [
                {
                    'name': badge.badge.name,
                    'earned_at': badge.earned_at.isoformat()
                } for badge in recent_badges
            ]
        }
    }), 200

