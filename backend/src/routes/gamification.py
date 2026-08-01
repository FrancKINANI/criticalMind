from flask import Blueprint, request, jsonify, g
from src.models import db
from src.models.gamification import Badge, UserBadge, UserPoints, Leaderboard
from src.utils.auth import token_required, role_required, organization_required
from src.utils.validators import validate_json, validate_pagination_params, sanitize_input
from datetime import datetime, date, timedelta

gamification_bp = Blueprint('gamification', __name__)

@gamification_bp.route('/badges', methods=['GET'])
@token_required
@organization_required
def get_badges():
    """Get all the available badges"""
    badges = Badge.query.filter(
        db.or_(
            Badge.organization_id == g.current_user.organization_id,
            Badge.organization_id.is_(None)  # Global badges
        )
    ).all()
    
    badges_data = []
    for badge in badges:
        badge_data = badge.to_dict()
        
        # Check if the user has this badge
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
    """Create a new badge"""
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
    """Get the current user's badges"""
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
    """Get the user's points history"""
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
    
    # Calculate the total points
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
    """Get the organization leaderboard"""
    leaderboard_type = request.args.get('type', 'all_time')  # 'weekly', 'monthly', 'all_time'
    limit = min(int(request.args.get('limit', 10)), 50)  # Max 50 users
    
    # Search for or create the leaderboard
    leaderboard = Leaderboard.query.filter_by(
        organization_id=g.current_user.organization_id,
        type=leaderboard_type,
        is_active=True
    ).first()
    
    if not leaderboard:
        # Create a new leaderboard
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
    
    # Get the rankings
    rankings = leaderboard.get_rankings(limit=limit)
    
    # Find the current user's position
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
    """Get the progress towards achievements"""
    from src.models.learning import UserProgress, UserResponse
    from src.models.forum import ForumTopic, ForumReply
    
    user_id = g.current_user.id
    
    # Calculate the statistics for achievements
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
    
    # Define the achievements and their progress
    achievements = [
        {
            'id': 'first_steps',
            'name': 'First steps',
            'description': 'Complete your first module',
            'target': 1,
            'current': stats['modules_completed'],
            'completed': stats['modules_completed'] >= 1,
            'category': 'learning'
        },
        {
            'id': 'dedicated_learner',
            'name': 'Dedicated learner',
            'description': 'Complete 5 modules',
            'target': 5,
            'current': stats['modules_completed'],
            'completed': stats['modules_completed'] >= 5,
            'category': 'learning'
        },
        {
            'id': 'expert_learner',
            'name': 'Learning expert',
            'description': 'Complete 20 modules',
            'target': 20,
            'current': stats['modules_completed'],
            'completed': stats['modules_completed'] >= 20,
            'category': 'learning'
        },
        {
            'id': 'accuracy_master',
            'name': 'Master of accuracy',
            'description': 'Get 90% correct answers on 50 exercises',
            'target': 45,  # 90% of 50
            'current': min(stats['correct_answers'], 45),
            'completed': stats['exercises_completed'] >= 50 and stats['correct_answers'] >= 45,
            'category': 'performance'
        },
        {
            'id': 'community_helper',
            'name': 'Community helper',
            'description': 'Create 10 replies in the forum',
            'target': 10,
            'current': stats['forum_replies'],
            'completed': stats['forum_replies'] >= 10,
            'category': 'community'
        },
        {
            'id': 'discussion_starter',
            'name': 'Discussion starter',
            'description': 'Create 5 topics in the forum',
            'target': 5,
            'current': stats['forum_topics'],
            'completed': stats['forum_topics'] >= 5,
            'category': 'community'
        },
        {
            'id': 'point_collector',
            'name': 'Point collector',
            'description': 'Accumulate 1000 points',
            'target': 1000,
            'current': min(int(stats['total_points']), 1000),
            'completed': stats['total_points'] >= 1000,
            'category': 'points'
        },
        {
            'id': 'badge_hunter',
            'name': 'Badge hunter',
            'description': 'Earn 10 badges',
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
    """Get the daily challenge"""
    today = date.today()
    
    # Generate a challenge based on the date (for consistency)
    import hashlib
    seed = hashlib.md5(f"{today.isoformat()}{g.current_user.id}".encode()).hexdigest()
    challenge_type = int(seed[:2], 16) % 4
    
    challenges = [
        {
            'type': 'exercises',
            'title': 'Master of exercises',
            'description': 'Complete 5 exercises today',
            'target': 5,
            'reward_points': 20
        },
        {
            'type': 'accuracy',
            'title': 'Perfect accuracy',
            'description': 'Get 100% correct answers on 3 exercises',
            'target': 3,
            'reward_points': 25
        },
        {
            'type': 'forum',
            'title': 'Community contributor',
            'description': 'Create 2 useful replies in the forum',
            'target': 2,
            'reward_points': 15
        },
        {
            'type': 'learning_time',
            'title': 'Learning session',
            'description': 'Spend 30 minutes on the platform',
            'target': 30,
            'reward_points': 10
        }
    ]
    
    daily_challenge = challenges[challenge_type]
    
    # Calculate the current progress
    from src.models.learning import UserResponse
    from src.models.forum import ForumReply
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
        # Simulate the time spent based on events
        events = AnalyticsEvent.query.filter(
            AnalyticsEvent.user_id == g.current_user.id,
            AnalyticsEvent.created_at >= today_start,
            AnalyticsEvent.created_at <= today_end
        ).count()
        current_progress = min(events * 2, daily_challenge['target'])  # 2 minutes per event
    
    daily_challenge['current'] = current_progress
    daily_challenge['completed'] = current_progress >= daily_challenge['target']
    daily_challenge['date'] = today.isoformat()
    
    return jsonify({
        'daily_challenge': daily_challenge
    }), 200

@gamification_bp.route('/stats/summary', methods=['GET'])
@token_required
def get_gamification_summary():
    """Get a summary of the gamification statistics"""
    user_id = g.current_user.id
    
    # Total points
    total_points = db.session.query(db.func.sum(UserPoints.points)).filter_by(
        user_id=user_id
    ).scalar() or 0
    
    # Badges
    badges_count = UserBadge.query.filter_by(user_id=user_id).count()
    recent_badges = UserBadge.query.filter_by(user_id=user_id).order_by(
        UserBadge.earned_at.desc()
    ).limit(3).all()
    
    # Position in the leaderboard
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
    
    # Streak (consecutive days of activity)
    # Simplified for the demo
    streak_days = 1  # To be implemented with the real logic
    
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

