# ⚡ Hero Swiper - Quick Start

## 🎯 Apa yang Sudah Dibuat?

**Auto-playing carousel** di bagian atas homepage yang menampilkan foto-foto coffee shop terbaik dari API!

---

## ✅ Fitur

✨ **Auto-play** - Berganti slide setiap 4 detik
🎨 **Smooth fade transition** - Transisi yang halus
◀️ ▶️ **Navigation arrows** - Bisa diklik untuk next/prev
🔘 **Pagination dots** - Clickable dots di bawah
📱 **Touch/Swipe** - Support gesture di mobile
⏸️ **Pause on hover** - Pause saat mouse hover
🔄 **Infinite loop** - Kembali ke awal setelah slide terakhir
⭐ **Smart selection** - Hanya coffee shops rating ≥ 4.0

---

## 🚀 Cara Melihat

### **1. Pastikan Backend & Frontend Running**

```bash
# Backend
cd C:\Users\User\cofind
python app.py

# Frontend (terminal baru)
cd frontend-cofind
npm run dev
```

### **2. Buka Browser**

```
http://localhost:5173
```

### **3. Lihat Hero Swiper**

Carousel akan muncul di **bagian paling atas** homepage, sebelum header "Temukan Coffee Shop Terbaik di Pontianak".

---

## 🎨 Tampilan

### **Setiap Slide Menampilkan:**

1. **Foto Coffee Shop** (full width, responsive height)
2. **Featured Badge** - "⭐ Featured #1, #2, dst"
3. **Rating Badge** - "4.5 ★"
4. **Review Count** - "555 reviews"
5. **Nama Coffee Shop** - Large, bold title
6. **Alamat** - Dengan icon lokasi
7. **CTA Button** - "Lihat Detail" dengan arrow

### **Navigation:**

- **Arrow Buttons** - Kiri/Kanan (desktop)
- **Pagination Dots** - Bawah tengah (semua device)
- **Touch/Swipe** - Geser kiri/kanan (mobile)
- **Keyboard** - Arrow keys (desktop)

---

## ⚙️ Konfigurasi

### **Jumlah Slides:**

Default: **8 coffee shops terbaik**

Untuk mengubah, edit `frontend-cofind/src/components/HeroSwiper.jsx` line 31:

```javascript
.slice(0, 8);  // Ubah angka 8 sesuai kebutuhan
```

### **Durasi Auto-play:**

Default: **4 detik per slide**

Untuk mengubah, edit line 50:

```javascript
autoplay={{
  delay: 4000,  // Ubah dalam milliseconds (4000 = 4 detik)
}}
```

### **Minimal Rating:**

Default: **Rating ≥ 4.0**

Untuk mengubah, edit line 23:

```javascript
.filter(shop => shop.rating >= 4.0)  // Ubah threshold
```

### **Height:**

Default: 
- Mobile: 300px
- Tablet: 400px
- Desktop: 500px
- Large: 600px

Untuk mengubah, edit line 59:

```javascript
h-[300px] sm:h-[400px] md:h-[500px] lg:h-[600px]
```

---

## 🐛 Troubleshooting

### **Swiper tidak muncul?**

1. **Check console untuk errors**
   ```
   F12 → Console
   ```

2. **Pastikan ada coffee shops dengan foto**
   ```
   Minimal 1 coffee shop dengan:
   - rating ≥ 4.0
   - photos tidak kosong
   ```

3. **Clear cache dan reload**
   ```
   Ctrl+Shift+R (Hard Reload)
   ```

### **Foto tidak muncul?**

1. **Restart backend** (backend harus sudah diperbaiki)
   ```bash
   Ctrl+C → python app.py
   ```

2. **Clear browser cache**
   ```
   F12 → Right-click Refresh → Empty Cache and Hard Reload
   ```

### **Autoplay tidak jalan?**

1. **Check browser console** untuk errors
2. **Pastikan Swiper modules loaded**
3. **Refresh page**

---

## 🎯 Tips

### **Untuk Development:**

1. **Gunakan dev-browser.html** untuk quick testing
2. **Monitor console logs** untuk debug
3. **Test di berbagai screen sizes** (responsive)

### **Untuk Production:**

1. **Optimize images** (compress, WebP format)
2. **Test loading time** (< 2 detik ideal)
3. **Test di berbagai browsers** (Chrome, Firefox, Safari)

---

## 📝 Files Created/Modified

### **New Files:**
1. `frontend-cofind/src/components/HeroSwiper.jsx` - Main component
2. `frontend-cofind/HERO_SWIPER_GUIDE.md` - Full documentation
3. `HERO_SWIPER_QUICK_START.md` - This file

### **Modified Files:**
1. `frontend-cofind/src/pages/ShopList.jsx` - Added HeroSwiper integration
2. `frontend-cofind/package.json` - Added swiper dependency

### **Installed:**
- `swiper` - Carousel library (v11+)

---

## ✨ Features Breakdown

### **Auto-Play:**
- ✅ Otomatis berganti slide
- ✅ Pause saat hover
- ✅ Resume setelah mouse leave
- ✅ Infinite loop

### **Navigation:**
- ✅ Arrow buttons (kiri/kanan)
- ✅ Pagination dots (clickable)
- ✅ Touch/swipe gestures
- ✅ Keyboard arrow keys

### **Visual:**
- ✅ Fade transition effect
- ✅ Gradient overlay
- ✅ Hover zoom effect (1.05x)
- ✅ Responsive heights

### **Content:**
- ✅ Featured badge
- ✅ Rating & reviews
- ✅ Coffee shop name
- ✅ Address with icon
- ✅ CTA button

### **Smart Selection:**
- ✅ Only shops with photos
- ✅ Only rating ≥ 4.0
- ✅ Sorted by score (rating + popularity)
- ✅ Top 8 shops

---

## 🚀 Next Steps

### **Optional Enhancements:**

1. **Add more transition effects**
   - Slide, cube, flip, coverflow

2. **Add video support**
   - Mix photos with videos

3. **Add social sharing**
   - Share button untuk setiap slide

4. **Add analytics**
   - Track which slides get most clicks

5. **Add lazy loading**
   - Load images only when needed

---

## 📚 Documentation

**Full Guide:** `frontend-cofind/HERO_SWIPER_GUIDE.md`

**Swiper Docs:** https://swiperjs.com/react

---

## ✅ Summary

**Hero Swiper sudah berhasil dibuat dan terintegrasi!**

- 🎨 Modern auto-playing carousel
- 📸 Menampilkan foto coffee shops dari API
- ⚡ Smooth transitions & responsive
- 🎯 Smart selection (top rated shops)
- 📱 Works on all devices

**Buka `http://localhost:5173` untuk melihat hasilnya! 🎉**

