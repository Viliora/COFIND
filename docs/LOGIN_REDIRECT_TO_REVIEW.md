# Fitur: Redirect ke Review Form Setelah Login

## 🎯 Deskripsi Fitur

Ketika guest menekan tombol "Masuk untuk Review" di halaman detail coffee shop, setelah login berhasil, user akan:
1. ✅ Diarahkan kembali ke halaman detail coffee shop yang sama
2. ✅ Otomatis scroll ke bagian review form
3. ✅ Siap untuk menulis review

---

## 🔄 Flow yang Diimplementasikan

### 1. **Guest di Detail Coffee Shop**
```
Guest → Detail Coffee Shop → Klik "Masuk untuk Review"
```

### 2. **Redirect ke Login dengan State**
```
ReviewForm → Link dengan state:
- from: `/shop/{placeId}`
- placeId: `{placeId}`
- shopName: `{shopName}`
- scrollToReview: true
```

### 3. **Login Berhasil**
```
Login → useEffect detect isAuthenticated → Navigate dengan state
```

### 4. **Kembali ke Detail + Scroll**
```
ShopDetail → useEffect detect scrollToReview → Scroll ke review form
```

---

## 📝 Perubahan yang Dibuat

### 1. **ReviewForm.jsx**
- ✅ Update `Link` untuk pass state ke login page
- ✅ Include `placeId`, `shopName`, dan `scrollToReview` flag

```jsx
<Link
  to="/login"
  state={{
    from: {
      pathname: `/shop/${placeId}`,
      search: '?scrollToReview=true'
    },
    placeId: placeId,
    shopName: shopName,
    scrollToReview: true
  }}
>
  Masuk untuk Review
</Link>
```

### 2. **Login.jsx**
- ✅ Update `useEffect` untuk handle redirect dengan state
- ✅ Support multiple state formats
- ✅ Pass state ke ShopDetail saat redirect

```jsx
useEffect(() => {
  if (isAuthenticated && !isSubmitting) {
    const redirectState = location.state;
    let redirectPath = '/';
    let scrollToReview = false;
    let placeId = null;
    
    // Handle different state formats
    if (redirectState?.from?.pathname) {
      redirectPath = redirectState.from.pathname;
      scrollToReview = redirectState.scrollToReview;
      placeId = redirectState.placeId;
    }
    // ... other formats
    
    navigate(redirectPath, { 
      replace: true,
      state: {
        scrollToReview: scrollToReview,
        placeId: placeId
      }
    });
  }
}, [isAuthenticated, navigate, location, isSubmitting]);
```

### 3. **ShopDetail.jsx**
- ✅ Tambah `useRef` untuk review form element
- ✅ Tambah `useEffect` untuk scroll ke review form
- ✅ Wrap ReviewForm dengan `div` yang punya ref

```jsx
const reviewFormRef = useRef(null);

useEffect(() => {
  const shouldScrollToReview = location.state?.scrollToReview;
  
  if (shouldScrollToReview && isAuthenticated && shop && !isLoading) {
    setTimeout(() => {
      if (reviewFormRef.current) {
        const navbarHeight = 60;
        const elementPosition = reviewFormRef.current.getBoundingClientRect().top;
        const offsetPosition = elementPosition + window.pageYOffset - navbarHeight;
        
        window.scrollTo({
          top: offsetPosition,
          behavior: 'smooth'
        });
      }
    }, 800);
  }
}, [isAuthenticated, shop, isLoading, location]);

// In JSX:
<div ref={reviewFormRef}>
  <ReviewForm ... />
</div>
```

---

## ✅ Testing

### Test Case 1: Guest → Login → Redirect
1. Buka detail coffee shop sebagai guest
2. Klik "Masuk untuk Review"
3. Login dengan username dan password
4. **Expected**: 
   - Redirect ke halaman detail coffee shop yang sama
   - Otomatis scroll ke review form
   - Review form terlihat dan siap digunakan

### Test Case 2: Guest → Sign Up → Auto Login → Redirect
1. Buka detail coffee shop sebagai guest
2. Klik "Masuk untuk Review"
3. Sign up dengan username baru
4. **Expected**:
   - Auto-login setelah signup
   - Redirect ke halaman detail coffee shop yang sama
   - Otomatis scroll ke review form

### Test Case 3: Direct Login (tanpa dari ReviewForm)
1. Buka `/login` langsung
2. Login
3. **Expected**:
   - Redirect ke home (`/`)
   - Tidak ada scroll behavior

---

## 🎨 UX Improvements

1. ✅ **Smooth Scroll**: Menggunakan `behavior: 'smooth'` untuk scroll yang halus
2. ✅ **Navbar Offset**: Menghitung offset untuk navbar agar review form tidak tertutup
3. ✅ **Delay**: 800ms delay untuk memastikan semua content ter-render sebelum scroll
4. ✅ **State Cleanup**: Clear state setelah scroll untuk prevent re-scroll pada refresh

---

## 📝 Catatan Penting

1. **State Persistence**: State hanya bertahan selama session, tidak persist di refresh
2. **Multiple Formats**: Support berbagai format state untuk backward compatibility
3. **Auto-login**: Setelah signup, user otomatis login dan redirect
4. **Error Handling**: Jika login gagal, user tetap di login page (tidak redirect)

---

## 🔧 Troubleshooting

### Masalah: Tidak scroll ke review form
- **Cek**: Apakah `location.state?.scrollToReview` ada?
- **Cek**: Apakah `isAuthenticated` sudah true?
- **Cek**: Apakah `shop` sudah ter-load?
- **Cek**: Console log untuk `[ShopDetail] Scrolled to review form after login`

### Masalah: Redirect ke home bukan detail
- **Cek**: Apakah `location.state` ter-pass dengan benar dari ReviewForm?
- **Cek**: Console log untuk `[Login] Redirecting after login`

### Masalah: Scroll terlalu cepat (sebelum render)
- **Solusi**: Increase timeout di `setTimeout` (saat ini 800ms)
