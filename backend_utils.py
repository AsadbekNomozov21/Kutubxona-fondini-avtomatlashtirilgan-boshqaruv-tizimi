"""
Yordamchi funksiyalar
Email, validation, date processing va boshqalar
"""

from datetime import date, datetime, timedelta
from typing import Optional, List
import re
from sqlalchemy.orm import Session
from models import Borrowing, Penalty, Member, Book

# =====================================================
# DATE UTILITIES
# =====================================================

def calculate_due_date(borrow_date: date, days: int = 14) -> date:
    """
    Qaytarish muddatini hisoblash
    Args:
        borrow_date: Olish sanasi
        days: Necha kun uchun (default: 14)
    Returns:
        date: Qaytarish muddati
    """
    return borrow_date + timedelta(days=days)

def get_days_late(due_date: date, return_date: Optional[date] = None) -> int:
    """
    Kechikkan kunlarni hisoblash
    Args:
        due_date: Qaytarish muddati
        return_date: Qaytarish sanasi (None bo'lsa bugungi kun)
    Returns:
        int: Kechikkan kunlar (0 yoki musbat)
    """
    actual_return = return_date or date.today()
    days_late = (actual_return - due_date).days
    return max(0, days_late)

def is_overdue(due_date: date) -> bool:
    """
    Muddat o'tganmi tekshirish
    Args:
        due_date: Qaytarish muddati
    Returns:
        bool: True agar muddat o'tgan bo'lsa
    """
    return date.today() > due_date

# =====================================================
# PENALTY CALCULATIONS
# =====================================================

def calculate_late_penalty(days_late: int, rate_per_day: float = 5000) -> float:
    """
    Kechikish jarimasi hisoblash (oddiy formula)
    Args:
        days_late: Kechikkan kunlar
        rate_per_day: Kun uchun stavka
    Returns:
        float: Jarima summasi
    """
    return days_late * rate_per_day

def calculate_progressive_penalty(days_late: int) -> float:
    """
    Progressiv jarima (uzoq kechikishlar uchun yuqori stavka)
    1-7 kun: 3000 so'm/kun
    8-14 kun: 5000 so'm/kun
    15-30 kun: 7000 so'm/kun
    30+ kun: 10000 so'm/kun
    """
    penalty = 0.0
    remaining_days = days_late
    
    # 1-7 kunlar
    if remaining_days > 0:
        days = min(remaining_days, 7)
        penalty += days * 3000
        remaining_days -= days
    
    # 8-14 kunlar
    if remaining_days > 0:
        days = min(remaining_days, 7)
        penalty += days * 5000
        remaining_days -= days
    
    # 15-30 kunlar
    if remaining_days > 0:
        days = min(remaining_days, 16)
        penalty += days * 7000
        remaining_days -= days
    
    # 30+ kunlar
    if remaining_days > 0:
        penalty += remaining_days * 10000
    
    return penalty

def apply_first_time_discount(
    db: Session, 
    member_id: str, 
    penalty_amount: float
) -> float:
    """
    Birinchi kechikish uchun 50% chegirma
    Args:
        db: Database session
        member_id: A'zo ID
        penalty_amount: Jarima summasi
    Returns:
        float: Chegirma qo'llanilgan summa
    """
    # Oldingi jarimalar bormi?
    previous_count = db.query(Penalty).filter(
        Penalty.member_id == member_id,
        Penalty.status != 'waived'
    ).count()
    
    if previous_count == 0:
        return penalty_amount * 0.5  # 50% chegirma
    
    return penalty_amount

def apply_penalty_cap(penalty: float, book_value: float, cap_percent: float = 0.8) -> float:
    """
    Jarimani kitob qiymatining ma'lum foizi bilan cheklash
    Args:
        penalty: Hisoblangan jarima
        book_value: Kitob qiymati
        cap_percent: Maksimal foiz (default: 80%)
    Returns:
        float: Cheklangan jarima
    """
    max_penalty = book_value * cap_percent
    return min(penalty, max_penalty)

# =====================================================
# VALIDATION
# =====================================================

def validate_email(email: str) -> bool:
    """Email formatini tekshirish"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def validate_phone(phone: str) -> bool:
    """Telefon raqam formatini tekshirish (O'zbekiston)"""
    # Format: +998901234567 yoki 901234567
    pattern = r'^(\+998)?[0-9]{9}$'
    return re.match(pattern, phone) is not None

def validate_isbn(isbn: str) -> bool:
    """ISBN formatini tekshirish"""
    # ISBN-10 yoki ISBN-13
    isbn = isbn.replace('-', '').replace(' ', '')
    return len(isbn) in [10, 13] and isbn.isdigit()

# =====================================================
# BUSINESS LOGIC CHECKS
# =====================================================

def can_borrow_book(
    db: Session,
    member_id: str,
    book_id: str
) -> tuple[bool, Optional[str]]:
    """
    A'zo kitob ola oladimi tekshirish
    Returns:
        tuple: (can_borrow: bool, error_message: Optional[str])
    """
    # A'zo mavjudmi va faolmi?
    member = db.query(Member).filter(Member.member_id == member_id).first()
    if not member:
        return False, "A'zo topilmadi"
    if not member.is_active:
        return False, "A'zo faol emas"
    
    # Kitob mavjudmi?
    book = db.query(Book).filter(Book.book_id == book_id).first()
    if not book:
        return False, "Kitob topilmadi"
    if not book.is_active:
        return False, "Kitob faol emas"
    if book.available_copies <= 0:
        return False, "Kitob mavjud emas"
    
    # To'lanmagan jarimalar bormi?
    unpaid_penalties = db.query(Penalty).filter(
        Penalty.member_id == member_id,
        Penalty.status == 'unpaid'
    ).count()
    if unpaid_penalties > 0:
        return False, f"A'zoning {unpaid_penalties} ta to'lanmagan jarimasi bor"
    
    # Maksimal kitoblar soni (masalan, 5 ta)
    MAX_CONCURRENT_BOOKS = 5
    if member.current_borrowed >= MAX_CONCURRENT_BOOKS:
        return False, f"A'zo maksimal {MAX_CONCURRENT_BOOKS} ta kitobgacha ola oladi"
    
    return True, None

def get_member_statistics(db: Session, member_id: str) -> dict:
    """
    A'zo statistikasi
    Returns:
        dict: Statistika ma'lumotlari
    """
    member = db.query(Member).filter(Member.member_id == member_id).first()
    if not member:
        return {}
    
    # Jarimalar
    total_penalties = db.query(Penalty).filter(
        Penalty.member_id == member_id
    ).count()
    
    unpaid_penalties = db.query(Penalty).filter(
        Penalty.member_id == member_id,
        Penalty.status == 'unpaid'
    ).count()
    
    total_penalty_amount = db.query(func.sum(Penalty.amount)).filter(
        Penalty.member_id == member_id
    ).scalar() or 0
    
    # Kechikkanlar
    late_returns = db.query(Borrowing).filter(
        Borrowing.member_id == member_id,
        Borrowing.status == 'late'
    ).count()
    
    # O'rtacha ijara muddati
    avg_borrow_days = db.query(
        func.avg(func.extract('day', Borrowing.return_date - Borrowing.borrow_date))
    ).filter(
        Borrowing.member_id == member_id,
        Borrowing.status == 'returned'
    ).scalar() or 0
    
    return {
        "member_id": str(member_id),
        "full_name": member.full_name,
        "total_borrowed": member.total_borrowed,
        "current_borrowed": member.current_borrowed,
        "total_penalties": total_penalties,
        "unpaid_penalties": unpaid_penalties,
        "total_penalty_amount": float(total_penalty_amount),
        "late_returns": late_returns,
        "average_borrow_days": float(avg_borrow_days),
        "registration_date": member.registration_date.isoformat()
    }

# =====================================================
# SEARCH & FILTER
# =====================================================

def search_books(
    db: Session,
    query: str,
    genre: Optional[str] = None,
    available_only: bool = False,
    limit: int = 50
) -> List[Book]:
    """
    Kitoblarni qidirish (title, author, ISBN)
    """
    search_pattern = f"%{query}%"
    
    filters = [
        Book.is_active == True,
        (
            Book.title.ilike(search_pattern) |
            Book.author.ilike(search_pattern) |
            Book.isbn.ilike(search_pattern)
        )
    ]
    
    if genre:
        filters.append(Book.genre == genre)
    
    if available_only:
        filters.append(Book.available_copies > 0)
    
    books = db.query(Book).filter(*filters).limit(limit).all()
    return books

def search_members(
    db: Session,
    query: str,
    active_only: bool = True,
    limit: int = 50
) -> List[Member]:
    """
    A'zolarni qidirish (name, email, phone)
    """
    search_pattern = f"%{query}%"
    
    filters = [
        (
            Member.full_name.ilike(search_pattern) |
            Member.email.ilike(search_pattern) |
            Member.phone.ilike(search_pattern)
        )
    ]
    
    if active_only:
        filters.append(Member.is_active == True)
    
    members = db.query(Member).filter(*filters).limit(limit).all()
    return members

# =====================================================
# FORMATTING
# =====================================================

def format_currency(amount: float) -> str:
    """
    Pulni formatlash (1000 -> "1,000 so'm")
    """
    return f"{amount:,.0f} so'm"

def format_phone(phone: str) -> str:
    """
    Telefon raqamni formatlash
    901234567 -> +998 90 123 45 67
    """
    if phone.startswith('+998'):
        phone = phone[4:]
    
    return f"+998 {phone[:2]} {phone[2:5]} {phone[5:7]} {phone[7:]}"

def format_date_uz(date_obj: date) -> str:
    """
    Sanani o'zbek formatida ko'rsatish
    2024-01-15 -> "15-yanvar-2024"
    """
    months = {
        1: 'yanvar', 2: 'fevral', 3: 'mart', 4: 'aprel',
        5: 'may', 6: 'iyun', 7: 'iyul', 8: 'avgust',
        9: 'sentabr', 10: 'oktabr', 11: 'noyabr', 12: 'dekabr'
    }
    
    return f"{date_obj.day}-{months[date_obj.month]}-{date_obj.year}"

# =====================================================
# NOTIFICATIONS (stub - email/SMS uchun)
# =====================================================

async def send_due_date_reminder(
    member_email: str,
    member_name: str,
    book_title: str,
    due_date: date
):
    """
    Muddat yaqinlashganda xabarnoma yuborish
    (Email yoki SMS integratsiya kerak)
    """
    # TODO: Email/SMS integratsiya
    print(f"📧 Reminder to {member_email}: Return '{book_title}' by {due_date}")

async def send_overdue_notification(
    member_email: str,
    member_name: str,
    book_title: str,
    days_late: int,
    penalty_amount: float
):
    """
    Kechikish haqida ogohlantirish
    """
    # TODO: Email/SMS integratsiya
    print(f"⚠️ Overdue notice to {member_email}: '{book_title}' - {days_late} days late")

# =====================================================
# LOGGING
# =====================================================

def log_action(
    action: str,
    user_id: str,
    details: dict
):
    """
    Foydalanuvchi harakatlarini loglash
    (Audit trail uchun)
    """
    timestamp = datetime.now().isoformat()
    print(f"[{timestamp}] {action} by {user_id}: {details}")

# =====================================================
# PAGINATION
# =====================================================

def paginate(query, page: int = 1, per_page: int = 50):
    """
    Query natijalarini sahifalash
    """
    total = query.count()
    items = query.offset((page - 1) * per_page).limit(per_page).all()
    
    return {
        "items": items,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": (total + per_page - 1) // per_page
    }