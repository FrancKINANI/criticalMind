"""
Comprehensive monitoring, logging, and metrics collection system
"""
import os
import time
import logging
import functools
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Callable
from flask import request, g, current_app
import sentry_sdk
from sentry_sdk.integrations.flask import FlaskIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
import redis
import json


class MetricsCollector:
    """Collect and store application metrics"""
    
    def __init__(self, redis_client=None):
        self.redis_client = redis_client or redis.from_url(
            os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
        )
        self.metrics_prefix = 'metrics:'
    
    def increment_counter(self, metric_name: str, value: int = 1, tags: Dict[str, str] = None):
        """Increment a counter metric"""
        key = f"{self.metrics_prefix}counter:{metric_name}"
        if tags:
            key += f":{self._serialize_tags(tags)}"
        
        self.redis_client.incr(key, value)
        self.redis_client.expire(key, 86400)  # Expire after 24 hours
    
    def record_gauge(self, metric_name: str, value: float, tags: Dict[str, str] = None):
        """Record a gauge metric"""
        key = f"{self.metrics_prefix}gauge:{metric_name}"
        if tags:
            key += f":{self._serialize_tags(tags)}"
        
        self.redis_client.set(key, value, ex=86400)
    
    def record_histogram(self, metric_name: str, value: float, tags: Dict[str, str] = None):
        """Record a histogram metric"""
        key = f"{self.metrics_prefix}histogram:{metric_name}"
        if tags:
            key += f":{self._serialize_tags(tags)}"
        
        # Store in a sorted set with timestamp as score
        timestamp = time.time()
        self.redis_client.zadd(key, {str(value): timestamp})
        self.redis_client.expire(key, 86400)
    
    def record_timing(self, metric_name: str, duration: float, tags: Dict[str, str] = None):
        """Record timing information"""
        self.record_histogram(f"{metric_name}.duration", duration, tags)
        self.increment_counter(f"{metric_name}.count", tags=tags)
    
    def get_metrics(self, metric_type: str = None, metric_name: str = None) -> Dict[str, Any]:
        """Retrieve metrics from Redis"""
        pattern = f"{self.metrics_prefix}"
        if metric_type:
            pattern += f"{metric_type}:"
        if metric_name:
            pattern += f"{metric_name}:"
        pattern += "*"
        
        keys = self.redis_client.keys(pattern)
        metrics = {}
        
        for key in keys:
            key_str = key.decode('utf-8')
            if 'counter:' in key_str or 'gauge:' in key_str:
                value = self.redis_client.get(key)
                metrics[key_str] = float(value) if value else 0
            elif 'histogram:' in key_str:
                values = self.redis_client.zrange(key, 0, -1, withscores=True)
                metrics[key_str] = [(float(v[0]), v[1]) for v in values]
        
        return metrics
    
    def _serialize_tags(self, tags: Dict[str, str]) -> str:
        """Serialize tags for use in Redis keys"""
        return ','.join(f"{k}={v}" for k, v in sorted(tags.items()))


class PerformanceMonitor:
    """Monitor application performance"""
    
    def __init__(self, metrics_collector: MetricsCollector):
        self.metrics = metrics_collector
    
    def time_function(self, metric_name: str = None, tags: Dict[str, str] = None):
        """Decorator to time function execution"""
        def decorator(func: Callable):
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                start_time = time.time()
                try:
                    result = func(*args, **kwargs)
                    status = 'success'
                    return result
                except Exception as e:
                    status = 'error'
                    raise
                finally:
                    duration = time.time() - start_time
                    name = metric_name or f"{func.__module__}.{func.__name__}"
                    final_tags = {'status': status}
                    if tags:
                        final_tags.update(tags)
                    self.metrics.record_timing(name, duration, final_tags)
            return wrapper
        return decorator
    
    def monitor_request(self):
        """Monitor HTTP request performance"""
        def decorator(func: Callable):
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                start_time = time.time()
                
                # Record request start
                self.metrics.increment_counter('http.requests.total', tags={
                    'method': request.method,
                    'endpoint': request.endpoint or 'unknown'
                })
                
                try:
                    result = func(*args, **kwargs)
                    status_code = getattr(result, 'status_code', 200)
                    status = 'success' if status_code < 400 else 'error'
                    return result
                except Exception as e:
                    status_code = 500
                    status = 'error'
                    raise
                finally:
                    duration = time.time() - start_time
                    
                    # Record metrics
                    tags = {
                        'method': request.method,
                        'endpoint': request.endpoint or 'unknown',
                        'status_code': str(status_code),
                        'status': status
                    }
                    
                    self.metrics.record_timing('http.request', duration, tags)
                    self.metrics.increment_counter('http.responses.total', tags=tags)
                    
                    # Record slow requests
                    if duration > 1.0:  # Requests taking more than 1 second
                        self.metrics.increment_counter('http.requests.slow', tags=tags)
            
            return wrapper
        return decorator


class SecurityMonitor:
    """Monitor security events and potential threats"""
    
    def __init__(self, metrics_collector: MetricsCollector):
        self.metrics = metrics_collector
        self.logger = logging.getLogger('security')
    
    def log_security_event(self, event_type: str, details: Dict[str, Any], severity: str = 'info'):
        """Log security events"""
        event_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'event_type': event_type,
            'ip_address': request.remote_addr if request else None,
            'user_agent': request.headers.get('User-Agent') if request else None,
            'user_id': getattr(g, 'current_user', {}).get('id') if hasattr(g, 'current_user') else None,
            'details': details,
            'severity': severity
        }
        
        # Log to application logger
        log_message = f"Security Event: {event_type} - {details}"
        if severity == 'critical':
            self.logger.critical(log_message, extra=event_data)
        elif severity == 'warning':
            self.logger.warning(log_message, extra=event_data)
        else:
            self.logger.info(log_message, extra=event_data)
        
        # Record metrics
        self.metrics.increment_counter('security.events.total', tags={
            'event_type': event_type,
            'severity': severity
        })
        
        # Send to Sentry for critical events
        if severity == 'critical':
            sentry_sdk.capture_message(log_message, level='error', extra=event_data)
    
    def monitor_failed_logins(self, email: str, ip_address: str):
        """Monitor failed login attempts"""
        key = f"failed_logins:{ip_address}"
        attempts = self.metrics.redis_client.incr(key)
        self.metrics.redis_client.expire(key, 3600)  # Reset after 1 hour
        
        if attempts >= 5:
            self.log_security_event('excessive_failed_logins', {
                'email': email,
                'ip_address': ip_address,
                'attempts': attempts
            }, severity='warning')
        
        if attempts >= 10:
            self.log_security_event('potential_brute_force', {
                'email': email,
                'ip_address': ip_address,
                'attempts': attempts
            }, severity='critical')
    
    def monitor_suspicious_activity(self, activity_type: str, details: Dict[str, Any]):
        """Monitor suspicious user activity"""
        self.log_security_event('suspicious_activity', {
            'activity_type': activity_type,
            **details
        }, severity='warning')


class ApplicationLogger:
    """Centralized application logging"""
    
    @staticmethod
    def setup_logging(app):
        """Setup comprehensive logging for the application"""
        
        # Create logs directory if it doesn't exist
        log_dir = os.path.join(os.path.dirname(app.root_path), 'logs')
        os.makedirs(log_dir, exist_ok=True)
        
        # Configure root logger
        logging.basicConfig(
            level=getattr(logging, app.config.get('LOG_LEVEL', 'INFO')),
            format=app.config.get('LOG_FORMAT', '%(asctime)s - %(name)s - %(levelname)s - %(message)s'),
            handlers=[
                logging.FileHandler(os.path.join(log_dir, 'app.log')),
                logging.StreamHandler()
            ]
        )
        
        # Configure specific loggers
        loggers = {
            'security': os.path.join(log_dir, 'security.log'),
            'performance': os.path.join(log_dir, 'performance.log'),
            'errors': os.path.join(log_dir, 'errors.log'),
            'audit': os.path.join(log_dir, 'audit.log')
        }
        
        for logger_name, log_file in loggers.items():
            logger = logging.getLogger(logger_name)
            handler = logging.FileHandler(log_file)
            handler.setFormatter(logging.Formatter(app.config.get('LOG_FORMAT')))
            logger.addHandler(handler)
            logger.setLevel(getattr(logging, app.config.get('LOG_LEVEL', 'INFO')))
        
        # Setup Sentry for error tracking
        if app.config.get('SENTRY_DSN'):
            sentry_sdk.init(
                dsn=app.config['SENTRY_DSN'],
                integrations=[
                    FlaskIntegration(transaction_style='endpoint'),
                    SqlalchemyIntegration()
                ],
                traces_sample_rate=0.1,
                environment=app.config.get('FLASK_ENV', 'production')
            )


def init_monitoring(app):
    """Initialize monitoring system"""
    
    # Setup logging
    ApplicationLogger.setup_logging(app)
    
    # Initialize metrics collector
    metrics_collector = MetricsCollector()
    
    # Initialize monitors
    performance_monitor = PerformanceMonitor(metrics_collector)
    security_monitor = SecurityMonitor(metrics_collector)
    
    # Store in app context
    app.metrics = metrics_collector
    app.performance_monitor = performance_monitor
    app.security_monitor = security_monitor
    
    # Setup request monitoring
    @app.before_request
    def before_request():
        g.start_time = time.time()
        g.request_id = f"req_{int(time.time())}_{os.urandom(4).hex()}"
    
    @app.after_request
    def after_request(response):
        # Record request metrics
        if hasattr(g, 'start_time'):
            duration = time.time() - g.start_time
            
            tags = {
                'method': request.method,
                'endpoint': request.endpoint or 'unknown',
                'status_code': str(response.status_code)
            }
            
            metrics_collector.record_timing('http.request', duration, tags)
            metrics_collector.increment_counter('http.responses.total', tags=tags)
        
        # Add monitoring headers
        response.headers['X-Request-ID'] = getattr(g, 'request_id', 'unknown')
        response.headers['X-Response-Time'] = str(int((time.time() - getattr(g, 'start_time', time.time())) * 1000))
        
        return response
    
    return app
