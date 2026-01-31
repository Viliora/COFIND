-- Script untuk mengubah kolom user_ratings_total menjadi total_reviews
-- dan update data total_reviews untuk coffee shops

-- ============================================================================
-- STEP 1: Rename kolom user_ratings_total menjadi total_reviews
-- ============================================================================
-- SQLite tidak support ALTER TABLE RENAME COLUMN langsung
-- Jadi kita perlu membuat tabel baru, copy data, drop tabel lama, rename tabel baru

BEGIN TRANSACTION;

-- 1. Buat tabel baru dengan struktur yang benar
CREATE TABLE coffee_shops_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    place_id TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    address TEXT,
    rating REAL,
    total_reviews INTEGER DEFAULT 0,
    photo_url TEXT,
    latitude REAL,
    longitude REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Copy data dari tabel lama ke tabel baru
-- Jika kolom user_ratings_total ada, gunakan nilainya, jika tidak gunakan 0
INSERT INTO coffee_shops_new (id, place_id, name, address, rating, total_reviews, photo_url, latitude, longitude, created_at)
SELECT 
    id,
    place_id,
    name,
    address,
    rating,
    COALESCE(user_ratings_total, 0) as total_reviews,
    photo_url,
    latitude,
    longitude,
    created_at
FROM coffee_shops;

-- 3. Drop tabel lama
DROP TABLE coffee_shops;

-- 4. Rename tabel baru menjadi coffee_shops
ALTER TABLE coffee_shops_new RENAME TO coffee_shops;

COMMIT;

-- ============================================================================
-- STEP 2: Update total_reviews dengan data yang diberikan
-- ============================================================================

BEGIN TRANSACTION;

-- Update total_reviews untuk setiap coffee shop
UPDATE coffee_shops SET total_reviews = 78 WHERE name LIKE '%2818 Coffee Roasters%';
UPDATE coffee_shops SET total_reviews = 744 WHERE name LIKE '%5 CM Coffee and Eatery%';
UPDATE coffee_shops SET total_reviews = 1371 WHERE name LIKE '%Aming Coffee Ilham%';
UPDATE coffee_shops SET total_reviews = 3024 WHERE name LIKE '%Aming Coffee Podomoro%';
UPDATE coffee_shops SET total_reviews = 522 WHERE name LIKE '%Aming Coffee Siantan%';
UPDATE coffee_shops SET total_reviews = 379 WHERE name LIKE '%CW Coffee Tanjung Raya%';
UPDATE coffee_shops SET total_reviews = 77 WHERE name LIKE '%Disela Coffee & Roastery%';
UPDATE coffee_shops SET total_reviews = 618 WHERE name LIKE '%Haruna Cafe%';
UPDATE coffee_shops SET total_reviews = 129 WHERE name LIKE '%Heim Coffee%';
UPDATE coffee_shops SET total_reviews = 178 WHERE name LIKE '%NUTRICULA COFFEE%';
UPDATE coffee_shops SET total_reviews = 40 WHERE name LIKE '%Osamu Coffee%';
UPDATE coffee_shops SET total_reviews = 80 WHERE name LIKE '%Seremoni Coffee%';

COMMIT;

-- ============================================================================
-- STEP 3: Verifikasi hasil update
-- ============================================================================

-- Tampilkan semua coffee shop dengan total_reviews yang sudah diupdate
SELECT 
    id,
    name AS "Nama Coffee Shop",
    total_reviews AS "Total Reviews",
    rating AS "Rating"
FROM coffee_shops 
ORDER BY name;
