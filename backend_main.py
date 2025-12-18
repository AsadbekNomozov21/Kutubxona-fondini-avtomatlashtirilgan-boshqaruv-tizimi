"""
Kutubxona Boshqaruv Tizimi - Backend API
FastAPI asosida ishlab chiqilgan
"""

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta
import uvicorn

from database import get_db, engine, Base
from models import *
from schemas import *
from auth import (
    verify_password, 
    get_password_hash, 
    create_access_token, 
    get_current_user,
    get_current_admin
)

# Ma'lumotlar bazasi jadvallarini yaratish
Base.metadata.create_all(bind=engine)

# FastAPI ilovasini yaratish
app = FastAPI(
    title="Kutubxona Boshqaruv Tizimi API",
    description="To'liq funktsional kutubxona boshqaruv tizimi",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

# CORS sozlamalari (Frontend bilan ishlash uchun)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Production da aniq domenlarni ko'rsating
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =====================================================
# AUTHENTICATION ENDPOINTS
# =====================================================

@app.post("/api/auth/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """
    Tizimga kirish (Login)
    Email va parol orqali autentifikatsiya
    """
    librarian = db.query(Librarian).filter(
        Librarian.email == form_data.username
    ).first()
    
    if not librarian or not verify_password(form_data.password, librarian.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email yoki parol noto'g'ri",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not librarian.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Foydalanuvchi faol emas"
        )
    
    access_token = create_access_token(
        data={"sub": str(librarian.librarian_id), "role": librarian.role}
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": str(librarian.librarian_id),
            "full_name": librarian.full_name,
            "email": librarian.email,
            "role": librarian.role
        }
    }

@app.get("/api/auth/me", response_model=LibrarianResponse)
async def get_current_user_info(
    current_user: Librarian = Depends(get_current_user)
):
    """Joriy foydalanuvchi ma'lumotlari"""
    return current_user

# =====================================================
# MEMBERS ENDPOINTS (A'zolar)
# =====================================================

@app.get("/api/members", response_model=List[MemberResponse])
async def get_members(
    skip: int = 0,
    limit: int = 100,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: Librarian = Depends(get_current_user)
):
    """
    Barcha a'zolarni olish
    Qidiruv: ism, email, telefon bo'yicha
    """
    query = db.query(Member)
    
    if search:
        search_filter = f"%{search}%"
        query = query.filter(
            (Member.full_name.ilike(search_filter)) |
            (Member.email.ilike(search_filter)) |
            (Member.phone.ilike(search_filter))
        )
    
    members = query.offset(skip).limit(limit).all()
    return members

@app.get("/api/members/{member_id}", response_model=MemberDetailResponse)
async def get_member(
    member_id: str,
    db: Session = Depends(get_db),
    current_user: Librarian = Depends(get_current_user)
):
    """Bitta a'zo ma'lumotlari"""
    member = db.query(Member).filter(Member.member_id == member_id).first()
    if not member:
        raise HTTPException(status_code=404, detail="A'zo topilmadi")
    
    # A'zoning barcha borrowings va penalties larini olish
    borrowings = db.query(Borrowing).filter(Borrowing.member_id == member_id).all()
    penalties = db.query(Penalty).filter(Penalty.member_id == member_id).all()
    
    return {
        **member.__dict__,
        "borrowings": borrowings,
        "penalties": penalties
    }

@app.post("/api/members", response_model=MemberResponse, status_code=status.HTTP_201_CREATED)
async def create_member(
    member: MemberCreate,
    db: Session = Depends(get_db),
    current_user: Librarian = Depends(get_current_user)
):
    """Yangi a'zo qo'shish"""
    # Email tekshirish
    existing = db.query(Member).filter(Member.email == member.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Bu email allaqachon ro'yxatdan o'tgan")
    
    db_member = Member(**member.dict())
    db.add(db_member)
    db.commit()
    db.refresh(db_member)
    return db_member

@app.put("/api/members/{member_id}", response_model=MemberResponse)
async def update_member(
    member_id: str,
    member: MemberUpdate,
    db: Session = Depends(get_db),
    current_user: Librarian = Depends(get_current_user)
):
    """A'zo ma'lumotlarini yangilash"""
    db_member = db.query(Member).filter(Member.member_id == member_id).first()
    if not db_member:
        raise HTTPException(status_code=404, detail="A'zo topilmadi")
    
    update_data = member.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_member, key, value)
    
    db.commit()
    db.refresh(db_member)
    return db_member

@app.delete("/api/members/{member_id}")
async def delete_member(
    member_id: str,
    db: Session = Depends(get_db),
    current_user: Librarian = Depends(get_current_admin)
):
    """A'zoni o'chirish (faqat admin)"""
    member = db.query(Member).filter(Member.member_id == member_id).first()
    if not member:
        raise HTTPException(status_code=404, detail="A'zo topilmadi")
    
    db.delete(member)
    db.commit()
    return {"message": "A'zo muvaffaqiyatli o'chirildi"}

# =====================================================
# BOOKS ENDPOINTS (Kitoblar)
# =====================================================

@app.get("/api/books", response_model=List[BookResponse])
async def get_books(
    skip: int = 0,
    limit: int = 100,
    search: Optional[str] = None,
    genre: Optional[str] = None,
    available_only: bool = False,
    db: Session = Depends(get_db)
):
    """
    Barcha kitoblarni olish
    Qidiruv: nomi, muallif bo'yicha
    Filter: janr, mavjudlik
    """
    query = db.query(Book).filter(Book.is_active == True)
    
    if search:
        search_filter = f"%{search}%"
        query = query.filter(
            (Book.title.ilike(search_filter)) |
            (Book.author.ilike(search_filter))
        )
    
    if genre:
        query = query.filter(Book.genre == genre)
    
    if available_only:
        query = query.filter(Book.available_copies > 0)
    
    books = query.offset(skip).limit(limit).all()
    return books

@app.get("/api/books/{book_id}", response_model=BookDetailResponse)
async def get_book(
    book_id: str,
    db: Session = Depends(get_db)
):
    """Bitta kitob ma'lumotlari"""
    book = db.query(Book).filter(Book.book_id == book_id).first()
    