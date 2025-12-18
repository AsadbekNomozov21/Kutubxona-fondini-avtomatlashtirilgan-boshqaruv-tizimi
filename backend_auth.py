"""
Autentifikatsiya va Avtorizatsiya
JWT token, parol xavfsizligi
"""

from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
import os
from dotenv import load_dotenv

from database import get_db
from models import Librarian

load_dotenv()

# Parol hashing sozlamalari
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 sozlamalari
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

# JWT sozlamalari
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-this-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 soat

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Parolni tekshirish
    Args:
        plain_password: Oddiy text parol
        hashed_password: Hashed parol
    Returns:
        bool: Agar parol to'g'ri bo'lsa True
    """
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """
    Parolni hash qilish
    Args:
        password: Oddiy text parol
    Returns:
        str: Hashed parol
    """
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    JWT access token yaratish
    Args:
        data: Token ichiga qo'yiladigan ma'lumotlar (user_id, role)
        expires_delta: Token amal qilish muddati
    Returns:
        str: JWT token
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    
    return encoded_jwt

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> Librarian:
    """
    JWT token dan joriy foydalanuvchini olish
    Args:
        token: JWT access token
        db: Database session
    Returns:
        Librarian: Joriy foydalanuvchi
    Raises:
        HTTPException: Agar token noto'g'ri yoki foydalanuvchi topilmasa
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Autentifikatsiya ma'lumotlarini tekshirib bo'lmadi",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        # Tokenni decode qilish
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        
        if user_id is None:
            raise credentials_exception
            
    except JWTError:
        raise credentials_exception
    
    # Foydalanuvchini bazadan olish
    user = db.query(Librarian).filter(Librarian.librarian_id == user_id).first()
    
    if user is None:
        raise credentials_exception
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Foydalanuvchi faol emas"
        )
    
    return user

async def get_current_admin(
    current_user: Librarian = Depends(get_current_user)
) -> Librarian:
    """
    Faqat admin foydalanuvchilar uchun
    Args:
        current_user: Joriy foydalanuvchi
    Returns:
        Librarian: Admin foydalanuvchi
    Raises:
        HTTPException: Agar foydalanuvchi admin bo'lmasa
    """
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bu operatsiya uchun admin huquqi kerak"
        )
    
    return current_user

def create_default_admin(db: Session):
    """
    Default admin yaratish (birinchi ishga tushirishda)
    Email: admin@library.uz
    Password: admin123
    """
    existing_admin = db.query(Librarian).filter(
        Librarian.email == "admin@library.uz"
    ).first()
    
    if not existing_admin:
        admin = Librarian(
            full_name="Admin Adminov",
            email="admin@library.uz",
            phone="+998901234567",
            password_hash=get_password_hash("admin123"),
            shift="morning",
            role="admin",
            is_active=True
        )
        db.add(admin)
        db.commit()
        print("✅ Default admin yaratildi: admin@library.uz / admin123")