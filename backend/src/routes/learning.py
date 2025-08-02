from flask import Blueprint, request, jsonify, g
from src.models import db
from src.models.learning import LearningModule, Exercise, UserProgress, UserResponse
from src.models.gamification import UserPoints, Badge, UserBadge
from src.models.notification import Notification
from src.utils.auth import token_required, role_required, organization_required
from src.utils.validators import validate_json, validate_pagination_params, sanitize_input
from src.utils.subscription_manager import require_subscription_limit, SubscriptionManager
from datetime import datetime
import openai
import os

learning_bp = Blueprint('learning', __name__)

@learning_bp.route('/modules', methods=['GET'])
@token_required
@organization_required
def get_learning_modules():
    """Obtenir les modules d'apprentissage disponibles"""
    page = request.args.get('page', 1)
    per_page = request.args.get('per_page', 20)
    difficulty = request.args.get('difficulty')
    premium_only = request.args.get('premium', 'false').lower() == 'true'
    
    page, per_page = validate_pagination_params(page, per_page)
    
    # Vérifier les limites d'abonnement pour le contenu premium
    if premium_only:
        limit_check = SubscriptionManager.check_subscription_limits(
            g.current_user.organization_id, 'premium_content'
        )
        if not limit_check['allowed']:
            return jsonify({
                'error': 'Premium content requires subscription upgrade',
                'upgrade_required': True
            }), 402
    
    # Construire la requête
    query = LearningModule.query.filter(
        db.or_(
            LearningModule.organization_id == g.current_user.organization_id,
            LearningModule.organization_id.is_(None)  # Modules publics
        ),
        LearningModule.is_active == True
    )
    
    if difficulty:
        query = query.filter(LearningModule.difficulty_level == int(difficulty))
    
    if premium_only:
        query = query.filter(LearningModule.is_premium == True)
    
    # Paginer les résultats
    pagination = query.paginate(
        page=page,
        per_page=per_page,
        error_out=False
    )
    
    modules = []
    for module in pagination.items:
        module_data = module.to_dict()
        
        # Ajouter la progression de l'utilisateur
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
    """Créer un nouveau module d'apprentissage"""
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
    
    # Suivre l'utilisation
    SubscriptionManager.track_usage(g.current_user.organization_id, 'modules')
    
    return jsonify({
        'message': 'Learning module created successfully',
        'module': module.to_dict()
    }), 201

@learning_bp.route('/modules/<module_id>', methods=['GET'])
@token_required
@organization_required
def get_learning_module(module_id):
    """Obtenir les détails d'un module d'apprentissage"""
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
    
    # Vérifier l'accès au contenu premium
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
    
    # Ajouter les exercices
    exercises = [exercise.to_dict() for exercise in module.exercises]
    module_data['exercises'] = exercises
    
    # Ajouter la progression de l'utilisateur
    progress = UserProgress.query.filter_by(
        user_id=g.current_user.id,
        module_id=module.id
    ).first()
    
    if progress:
        module_data['user_progress'] = progress.to_dict()
    else:
        # Créer une nouvelle progression
        progress = UserProgress(
            user_id=g.current_user.id,
            module_id=module.id,
            started_at=datetime.utcnow()
        )
        db.session.add(progress)
        db.session.commit()
        module_data['user_progress'] = progress.to_dict()
    
    # Mettre à jour le dernier accès
    progress.last_accessed = datetime.utcnow()
    db.session.commit()
    
    return jsonify({'module': module_data}), 200

@learning_bp.route('/modules/<module_id>/exercises', methods=['POST'])
@token_required
@organization_required
@role_required('admin', 'teacher')
@validate_json('title', 'question', 'exercise_type')
def create_exercise(module_id):
    """Créer un nouvel exercice pour un module"""
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
    """Soumettre une réponse à un exercice"""
    data = request.get_json()
    
    exercise = Exercise.query.get(exercise_id)
    if not exercise:
        return jsonify({'error': 'Exercise not found'}), 404
    
    # Vérifier l'accès au module
    module = exercise.module
    if module.organization_id and module.organization_id != g.current_user.organization_id:
        return jsonify({'error': 'Access denied'}), 403
    
    # Vérifier si l'utilisateur a déjà répondu
    existing_response = UserResponse.query.filter_by(
        user_id=g.current_user.id,
        exercise_id=exercise_id
    ).first()
    
    if existing_response:
        return jsonify({'error': 'Response already submitted'}), 409
    
    # Évaluer la réponse
    is_correct = False
    points_earned = 0
    
    if exercise.exercise_type == 'multiple_choice':
        is_correct = data['response'] == exercise.correct_answer
        points_earned = exercise.points if is_correct else 0
    elif exercise.exercise_type == 'essay':
        # Pour les essais, utiliser l'IA pour l'évaluation
        ai_feedback, points_earned = evaluate_essay_with_ai(
            exercise.question, 
            data['response'], 
            exercise.correct_answer,
            exercise.points
        )
        is_correct = points_earned >= (exercise.points * 0.7)  # 70% pour être considéré comme correct
    
    # Créer la réponse
    response = UserResponse(
        user_id=g.current_user.id,
        exercise_id=exercise_id,
        response=data['response'],
        is_correct=is_correct,
        points_earned=points_earned,
        ai_feedback=ai_feedback if exercise.exercise_type == 'essay' else None
    )
    
    db.session.add(response)
    
    # Ajouter les points à l'utilisateur
    if points_earned > 0:
        user_points = UserPoints(
            user_id=g.current_user.id,
            points=points_earned,
            source='exercise_completion',
            description=f'Exercice: {exercise.title}'
        )
        db.session.add(user_points)
    
    # Mettre à jour la progression du module
    progress = UserProgress.query.filter_by(
        user_id=g.current_user.id,
        module_id=module.id
    ).first()
    
    if progress:
        # Recalculer la progression
        total_exercises = len(module.exercises)
        completed_exercises = UserResponse.query.filter_by(
            user_id=g.current_user.id
        ).join(Exercise).filter(Exercise.module_id == module.id).count()
        
        progress.completion_percentage = (completed_exercises / total_exercises) * 100
        progress.score += points_earned
        
        if progress.completion_percentage >= 100 and not progress.completed_at:
            progress.completed_at = datetime.utcnow()
            
            # Vérifier les badges à attribuer
            check_and_award_badges(g.current_user.id)
    
    db.session.commit()
    
    # Suivre l'utilisation
    SubscriptionManager.track_usage(g.current_user.organization_id, 'exercises')
    
    return jsonify({
        'message': 'Response submitted successfully',
        'response': response.to_dict(),
        'is_correct': is_correct,
        'points_earned': points_earned,
        'explanation': exercise.explanation,
        'ai_feedback': response.ai_feedback
    }), 201

@learning_bp.route('/progress', methods=['GET'])
@token_required
def get_user_progress():
    """Obtenir la progression de l'utilisateur"""
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
    """Obtenir un indice IA pour un exercice"""
    data = request.get_json()
    exercise_id = data['exercise_id']
    user_response = data['user_response']
    
    # Vérifier les limites d'abonnement pour les requêtes IA
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
    
    # Générer un indice avec l'IA
    hint = generate_ai_hint(exercise.question, user_response)
    
    # Suivre l'utilisation
    SubscriptionManager.track_usage(g.current_user.organization_id, 'ai_requests')
    
    return jsonify({
        'hint': hint
    }), 200

def evaluate_essay_with_ai(question, user_response, expected_answer, max_points):
    """Évaluer un essai avec l'IA"""
    try:
        client = openai.OpenAI()
        
        prompt = f"""
        Évaluez cette réponse d'étudiant sur une échelle de 0 à {max_points} points.
        
        Question: {question}
        
        Réponse attendue/Critères: {expected_answer}
        
        Réponse de l'étudiant: {user_response}
        
        Fournissez:
        1. Un score sur {max_points} points
        2. Des commentaires constructifs en français
        3. Des suggestions d'amélioration
        
        Format de réponse:
        Score: X/{max_points}
        Commentaires: [vos commentaires]
        """
        
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300
        )
        
        ai_feedback = response.choices[0].message.content
        
        # Extraire le score
        score_line = [line for line in ai_feedback.split('\n') if line.startswith('Score:')]
        if score_line:
            score_text = score_line[0].split(':')[1].strip()
            points_earned = int(score_text.split('/')[0])
        else:
            points_earned = max_points // 2  # Score par défaut
        
        return ai_feedback, min(points_earned, max_points)
    
    except Exception as e:
        return f"Évaluation automatique non disponible. Réponse reçue et enregistrée.", max_points // 2

def generate_ai_hint(question, user_response):
    """Générer un indice IA"""
    try:
        client = openai.OpenAI()
        
        prompt = f"""
        Un étudiant travaille sur cette question: {question}
        
        Sa réponse actuelle: {user_response}
        
        Donnez un indice utile en français pour l'aider à améliorer sa réponse, sans donner directement la réponse complète.
        Soyez encourageant et pédagogique.
        """
        
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=150
        )
        
        return response.choices[0].message.content
    
    except Exception as e:
        return "Désolé, l'assistant IA n'est pas disponible pour le moment. Continuez à réfléchir et n'hésitez pas à demander de l'aide à votre enseignant."

def check_and_award_badges(user_id):
    """Vérifier et attribuer les badges mérités"""
    # Badge "Premier module terminé"
    completed_modules = UserProgress.query.filter_by(
        user_id=user_id
    ).filter(UserProgress.completion_percentage >= 100).count()
    
    if completed_modules == 1:
        award_badge(user_id, "first_module_completed")
    elif completed_modules == 5:
        award_badge(user_id, "five_modules_completed")
    elif completed_modules == 10:
        award_badge(user_id, "ten_modules_completed")
    
    # Badge "Streak d'apprentissage"
    # Implémenter la logique pour les streaks quotidiens
    
def award_badge(user_id, badge_type):
    """Attribuer un badge à un utilisateur"""
    # Vérifier si l'utilisateur a déjà ce badge
    user = db.session.get(User, user_id)
    badge = Badge.query.filter_by(
        organization_id=user.organization_id,
        name=badge_type
    ).first()
    
    if not badge:
        return  # Badge n'existe pas
    
    existing_badge = UserBadge.query.filter_by(
        user_id=user_id,
        badge_id=badge.id
    ).first()
    
    if existing_badge:
        return  # Badge déjà attribué
    
    # Attribuer le badge
    user_badge = UserBadge(
        user_id=user_id,
        badge_id=badge.id
    )
    db.session.add(user_badge)
    
    # Ajouter des points bonus
    if badge.points_value > 0:
        user_points = UserPoints(
            user_id=user_id,
            points=badge.points_value,
            source='badge_earned',
            description=f'Badge obtenu: {badge.name}'
        )
        db.session.add(user_points)
    
    # Créer une notification
    Notification.create_notification(
        user_id=user_id,
        notification_type='badge_earned',
        title='Nouveau badge obtenu !',
        message=f'Félicitations ! Vous avez obtenu le badge "{badge.name}"',
        data={'badge_id': badge.id}
    )
    
    db.session.commit()

