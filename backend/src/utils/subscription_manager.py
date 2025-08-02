from datetime import datetime, timedelta
from src.models import db
from src.models.subscription import Subscription, SubscriptionPlan
from src.models.organization import Organization
from src.models.user import User

class SubscriptionManager:
    """Gestionnaire des abonnements et des limites"""
    
    @staticmethod
    def check_subscription_limits(organization_id: str, feature: str) -> dict:
        """Vérifier les limites d'abonnement pour une fonctionnalité"""
        organization = Organization.query.get(organization_id)
        if not organization:
            return {'allowed': False, 'reason': 'Organization not found'}
        
        subscription = Subscription.query.filter_by(
            organization_id=organization_id,
            status='active'
        ).first()
        
        if not subscription:
            # Utiliser les limites du plan gratuit
            return SubscriptionManager._check_free_plan_limits(organization_id, feature)
        
        plan = subscription.plan
        if not plan:
            return {'allowed': False, 'reason': 'Subscription plan not found'}
        
        # Vérifier les limites selon le plan
        return SubscriptionManager._check_plan_limits(organization_id, plan, feature)
    
    @staticmethod
    def _check_free_plan_limits(organization_id: str, feature: str) -> dict:
        """Vérifier les limites du plan gratuit"""
        limits = {
            'max_users': 5,
            'max_modules': 3,
            'max_storage_mb': 100,
            'ai_requests_per_month': 50,
            'forum_posts_per_day': 10
        }
        
        if feature == 'users':
            current_users = User.query.filter_by(
                organization_id=organization_id,
                is_active=True
            ).count()
            
            return {
                'allowed': current_users < limits['max_users'],
                'current': current_users,
                'limit': limits['max_users'],
                'reason': f'Free plan limited to {limits["max_users"]} users'
            }
        
        elif feature == 'modules':
            from src.models.learning import LearningModule
            current_modules = LearningModule.query.filter_by(
                organization_id=organization_id,
                is_active=True
            ).count()
            
            return {
                'allowed': current_modules < limits['max_modules'],
                'current': current_modules,
                'limit': limits['max_modules'],
                'reason': f'Free plan limited to {limits["max_modules"]} learning modules'
            }
        
        elif feature == 'ai_requests':
            # Compter les requêtes IA du mois en cours
            from src.models.analytics import AnalyticsEvent
            start_of_month = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            
            ai_requests = AnalyticsEvent.query.filter(
                AnalyticsEvent.organization_id == organization_id,
                AnalyticsEvent.event_type == 'ai_request',
                AnalyticsEvent.created_at >= start_of_month
            ).count()
            
            return {
                'allowed': ai_requests < limits['ai_requests_per_month'],
                'current': ai_requests,
                'limit': limits['ai_requests_per_month'],
                'reason': f'Free plan limited to {limits["ai_requests_per_month"]} AI requests per month'
            }
        
        elif feature == 'premium_content':
            return {
                'allowed': False,
                'reason': 'Premium content requires a paid subscription'
            }
        
        return {'allowed': True}
    
    @staticmethod
    def _check_plan_limits(organization_id: str, plan: SubscriptionPlan, feature: str) -> dict:
        """Vérifier les limites d'un plan payant"""
        features = plan.features or {}
        
        if feature == 'users':
            max_users = plan.max_users or features.get('max_users', 999999)
            current_users = User.query.filter_by(
                organization_id=organization_id,
                is_active=True
            ).count()
            
            return {
                'allowed': current_users < max_users,
                'current': current_users,
                'limit': max_users,
                'reason': f'{plan.name} plan limited to {max_users} users'
            }
        
        elif feature == 'modules':
            max_modules = features.get('max_modules', 999999)
            from src.models.learning import LearningModule
            current_modules = LearningModule.query.filter_by(
                organization_id=organization_id,
                is_active=True
            ).count()
            
            return {
                'allowed': current_modules < max_modules,
                'current': current_modules,
                'limit': max_modules,
                'reason': f'{plan.name} plan limited to {max_modules} learning modules'
            }
        
        elif feature == 'ai_requests':
            max_requests = features.get('ai_requests_per_month', 999999)
            from src.models.analytics import AnalyticsEvent
            start_of_month = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            
            ai_requests = AnalyticsEvent.query.filter(
                AnalyticsEvent.organization_id == organization_id,
                AnalyticsEvent.event_type == 'ai_request',
                AnalyticsEvent.created_at >= start_of_month
            ).count()
            
            return {
                'allowed': ai_requests < max_requests,
                'current': ai_requests,
                'limit': max_requests,
                'reason': f'{plan.name} plan limited to {max_requests} AI requests per month'
            }
        
        elif feature == 'premium_content':
            return {
                'allowed': features.get('premium_content', True),
                'reason': 'Premium content included in this plan'
            }
        
        elif feature == 'analytics':
            return {
                'allowed': features.get('advanced_analytics', True),
                'reason': 'Advanced analytics included in this plan'
            }
        
        elif feature == 'api_access':
            return {
                'allowed': features.get('api_access', True),
                'reason': 'API access included in this plan'
            }
        
        return {'allowed': True}
    
    @staticmethod
    def get_subscription_status(organization_id: str) -> dict:
        """Obtenir le statut complet de l'abonnement"""
        organization = Organization.query.get(organization_id)
        if not organization:
            return {'error': 'Organization not found'}
        
        subscription = Subscription.query.filter_by(
            organization_id=organization_id
        ).order_by(Subscription.created_at.desc()).first()
        
        if not subscription:
            return {
                'plan': 'free',
                'status': 'active',
                'trial': False,
                'days_remaining': None,
                'features': {
                    'max_users': 5,
                    'max_modules': 3,
                    'premium_content': False,
                    'advanced_analytics': False,
                    'api_access': False
                }
            }
        
        plan = subscription.plan
        now = datetime.utcnow()
        
        # Vérifier si c'est une période d'essai
        is_trial = (
            subscription.status in ['trialing', 'active'] and
            subscription.current_period_end and
            (subscription.current_period_end - subscription.current_period_start).days <= 14
        )
        
        days_remaining = None
        if subscription.current_period_end:
            days_remaining = (subscription.current_period_end - now).days
            if days_remaining < 0:
                days_remaining = 0
        
        return {
            'plan': plan.name,
            'status': subscription.status,
            'trial': is_trial,
            'days_remaining': days_remaining,
            'cancel_at_period_end': subscription.cancel_at_period_end,
            'current_period_end': subscription.current_period_end.isoformat() if subscription.current_period_end else None,
            'features': plan.features or {}
        }
    
    @staticmethod
    def track_usage(organization_id: str, feature: str, amount: int = 1):
        """Suivre l'utilisation d'une fonctionnalité"""
        from src.models.analytics import AnalyticsEvent
        
        AnalyticsEvent.track_event(
            event_type=f'usage_{feature}',
            organization_id=organization_id,
            event_data={'amount': amount}
        )
    
    @staticmethod
    def get_usage_stats(organization_id: str, period_days: int = 30) -> dict:
        """Obtenir les statistiques d'utilisation"""
        from src.models.analytics import AnalyticsEvent
        from src.models.learning import LearningModule
        from src.models.user import User
        
        start_date = datetime.utcnow() - timedelta(days=period_days)
        
        # Utilisateurs actifs
        active_users = User.query.filter_by(
            organization_id=organization_id,
            is_active=True
        ).count()
        
        # Modules créés
        modules_count = LearningModule.query.filter_by(
            organization_id=organization_id,
            is_active=True
        ).count()
        
        # Requêtes IA
        ai_requests = AnalyticsEvent.query.filter(
            AnalyticsEvent.organization_id == organization_id,
            AnalyticsEvent.event_type == 'ai_request',
            AnalyticsEvent.created_at >= start_date
        ).count()
        
        # Connexions
        logins = AnalyticsEvent.query.filter(
            AnalyticsEvent.organization_id == organization_id,
            AnalyticsEvent.event_type == 'user_login',
            AnalyticsEvent.created_at >= start_date
        ).count()
        
        return {
            'period_days': period_days,
            'active_users': active_users,
            'modules_count': modules_count,
            'ai_requests': ai_requests,
            'logins': logins,
            'start_date': start_date.isoformat(),
            'end_date': datetime.utcnow().isoformat()
        }

def require_subscription_limit(feature: str):
    """Décorateur pour vérifier les limites d'abonnement"""
    def decorator(f):
        from functools import wraps
        from flask import g, jsonify
        
        @wraps(f)
        def decorated(*args, **kwargs):
            if not hasattr(g, 'current_user') or not g.current_user.organization_id:
                return jsonify({'error': 'Organization required'}), 403
            
            limit_check = SubscriptionManager.check_subscription_limits(
                g.current_user.organization_id, 
                feature
            )
            
            if not limit_check['allowed']:
                return jsonify({
                    'error': 'Subscription limit exceeded',
                    'reason': limit_check['reason'],
                    'current': limit_check.get('current'),
                    'limit': limit_check.get('limit'),
                    'upgrade_required': True
                }), 402  # Payment Required
            
            return f(*args, **kwargs)
        
        return decorated
    return decorator

