-- ============================================
-- SUPABASE INDEXES FOR PERFORMANCE OPTIMIZATION
-- Jalankan script ini di Supabase SQL Editor untuk meningkatkan performa query
-- ============================================

-- Index untuk reviews table (CRITICAL untuk query berdasarkan place_id)
-- Query: SELECT * FROM reviews WHERE place_id = ? ORDER BY created_at DESC
CREATE INDEX IF NOT EXISTS idx_reviews_place_id ON reviews(place_id);
CREATE INDEX IF NOT EXISTS idx_reviews_place_id_created_at ON reviews(place_id, created_at DESC);

-- Index untuk reviews table (untuk query berdasarkan user_id)
CREATE INDEX IF NOT EXISTS idx_reviews_user_id ON reviews(user_id);
CREATE INDEX IF NOT EXISTS idx_reviews_user_id_created_at ON reviews(user_id, created_at DESC);

-- Index untuk review_photos (untuk join dengan reviews)
CREATE INDEX IF NOT EXISTS idx_review_photos_review_id ON review_photos(review_id);

-- Index untuk review_replies (untuk join dengan reviews)
CREATE INDEX IF NOT EXISTS idx_review_replies_review_id ON review_replies(review_id);
CREATE INDEX IF NOT EXISTS idx_review_replies_created_at ON review_replies(created_at DESC);

-- Index untuk profiles (untuk join dengan reviews)
-- Note: profiles.id sudah PRIMARY KEY, jadi sudah ada index otomatis
-- Tapi kita bisa tambahkan index untuk username jika sering di-query
CREATE INDEX IF NOT EXISTS idx_profiles_username ON profiles(username);

-- Index untuk favorites (untuk query berdasarkan user_id atau place_id)
CREATE INDEX IF NOT EXISTS idx_favorites_user_id ON favorites(user_id);
CREATE INDEX IF NOT EXISTS idx_favorites_place_id ON favorites(place_id);

-- Index untuk want_to_visit (untuk query berdasarkan user_id atau place_id)
CREATE INDEX IF NOT EXISTS idx_want_to_visit_user_id ON want_to_visit(user_id);
CREATE INDEX IF NOT EXISTS idx_want_to_visit_place_id ON want_to_visit(place_id);

-- ============================================
-- VERIFY INDEXES
-- ============================================
-- Jalankan query ini untuk memverifikasi index sudah dibuat:
-- SELECT 
--   tablename,
--   indexname,
--   indexdef
-- FROM pg_indexes
-- WHERE schemaname = 'public'
--   AND tablename IN ('reviews', 'review_photos', 'review_replies', 'profiles', 'favorites', 'want_to_visit')
-- ORDER BY tablename, indexname;
