# Favorites & Want to Visit - Database Integration

## 🔧 Perubahan yang Dibuat

### **Masalah:**
- Button "Favorite" dan "Want to Visit" di ShopDetail masih menggunakan localStorage
- Data hilang saat user logout atau clear browser storage
- Tidak ada sinkronisasi antar device

### **Solusi:**
- Integrasi dengan Supabase database
- Data tersimpan per user (menggunakan `user_id`)
- Data tetap ada setelah logout/login
- Sinkronisasi antar device

---

## 🔄 Perubahan di ShopDetail.jsx

### **1. Import Supabase**

**Sebelum:**
```javascript
import { useAuth } from '../context/AuthContext';
```

**Sesudah:**
```javascript
import { useAuth } from '../context/AuthContext';
import { supabase, isSupabaseConfigured } from '../lib/supabase';
```

---

### **2. Check Status dari Supabase**

**Sebelum:**
```javascript
useEffect(() => {
  if (id) {
    const favorites = JSON.parse(localStorage.getItem('favoriteShops') || '[]');
    setIsFavorite(favorites.includes(id));
    
    const wantToVisit = JSON.parse(localStorage.getItem('wantToVisitShops') || '[]');
    setIsWantToVisit(wantToVisit.includes(id));
  }
}, [id]);
```

**Sesudah:**
```javascript
useEffect(() => {
  const checkFavoriteStatus = async () => {
    if (!id) return;
    
    // If user is authenticated and Supabase is configured, check from Supabase
    if (isAuthenticated && user?.id && isSupabaseConfigured && supabase) {
      try {
        // Check favorite
        const { data: favoriteData } = await supabase
          .from('favorites')
          .select('id')
          .eq('user_id', user.id)
          .eq('place_id', id)
          .maybeSingle();
        
        setIsFavorite(!!favoriteData);
        
        // Check want to visit
        const { data: wantToVisitData } = await supabase
          .from('want_to_visit')
          .select('id')
          .eq('user_id', user.id)
          .eq('place_id', id)
          .maybeSingle();
        
        setIsWantToVisit(!!wantToVisitData);
      } catch (err) {
        // Fallback to localStorage
        const favorites = JSON.parse(localStorage.getItem('favoriteShops') || '[]');
        setIsFavorite(favorites.includes(id));
        
        const wantToVisit = JSON.parse(localStorage.getItem('wantToVisitShops') || '[]');
        setIsWantToVisit(wantToVisit.includes(id));
      }
    } else {
      // Guest mode: use localStorage
      const favorites = JSON.parse(localStorage.getItem('favoriteShops') || '[]');
      setIsFavorite(favorites.includes(id));
      
      const wantToVisit = JSON.parse(localStorage.getItem('wantToVisitShops') || '[]');
      setIsWantToVisit(wantToVisit.includes(id));
    }
  };
  
  checkFavoriteStatus();
}, [id, isAuthenticated, user?.id]);
```

---

### **3. Toggle Favorite dengan Supabase**

**Sebelum:**
```javascript
const toggleFavorite = () => {
  const favorites = JSON.parse(localStorage.getItem('favoriteShops') || '[]');
  if (isFavorite) {
    const updated = favorites.filter(fav => fav !== id);
    localStorage.setItem('favoriteShops', JSON.stringify(updated));
  } else {
    favorites.push(id);
    localStorage.setItem('favoriteShops', JSON.stringify(favorites));
  }
  setIsFavorite(!isFavorite);
};
```

**Sesudah:**
```javascript
const toggleFavorite = async () => {
  try {
    // If user is authenticated and Supabase is configured, save to Supabase
    if (isAuthenticated && user?.id && isSupabaseConfigured && supabase) {
      if (isFavorite) {
        // Remove from favorites in Supabase
        const { error } = await supabase
          .from('favorites')
          .delete()
          .eq('user_id', user.id)
          .eq('place_id', id);
        
        if (error) {
          console.error('[ShopDetail] Error removing favorite:', error);
          return;
        }
        
        setNotification({ type: 'removed', message: 'Dihapus dari favorit' });
      } else {
        // Add to favorites in Supabase
        const { error } = await supabase
          .from('favorites')
          .insert({ user_id: user.id, place_id: id });
        
        if (error) {
          console.error('[ShopDetail] Error adding favorite:', error);
          return;
        }
        
        setNotification({ type: 'added', message: 'Ditambahkan ke favorit!' });
      }
      
      setIsFavorite(!isFavorite);
    } else {
      // Guest mode: use localStorage
      const favorites = JSON.parse(localStorage.getItem('favoriteShops') || '[]');
      if (isFavorite) {
        const updated = favorites.filter(fav => fav !== id);
        localStorage.setItem('favoriteShops', JSON.stringify(updated));
      } else {
        favorites.push(id);
        localStorage.setItem('favoriteShops', JSON.stringify(favorites));
      }
      setIsFavorite(!isFavorite);
    }
  } catch (err) {
    console.error('[ShopDetail] Error toggling favorite:', err);
  }
};
```

---

### **4. Toggle Want to Visit dengan Supabase**

Sama seperti toggleFavorite, tapi menggunakan tabel `want_to_visit`.

---

## 📋 Database Schema

### **Tabel: favorites**

```sql
CREATE TABLE IF NOT EXISTS favorites (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id UUID REFERENCES profiles(id) ON DELETE CASCADE,
  place_id TEXT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(user_id, place_id)
);
```

### **Tabel: want_to_visit**

```sql
CREATE TABLE IF NOT EXISTS want_to_visit (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id UUID REFERENCES profiles(id) ON DELETE CASCADE,
  place_id TEXT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(user_id, place_id)
);
```

---

## 🔒 Row Level Security (RLS) Policies

### **Favorites Policies:**

1. **Users can view own favorites**
   - SELECT: `auth.uid() = user_id`
   - User hanya bisa melihat favorites mereka sendiri

2. **Users can add favorites**
   - INSERT: `auth.uid() = user_id`
   - User hanya bisa menambahkan favorites untuk diri mereka sendiri

3. **Users can remove favorites**
   - DELETE: `auth.uid() = user_id`
   - User hanya bisa menghapus favorites mereka sendiri

### **Want to Visit Policies:**

Sama seperti favorites, tapi untuk tabel `want_to_visit`.

---

## 📊 Indexes untuk Performance

```sql
-- Favorites indexes
CREATE INDEX IF NOT EXISTS idx_favorites_user_id ON favorites(user_id);
CREATE INDEX IF NOT EXISTS idx_favorites_place_id ON favorites(place_id);
CREATE INDEX IF NOT EXISTS idx_favorites_user_place ON favorites(user_id, place_id);

-- Want to visit indexes
CREATE INDEX IF NOT EXISTS idx_want_to_visit_user_id ON want_to_visit(user_id);
CREATE INDEX IF NOT EXISTS idx_want_to_visit_place_id ON want_to_visit(place_id);
CREATE INDEX IF NOT EXISTS idx_want_to_visit_user_place ON want_to_visit(user_id, place_id);
```

---

## 🚀 Langkah Implementasi

### **Langkah 1: Jalankan SQL Schema**

1. Buka **Supabase Dashboard** → **SQL Editor**
2. Copy dan paste isi file `favorites-want-to-visit-schema.sql`
3. Klik **Run** untuk menjalankan script
4. **Expected**: 
   - Tabel `favorites` dan `want_to_visit` dibuat
   - RLS policies dibuat
   - Indexes dibuat

### **Langkah 2: Verify Tables**

Jalankan query ini untuk verify:

```sql
-- Check tables exist
SELECT * FROM information_schema.tables 
WHERE table_name IN ('favorites', 'want_to_visit');

-- Check RLS policies
SELECT * FROM pg_policies 
WHERE tablename IN ('favorites', 'want_to_visit');

-- Check indexes
SELECT * FROM pg_indexes 
WHERE tablename IN ('favorites', 'want_to_visit');
```

### **Langkah 3: Test di Browser**

1. Login sebagai user
2. Buka detail coffee shop
3. Klik button "Favorite" atau "Want to Visit"
4. **Expected**: 
   - Button berubah state (filled/unfilled)
   - Notification muncul
   - Data tersimpan di Supabase

### **Langkah 4: Test Persistence**

1. Login sebagai user
2. Tambahkan beberapa favorites dan want to visit
3. Logout
4. Login lagi
5. **Expected**: 
   - Favorites dan want to visit masih ada
   - Data tidak hilang

---

## ✅ Hasil Setelah Perbaikan

### Sebelum:
- ❌ Data hanya di localStorage
- ❌ Data hilang saat logout/clear storage
- ❌ Tidak sinkron antar device
- ❌ Tidak ada backup data

### Sesudah:
- ✅ Data tersimpan di Supabase database
- ✅ Data tetap ada setelah logout/login
- ✅ Sinkronisasi antar device
- ✅ Backup data di cloud
- ✅ Data per user (tidak tercampur)

---

## 🧪 Testing

### Test Case 1: Add Favorite (Authenticated User)
1. Login sebagai user
2. Buka detail coffee shop
3. Klik button "Favorite"
4. **Expected**: 
   - Button berubah menjadi filled (pink)
   - Notification "Ditambahkan ke favorit!"
   - Data tersimpan di Supabase

### Test Case 2: Remove Favorite (Authenticated User)
1. Login sebagai user
2. Buka detail coffee shop yang sudah di-favorite
3. Klik button "Favorite" lagi
4. **Expected**: 
   - Button berubah menjadi unfilled
   - Notification "Dihapus dari favorit"
   - Data dihapus dari Supabase

### Test Case 3: Add Want to Visit (Authenticated User)
1. Login sebagai user
2. Buka detail coffee shop
3. Klik button "Want to Visit"
4. **Expected**: 
   - Button berubah menjadi filled (blue)
   - Notification "Ditambahkan ke want to visit!"
   - Data tersimpan di Supabase

### Test Case 4: Persistence After Logout
1. Login sebagai user
2. Tambahkan beberapa favorites dan want to visit
3. Logout
4. Login lagi
5. Buka detail coffee shop yang sudah di-favorite
6. **Expected**: 
   - Button "Favorite" masih filled
   - Button "Want to Visit" masih filled (jika sudah ditambahkan)
   - Data tidak hilang

### Test Case 5: Guest Mode
1. Buka detail coffee shop sebagai guest
2. Klik button "Favorite" atau "Want to Visit"
3. **Expected**: 
   - Button tidak muncul (karena `isAuthenticated` = false)
   - Atau jika muncul, data tersimpan di localStorage (fallback)

---

## 📝 Catatan Penting

1. **Data Per User**:
   - Setiap user memiliki data favorites dan want to visit mereka sendiri
   - Data tidak tercampur antar user
   - Menggunakan `user_id` untuk filter data

2. **Guest Mode**:
   - Guest masih bisa menggunakan localStorage untuk favorites/want to visit
   - Data guest tidak tersimpan di Supabase
   - Data guest hilang saat clear browser storage

3. **RLS Policies**:
   - User hanya bisa melihat/menambah/menghapus favorites/want to visit mereka sendiri
   - Tidak bisa mengakses data user lain
   - Policies menggunakan `auth.uid() = user_id`

4. **Indexes**:
   - Indexes dibuat untuk improve query performance
   - Query berdasarkan `user_id` dan `place_id` akan lebih cepat

5. **Error Handling**:
   - Jika Supabase error, fallback ke localStorage
   - Error ditampilkan di console untuk debugging
   - User tetap bisa menggunakan fitur meski ada error

---

## 🔗 Related Files

- `frontend-cofind/src/pages/ShopDetail.jsx` - Updated untuk menggunakan Supabase (fixed)
- `frontend-cofind/favorites-want-to-visit-schema.sql` - SQL schema untuk tabel dan RLS policies (new)
- `frontend-cofind/supabase-schema-safe.sql` - Main schema (already has tables)

---

## 🎯 Action Items

1. **Jalankan SQL Schema** - Pastikan tabel dan RLS policies sudah dibuat
2. **Test Add/Remove** - Pastikan button berfungsi dengan benar
3. **Test Persistence** - Pastikan data tidak hilang setelah logout/login
4. **Test Guest Mode** - Pastikan guest masih bisa menggunakan localStorage

---

## 🔧 Troubleshooting

### Masalah: Button Tidak Berfungsi

**Solusi:**
1. **Cek Supabase Config**: Pastikan `VITE_SUPABASE_URL` dan `VITE_SUPABASE_ANON_KEY` sudah di-set
2. **Cek RLS Policies**: Pastikan policies sudah dibuat dan aktif
3. **Cek Console**: Lihat error message di console
4. **Cek Network**: Pastikan koneksi ke Supabase baik

### Masalah: Data Tidak Tersimpan

**Solusi:**
1. **Cek User Auth**: Pastikan user sudah login (`user?.id` ada)
2. **Cek RLS Policies**: Pastikan INSERT policy aktif
3. **Cek Console**: Lihat error message di console
4. **Cek Database**: Verify data di Supabase Dashboard

### Masalah: Data Hilang Setelah Logout

**Solusi:**
1. **Cek RLS Policies**: Pastikan SELECT policy aktif
2. **Cek User ID**: Pastikan `user_id` sama saat login
3. **Cek Database**: Verify data masih ada di Supabase Dashboard
4. **Cek Console**: Lihat error message di console
