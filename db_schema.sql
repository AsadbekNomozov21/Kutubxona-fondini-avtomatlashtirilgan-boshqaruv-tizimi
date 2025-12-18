-- Kutubxona boshqaruv tizimi - Ma'lumotlar bazasi sxemasi
-- PostgreSQL 12+ uchun

-- Ma'lumotlar bazasini yaratish
CREATE DATABASE library_management;

-- Ma'lumotlar bazasiga ulanish
\c library_management;

-- UUID kengaytmasini yoqish
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =====================================================
-- 1. LIBRARIANS JADVALI (Kutubxonachilar)
-- =====================================================
CREATE TABLE librarians (
    librarian_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    full_name VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    phone VARCHAR(20),
    password_hash VARCHAR(255) NOT NULL,
    shift VARCHAR(20) CHECK (shift IN ('morning', 'evening', 'night')),
    role VARCHAR(20) DEFAULT 'librarian' CHECK (role IN ('admin', 'librarian')),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =====================================================
-- 2. MEMBERS JADVALI (A'zolar)
-- =====================================================
CREATE TABLE members (
    member_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    full_name VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    phone VARCHAR(20),
    address TEXT,
    registration_date DATE DEFAULT CURRENT_DATE,
    is_active BOOLEAN DEFAULT TRUE,
    total_borrowed INT DEFAULT 0,
    current_borrowed INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =====================================================
-- 3. BOOKS JADVALI (Kitoblar)
-- =====================================================
CREATE TABLE books (
    book_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title VARCHAR(500) NOT NULL,
    author VARCHAR(255) NOT NULL,
    genre VARCHAR(100),
    publisher VARCHAR(255),
    year INT CHECK (year >= 1000 AND year <= EXTRACT(YEAR FROM CURRENT_DATE)),
    isbn VARCHAR(20) UNIQUE,
    total_copies INT DEFAULT 1 CHECK (total_copies >= 0),
    available_copies INT DEFAULT 1 CHECK (available_copies >= 0),
    description TEXT,
    image_url VARCHAR(500),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT check_available_copies CHECK (available_copies <= total_copies)
);

-- =====================================================
-- 4. BORROWINGS JADVALI (Ijaralar)
-- =====================================================
CREATE TABLE borrowings (
    borrow_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    member_id UUID NOT NULL REFERENCES members(member_id) ON DELETE CASCADE,
    book_id UUID NOT NULL REFERENCES books(book_id) ON DELETE CASCADE,
    librarian_id UUID REFERENCES librarians(librarian_id) ON DELETE SET NULL,
    borrow_date DATE DEFAULT CURRENT_DATE,
    due_date DATE NOT NULL,
    return_date DATE,
    status VARCHAR(20) DEFAULT 'borrowed' CHECK (status IN ('borrowed', 'returned', 'late', 'lost')),
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =====================================================
-- 5. PENALTIES JADVALI (Jarimalar)
-- =====================================================
CREATE TABLE penalties (
    penalty_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    member_id UUID NOT NULL REFERENCES members(member_id) ON DELETE CASCADE,
    borrow_id UUID REFERENCES borrowings(borrow_id) ON DELETE SET NULL,
    amount DECIMAL(10, 2) NOT NULL CHECK (amount >= 0),
    reason TEXT NOT NULL,
    issued_date DATE DEFAULT CURRENT_DATE,
    status VARCHAR(20) DEFAULT 'unpaid' CHECK (status IN ('paid', 'unpaid', 'waived')),
    paid_date DATE,
    paid_amount DECIMAL(10, 2) DEFAULT 0,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =====================================================
-- INDEKSLAR (Tezlik uchun)
-- =====================================================
CREATE INDEX idx_members_email ON members(email);
CREATE INDEX idx_members_active ON members(is_active);
CREATE INDEX idx_books_title ON books(title);
CREATE INDEX idx_books_author ON books(author);
CREATE INDEX idx_books_genre ON books(genre);
CREATE INDEX idx_borrowings_member ON borrowings(member_id);
CREATE INDEX idx_borrowings_book ON borrowings(book_id);
CREATE INDEX idx_borrowings_status ON borrowings(status);
CREATE INDEX idx_borrowings_due_date ON borrowings(due_date);
CREATE INDEX idx_penalties_member ON penalties(member_id);
CREATE INDEX idx_penalties_status ON penalties(status);

-- =====================================================
-- TRIGGER FUNKSIYALAR
-- =====================================================

-- 1. Updated_at ni avtomatik yangilash
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Barcha jadvallarga trigger qo'shish
CREATE TRIGGER update_librarians_updated_at BEFORE UPDATE ON librarians
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_members_updated_at BEFORE UPDATE ON members
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_books_updated_at BEFORE UPDATE ON books
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_borrowings_updated_at BEFORE UPDATE ON borrowings
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_penalties_updated_at BEFORE UPDATE ON penalties
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- 2. Kitob ijaraga berilganda available_copies ni kamaytirish
CREATE OR REPLACE FUNCTION decrease_available_copies()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.status = 'borrowed' THEN
        UPDATE books 
        SET available_copies = available_copies - 1
        WHERE book_id = NEW.book_id AND available_copies > 0;
        
        UPDATE members
        SET current_borrowed = current_borrowed + 1,
            total_borrowed = total_borrowed + 1
        WHERE member_id = NEW.member_id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_decrease_copies AFTER INSERT ON borrowings
    FOR EACH ROW EXECUTE FUNCTION decrease_available_copies();

-- 3. Kitob qaytarilganda available_copies ni oshirish
CREATE OR REPLACE FUNCTION increase_available_copies()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.status = 'borrowed' AND NEW.status = 'returned' THEN
        UPDATE books 
        SET available_copies = available_copies + 1
        WHERE book_id = NEW.book_id;
        
        UPDATE members
        SET current_borrowed = current_borrowed - 1
        WHERE member_id = NEW.member_id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_increase_copies AFTER UPDATE ON borrowings
    FOR EACH ROW EXECUTE FUNCTION increase_available_copies();

-- 4. Kechikkan kitoblar uchun avtomatik jarima
CREATE OR REPLACE FUNCTION auto_create_penalty()
RETURNS TRIGGER AS $$
DECLARE
    days_late INT;
    penalty_amount DECIMAL(10, 2);
BEGIN
    IF NEW.status = 'late' AND OLD.status = 'borrowed' THEN
        days_late := CURRENT_DATE - NEW.due_date;
        penalty_amount := days_late * 5000; -- Har kun uchun 5000 so'm
        
        INSERT INTO penalties (member_id, borrow_id, amount, reason)
        VALUES (
            NEW.member_id,
            NEW.borrow_id,
            penalty_amount,
            'Kitobni muddatidan ' || days_late || ' kun kechiktirib qaytarganlik uchun jarima'
        );
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_auto_penalty AFTER UPDATE ON borrowings
    FOR EACH ROW EXECUTE FUNCTION auto_create_penalty();

-- 5. Kechikkan borrowinglarni har kuni tekshirish uchun funksiya
CREATE OR REPLACE FUNCTION update_late_borrowings()
RETURNS void AS $$
BEGIN
    UPDATE borrowings
    SET status = 'late'
    WHERE status = 'borrowed' 
    AND due_date < CURRENT_DATE
    AND return_date IS NULL;
END;
$$ LANGUAGE plpgsql;

-- =====================================================
-- BOSHLANG'ICH MA'LUMOTLAR
-- =====================================================

-- Admin yaratish (parol: admin123)
INSERT INTO librarians (full_name, email, phone, password_hash, shift, role) VALUES
('Admin Adminov', 'admin@library.uz', '+998901234567', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5NU7ELNLnDPe2', 'morning', 'admin');

-- Kutubxonachilar yaratish (parol: librarian123)
INSERT INTO librarians (full_name, email, phone, password_hash, shift, role) VALUES
('Dilshod Karimov', 'dilshod@library.uz', '+998901234568', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5NU7ELNLnDPe2', 'morning', 'librarian'),
('Nodira Rahimova', 'nodira@library.uz', '+998901234569', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5NU7ELNLnDPe2', 'evening', 'librarian');

-- A'zolar yaratish
INSERT INTO members (full_name, email, phone, address) VALUES
('Alisher Navoiy', 'alisher@mail.uz', '+998901111111', 'Toshkent sh., Yunusobod t.'),
('Zarina Karimova', 'zarina@mail.uz', '+998902222222', 'Toshkent sh., Chilonzor t.'),
('Jasur Umarov', 'jasur@mail.uz', '+998903333333', 'Toshkent sh., Mirzo Ulug\'bek t.'),
('Malika Yusupova', 'malika@mail.uz', '+998904444444', 'Toshkent sh., Yakkasaroy t.'),
('Sardor Azimov', 'sardor@mail.uz', '+998905555555', 'Toshkent sh., Sergeli t.');

-- Kitoblar yaratish
INSERT INTO books (title, author, genre, publisher, year, isbn, total_copies, available_copies, description) VALUES
('O''tkan kunlar', 'Abdulla Qodiriy', 'Roman', 'O''zbekiston', 1925, '978-9943-01-234-5', 5, 5, 'O''zbek adabiyotining eng yirik asarlaridan biri'),
('Mehrobdan chayon', 'Abdulla Qodiriy', 'Roman', 'O''zbekiston', 1928, '978-9943-01-235-2', 3, 3, 'Tarixiy roman'),
('Kecha va kunduz', 'Cho''lpon', 'Roman', 'O''zbekiston', 1936, '978-9943-01-236-9', 4, 4, 'Klassik adabiyot'),
('Ikki eshik orasi', 'Ulug''bek Hamdam', 'Roman', 'Sharq', 2010, '978-9943-01-237-6', 6, 6, 'Zamonaviy adabiyot'),
('Qalbim yig''laydi', 'Odil Yoqubov', 'She''rlar', 'Yangi asr avlodi', 2015, '978-9943-01-238-3', 3, 3, 'She''rlar to''plami'),
('Python dasturlash', 'John Smith', 'Dasturlash', 'Tech Books', 2022, '978-9943-01-239-0', 10, 10, 'Python dasturlash asoslari'),
('JavaScript mukammal qo''llanma', 'Jane Doe', 'Dasturlash', 'Web Dev Press', 2023, '978-9943-01-240-6', 8, 8, 'JavaScript to''liq kursi'),
('Ma''lumotlar bazalari', 'Ali Valiyev', 'Texnologiya', 'IT Nashriyot', 2021, '978-9943-01-241-3', 5, 5, 'SQL va NoSQL ma''lumotlar bazalari'),
('Sun''iy intellekt asoslari', 'Sara Johnson', 'AI', 'Future Tech', 2024, '978-9943-01-242-0', 4, 4, 'Sun''iy intellekt va mashina o''rganish'),
('Hamsa', 'Alisher Navoiy', 'She''riyat', 'O''zbekiston', 1485, '978-9943-01-243-7', 7, 7, 'Buyuk she''riy asar');

-- =====================================================
-- VIEWS (Ko'rinishlar)
-- =====================================================

-- Kechikkan borrowinglar
CREATE VIEW late_borrowings_view AS
SELECT 
    b.borrow_id,
    m.full_name AS member_name,
    m.email AS member_email,
    bk.title AS book_title,
    b.borrow_date,
    b.due_date,
    CURRENT_DATE - b.due_date AS days_late,
    b.status
FROM borrowings b
JOIN members m ON b.member_id = m.member_id
JOIN books bk ON b.book_id = bk.book_id
WHERE b.status IN ('borrowed', 'late') AND b.due_date < CURRENT_DATE;

-- Eng mashhur kitoblar
CREATE VIEW popular_books_view AS
SELECT 
    b.book_id,
    b.title,
    b.author,
    b.genre,
    COUNT(br.borrow_id) AS borrow_count
FROM books b
LEFT JOIN borrowings br ON b.book_id = br.book_id
GROUP BY b.book_id, b.title, b.author, b.genre
ORDER BY borrow_count DESC;

-- Eng faol a'zolar
CREATE VIEW active_members_view AS
SELECT 
    m.member_id,
    m.full_name,
    m.email,
    m.total_borrowed,
    m.current_borrowed,
    COALESCE(SUM(CASE WHEN p.status = 'unpaid' THEN p.amount ELSE 0 END), 0) AS total_penalties
FROM members m
LEFT JOIN penalties p ON m.member_id = p.member_id
GROUP BY m.member_id, m.full_name, m.email, m.total_borrowed, m.current_borrowed
ORDER BY m.total_borrowed DESC;

-- =====================================================
-- STORED PROCEDURES
-- =====================================================

-- Kitobni ijaraga berish
CREATE OR REPLACE FUNCTION borrow_book(
    p_member_id UUID,
    p_book_id UUID,
    p_librarian_id UUID,
    p_days INT DEFAULT 14
)
RETURNS UUID AS $$
DECLARE
    v_borrow_id UUID;
    v_available INT;
BEGIN
    -- Kitob mavjudligini tekshirish
    SELECT available_copies INTO v_available
    FROM books WHERE book_id = p_book_id;
    
    IF v_available <= 0 THEN
        RAISE EXCEPTION 'Kitob mavjud emas';
    END IF;
    
    -- Borrowing yaratish
    INSERT INTO borrowings (member_id, book_id, librarian_id, due_date)
    VALUES (p_member_id, p_book_id, p_librarian_id, CURRENT_DATE + p_days)
    RETURNING borrow_id INTO v_borrow_id;
    
    RETURN v_borrow_id;
END;
$$ LANGUAGE plpgsql;

-- Kitobni qaytarish
CREATE OR REPLACE FUNCTION return_book(p_borrow_id UUID)
RETURNS void AS $$
BEGIN
    UPDATE borrowings
    SET status = 'returned',
        return_date = CURRENT_DATE
    WHERE borrow_id = p_borrow_id AND status IN ('borrowed', 'late');
END;
$$ LANGUAGE plpgsql;

-- =====================================================
-- STATISTIKA FUNKSIYALARI
-- =====================================================

CREATE OR REPLACE FUNCTION get_library_stats()
RETURNS TABLE (
    total_books BIGINT,
    total_members BIGINT,
    active_borrowings BIGINT,
    late_borrowings BIGINT,
    total_penalties NUMERIC,
    unpaid_penalties NUMERIC
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        (SELECT COUNT(*) FROM books WHERE is_active = TRUE),
        (SELECT COUNT(*) FROM members WHERE is_active = TRUE),
        (SELECT COUNT(*) FROM borrowings WHERE status = 'borrowed'),
        (SELECT COUNT(*) FROM borrowings WHERE status = 'late'),
        (SELECT COALESCE(SUM(amount), 0) FROM penalties),
        (SELECT COALESCE(SUM(amount), 0) FROM penalties WHERE status = 'unpaid');
END;
$$ LANGUAGE plpgsql;

COMMENT ON DATABASE library_management IS 'Kutubxona fondini boshqarish tizimi';
COMMENT ON TABLE members IS 'Kutubxona a''zolari ma''lumotlari';
COMMENT ON TABLE books IS 'Kutubxona kitoblari katalogi';
COMMENT ON TABLE borrowings IS 'Kitoblar ijarasi tarixi';
COMMENT ON TABLE penalties IS 'A''zolar jarimasini boshqarish';
COMMENT ON TABLE librarians IS 'Kutubxona xodimlari';



