-- Script sederhana untuk update total_reviews
-- Gunakan script ini jika kolom sudah di-rename atau jika ingin update langsung

-- ============================================================================
-- Update total_reviews untuk setiap coffee shop berdasarkan nama
-- ============================================================================

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

-- Verifikasi hasil
SELECT name, total_reviews FROM coffee_shops ORDER BY name;
