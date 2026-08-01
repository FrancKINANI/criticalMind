from flask import Blueprint, request, jsonify, g
from src.models import db
from src.models.user import User
from src.models.learning import LearningModule, Exercise, UserProgress, UserResponse
from src.models.gamification import UserPoints, Badge, UserBadge
from src.models.notification import Notification
from src.utils.auth import token_required, role_required, organization_required
from src.utils.validators import validate_json, validate_pagination_params, sanitize_input
from src.utils.subscription_manager import require_subscription_limit, SubscriptionManager
from src.services.llm_provider import get_llm_provider
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

learning_bp = Blueprint('learning', __name__)

@learning_bp.route('/modules', methods=['GET'])
@token_required
@organization_required
def get_learning_modules():
    """Get the available learning modules"""
    page = request.args.get('page', 1)
    per_page = request.args.get('per_page', 20)
    difficulty = request.args.get('difficulty')
    premium_only = request.args.get('premium', 'false').lower() == 'true'
    
    page, per_page = validate_pagination_params(page, per_page)
    
    # Check the subscription limits for premium content
    if premium_only:
        limit_check = SubscriptionManager.check_subscription_limits(
            g.current_user.organization_id, 'premium_content'
        )
        if not limit_check['allowed']:
            return jsonify({
                'error': 'Premium content requires subscription upgrade',
                'upgrade_required': True
            }), 402
    
    # Build the query
    query = LearningModule.query.filter(
        db.or_(
            LearningModule.organization_id == g.current_user.organization_id,
            LearningModule.organization_id.is_(None)  # Public modules
        ),
        LearningModule.is_active == True
    )
    
    if difficulty:
        query = query.filter(LearningModule.difficulty_level == int(difficulty))
    
    if premium_only:
        query = query.filter(LearningModule.is_premium == True)
    
    # Paginate the results
    pagination = query.paginate(
        page=page,
        per_page=per_page,
        error_out=False
    )
    
    modules = []
    for module in pagination.items:
        module_data = module.to_dict()
        
        # Add the user's progress
        progress = UserProgress.query.filter_by(
            user_id=g.current_user.id,
            module_id=module.id
        ).first()
        
        if progress:
            module_data['user_progress'] = progress.to_dict()
        else:
            module_data['user_progress'] = None
        
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

@learning_bp.route('/modules', methods=['POST'])
@token_required
@organization_required
@role_required('admin', 'teacher')
@require_subscription_limit('modules')
@validate_json('title', 'content')
def create_learning_module():
    """Create a new learning module"""
    data = request.get_json()
    
    module = LearningModule(
        organization_id=g.current_user.organization_id,
        title=sanitize_input(data['title'], 255),
        description=sanitize_input(data.get('description', ''), 1000),
        content=data['content'],
        difficulty_level=data.get('difficulty_level', 1),
        estimated_duration=data.get('estimated_duration'),
        is_premium=data.get('is_premium', False),
        created_by=g.current_user.id
    )
    
    db.session.add(module)
    db.session.commit()
    
    # Track the usage
    SubscriptionManager.track_usage(g.current_user.organization_id, 'modules')
    
    return jsonify({
        'message': 'Learning module created successfully',
        'module': module.to_dict()
    }), 201

@learning_bp.route('/modules/<module_id>', methods=['GET'])
@token_required
@organization_required
def get_learning_module(module_id):
    """Get the details of a learning module"""
    module = LearningModule.query.filter(
        LearningModule.id == module_id,
        db.or_(
            LearningModule.organization_id == g.current_user.organization_id,
            LearningModule.organization_id.is_(None)
        ),
        LearningModule.is_active == True
    ).first()
    
    if not module:
        return jsonify({'error': 'Module not found'}), 404
    
    # Check access to the premium content
    if module.is_premium:
        limit_check = SubscriptionManager.check_subscription_limits(
            g.current_user.organization_id, 'premium_content'
        )
        if not limit_check['allowed']:
            return jsonify({
                'error': 'Premium content requires subscription upgrade',
                'upgrade_required': True
            }), 402
    
    module_data = module.to_dict()
    
    # Add the exercises
    exercises = [exercise.to_dict() for exercise in module.exercises]
    module_data['exercises'] = exercises
    
    # Add the user's progress
    progress = UserProgress.query.filter_by(
        user_id=g.current_user.id,
        module_id=module.id
    ).first()
    
    if progress:
        module_data['user_progress'] = progress.to_dict()
    else:
        # Create new progress
        progress = UserProgress(
            user_id=g.current_user.id,
            module_id=module.id,
            started_at=datetime.utcnow()
        )
        db.session.add(progress)
        db.session.commit()
        module_data['user_progress'] = progress.to_dict()
    
    # Update the last access
    progress.last_accessed = datetime.utcnow()
    db.session.commit()
    
    return jsonify({'module': module_data}), 200

@learning_bp.route('/modules/<module_id>/exercises', methods=['POST'])
@token_required
@organization_required
@role_required('admin', 'teacher')
@validate_json('title', 'question', 'exercise_type')
def create_exercise(module_id):
    """Create a new exercise for a module"""
    data = request.get_json()
    
    module = LearningModule.query.filter_by(
        id=module_id,
        organization_id=g.current_user.organization_id
    ).first()
    
    if not module:
        return jsonify({'error': 'Module not found'}), 404
    
    exercise = Exercise(
        module_id=module_id,
        title=sanitize_input(data['title'], 255),
        question=sanitize_input(data['question'], 2000),
        exercise_type=data['exercise_type'],
        options=data.get('options'),
        correct_answer=data.get('correct_answer'),
        explanation=sanitize_input(data.get('explanation', ''), 1000),
        points=data.get('points', 10)
    )
    
    db.session.add(exercise)
    db.session.commit()
    
    return jsonify({
        'message': 'Exercise created successfully',
        'exercise': exercise.to_dict(include_answers=True)
    }), 201

@learning_bp.route('/exercises/<exercise_id>/submit', methods=['POST'])
@token_required
@organization_required
@validate_json('response')
def submit_exercise_response(exercise_id):
    """Submit a response to an exercise"""
    data = request.get_json()
    
    exercise = Exercise.query.get(exercise_id)
    if not exercise:
        return jsonify({'error': 'Exercise not found'}), 404
    
    # Check access to the module
    module = exercise.module
    if module.organization_id and module.organization_id != g.current_user.organization_id:
        return jsonify({'error': 'Access denied'}), 403
    
    # Check if the user has already responded
    existing_response = UserResponse.query.filter_by(
        user_id=g.current_user.id,
        exercise_id=exercise_id
    ).first()
    
    if existing_response:
        return jsonify({'error': 'Response already submitted'}), 409
    
    # Evaluate the response
    is_correct = False
    points_earned = 0
    ai_feedback = None
    provider_warning = False  # True when the active provider is a local/edge model
    
    if exercise.exercise_type == 'multiple_choice':
        is_correct = data['response'] == exercise.correct_answer
        points_earned = exercise.points if is_correct else 0
    elif exercise.exercise_type == 'essay':
        # For essays, use AI for evaluation
        ai_feedback, points_earned, provider_warning = evaluate_essay_with_ai(
            exercise.question, 
            data['response'], 
            exercise.correct_answer,
            exercise.points
        )
        is_correct = points_earned >= (exercise.points * 0.7)  # 70% to be considered correct
    
    # Create the response
    response = UserResponse(
        user_id=g.current_user.id,
        exercise_id=exercise_id,
        response=data['response'],
        is_correct=is_correct,
        points_earned=points_earned,
        ai_feedback=ai_feedback if exercise.exercise_type == 'essay' else None
    )
    
    db.session.add(response)
    
    # Add the points to the user
    if points_earned > 0:
        user_points = UserPoints(
            user_id=g.current_user.id,
            points=points_earned,
            source='exercise_completion',
            description=f'Exercise: {exercise.title}'
        )
        db.session.add(user_points)
    
    # Update the module progress
    progress = UserProgress.query.filter_by(
        user_id=g.current_user.id,
        module_id=module.id
    ).first()
    
    if progress:
        # Recalculate the progress
        total_exercises = len(module.exercises)
        completed_exercises = UserResponse.query.filter_by(
            user_id=g.current_user.id
        ).join(Exercise).filter(Exercise.module_id == module.id).count()
        
        progress.completion_percentage = (completed_exercises / total_exercises) * 100
        progress.score += points_earned
        
        if progress.completion_percentage >= 100 and not progress.completed_at:
            progress.completed_at = datetime.utcnow()
            
            # Check the badges to award
            check_and_award_badges(g.current_user.id)
    
    db.session.commit()
    
    # Track the usage
    SubscriptionManager.track_usage(g.current_user.organization_id, 'exercises')
    
    return jsonify({
        'message': 'Response submitted successfully',
        'response': response.to_dict(),
        'is_correct': is_correct,
        'points_earned': points_earned,
        'explanation': exercise.explanation,
        'ai_feedback': response.ai_feedback,
        'evaluation_warning': provider_warning if exercise.exercise_type == 'essay' else False
    }), 201

@learning_bp.route('/progress', methods=['GET'])
@token_required
def get_user_progress():
    """Get the user's progress"""
    page = request.args.get('page', 1)
    per_page = request.args.get('per_page', 20)
    
    page, per_page = validate_pagination_params(page, per_page)
    
    pagination = UserProgress.query.filter_by(
        user_id=g.current_user.id
    ).order_by(UserProgress.last_accessed.desc()).paginate(
        page=page,
        per_page=per_page,
        error_out=False
    )
    
    progress_list = []
    for progress in pagination.items:
        progress_data = progress.to_dict()
        progress_data['module'] = progress.module.to_dict()
        progress_list.append(progress_data)
    
    return jsonify({
        'progress': progress_list,
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total': pagination.total,
            'pages': pagination.pages,
            'has_next': pagination.has_next,
            'has_prev': pagination.has_prev
        }
    }), 200

@learning_bp.route('/ai-hint', methods=['POST'])
@token_required
@organization_required
@validate_json('exercise_id', 'user_response')
def get_ai_hint(exercise_id=None):
    """Get an AI hint for an exercise"""
    data = request.get_json()
    exercise_id = data['exercise_id']
    user_response = data['user_response']
    
    # Check the subscription limits for AI requests
    limit_check = SubscriptionManager.check_subscription_limits(
        g.current_user.organization_id, 'ai_requests'
    )
    if not limit_check['allowed']:
        return jsonify({
            'error': 'AI request limit exceeded',
            'reason': limit_check['reason'],
            'upgrade_required': True
        }), 402
    
    exercise = Exercise.query.get(exercise_id)
    if not exercise:
        return jsonify({'error': 'Exercise not found'}), 404
    
    # Generate a hint with AI
    hint = generate_ai_hint(exercise.question, user_response)
    
    # Track the usage
    SubscriptionManager.track_usage(g.current_user.organization_id, 'ai_requests')
    
    return jsonify({
        'hint': hint
    }), 200

def evaluate_essay_with_ai(question, user_response, expected_answer, max_points):
    """Evaluate an essay with AI (cloud or edge).

    Returns a triple (ai_feedback, points_earned, provider_warning):
    ``provider_warning`` is True when the active provider is a local/edge
    model (Ollama) — quality not guaranteed to be equivalent to cloud mode
    until a benchmark validates the parity (paid Stripe feature).
    """
    provider = get_llm_provider()
    provider_warning = provider.is_edge
    if provider_warning:
        logger.warning(
            '[EDGE LLM] evaluate_essay_with_ai uses a local model (%s, %s). '
            'Quality not guaranteed to be equivalent to cloud mode — paid grading.',
            provider.name, provider.model_name
        )

    try:
        prompt = f"""
        Evaluate this student's answer on a scale from 0 to {max_points} points.
        
        Question: {question}
        
        Expected answer/Criteria: {expected_answer}
        
        Student's answer: {user_response}
        
        Provide:
        1. A score out of {max_points} points
        2. Constructive comments in English
        3. Suggestions for improvement
        
        Response format:
        Score: X/{max_points}
        Comments: [your comments]
        """
        
        ai_feedback = provider.generate(
            prompt,
            system="You are a rigorous and constructive pedagogical grader for critical thinking.",
            temperature=0.3,
            max_tokens=300
        )
        
        # Extract the score
        score_line = [line for line in ai_feedback.split('\n') if line.startswith('Score:')]
        if score_line:
            score_text = score_line[0].split(':')[1].strip()
            points_earned = int(score_text.split('/')[0])
        else:
            points_earned = max_points // 2  # Default score
        
        return ai_feedback, min(points_earned, max_points), provider_warning
    
    except Exception as e:
        logger.error('AI essay evaluation failed (%s): %s', provider, e)
        return f"Automatic evaluation unavailable. Response received and recorded.", max_points // 2, provider_warning

def generate_ai_hint(question, user_response):
    """Generate an AI hint (cloud or edge)"""
    provider = get_llm_provider()
    if provider.is_edge:
        logger.warning(
            '[EDGE LLM] generate_ai_hint uses a local model (%s, %s).',
            provider.name, provider.model_name
        )

    try:
        prompt = f"""
        A student is working on this question: {question}
        
        Their current answer: {user_response}
        
        Give a useful hint in English to help them improve their answer, without directly giving the complete answer.
        Be encouraging and pedagogical.
        """
        
        return provider.generate(
            prompt,
            system="You are an encouraging and supportive pedagogical assistant for critical thinking.",
            temperature=0.5,
            max_tokens=150
        )
    
    except Exception as e:
        logger.error('AI hint generation failed (%s): %s', provider, e)
        return "Sorry, the AI assistant is not available right now. Keep thinking and do not hesitate to ask your teacher for help."

def check_and_award_badges(user_id):
    """Check and award the deserved badges"""
    # Badge "First module completed"
    completed_modules = UserProgress.query.filter_by(
        user_id=user_id
    ).filter(UserProgress.completion_percentage >= 100).count()
    
    if completed_modules == 1:
        award_badge(user_id, "first_module_completed")
    elif completed_modules == 5:
        award_badge(user_id, "five_modules_completed")
    elif completed_modules == 10:
        award_badge(user_id, "ten_modules_completed")
    
    # Badge "Learning streak"
    # Implement the logic for daily streaks
    
def award_badge(user_id, badge_type):
    """Award a badge to a user"""
    # Check if the user already has this badge
    user = db.session.get(User, user_id)
    badge = Badge.query.filter_by(
        organization_id=user.organization_id,
        name=badge_type
    ).first()
    
    if not badge:
        return  # Badge does not exist
    
    existing_badge = UserBadge.query.filter_by(
        user_id=user_id,
        badge_id=badge.id
    ).first()
    
    if existing_badge:
        return  # Badge already awarded
    
    # Award the badge
    user_badge = UserBadge(
        user_id=user_id,
        badge_id=badge.id
    )
    db.session.add(user_badge)
    
    # Add bonus points
    if badge.points_value > 0:
        user_points = UserPoints(
            user_id=user_id,
            points=badge.points_value,
            source='badge_earned',
            description=f'Badge earned: {badge.name}'
        )
        db.session.add(user_points)
    
    # Create a notification
    Notification.create_notification(
        user_id=user_id,
        notification_type='badge_earned',
        title='New badge earned!',
        message=f'Congratulations! You earned the badge "{badge.name}"',
        data={'badge_id': badge.id}
    )
    
    db.session.commit()

