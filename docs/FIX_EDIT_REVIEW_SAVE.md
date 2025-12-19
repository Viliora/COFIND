# Perbaikan: Fungsi Simpan Setelah Edit Review

## 🔧 Masalah yang Diperbaiki

### **Masalah:**
Fungsi "Simpan" setelah edit review belum berfungsi. User tidak bisa menyimpan perubahan review yang sudah di-edit.

### **Penyebab:**
1. **Error handling tidak lengkap** - Error tidak ditampilkan dengan jelas ke user
2. **Data tidak lengkap setelah update** - `onUpdate` dipanggil dengan data yang tidak lengkap
3. **Profile data hilang** - Profile data tidak di-fetch setelah update
4. **No user feedback** - User tidak tahu apakah update berhasil atau gagal

---

## 🔄 Perbaikan yang Dibuat

### **1. Enhanced Error Handling**

**Sebelum:**
```javascript
if (!error) {
  setIsEditing(false);
  if (onUpdate) onUpdate({ ...review, text: editText.trim(), rating: editRating });
}
```

**Masalah:**
- Error tidak ditangani dengan baik
- User tidak tahu jika update gagal
- No error message

**Sesudah:**
```javascript
if (error) {
  console.error('[ReviewCard] Error updating review:', error);
  alert('Gagal menyimpan perubahan: ' + (error.message || 'Unknown error'));
  setLoading(false);
  return;
}

// Success handling dengan data lengkap
if (updatedReview) {
  // Fetch profile data
  // Prepare final updated review
  // Call onUpdate dengan data lengkap
}
```

**Manfaat:**
- Error ditampilkan dengan jelas ke user
- User tahu jika update gagal
- Better error messages

---

### **2. Fetch Updated Review dengan Select**

**Sebelum:**
```javascript
const { error } = await supabase
  .from('reviews')
  .update({ text: editText.trim(), rating: editRating, updated_at: new Date().toISOString() })
  .eq('id', review.id);
```

**Masalah:**
- Tidak fetch updated data dari Supabase
- Harus manual construct updated review
- `updated_at` mungkin tidak ter-update dengan benar

**Sesudah:**
```javascript
const { data: updatedReview, error } = await supabase
  .from('reviews')
  .update({ 
    text: editText.trim(), 
    rating: editRating, 
    updated_at: new Date().toISOString() 
  })
  .eq('id', review.id)
  .select(`
    id,
    user_id,
    place_id,
    rating,
    text,
    created_at,
    updated_at
  `)
  .single();
```

**Manfaat:**
- Fetch updated data langsung dari Supabase
- Pastikan data up-to-date
- `updated_at` ter-update dengan benar

---

### **3. Fetch Profile Data Setelah Update**

**Perbaikan:**
- Fetch profile data terpisah setelah update review
- Keep existing profile data jika fetch gagal
- Ensure `author_name` tetap ada

**Code:**
```javascript
if (updatedReview) {
  // Fetch profile data untuk updated review
  let profileData = review.profiles; // Keep existing profile data
  
  if (updatedReview.user_id) {
    try {
      const { data: profile } = await supabase
        .from('profiles')
        .select('id, username, avatar_url, full_name')
        .eq('id', updatedReview.user_id)
        .single();
      
      if (profile) {
        profileData = profile;
      }
    } catch (profileError) {
      console.warn('[ReviewCard] Error fetching profile (non-critical):', profileError);
      // Keep existing profile data if fetch fails
    }
  }
  
  // Prepare final updated review dengan semua data
  const finalUpdatedReview = {
    ...review, // Keep existing data (photos, replies, etc.)
    ...updatedReview, // Override with updated data
    profiles: profileData,
    author_name: profileData?.username || profileData?.full_name || 'Anonim',
    source: review.source || 'supabase'
  };
  
  // Call onUpdate dengan data lengkap
  if (onUpdate) {
    onUpdate(finalUpdatedReview);
  }
}
```

---

### **4. Enhanced UI Feedback**

**Perbaikan:**
- Tambahkan error message di UI (bukan hanya alert)
- Disable button saat loading
- Show loading state di button
- Clear error saat user mengetik

**Code:**
```javascript
const [editError, setEditError] = useState('');

// Di textarea onChange
onChange={(e) => {
  setEditText(e.target.value);
  setEditError(''); // Clear error saat user mengetik
}}

// Di button
disabled={loading || !editText.trim()}
{loading ? 'Menyimpan...' : 'Simpan'}

// Error display
{editError && (
  <p className="text-sm text-red-600 dark:text-red-400 mt-1">{editError}</p>
)}
```

---

### **5. Fix Edit State Management**

**Perbaikan:**
- Reset edit state saat mulai edit
- Sync dengan review data saat mulai edit
- Clear error saat cancel

**Code:**
```javascript
const handleEditClick = () => {
  setEditText(review.text || '');
  setEditRating(review.rating || 0);
  setEditError('');
  setIsEditing(true);
};

// Di cancel button
onClick={() => {
  setIsEditing(false);
  setEditText(review.text || '');
  setEditRating(review.rating || 0);
  setEditError('');
}}
```

---

## 📋 Langkah Implementasi

### **Langkah 1: Test Edit Review**

1. Login sebagai user
2. Buka detail coffee shop dengan review Anda
3. Klik "Edit" pada review
4. Ubah text dan rating
5. Klik "Simpan"
6. **Expected**: 
   - Review ter-update dengan benar
   - Tidak ada error
   - Changes terlihat langsung di UI

### **Langkah 2: Test Error Handling**

1. Simulate error (misalnya disconnect network)
2. Edit review dan klik "Simpan"
3. **Expected**: 
   - Error message muncul
   - User tahu bahwa update gagal
   - Review tetap dalam mode edit (bisa coba lagi)

### **Langkah 3: Test Cancel**

1. Edit review
2. Klik "Batal"
3. **Expected**: 
   - Review kembali ke state original
   - Tidak ada perubahan yang tersimpan

---

## ✅ Hasil Setelah Perbaikan

### Sebelum:
- ❌ Error handling tidak lengkap
- ❌ Data tidak lengkap setelah update
- ❌ Profile data hilang
- ❌ No user feedback
- ❌ Update tidak berfungsi

### Sesudah:
- ✅ Error handling lengkap dengan user feedback
- ✅ Fetch updated data dari Supabase
- ✅ Profile data tetap ada setelah update
- ✅ Loading state dan error message di UI
- ✅ Update berfungsi dengan benar

---

## 🧪 Testing

### Test Case 1: Edit Text Only
1. Edit review text
2. Klik "Simpan"
3. **Expected**: 
   - Text ter-update
   - Rating tetap sama
   - Profile data tetap ada

### Test Case 2: Edit Rating Only
1. Edit rating
2. Klik "Simpan"
3. **Expected**: 
   - Rating ter-update
   - Text tetap sama
   - Profile data tetap ada

### Test Case 3: Edit Both
1. Edit text dan rating
2. Klik "Simpan"
3. **Expected**: 
   - Text dan rating ter-update
   - Profile data tetap ada
   - Changes terlihat langsung

### Test Case 4: Error Handling
1. Simulate error (network offline)
2. Edit review dan klik "Simpan"
3. **Expected**: 
   - Error message muncul
   - Review tetap dalam mode edit
   - User bisa coba lagi

---

## 📝 Catatan Penting

1. **RLS Policy**:
   - Policy "Users can update own reviews" sudah ada di schema
   - Policy menggunakan `auth.uid() = user_id` untuk verify ownership
   - Pastikan user adalah owner review untuk bisa update

2. **Data Consistency**:
   - Fetch updated data dari Supabase untuk ensure consistency
   - Profile data di-fetch terpisah untuk prevent missing data
   - Keep existing data (photos, replies) saat update

3. **Error Handling**:
   - Error ditampilkan dengan jelas ke user
   - Non-critical errors (profile fetch) tidak block update
   - User bisa retry jika update gagal

4. **User Experience**:
   - Loading state di button
   - Error message di UI
   - Success feedback (review ter-update langsung)

---

## 🔗 Related Files

- `frontend-cofind/src/components/ReviewCard.jsx` - Enhanced edit submit dengan error handling (fixed)
- `frontend-cofind/src/components/ReviewList.jsx` - handleUpdate untuk update state (already exists)
- `frontend-cofind/supabase-schema-safe.sql` - RLS policy untuk UPDATE reviews

---

## 🎯 Action Items

1. **Test Edit Review** - Pastikan update berfungsi dengan benar
2. **Test Error Handling** - Pastikan error ditampilkan dengan jelas
3. **Test Cancel** - Pastikan cancel berfungsi dengan benar
4. **Verify RLS Policy** - Pastikan policy "Users can update own reviews" aktif

---

## 🔧 Troubleshooting

### Masalah: Update Gagal dengan Error 401/403

**Solusi:**
1. **Cek RLS Policy**: Pastikan policy "Users can update own reviews" aktif
2. **Cek User Ownership**: Pastikan user adalah owner review
3. **Cek Auth State**: Pastikan user sudah login dengan benar

### Masalah: Profile Data Hilang Setelah Update

**Solusi:**
1. **Cek Profile Fetch**: Pastikan profile fetch berhasil
2. **Cek Fallback**: Pastikan existing profile data di-keep jika fetch gagal
3. **Cek Console**: Lihat error message di console

### Masalah: Changes Tidak Terlihat Setelah Simpan

**Solusi:**
1. **Cek onUpdate**: Pastikan `onUpdate` dipanggil dengan data lengkap
2. **Cek ReviewList**: Pastikan `handleUpdate` di ReviewList berfungsi
3. **Cek State**: Pastikan state ter-update dengan benar
