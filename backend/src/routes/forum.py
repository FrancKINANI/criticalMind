from flask import Blueprint, request, jsonify, g
from src.models import db
from src.models.forum import ForumCategory, ForumTopic, ForumReply
from src.models.gamification import UserPoints
from src.models.notification import Notification
from src.utils.auth import token_required, role_required, organization_required
from src.utils.validators import validate_json, validate_pagination_params, sanitize_input
from datetime import datetime

forum_bp = Blueprint('forum', __name__)

@forum_bp.route('/categories', methods=['GET'])
@token_required
@organization_required
def get_forum_categories():
    """Get the forum categories"""
    categories = ForumCategory.query.filter_by(
        organization_id=g.current_user.organization_id,
        is_active=True
    ).all()
    
    return jsonify({
        'categories': [category.to_dict() for category in categories]
    }), 200

@forum_bp.route('/categories', methods=['POST'])
@token_required
@organization_required
@role_required('admin', 'teacher')
@validate_json('name')
def create_forum_category():
    """Create a new forum category"""
    data = request.get_json()
    
    category = ForumCategory(
        organization_id=g.current_user.organization_id,
        name=sanitize_input(data['name'], 100),
        description=sanitize_input(data.get('description', ''), 500),
        color=data.get('color', '#3B82F6')
    )
    
    db.session.add(category)
    db.session.commit()
    
    return jsonify({
        'message': 'Forum category created successfully',
        'category': category.to_dict()
    }), 201

@forum_bp.route('/categories/<category_id>/topics', methods=['GET'])
@token_required
@organization_required
def get_category_topics(category_id):
    """Get the topics of a category"""
    page = request.args.get('page', 1)
    per_page = request.args.get('per_page', 20)
    
    page, per_page = validate_pagination_params(page, per_page)
    
    category = ForumCategory.query.filter_by(
        id=category_id,
        organization_id=g.current_user.organization_id
    ).first()
    
    if not category:
        return jsonify({'error': 'Category not found'}), 404
    
    # Order by pinned first, then by latest reply
    pagination = ForumTopic.query.filter_by(
        category_id=category_id
    ).order_by(
        ForumTopic.is_pinned.desc(),
        ForumTopic.last_reply_at.desc().nullslast(),
        ForumTopic.created_at.desc()
    ).paginate(
        page=page,
        per_page=per_page,
        error_out=False
    )
    
    topics = []
    for topic in pagination.items:
        topic_data = topic.to_dict()
        
        # Add the author information
        from src.models.user import User
        author = User.query.get(topic.user_id)
        if author:
            topic_data['author'] = {
                'id': author.id,
                'name': author.full_name,
                'role': author.role
            }
        
        topics.append(topic_data)
    
    return jsonify({
        'topics': topics,
        'category': category.to_dict(),
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total': pagination.total,
            'pages': pagination.pages,
            'has_next': pagination.has_next,
            'has_prev': pagination.has_prev
        }
    }), 200

@forum_bp.route('/topics', methods=['POST'])
@token_required
@organization_required
@validate_json('category_id', 'title', 'content')
def create_topic():
    """Create a new forum topic"""
    data = request.get_json()
    
    category = ForumCategory.query.filter_by(
        id=data['category_id'],
        organization_id=g.current_user.organization_id
    ).first()
    
    if not category:
        return jsonify({'error': 'Category not found'}), 404
    
    topic = ForumTopic(
        category_id=data['category_id'],
        user_id=g.current_user.id,
        title=sanitize_input(data['title'], 255),
        content=sanitize_input(data['content'], 5000)
    )
    
    db.session.add(topic)
    db.session.commit()
    
    # Add points for creating a topic
    user_points = UserPoints(
        user_id=g.current_user.id,
        points=5,
        source='forum_topic_created',
        description=f'Topic created: {topic.title}'
    )
    db.session.add(user_points)
    db.session.commit()
    
    return jsonify({
        'message': 'Topic created successfully',
        'topic': topic.to_dict()
    }), 201

@forum_bp.route('/topics/<topic_id>', methods=['GET'])
@token_required
@organization_required
def get_topic(topic_id):
    """Get a topic with its replies"""
    topic = ForumTopic.query.get(topic_id)
    if not topic:
        return jsonify({'error': 'Topic not found'}), 404
    
    # Check access
    category = topic.category
    if category.organization_id != g.current_user.organization_id:
        return jsonify({'error': 'Access denied'}), 403
    
    # Increment the view count
    topic.increment_views()
    
    # Get the paginated replies
    page = request.args.get('page', 1)
    per_page = request.args.get('per_page', 20)
    page, per_page = validate_pagination_params(page, per_page)
    
    replies_pagination = ForumReply.query.filter_by(
        topic_id=topic_id
    ).order_by(ForumReply.created_at.asc()).paginate(
        page=page,
        per_page=per_page,
        error_out=False
    )
    
    # Prepare the topic data
    topic_data = topic.to_dict()
    
    # Add the author information
    from src.models.user import User
    author = User.query.get(topic.user_id)
    if author:
        topic_data['author'] = {
            'id': author.id,
            'name': author.full_name,
            'role': author.role
        }
    
    # Add the replies with their authors
    replies = []
    for reply in replies_pagination.items:
        reply_data = reply.to_dict()
        reply_author = User.query.get(reply.user_id)
        if reply_author:
            reply_data['author'] = {
                'id': reply_author.id,
                'name': reply_author.full_name,
                'role': reply_author.role
            }
        replies.append(reply_data)
    
    return jsonify({
        'topic': topic_data,
        'replies': replies,
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total': replies_pagination.total,
            'pages': replies_pagination.pages,
            'has_next': replies_pagination.has_next,
            'has_prev': replies_pagination.has_prev
        }
    }), 200

@forum_bp.route('/topics/<topic_id>/replies', methods=['POST'])
@token_required
@organization_required
@validate_json('content')
def create_reply(topic_id):
    """Create a reply to a topic"""
    data = request.get_json()
    
    topic = ForumTopic.query.get(topic_id)
    if not topic:
        return jsonify({'error': 'Topic not found'}), 404
    
    # Check access
    category = topic.category
    if category.organization_id != g.current_user.organization_id:
        return jsonify({'error': 'Access denied'}), 403
    
    # Check if the topic is locked
    if topic.is_locked:
        return jsonify({'error': 'Topic is locked'}), 403
    
    reply = ForumReply(
        topic_id=topic_id,
        user_id=g.current_user.id,
        content=sanitize_input(data['content'], 5000)
    )
    
    db.session.add(reply)
    
    # Update the topic statistics
    topic.update_reply_stats()
    
    # Add points for the reply
    user_points = UserPoints(
        user_id=g.current_user.id,
        points=2,
        source='forum_reply_created',
        description=f'Reply in: {topic.title}'
    )
    db.session.add(user_points)
    
    # Notify the topic author (if it is not themselves)
    if topic.user_id != g.current_user.id:
        Notification.create_notification(
            user_id=topic.user_id,
            notification_type='reply_received',
            title='New reply to your topic',
            message=f'{g.current_user.full_name} replied to your topic "{topic.title}"',
            data={'topic_id': topic_id, 'reply_id': reply.id}
        )
    
    db.session.commit()
    
    return jsonify({
        'message': 'Reply created successfully',
        'reply': reply.to_dict()
    }), 201

@forum_bp.route('/replies/<reply_id>/mark-solution', methods=['POST'])
@token_required
@organization_required
def mark_reply_as_solution(reply_id):
    """Mark a reply as the solution"""
    reply = ForumReply.query.get(reply_id)
    if not reply:
        return jsonify({'error': 'Reply not found'}), 404
    
    topic = reply.topic
    
    # Only the topic author or an admin/teacher can mark a solution
    if topic.user_id != g.current_user.id and g.current_user.role not in ['admin', 'teacher']:
        return jsonify({'error': 'Permission denied'}), 403
    
    # Mark as solution
    reply.mark_as_solution()
    
    # Add bonus points to the reply author
    bonus_points = UserPoints(
        user_id=reply.user_id,
        points=10,
        source='solution_marked',
        description=f'Solution accepted in: {topic.title}'
    )
    db.session.add(bonus_points)
    
    # Notify the reply author
    if reply.user_id != g.current_user.id:
        Notification.create_notification(
            user_id=reply.user_id,
            notification_type='solution_marked',
            title='Your reply was marked as the solution!',
            message=f'Your reply in "{topic.title}" was accepted as the solution',
            data={'topic_id': topic.id, 'reply_id': reply.id}
        )
    
    db.session.commit()
    
    return jsonify({
        'message': 'Reply marked as solution successfully'
    }), 200

@forum_bp.route('/topics/<topic_id>/pin', methods=['POST'])
@token_required
@organization_required
@role_required('admin', 'teacher')
def pin_topic(topic_id):
    """Pin a topic"""
    topic = ForumTopic.query.get(topic_id)
    if not topic:
        return jsonify({'error': 'Topic not found'}), 404
    
    # Check access
    category = topic.category
    if category.organization_id != g.current_user.organization_id:
        return jsonify({'error': 'Access denied'}), 403
    
    topic.is_pinned = not topic.is_pinned
    db.session.commit()
    
    action = 'pinned' if topic.is_pinned else 'unpinned'
    
    return jsonify({
        'message': f'Topic {action} successfully',
        'is_pinned': topic.is_pinned
    }), 200

@forum_bp.route('/topics/<topic_id>/lock', methods=['POST'])
@token_required
@organization_required
@role_required('admin', 'teacher')
def lock_topic(topic_id):
    """Lock a topic"""
    topic = ForumTopic.query.get(topic_id)
    if not topic:
        return jsonify({'error': 'Topic not found'}), 404
    
    # Check access
    category = topic.category
    if category.organization_id != g.current_user.organization_id:
        return jsonify({'error': 'Access denied'}), 403
    
    topic.is_locked = not topic.is_locked
    db.session.commit()
    
    action = 'locked' if topic.is_locked else 'unlocked'
    
    return jsonify({
        'message': f'Topic {action} successfully',
        'is_locked': topic.is_locked
    }), 200

@forum_bp.route('/search', methods=['GET'])
@token_required
@organization_required
def search_forum():
    """Search the forum"""
    query = request.args.get('q', '').strip()
    category_id = request.args.get('category_id')
    page = request.args.get('page', 1)
    per_page = request.args.get('per_page', 20)
    
    if not query:
        return jsonify({'error': 'Search query is required'}), 400
    
    page, per_page = validate_pagination_params(page, per_page)
    
    # Search in topics
    topics_query = ForumTopic.query.join(ForumCategory).filter(
        ForumCategory.organization_id == g.current_user.organization_id,
        db.or_(
            ForumTopic.title.ilike(f'%{query}%'),
            ForumTopic.content.ilike(f'%{query}%')
        )
    )
    
    if category_id:
        topics_query = topics_query.filter(ForumTopic.category_id == category_id)
    
    topics_pagination = topics_query.order_by(
        ForumTopic.created_at.desc()
    ).paginate(
        page=page,
        per_page=per_page,
        error_out=False
    )
    
    topics = []
    for topic in topics_pagination.items:
        topic_data = topic.to_dict()
        topic_data['category'] = topic.category.to_dict()
        
        # Add the author information
        from src.models.user import User
        author = User.query.get(topic.user_id)
        if author:
            topic_data['author'] = {
                'id': author.id,
                'name': author.full_name,
                'role': author.role
            }
        
        topics.append(topic_data)
    
    return jsonify({
        'topics': topics,
        'query': query,
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total': topics_pagination.total,
            'pages': topics_pagination.pages,
            'has_next': topics_pagination.has_next,
            'has_prev': topics_pagination.has_prev
        }
    }), 200

@forum_bp.route('/my-topics', methods=['GET'])
@token_required
def get_my_topics():
    """Get the topics created by the current user"""
    page = request.args.get('page', 1)
    per_page = request.args.get('per_page', 20)
    
    page, per_page = validate_pagination_params(page, per_page)
    
    pagination = ForumTopic.query.filter_by(
        user_id=g.current_user.id
    ).order_by(ForumTopic.created_at.desc()).paginate(
        page=page,
        per_page=per_page,
        error_out=False
    )
    
    topics = []
    for topic in pagination.items:
        topic_data = topic.to_dict()
        topic_data['category'] = topic.category.to_dict()
        topics.append(topic_data)
    
    return jsonify({
        'topics': topics,
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total': pagination.total,
            'pages': pagination.pages,
            'has_next': pagination.has_next,
            'has_prev': pagination.has_prev
        }
    }), 200

