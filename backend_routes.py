"""
To'liq API Endpoints
Barcha CRUD operatsiyalar va biznes logika
"""

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, and_
from typing import List, Optional
from datetime import datetime, date, timedelta
from uuid import UUID

from database import get_db
from models import *
from schemas import *
from auth import get_current_user, get_current_admin

router = APIRouter()

# =====================================================
# BOOKS ENDPOINTS (To'liq)
# =====================================================

@router.post("/api/books", response_model=BookResponse, status_code=status.HTTP_201_CREATED)
async def create_book(
    book: BookCreate,
    db: Session = Depends(get_db),
    current_user: Librarian = Depends(get_current_user)
):
    """Yangi kitob qo'shish"""
    # ISBN tekshirish
    if book.isbn:
        existing = db.query(Book).filter(Book.isbn == book.isbn).first()
        if existing:
            raise HTTPException(status_code=400, detail="Bu ISBN allaqachon mavjud")
    
    db_book = Book(**book.dict())
    db.add(db_book)
    db.commit()
    db.refresh(db_book)
    return db_book

@router.put("/api/books/{book_id}", response_model=BookResponse)
async def update_book(
    book_id: str,
    book: BookUpdate,
    db: Session = Depends(get_db),
    current_user: Librarian = Depends(get_current_user)
):
    """Kitob ma'lumotlarini yangilash"""
    db_book = db.query(Book).filter(Book.book_id == book_id).first()
    if not db_book:
        raise HTTPException(status_code=404, detail="Kitob topilmadi")
    
    update_data = book.dict(exclude_unset=True)
    
    # Agar total_copies o'zgartirilsa, available_copies ni ham o'zgartirish kerak
    if 'total_copies' in update_data:
        old_total = db_book.total_copies
        new_total = update_data['total_copies']
        difference = new_total - old_total
        db_book.available_copies = max(0, db_book.available_copies + difference)
    
    for key, value in update_data.items():
        setattr(db_book, key, value)
    
    db.commit()
    db.refresh(db_book)
    return db_book

@router.delete("/api/books/{book_id}")
async def delete_book(
    book_id: str,
    db: Session = Depends(get_db),
    current_user: Librarian = Depends(get_current_admin)
):
    """Kitobni o'chirish (faqat admin)"""
    book = db.query(Book).filter(Book.book_id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Kitob topilmadi")
    
    # Aktiv borrowinglar bo'lsa o'chirib bo'lmaydi
    active_borrowings = db.query(Borrowing).filter(
        Borrowing.book_id == book_id,
        Borrowing.status.in_(['borrowed', 'late'])
    ).count()
    
    if active_borrowings > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Bu kitobning {active_borrowings} ta aktiv ijarasi bor. Avval ularni qaytaring."
        )
    
    db.delete(book)
    db.commit()
    return {"message": "Kitob muvaffaqiyatli o'chirildi"}

@router.get("/api/books/genres", response_model=List[str])
async def get_genres(db: Session = Depends(get_db)):
    """Barcha janrlar ro'yxati"""
    genres = db.query(Book.genre).distinct().filter(Book.genre.isnot(None)).all()
    return [g[0] for g in genres]

# =====================================================
# BORROWINGS ENDPOINTS (To'liq)
# =====================================================

@router.get("/api/borrowings", response_model=List[BorrowingDetailResponse])
async def get_borrowings(
    skip: int = 0,
    limit: int = 100,
    status_filter: Optional[str] = None,
    member_id: Optional[str] = None,
    book_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: Librarian = Depends(get_current_user)
):
    """
    Barcha ijaralarni olish
    Filter: status, member_id, book_id
    """
    query = db.query(Borrowing).join(Member).join(Book)
    
    if status_filter:
        query = query.filter(Borrowing.status == status_filter)
    
    if member_id:
        query = query.filter(Borrowing.member_id == member_id)
    
    if book_id:
        query = query.filter(Borrowing.book_id == book_id)
    
    borrowings = query.order_by(desc(Borrowing.borrow_date)).offset(skip).limit(limit).all()
    
    # Ma'lumotlarni to'ldirish
    result = []
    for b in borrowings:
        days_late = None
        if b.status in ['borrowed', 'late'] and b.due_date < date.today():
            days_late = (date.today() - b.due_date).days
        
        result.append({
            **b.__dict__,
            "member_name": b.member.full_name,
            "book_title": b.book.title,
            "days_late": days_late
        })
    
    return result

@router.post("/api/borrowings", response_model=BorrowingResponse, status_code=status.HTTP_201_CREATED)
async def create_borrowing(
    borrowing: BorrowingCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: Librarian = Depends(get_current_user)
):
    """
    Kitobni ijaraga berish
    Validatsiya: kitob mavjudmi, a'zo faolmi
    """
    # Kitob mavjudligini tekshirish
    book = db.query(Book).filter(Book.book_id == borrowing.book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Kitob topilmadi")
    
    if book.available_copies <= 0:
        raise HTTPException(status_code=400, detail="Bu kitobning mavjud nusxalari yo'q")
    
    # A'zo faolligini tekshirish
    member = db.query(Member).filter(Member.member_id == borrowing.member_id).first()
    if not member:
        raise HTTPException(status_code=404, detail="A'zo topilmadi")
    
    if not member.is_active:
        raise HTTPException(status_code=400, detail="Bu a'zo faol emas")
    
    # To'lanmagan jarimalar tekshiruvi
    unpaid_penalties = db.query(func.sum(Penalty.amount)).filter(
        Penalty.member_id == borrowing.member_id,
        Penalty.status == 'unpaid'
    ).scalar() or 0
    
    if unpaid_penalties > 0:
        raise HTTPException(
            status_code=400,
            detail=f"A'zoning {unpaid_penalties} so'm to'lanmagan jarimasi bor"
        )
    
    # Borrowing yaratish
    due_date = date.today() + timedelta(days=borrowing.days)
    db_borrowing = Borrowing(
        member_id=borrowing.member_id,
        book_id=borrowing.book_id,
        librarian_id=current_user.librarian_id,
        due_date=due_date,
        notes=borrowing.notes
    )
    
    db.add(db_borrowing)
    
    # Kitob va a'zo statistikasini yangilash
    book.available_copies -= 1
    member.current_borrowed += 1
    member.total_borrowed += 1
    
    db.commit()
    db.refresh(db_borrowing)
    
    # Email xabarnoma yuborish (background task)
    # background_tasks.add_task(send_borrow_notification, member.email, book.title, due_date)
    
    return db_borrowing

@router.put("/api/borrowings/{borrow_id}/return", response_model=BorrowingResponse)
async def return_book(
    borrow_id: str,
    return_data: BorrowingReturn,
    db: Session = Depends(get_db),
    current_user: Librarian = Depends(get_current_user)
):
    """
    Kitobni qaytarish
    Agar kechikkan bo'lsa avtomatik jarima yaratiladi
    """
    borrowing = db.query(Borrowing).filter(Borrowing.borrow_id == borrow_id).first()
    if not borrowing:
        raise HTTPException(status_code=404, detail="Ijara topilmadi")
    
    if borrowing.status == 'returned':
        raise HTTPException(status_code=400, detail="Bu kitob allaqachon qaytarilgan")
    
    # Kechikish tekshiruvi
    today = date.today()
    is_late = today > borrowing.due_date
    days_late = (today - borrowing.due_date).days if is_late else 0
    
    # Statusni yangilash
    borrowing.status = 'returned'
    borrowing.return_date = today
    if return_data.notes:
        borrowing.notes = return_data.notes
    
    # Kitob va a'zo statistikasini yangilash
    book = db.query(Book).filter(Book.book_id == borrowing.book_id).first()
    member = db.query(Member).filter(Member.member_id == borrowing.member_id).first()
    
    book.available_copies += 1
    member.current_borrowed -= 1
    
    # Agar kechikkan bo'lsa jarima yaratish
    if is_late:
        penalty_amount = days_late * 5000  # Har kun uchun 5000 so'm
        penalty = Penalty(
            member_id=borrowing.member_id,
            borrow_id=borrowing.borrow_id,
            amount=penalty_amount,
            reason=f"Kitobni muddatidan {days_late} kun kechiktirib qaytarganlik uchun jarima"
        )
        db.add(penalty)
    
    db.commit()
    db.refresh(borrowing)
    
    return borrowing

@router.get("/api/borrowings/late", response_model=List[BorrowingDetailResponse])
async def get_late_borrowings(
    db: Session = Depends(get_db),
    current_user: Librarian = Depends(get_current_user)
):
    """Kechikkan ijaralar ro'yxati"""
    late_borrowings = db.query(Borrowing).join(Member).join(Book).filter(
        Borrowing.status.in_(['borrowed', 'late']),
        Borrowing.due_date < date.today()
    ).all()
    
    result = []
    for b in late_borrowings:
        days_late = (date.today() - b.due_date).days
        result.append({
            **b.__dict__,
            "member_name": b.member.full_name,
            "book_title": b.book.title,
            "days_late": days_late
        })
    
    return result

# =====================================================
# PENALTIES ENDPOINTS (To'liq)
# =====================================================

@router.get("/api/penalties", response_model=List[PenaltyDetailResponse])
async def get_penalties(
    skip: int = 0,
    limit: int = 100,
    status_filter: Optional[str] = None,
    member_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: Librarian = Depends(get_current_user)
):
    """Barcha jarimalar ro'yxati"""
    query = db.query(Penalty).join(Member)
    
    if status_filter:
        query = query.filter(Penalty.status == status_filter)
    
    if member_id:
        query = query.filter(Penalty.member_id == member_id)
    
    penalties = query.order_by(desc(Penalty.issued_date)).offset(skip).limit(limit).all()
    
    result = []
    for p in penalties:
        result.append({
            **p.__dict__,
            "member_name": p.member.full_name
        })
    
    return result

@router.post("/api/penalties", response_model=PenaltyResponse, status_code=status.HTTP_201_CREATED)
async def create_penalty(
    penalty: PenaltyCreate,
    db: Session = Depends(get_db),
    current_user: Librarian = Depends(get_current_user)
):
    """Yangi jarima yaratish"""
    member = db.query(Member).filter(Member.member_id == penalty.member_id).first()
    if not member:
        raise HTTPException(status_code=404, detail="A'zo topilmadi")
    
    db_penalty = Penalty(**penalty.dict())
    db.add(db_penalty)
    db.commit()
    db.refresh(db_penalty)
    return db_penalty

@router.put("/api/penalties/{penalty_id}/pay", response_model=PenaltyResponse)
async def pay_penalty(
    penalty_id: str,
    payment: PenaltyUpdate,
    db: Session = Depends(get_db),
    current_user: Librarian = Depends(get_current_user)
):
    """Jarimani to'lash"""
    penalty = db.query(Penalty).filter(Penalty.penalty_id == penalty_id).first()
    if not penalty:
        raise HTTPException(status_code=404, detail="Jarima topilmadi")
    
    if penalty.status == 'paid':
        raise HTTPException(status_code=400, detail="Bu jarima allaqachon to'langan")
    
    penalty.status = 'paid'
    penalty.paid_date = date.today()
    penalty.paid_amount = payment.paid_amount or penalty.amount
    if payment.notes:
        penalty.notes = payment.notes
    
    db.commit()
    db.refresh(penalty)
    return penalty

# =====================================================
# STATISTICS ENDPOINTS
# =====================================================

@router.get("/api/stats", response_model=LibraryStats)
async def get_statistics(
    db: Session = Depends(get_db),
    current_user: Librarian = Depends(get_current_user)
):
    """Umumiy statistika"""
    total_books = db.query(func.count(Book.book_id)).filter(Book.is_active == True).scalar()
    total_members = db.query(func.count(Member.member_id)).filter(Member.is_active == True).scalar()
    active_borrowings = db.query(func.count(Borrowing.borrow_id)).filter(Borrowing.status == 'borrowed').scalar()
    late_borrowings = db.query(func.count(Borrowing.borrow_id)).filter(
        Borrowing.status.in_(['borrowed', 'late']),
        Borrowing.due_date < date.today()
    ).scalar()
    total_penalties = db.query(func.sum(Penalty.amount)).scalar() or 0
    unpaid_penalties = db.query(func.sum(Penalty.amount)).filter(Penalty.status == 'unpaid').scalar() or 0
    
    return {
        "total_books": total_books,
        "total_members": total_members,
        "active_borrowings": active_borrowings,
        "late_borrowings": late_borrowings,
        "total_penalties": float(total_penalties),
        "unpaid_penalties": float(unpaid_penalties)
    }

@router.get("/api/stats/popular-books", response_model=List[PopularBook])
async def get_popular_books(
    limit: int = 10,
    db: Session = Depends(get_db),
    current_user: Librarian = Depends(get_current_user)
):
    """Eng mashhur kitoblar"""
    popular = db.query(
        Book.book_id,
        Book.title,
        Book.author,
        Book.genre,
        func.count(Borrowing.borrow_id).label('borrow_count')
    ).join(Borrowing).group_by(
        Book.book_id, Book.title, Book.author, Book.genre
    ).order_by(desc('borrow_count')).limit(limit).all()
    
    return [
        {
            "book_id": p.book_id,
            "title": p.title,
            "author": p.author,
            "genre": p.genre,
            "borrow_count": p.borrow_count
        }
        for p in popular
    ]

@router.get("/api/stats/active-members", response_model=List[ActiveMember])
async def get_active_members(
    limit: int = 10,
    db: Session = Depends(get_db),
    current_user: Librarian = Depends(get_current_user)
):
    """Eng faol a'zolar"""
    active = db.query(
        Member.member_id,
        Member.full_name,
        Member.email,
        Member.total_borrowed,
        Member.current_borrowed,
        func.coalesce(func.sum(Penalty.amount), 0).label('total_penalties')
    ).outerjoin(Penalty, and_(
        Penalty.member_id == Member.member_id,
        Penalty.status == 'unpaid'
    )).group_by(
        Member.member_id,
        Member.full_name,
        Member.email,
        Member.total_borrowed,
        Member.current_borrowed
    ).order_by(desc(Member.total_borrowed)).limit(limit).all()
    
    return [
        {
            "member_id": a.member_id,
            "full_name": a.full_name,
            "email": a.email,
            "total_borrowed": a.total_borrowed,
            "current_borrowed": a.current_borrowed,
            "total_penalties": float(a.total_penalties)
        }
        for a in active
    ]