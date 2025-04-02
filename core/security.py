from typing import Any, Dict, Set
from pydantic import BaseModel
from core.exceptions import ValidationError

class SecurityConfig:
    """Security configuration and utilities"""
    
    @staticmethod
    def sanitize_dict(data: Dict[str, Any], sensitive_fields: Set[str]) -> Dict[str, Any]:
        """Remove sensitive fields from dictionary"""
        return {k: v for k, v in data.items() if k not in sensitive_fields}
    
    @staticmethod
    def validate_password_strength(password: str) -> bool:
        """Validate password strength"""
        if len(password) < 8:
            return False
        if not any(c.isupper() for c in password):
            return False
        if not any(c.islower() for c in password):
            return False
        if not any(c.isdigit() for c in password):
            return False
        if not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
            return False
        return True

    @staticmethod
    def validate_password(password: str) -> None:
        """Validate password and raise exception if invalid"""
        if not SecurityConfig.validate_password_strength(password):
            raise ValidationError(
                "Password must be at least 8 characters long and contain at least one uppercase letter, "
                "one lowercase letter, one number, and one special character"
            ) 