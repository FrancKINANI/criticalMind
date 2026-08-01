from flask import Blueprint, request, jsonify, g
from src.models import db
from src.models.notification import Notification
from src.utils.auth import token_required
from src.utils.validators import validate_pagination_params

notifications_bp = Blueprint('notifications', __name__)

@notifications_bp.route('/', methods=['GET'])
@token_required
def get_notifications():
    """Get the user's notifications"""
    page = request.args.get('page', 1)
    per_page = request.args.get('per_page', 20)
    unread_only = request.args.get('unread_only', 'false').lower() == 'true'
    
    page, per_page = validate_pagination_params(page, per_page)
    
    query = Notification.query.filter_by(user_id=g.current_user.id)
    
    if unread_only:
        query = query.filter_by(is_read=False)
    
    pagination = query.order_by(Notification.created_at.desc()).paginate(
        page=page,
        per_page=per_page,
        error_out=False
    )
    
    notifications = [notification.to_dict() for notification in pagination.items]
    
    return jsonify({
        'notifications': notifications,
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total': pagination.total,
            'pages': pagination.pages,
            'has_next': pagination.has_next,
            'has_prev': pagination.has_prev
        }
    }), 200

@notifications_bp.route('/unread-count', methods=['GET'])
@token_required
def get_unread_count():
    """Get the number of unread notifications"""
    count = Notification.get_unread_count(g.current_user.id)
    
    return jsonify({
        'unread_count': count
    }), 200

@notifications_bp.route('/<notification_id>/mark-read', methods=['POST'])
@token_required
def mark_notification_read(notification_id):
    """Mark a notification as read"""
    notification = Notification.query.filter_by(
        id=notification_id,
        user_id=g.current_user.id
    ).first()
    
    if not notification:
        return jsonify({'error': 'Notification not found'}), 404
    
    notification.mark_as_read()
    
    return jsonify({
        'message': 'Notification marked as read'
    }), 200

@notifications_bp.route('/mark-all-read', methods=['POST'])
@token_required
def mark_all_notifications_read():
    """Mark all notifications as read"""
    Notification.query.filter_by(
        user_id=g.current_user.id,
        is_read=False
    ).update({'is_read': True})
    
    db.session.commit()
    
    return jsonify({
        'message': 'All notifications marked as read'
    }), 200

@notifications_bp.route('/<notification_id>', methods=['DELETE'])
@token_required
def delete_notification(notification_id):
    """Delete a notification"""
    notification = Notification.query.filter_by(
        id=notification_id,
        user_id=g.current_user.id
    ).first()
    
    if not notification:
        return jsonify({'error': 'Notification not found'}), 404
    
    db.session.delete(notification)
    db.session.commit()
    
    return jsonify({
        'message': 'Notification deleted successfully'
    }), 200

