from datetime import datetime, timedelta
from typing import Optional, Tuple
from jose import JWTError, jwt
from passlib.context import CryptContext
from core.config import get_settings
from core.exceptions import AuthenticationError
from core.security import SecurityConfig
from repositories.base import Repository
from domain.models import User, UserCreate, UserInDB, Token, TokenData

settings = get_settings()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class AuthService:
    def __init__(self):
        self.repository = Repository(UserInDB, "users")

    def get_password_hash(self, password: str) -> str:
        """Hash a password using bcrypt"""
        return pwd_context.hash(password)

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash"""
        return pwd_context.verify(plain_password, hashed_password)

    def create_access_token(self, data: dict, expires_delta: Optional[timedelta] = None) -> str:
        """Create a JWT access token"""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=15)
        to_encode.update({"exp": expire})
        return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

    def create_refresh_token(self, data: dict) -> str:
        """Create a JWT refresh token"""
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        to_encode.update({"exp": expire})
        return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

    async def create_user(self, user: UserCreate) -> User:
        """Create a new user with hashed password"""
        # Check if user exists - we don't need sensitive fields for this check
        existing_users = await self.repository.list({"email": user.email}, include_sensitive=False)
        if existing_users:
            raise AuthenticationError("Email already registered")

        if user.username:
            existing_users = await self.repository.list({"username": user.username}, include_sensitive=False)
            if existing_users:
                raise AuthenticationError("Username already taken")

        # Create new user with hashed password
        user_dict = user.dict(exclude={'password'})
        user_dict["password"] = self.get_password_hash(user.password)
        
        # Create user with sensitive data
        user_in_db = await self.repository.create(user_dict)
        
        # Return sanitized user data
        return User(**user_in_db.dict(exclude={'password'}))

    async def authenticate_user(self, login: str, password: str) -> Optional[User]:
        """Authenticate a user by email/username and password"""
        # Find user by email or username with sensitive data
        users = await self.repository.list({
            "$or": [
                {"email": login},
                {"username": login}
            ]
        }, include_sensitive=True)
        
        if not users:
            return None

        user_in_db = users[0]
        if not self.verify_password(password, user_in_db.password):
            return None

        # Return sanitized user data
        return User(**user_in_db.dict(exclude={'password'}))

    async def get_current_user(self, token: str) -> User:
        """Get current user from JWT token"""
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            user_id: str = payload.get("sub")
            if user_id is None:
                raise AuthenticationError("Invalid token")
        except JWTError:
            raise AuthenticationError("Invalid token")

        user_in_db = await self.repository.get(user_id, include_sensitive=True)
        if user_in_db is None:
            raise AuthenticationError("User not found")
        return User(**user_in_db.dict(exclude={'password'}))

    async def refresh_access_token(self, refresh_token: str) -> str:
        """Refresh an access token using a refresh token"""
        try:
            payload = jwt.decode(refresh_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            user_id: str = payload.get("sub")
            if user_id is None:
                raise AuthenticationError("Invalid refresh token")

            user_in_db = await self.repository.get(user_id, include_sensitive=True)
            if user_in_db is None:
                raise AuthenticationError("User not found")

            access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_HOURS)
            return self.create_access_token(
                data={"sub": str(user_id)},
                expires_delta=access_token_expires
            )
        except JWTError:
            raise AuthenticationError("Invalid refresh token")

    async def check_availability(self, email: Optional[str] = None, username: Optional[str] = None) -> Tuple[bool, str]:
        """Check if email and/or username are available"""
        if not email and not username:
            return False, "At least one field (email or username) must be provided"

        query = {}
        if email:
            query["email"] = email
        if username:
            query["username"] = username

        existing_users = await self.repository.list(query, include_sensitive=False)
        
        if not existing_users:
            return True, "All checked fields are available"
        
        # Determine which fields are taken
        taken_fields = []
        for user in existing_users:
            if email and user.email == email:
                taken_fields.append("email")
            if username and user.username == username:
                taken_fields.append("username")
        
        return False, f"Following fields are already taken: {', '.join(taken_fields)}" 