# 🚨 EMERGENCY TROUBLESHOOTING - Timeout 20 Detik

## Situasi
- Index sudah dibuat ✅
- Policy sudah di-fix ✅  
- **MASIH TIMEOUT 20 DETIK** ❌

## Root Cause Kemungkinan Besar: NETWORK / SUPABASE PROJECT

### 🔍 Test 1: Cek Status Supabase Project (PALING PENTING!)

1. **Buka Supabase Dashboard:**
   - URL: https://supabase.com/dashboard/project/_/settings/general
   
2. **Cek Status Project:**
   - ✅ **Active** = OK
   - ⚠️ **Paused** = MASALAH! (Restart project)
   - ⚠️ **Restoring** = Tunggu selesai
   
3. **Cek CPU Usage:**
   - Buka: https://supabase.com/dashboard/project/_/reports/database
   - Jika **CPU > 80%** → Restart project atau upgrade plan

### 🔍 Test 2: Cek Koneksi Network

**A. Test Ping (Command Prompt / PowerShell):**
```powershell
ping cpnzglvpqyugtacodwtr.supabase.co
```

**Expected:**
```
Reply from ... time=50ms TTL=...
```

**Bad (Timeout/Unreachable):**
```
Request timed out
```

**B. Test Fetch dari Browser Console:**
```javascript
// Buka DevTools Console (F12), paste ini:
fetch('https://cpnzglvpqyugtacodwtr.supabase.co/rest/v1/', {
  headers: {
    'apikey': 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...' // Your anon key
  }
})
  .then(r => {
    console.log('✅ Supabase reachable, status:', r.status);
    console.log('Response time:', performance.now(), 'ms');
  })
  .catch(e => {
    console.error('❌ Cannot reach Supabase:', e);
  });
```

### 🔍 Test 3: Query Langsung di SQL Editor

**Jalankan query ini DI SUPABASE SQL EDITOR:**

```sql
-- Query paling simple
SELECT COUNT(*) FROM reviews;
```

**Hasil:**
- ✅ **< 1 detik** = Database OK, masalah di client/network
- ❌ **> 5 detik** = Database overloaded
- ❌ **Timeout** = Supabase project bermasalah

### 🔍 Test 4: Disable RLS Sementara (untuk isolasi masalah)

```sql
-- SEMENTARA disable RLS untuk test
ALTER TABLE reviews DISABLE ROW LEVEL SECURITY;

-- Test query
SELECT * FROM reviews LIMIT 5;

-- ENABLE kembali setelah test
ALTER TABLE reviews ENABLE ROW LEVEL SECURITY;
```

Jika query CEPAT setelah disable RLS → **Masalah di RLS Policy**  
Jika query MASIH LAMBAT → **Masalah di Database/Network**

### 🔧 Solusi Berdasarkan Hasil Test

#### Skenario A: Supabase Project Paused/Overloaded
**Solusi:**
1. Buka Dashboard → Settings → General
2. Restart project (Pause → Restore)
3. Tunggu 2-3 menit
4. Test lagi

#### Skenario B: Network Blocked (Firewall/Antivirus)
**Solusi:**
1. Matikan antivirus sementara
2. Coba gunakan VPN atau ganti WiFi ke 4G
3. Flush DNS:
   ```powershell
   ipconfig /flushdns
   ```
4. Test lagi

#### Skenario C: Browser Cache Issue
**Solusi:**
1. Hard refresh: `Ctrl + Shift + R` atau `Ctrl + F5`
2. Clear browser cache untuk localhost:
   - DevTools → Application → Clear storage → Clear
3. Restart browser
4. Test lagi

#### Skenario D: RLS Policy Masalah
**Solusi:**
```sql
-- Check existing policies
SELECT policyname, qual::text 
FROM pg_policies 
WHERE tablename = 'reviews';

-- Drop SEMUA policies
DROP POLICY IF EXISTS "simple_select_reviews" ON reviews;
DROP POLICY IF EXISTS "Reviews viewable by everyone" ON reviews;
DROP POLICY IF EXISTS "Enable read access for all users" ON reviews;
DROP POLICY IF EXISTS "Public reviews are viewable by everyone" ON reviews;

-- Disable RLS completely (TEMPORARY - untuk test)
ALTER TABLE reviews DISABLE ROW LEVEL SECURITY;

-- Test query
SELECT * FROM reviews LIMIT 5;

-- Jika BERHASIL, buat policy baru yang SIMPLE
ALTER TABLE reviews ENABLE ROW LEVEL SECURITY;

CREATE POLICY "allow_read_all"
ON reviews FOR SELECT
TO public
USING (true);
```

### 🎯 Quick Fix Steps (Lakukan Berurutan)

#### Step 1: Restart Supabase Project
1. Dashboard → Settings → General → Pause Project
2. Tunggu 30 detik
3. Restore Project
4. Tunggu 2 menit
5. **Test web, apakah masih timeout?**

#### Step 2: Disable RLS (Test)
```sql
ALTER TABLE reviews DISABLE ROW LEVEL SECURITY;
ALTER TABLE review_photos DISABLE ROW LEVEL SECURITY;
ALTER TABLE review_replies DISABLE ROW LEVEL SECURITY;
```
6. **Refresh web (F5), apakah masih timeout?**

#### Step 3: Network Test
7. Ganti koneksi (WiFi → 4G atau sebaliknya)
8. Flush DNS: `ipconfig /flushdns`
9. **Test web, apakah masih timeout?**

#### Step 4: Browser Reset
10. Close semua tab browser
11. Clear cache: DevTools → Application → Clear storage
12. Restart browser
13. **Test web, apakah masih timeout?**

### ⚡ NUCLEAR OPTION - Temporary Disable Everything

Jika semua gagal, test dengan konfigurasi minimal:

```sql
-- Di Supabase SQL Editor
BEGIN;

-- 1. Disable ALL RLS
ALTER TABLE reviews DISABLE ROW LEVEL SECURITY;
ALTER TABLE review_photos DISABLE ROW LEVEL SECURITY;
ALTER TABLE review_replies DISABLE ROW LEVEL SECURITY;
ALTER TABLE profiles DISABLE ROW LEVEL SECURITY;

-- 2. Drop ALL indexes (akan dikembalikan nanti)
-- SKIP THIS - biarkan index tetap ada

-- 3. Increase timeout
ALTER DATABASE postgres SET statement_timeout = '60s';

-- 4. Reload
SELECT pg_reload_conf();

COMMIT;
```

**Lalu test web. Jika BERHASIL:**
- Masalah di RLS policy
- Solusi: Buat policy yang lebih simple

**Jika MASIH TIMEOUT:**
- Masalah di network/Supabase
- Solusi: Restart project atau ganti network

### 📊 Monitoring Tools

**1. Supabase Performance Dashboard:**
- https://supabase.com/dashboard/project/_/reports

**2. Browser Network Tab:**
- DevTools → Network → Filter: "Fetch/XHR"
- Look for Supabase requests
- Check status, time, response

**3. Supabase Logs:**
- Dashboard → Logs → Postgres Logs
- Filter: "SELECT" 
- Look for slow queries

### 🆘 Last Resort - Contact Support

Jika SEMUA di atas gagal:

1. **Screenshot:**
   - Supabase Dashboard → Database → Performance (CPU/Memory)
   - Browser Network tab (Supabase request dengan timeout)
   - SQL Editor dengan hasil EXPLAIN ANALYZE

2. **Informasi:**
   - Supabase plan (Free/Pro)
   - Location/region
   - Internet speed
   - Browser & OS

3. **Contact Supabase Support:**
   - Dashboard → Support
   - Atau: https://supabase.com/docs/support

## 💡 Kemungkinan Terbesar

Berdasarkan gejala (timeout 20 detik tanpa response):

**90% kemungkinan:**
1. ❌ Supabase project paused/overloaded (CPU 100%)
2. ❌ Network blocked (firewall/antivirus/ISP)
3. ❌ DNS issue (tidak bisa resolve Supabase URL)

**10% kemungkinan:**
- RLS policy (tapi biasanya error 401, bukan timeout)
- Index (tapi biasanya slow, bukan timeout total)

## ✅ Next Step

**LAKUKAN INI SEKARANG:**

1. Buka: https://supabase.com/dashboard/project/_/settings/general
2. Cek status project: Active/Paused?
3. Jalankan di PowerShell: `ping cpnzglvpqyugtacodwtr.supabase.co`
4. Jalankan di SQL Editor: `SELECT COUNT(*) FROM reviews;`
5. **Beri tahu hasil dari 4 step di atas**

Saya akan bantu sesuai dengan hasilnya.
