"""
Input validation and sanitization utilities for enhanced security
"""
import re
import html
import bleach
from typing import Any, Dict, List, Optional, Union
from marshmallow import Schema, fields, ValidationError, validates_schema
from email_validator import validate_email, EmailNotValidError


class ValidationError(Exception):
    """Custom validation error"""
    def __init__(self, message: str, field: str = None):
        self.message = message
        self.field = field
        super().__init__(message)


class InputValidator:
    """Comprehensive input validation and sanitization"""
    
    # Common regex patterns
    PATTERNS = {
        'email': re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'),
        'phone': re.compile(r'^\+?1?-?\.?\s?\(?([0-9]{3})\)?[-.\s]?([0-9]{3})[-.\s]?([0-9]{4})$'),
        'url': re.compile(r'^https?:\/\/(www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b([-a-zA-Z0-9()@:%_\+.~#?&//=]*)$'),
        'uuid': re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'),
        'slug': re.compile(r'^[a-z0-9]+(?:-[a-z0-9]+)*$'),
        'username': re.compile(r'^[a-zA-Z0-9_]{3,20}$'),
        'password': re.compile(r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$')
    }
    
    # Dangerous patterns to block
    DANGEROUS_PATTERNS = [
        r'<script[^>]*>.*?</script>',
        r'javascript:',
        r'vbscript:',
        r'onload\s*=',
        r'onerror\s*=',
        r'onclick\s*=',
        r'onmouseover\s*=',
        r'eval\s*\(',
        r'expression\s*\(',
        r'<iframe[^>]*>',
        r'<object[^>]*>',
        r'<embed[^>]*>',
        r'<link[^>]*>',
        r'<meta[^>]*>',
        r'<style[^>]*>.*?</style>',
        r'data:text/html',
        r'data:application/javascript'
    ]
    
    @classmethod
    def sanitize_string(cls, value: str, max_length: int = None, allow_html: bool = False) -> str:
        """Sanitize string input"""
        if not isinstance(value, str):
            raise ValidationError("Value must be a string")
        
        # Remove null bytes
        value = value.replace('\x00', '')
        
        # Check for dangerous patterns
        for pattern in cls.DANGEROUS_PATTERNS:
            if re.search(pattern, value, re.IGNORECASE):
                raise ValidationError("Input contains potentially dangerous content")
        
        if allow_html:
            # Allow only safe HTML tags
            allowed_tags = ['p', 'br', 'strong', 'em', 'u', 'ol', 'ul', 'li', 'a', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6']
            allowed_attributes = {'a': ['href', 'title']}
            value = bleach.clean(value, tags=allowed_tags, attributes=allowed_attributes, strip=True)
        else:
            # Escape HTML entities
            value = html.escape(value)
        
        # Trim whitespace
        value = value.strip()
        
        # Check length
        if max_length and len(value) > max_length:
            raise ValidationError(f"Value exceeds maximum length of {max_length} characters")
        
        return value
    
    @classmethod
    def validate_email(cls, email: str) -> str:
        """Validate and normalize email address"""
        try:
            # Use email-validator library for comprehensive validation
            validated_email = validate_email(email)
            return validated_email.email.lower()
        except EmailNotValidError as e:
            raise ValidationError(f"Invalid email address: {str(e)}")
    
    @classmethod
    def validate_password(cls, password: str) -> bool:
        """Validate password strength"""
        if len(password) < 8:
            raise ValidationError("Password must be at least 8 characters long")
        
        if len(password) > 128:
            raise ValidationError("Password must be less than 128 characters")
        
        if not re.search(r'[a-z]', password):
            raise ValidationError("Password must contain at least one lowercase letter")
        
        if not re.search(r'[A-Z]', password):
            raise ValidationError("Password must contain at least one uppercase letter")
        
        if not re.search(r'\d', password):
            raise ValidationError("Password must contain at least one digit")
        
        if not re.search(r'[@$!%*?&]', password):
            raise ValidationError("Password must contain at least one special character (@$!%*?&)")
        
        # Check for common weak passwords
        weak_passwords = [
            'password', '12345678', 'qwerty', 'abc123', 'password123',
            'admin', 'letmein', 'welcome', 'monkey', '1234567890'
        ]
        
        if password.lower() in weak_passwords:
            raise ValidationError("Password is too common")
        
        return True
    
    @classmethod
    def validate_url(cls, url: str) -> str:
        """Validate URL format"""
        if not cls.PATTERNS['url'].match(url):
            raise ValidationError("Invalid URL format")
        
        # Ensure HTTPS in production
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        
        return url
    
    @classmethod
    def validate_phone(cls, phone: str) -> str:
        """Validate and normalize phone number"""
        # Remove all non-digit characters except +
        cleaned = re.sub(r'[^\d+]', '', phone)
        
        if not cls.PATTERNS['phone'].match(phone):
            raise ValidationError("Invalid phone number format")
        
        return cleaned
    
    @classmethod
    def validate_file_upload(cls, file, allowed_extensions: set = None, max_size: int = None):
        """Validate file upload"""
        if not file or not file.filename:
            raise ValidationError("No file provided")
        
        # Check file extension
        if allowed_extensions:
            ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''
            if ext not in allowed_extensions:
                raise ValidationError(f"File type not allowed. Allowed types: {', '.join(allowed_extensions)}")
        
        # Check file size
        if max_size:
            file.seek(0, 2)  # Seek to end
            size = file.tell()
            file.seek(0)  # Reset to beginning
            
            if size > max_size:
                raise ValidationError(f"File size exceeds maximum of {max_size} bytes")
        
        # Check for dangerous file content
        file.seek(0)
        content = file.read(1024).decode('utf-8', errors='ignore')
        file.seek(0)
        
        for pattern in cls.DANGEROUS_PATTERNS:
            if re.search(pattern, content, re.IGNORECASE):
                raise ValidationError("File contains potentially dangerous content")
        
        return True


# Marshmallow schemas for API validation
class UserRegistrationSchema(Schema):
    email = fields.Email(required=True)
    password = fields.Str(required=True, validate=lambda x: InputValidator.validate_password(x))
    first_name = fields.Str(required=True, validate=lambda x: len(x.strip()) >= 2)
    last_name = fields.Str(required=True, validate=lambda x: len(x.strip()) >= 2)
    terms_accepted = fields.Bool(required=True, validate=lambda x: x is True)
    marketing_consent = fields.Bool(missing=False)


class UserLoginSchema(Schema):
    email = fields.Email(required=True)
    password = fields.Str(required=True)
    remember_me = fields.Bool(missing=False)


class PasswordResetSchema(Schema):
    token = fields.Str(required=True)
    password = fields.Str(required=True, validate=lambda x: InputValidator.validate_password(x))
    confirm_password = fields.Str(required=True)
    
    @validates_schema
    def validate_passwords_match(self, data, **kwargs):
        if data['password'] != data['confirm_password']:
            raise ValidationError('Passwords do not match')


class ProfileUpdateSchema(Schema):
    first_name = fields.Str(validate=lambda x: len(x.strip()) >= 2 if x else True)
    last_name = fields.Str(validate=lambda x: len(x.strip()) >= 2 if x else True)
    bio = fields.Str(validate=lambda x: len(x) <= 500 if x else True)
    location = fields.Str(validate=lambda x: len(x) <= 100 if x else True)
    website = fields.Url()
    linkedin_url = fields.Url()
    twitter_url = fields.Url()
    github_url = fields.Url()


def validate_request_data(schema_class: Schema, data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate request data using Marshmallow schema"""
    try:
        schema = schema_class()
        return schema.load(data)
    except ValidationError as e:
        raise ValidationError(f"Validation failed: {e.messages}")


def sanitize_dict(data: Dict[str, Any], max_string_length: int = 1000) -> Dict[str, Any]:
    """Recursively sanitize dictionary data"""
    sanitized = {}
    
    for key, value in data.items():
        # Sanitize key
        clean_key = InputValidator.sanitize_string(str(key), max_length=100)
        
        # Sanitize value based on type
        if isinstance(value, str):
            sanitized[clean_key] = InputValidator.sanitize_string(value, max_length=max_string_length)
        elif isinstance(value, dict):
            sanitized[clean_key] = sanitize_dict(value, max_string_length)
        elif isinstance(value, list):
            sanitized[clean_key] = [
                InputValidator.sanitize_string(str(item), max_length=max_string_length) 
                if isinstance(item, str) else item 
                for item in value
            ]
        else:
            sanitized[clean_key] = value
    
    return sanitized
