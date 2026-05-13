import jwt
from datetime import datetime, timedelta
from typing import Optional, Dict, Any


SECRET_KEY = "payment-infrastructure-secret-key-change-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60


class JWTHandler:
    def __init__(self, secret_key: str = SECRET_KEY, algorithm: str = ALGORITHM):
        self.secret_key = secret_key
        self.algorithm = algorithm

    def create_token(self, data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
        to_encode = data.copy()
        
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        
        to_encode.update({"exp": expire, "iat": datetime.utcnow()})
        
        return jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)

    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None

    def decode_token(self, token: str) -> Optional[Dict[str, Any]]:
        return self.verify_token(token)


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    handler = JWTHandler()
    return handler.create_token(data, expires_delta)


def verify_access_token(token: str) -> Optional[Dict[str, Any]]:
    handler = JWTHandler()
    return handler.verify_token(token)