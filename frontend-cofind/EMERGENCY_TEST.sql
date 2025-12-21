-- =====================================================
-- EMERGENCY TEST - CEK KONEKSI SUPABASE
-- =====================================================

-- TEST 1: Query paling simple (tanpa filter)
SELECT COUNT(*) FROM reviews;

-- Jika ini timeout juga, berarti masalah di:
-- 1. Supabase project paused/overloaded
-- 2. Network connection
-- 3. RLS policy blocking

-- TEST 2: Query tanpa RLS (harus pakai service_role key)
-- JANGAN jalankan di SQL Editor biasa, ini test dari browser console
-- Copy ke browser console:
/*
const { data, error } = await supabase
  .from('reviews')
  .select('count')
  .eq('place_id', 'ChIJDcJgropZHS4RKuh8s52jy9U');
console.log('Result:', data, error);
*/

-- TEST 3: Disable RLS SEMENTARA (untuk testing saja!)
ALTER TABLE reviews DISABLE ROW LEVEL SECURITY;

-- Setelah test, ENABLE kembali:
-- ALTER TABLE reviews ENABLE ROW LEVEL SECURITY;

-- TEST 4: Cek Supabase project status
-- Buka: https://supabase.com/dashboard/project/_/settings/general
-- Cek status: Active / Paused / Restoring

-- TEST 5: Query dengan timeout lebih panjang di SQL Editor
SET statement_timeout = '60s';
SELECT * FROM reviews LIMIT 5;

-- TEST 6: Cek koneksi
-- Di browser console, jalankan:
/*
fetch('https://cpnzglvpqyugtacodwtr.supabase.co/rest/v1/')
  .then(r => console.log('Supabase reachable:', r.status))
  .catch(e => console.error('Cannot reach Supabase:', e));
*/
