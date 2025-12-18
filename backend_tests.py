"""
Kutubxona Boshqaruv Tizimi - API Tests
pytest bilan avtomatik testlar
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import date, timedelta

from main import app
from database import Base, get_db
from models import *
from auth import get_password_hash

# Test database
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Dependency override
def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

# Test client
client = TestClient(app)

# =====================================================
# FIXTURES
# =====================================================

@pytest.fixture(scope="module")
def setup_database():
    """Test uchun database yaratish"""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def db_session():
    """Database session"""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

@pytest.fixture
def admin_token(db_session):
    """Admin token yaratish"""
    # Admin yaratish
    admin = Librarian(
        full_name="Test Admin",
        email="admin@test.com",
        password_hash=get_password_hash("admin123"),
        role="admin",
        shift="morning"
    )
    db_session.add(admin)
    db_session.commit()
    
    # Login
    response = client.post(
        "/api/auth/login",
        data={"username": "admin@test.com", "password": "admin123"}
    )
    return response.json()["access_token"]

@pytest.fixture
def test_member(db_session):
    """Test a'zo yaratish"""
    member = Member(
        full_name="Test Member",
        email="member@test.com",
        phone="+998901234567",
        address="Test address"
    )
    db_session.add(member)
    db_session.commit()
    db_session.refresh(member)
    return member

@pytest.fixture
def test_book(db_session):
    """Test kitob yaratish"""
    book = Book(
        title="Test Book",
        author="Test Author",
        genre="Test Genre",
        publisher="Test Publisher",
        year=2024,
        isbn="1234567890",
        total_copies=5,
        available_copies=5
    )
    db_session.add(book)
    db_session.commit()
    db_session.refresh(book)
    return book

# =====================================================
# AUTHENTICATION TESTS
# =====================================================

def test_login_success(setup_database, db_session):
    """Muvaffaqiyatli login"""
    # Admin yaratish
    admin = Librarian(
        full_name="Admin",
        email="login@test.com",
        password_hash=get_password_hash("password123"),
        role="admin"
    )
    db_session.add(admin)
    db_session.commit()
    
    # Login
    response = client.post(
        "/api/auth/login",
        data={"username": "login@test.com", "password": "password123"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

def test_login_invalid_credentials(setup_database):
    """Noto'g'ri login"""
    response = client.post(
        "/api/auth/login",
        data={"username": "wrong@test.com", "password": "wrong"}
    )
    assert response.status_code == 401

def test_get_current_user(setup_database, admin_token):
    """Joriy foydalanuvchi ma'lumotlari"""
    response = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "email" in data
    assert "role" in data

# =====================================================
# BOOKS TESTS
# =====================================================

def test_get_books(setup_database, admin_token):
    """Barcha kitoblarni olish"""
    response = client.get(
        "/api/books",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_create_book(setup_database, admin_token):
    """Yangi kitob yaratish"""
    book_data = {
        "title": "New Test Book",
        "author": "New Author",
        "genre": "Fiction",
        "publisher": "Publisher",
        "year": 2024,
        "total_copies": 3
    }
    
    response = client.post(
        "/api/books",
        json=book_data,
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == book_data["title"]
    assert data["author"] == book_data["author"]

def test_search_books(setup_database, admin_token, test_book):
    """Kitoblarni qidirish"""
    response = client.get(
        "/api/books?search=Test",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    
    assert response.status_code == 200
    books = response.json()
    assert len(books) > 0

def test_update_book(setup_database, admin_token, test_book):
    """Kitob yangilash"""
    update_data = {"total_copies": 10}
    
    response = client.put(
        f"/api/books/{test_book.book_id}",
        json=update_data,
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["total_copies"] == 10

# =====================================================
# MEMBERS TESTS
# =====================================================

def test_get_members(setup_database, admin_token):
    """Barcha a'zolarni olish"""
    response = client.get(
        "/api/members",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_create_member(setup_database, admin_token):
    """Yangi a'zo yaratish"""
    member_data = {
        "full_name": "New Member",
        "email": "newmember@test.com",
        "phone": "+998901111111",
        "address": "New Address"
    }
    
    response = client.post(
        "/api/members",
        json=member_data,
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == member_data["email"]

def test_create_member_duplicate_email(setup_database, admin_token, test_member):
    """Dublikat email bilan a'zo yaratishga urinish"""
    member_data = {
        "full_name": "Duplicate",
        "email": test_member.email,
        "phone": "+998902222222"
    }
    
    response = client.post(
        "/api/members",
        json=member_data,
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    
    assert response.status_code == 400

# =====================================================
# BORROWINGS TESTS
# =====================================================

def test_create_borrowing(setup_database, admin_token, test_member, test_book):
    """Kitobni ijaraga berish"""
    borrow_data = {
        "member_id": str(test_member.member_id),
        "book_id": str(test_book.book_id),
        "days": 14
    }
    
    response = client.post(
        "/api/borrowings",
        json=borrow_data,
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "borrowed"

def test_borrow_unavailable_book(setup_database, admin_token, test_member, db_session):
    """Mavjud bo'lmagan kitobni olishga urinish"""
    # Kitob yaratish (nusxalar 0)
    book = Book(
        title="Unavailable Book",
        author="Author",
        total_copies=0,
        available_copies=0
    )
    db_session.add(book)
    db_session.commit()
    
    borrow_data = {
        "member_id": str(test_member.member_id),
        "book_id": str(book.book_id),
        "days": 14
    }
    
    response = client.post(
        "/api/borrowings",
        json=borrow_data,
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    
    assert response.status_code == 400

def test_return_book(setup_database, admin_token, test_member, test_book, db_session):
    """Kitobni qaytarish"""
    # Avval olish
    borrowing = Borrowing(
        member_id=test_member.member_id,
        book_id=test_book.book_id,
        due_date=date.today() + timedelta(days=14),
        status="borrowed"
    )
    db_session.add(borrowing)
    test_book.available_copies -= 1
    db_session.commit()
    
    # Qaytarish
    response = client.put(
        f"/api/borrowings/{borrowing.borrow_id}/return",
        json={},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "returned"

def test_late_return_creates_penalty(setup_database, admin_token, test_member, test_book, db_session):
    """Kechikkan qaytarish jarima yaratadi"""
    # Avval olish (muddat o'tgan)
    borrowing = Borrowing(
        member_id=test_member.member_id,
        book_id=test_book.book_id,
        borrow_date=date.today() - timedelta(days=20),
        due_date=date.today() - timedelta(days=5),  # 5 kun kechikgan
        status="borrowed"
    )
    db_session.add(borrowing)
    db_session.commit()
    
    # Qaytarish
    response = client.put(
        f"/api/borrowings/{borrowing.borrow_id}/return",
        json={},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    
    assert response.status_code == 200
    
    # Jarima yaratilganini tekshirish
    penalties = db_session.query(Penalty).filter(
        Penalty.member_id == test_member.member_id
    ).all()
    assert len(penalties) > 0

# =====================================================
# PENALTIES TESTS
# =====================================================

def test_get_penalties(setup_database, admin_token):
    """Barcha jarimalarni olish"""
    response = client.get(
        "/api/penalties",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_pay_penalty(setup_database, admin_token, test_member, db_session):
    """Jarimani to'lash"""
    # Jarima yaratish
    penalty = Penalty(
        member_id=test_member.member_id,
        amount=10000,
        reason="Test penalty",
        status="unpaid"
    )
    db_session.add(penalty)
    db_session.commit()
    
    # To'lash
    response = client.put(
        f"/api/penalties/{penalty.penalty_id}/pay",
        json={"paid_amount": 10000},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "paid"

# =====================================================
# STATISTICS TESTS
# =====================================================

def test_get_statistics(setup_database, admin_token):
    """Umumiy statistika"""
    response = client.get(
        "/api/stats",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "total_books" in data
    assert "total_members" in data
    assert "active_borrowings" in data

def test_get_popular_books(setup_database, admin_token):
    """Mashhur kitoblar"""
    response = client.get(
        "/api/stats/popular-books",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    
    assert response.status_code == 200
    assert isinstance(response.json(), list)

# =====================================================
# AUTHORIZATION TESTS
# =====================================================

def test_unauthorized_access():
    """Tokensiz so'rov"""
    response = client.get("/api/books")
    assert response.status_code == 401

def test_invalid_token():
    """Noto'g'ri token"""
    response = client.get(
        "/api/books",
        headers={"Authorization": "Bearer invalid_token"}
    )
    assert response.status_code == 401

# =====================================================
# VALIDATION TESTS
# =====================================================

def test_create_book_invalid_data(setup_database, admin_token):
    """Noto'g'ri ma'lumot bilan kitob yaratish"""
    invalid_data = {
        "title": "",  # Bo'sh title
        "author": "Author"
    }
    
    response = client.post(
        "/api/books",
        json=invalid_data,
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    
    assert response.status_code == 422  # Validation error

def test_create_member_invalid_email(setup_database, admin_token):
    """Noto'g'ri email bilan a'zo yaratish"""
    invalid_data = {
        "full_name": "Test",
        "email": "not-an-email",
        "phone": "+998901234567"
    }
    
    response = client.post(
        "/api/members",
        json=invalid_data,
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    
    assert response.status_code == 422

# =====================================================
# EDGE CASES
# =====================================================

def test_borrow_with_unpaid_penalties(setup_database, admin_token, test_member, test_book, db_session):
    """To'lanmagan jarima bilan kitob olishga urinish"""
    # Jarima yaratish
    penalty = Penalty(
        member_id=test_member.member_id,
        amount=5000,
        reason="Test",
        status="unpaid"
    )
    db_session.add(penalty)
    db_session.commit()
    
    # Kitob olishga urinish
    borrow_data = {
        "member_id": str(test_member.member_id),
        "book_id": str(test_book.book_id),
        "days": 14
    }
    
    response = client.post(
        "/api/borrowings",
        json=borrow_data,
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    
    assert response.status_code == 400

# Testlarni ishga tushirish:
# pytest test_api.py -v