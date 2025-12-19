# Menghapus Integrasi reviews.json - Migrasi ke Supabase Only

## 🔧 Perubahan yang Dibuat

### **Tujuan:**
Menghapus semua integrasi dengan `reviews.json` dan hanya menggunakan data review dari Supabase database.

---

## 🔄 Perubahan di Setiap File

### 1. **ReviewList.jsx - Hapus Legacy Reviews**

**Perubahan:**
- ❌ Hapus import `reviewsData from '../data/reviews.json'`
- ❌ Hapus state `legacyReviews` dan `supabaseReviews` (hanya `reviews` sekarang)
- ❌ Hapus logic untuk load dari `reviews.json`
- ❌ Hapus filter tabs ("Google Reviews", "Review Pengguna")
- ❌ Hapus `showSourceBadge` (tidak perlu badge lagi)
- ✅ Hanya fetch dari Supabase
- ✅ Simplified state management

**Sebelum:**
```javascript
import reviewsData from '../data/reviews.json';
const [legacyReviews, setLegacyReviews] = useState([]);
const [supabaseReviews, setSupabaseReviews] = useState([]);
// Load dari reviews.json...
// Combine: Supabase + Legacy
```

**Sesudah:**
```javascript
// Tidak ada import reviews.json
const [reviews, setReviews] = useState([]);
// Hanya fetch dari Supabase
```

### 2. **ShopDetail.jsx - Hapus Referensi reviews.json**

**Perubahan:**
- ❌ Hapus import `localReviewsData from '../data/reviews.json'`
- ❌ Hapus logic untuk load reviews dari `reviews.json`
- ✅ Reviews sekarang hanya dari Supabase (via ReviewList component)
- ✅ SmartReviewSummary fetch reviews sendiri dari Supabase

**Sebelum:**
```javascript
import localReviewsData from '../data/reviews.json';
const reviewsForShop = localReviewsData?.reviews_by_place_id?.[id] || [];
setReviews(localReviews);
```

**Sesudah:**
```javascript
// Reviews sekarang hanya dari Supabase (via ReviewList component)
setReviews([]);
```

### 3. **ShopList.jsx - Update Filter Logic**

**Perubahan:**
- ❌ Hapus import `localReviewsData from '../data/reviews.json'`
- ⚠️ **Filter berdasarkan pill preferences sekarang tidak tersedia** (karena tidak ada reviews.json)
- ✅ TODO: Implement filtering dengan fetch reviews dari Supabase jika diperlukan

**Sebelum:**
```javascript
import localReviewsData from '../data/reviews.json';
const reviewsByPlaceId = localReviewsData?.reviews_by_place_id || {};
// Filter berdasarkan reviews...
```

**Sesudah:**
```javascript
// TODO: Implement filtering dengan fetch reviews dari Supabase jika diperlukan
// Untuk sekarang, return semua shops jika ada pill yang dipilih
return shops;
```

### 4. **personalizedRecommendations.js - Update Context Extraction**

**Perubahan:**
- ❌ Hapus import `localReviewsData from '../data/reviews.json'`
- ❌ Hapus function `extractReviewContext` (tidak digunakan lagi)
- ✅ Gunakan nama dan address shop sebagai context (bukan reviews)

**Sebelum:**
```javascript
import localReviewsData from '../data/reviews.json';
const reviews = reviewsByPlaceId[shop.place_id] || [];
const context = extractReviewContext(reviews);
```

**Sesudah:**
```javascript
// Reviews sekarang hanya dari Supabase
// Gunakan nama dan address sebagai context
const shopContext = `${shop.name || ''} ${shop.address || ''}`.toLowerCase();
```

### 5. **SmartReviewSummary.jsx - Fetch Reviews dari Supabase**

**Perubahan:**
- ✅ Import Supabase client
- ✅ Fetch reviews dari Supabase jika tidak ada di props
- ✅ Support untuk reviews dari props (backward compatibility)

**Sebelum:**
```javascript
const SmartReviewSummary = ({ shopName, placeId, reviews }) => {
  // Langsung gunakan reviews dari props
```

**Sesudah:**
```javascript
import { supabase, isSupabaseConfigured } from '../lib/supabase';

const SmartReviewSummary = ({ shopName, placeId, reviews: propReviews }) => {
  const [reviews, setReviews] = useState(propReviews || []);
  
  // Fetch reviews dari Supabase jika tidak ada di props
  useEffect(() => {
    if (!placeId || !isSupabaseConfigured || !supabase) return;
    if (propReviews && propReviews.length > 0) {
      setReviews(propReviews);
      return;
    }
    // Fetch dari Supabase...
  }, [placeId, propReviews]);
```

### 6. **ReviewCard.jsx - Hapus Source Badge**

**Perubahan:**
- ❌ Hapus logic untuk source badge (tidak perlu lagi)
- ✅ Tetap support `relative_time` untuk backward compatibility

**Sebelum:**
```javascript
{showSourceBadge && review.source && (
  <span>
    {review.source === 'legacy' ? 'Google Review' : 'Review Pengguna'}
  </span>
)}
```

**Sesudah:**
```javascript
// Source badge dihapus - semua review sekarang dari Supabase
// showSourceBadge={false} di ReviewList
```

---

## 📋 Checklist Perubahan

### **Files yang Diubah:**
- [x] `ReviewList.jsx` - Hapus legacy reviews, simplified state
- [x] `ShopDetail.jsx` - Hapus referensi reviews.json
- [x] `ShopList.jsx` - Update filter logic (temporary disabled)
- [x] `personalizedRecommendations.js` - Update context extraction
- [x] `SmartReviewSummary.jsx` - Fetch reviews dari Supabase
- [x] `ReviewCard.jsx` - Hapus source badge (via showSourceBadge={false})

### **Files yang Masih Menggunakan reviews.json (Opsional untuk Dihapus):**
- [ ] `LLMAnalyzer.jsx` - Masih menggunakan reviews.json (component ini mungkin tidak aktif)
- [ ] `LLMAnalysisModal.jsx` - Masih menggunakan reviews.json (component ini mungkin tidak aktif)

**Catatan:** `LLMAnalyzer` dan `LLMAnalysisModal` mungkin tidak aktif di aplikasi. Jika masih digunakan, perlu diupdate untuk fetch dari Supabase.

---

## ✅ Hasil Setelah Perubahan

### Sebelum:
- ✅ Review hybrid dari Supabase + reviews.json
- ✅ Filter tabs untuk "Google Reviews" dan "Review Pengguna"
- ✅ Source badge untuk membedakan review source
- ✅ Filtering di ShopList berdasarkan reviews.json

### Sesudah:
- ✅ Review hanya dari Supabase
- ✅ Tidak ada filter tabs (semua review sama)
- ✅ Tidak ada source badge
- ⚠️ Filtering di ShopList sementara tidak tersedia (TODO: implement dengan Supabase)

---

## 🧪 Testing

### Test Case 1: Review Display
1. Buka detail coffee shop
2. **Expected**: 
   - Hanya review dari Supabase yang muncul
   - Tidak ada filter tabs
   - Tidak ada source badge
   - "Belum ada review" jika tidak ada review di Supabase

### Test Case 2: Submit New Review
1. Login sebagai user
2. Submit review baru
3. **Expected**:
   - Review muncul langsung di list
   - Tidak ada badge
   - Review tersimpan di Supabase

### Test Case 3: Guest Mode
1. Logout (mode guest)
2. Buka detail coffee shop
3. **Expected**:
   - Review dari Supabase muncul (jika RLS policy benar)
   - Tidak ada error
   - Tidak ada filter tabs

---

## 📝 Catatan Penting

1. **Filtering di ShopList**:
   - Filter berdasarkan pill preferences sementara tidak tersedia
   - TODO: Implement dengan fetch reviews dari Supabase jika diperlukan
   - Atau gunakan data dari `places.json` (amenities/features) untuk filtering

2. **Personalized Recommendations**:
   - Sekarang menggunakan nama dan address shop sebagai context
   - Bisa di-enhance dengan fetch reviews dari Supabase untuk better recommendations

3. **SmartReviewSummary**:
   - Sekarang fetch reviews sendiri dari Supabase
   - Support backward compatibility dengan reviews dari props

4. **Backward Compatibility**:
   - ReviewCard tetap support `relative_time` untuk backward compatibility
   - SmartReviewSummary tetap support reviews dari props

---

## 🔗 Related Files

- `frontend-cofind/src/components/ReviewList.jsx` - Simplified, hanya Supabase
- `frontend-cofind/src/pages/ShopDetail.jsx` - Hapus reviews.json
- `frontend-cofind/src/pages/ShopList.jsx` - Update filter logic
- `frontend-cofind/src/utils/personalizedRecommendations.js` - Update context extraction
- `frontend-cofind/src/components/SmartReviewSummary.jsx` - Fetch dari Supabase
- `frontend-cofind/src/components/ReviewCard.jsx` - Hapus source badge

---

## 🎯 Action Items

1. **Test Review Display** - Pastikan review dari Supabase muncul
2. **Test Submit Review** - Pastikan review baru muncul
3. **Test Guest Mode** - Pastikan guest bisa melihat review
4. **Optional**: Update LLMAnalyzer dan LLMAnalysisModal jika masih digunakan
