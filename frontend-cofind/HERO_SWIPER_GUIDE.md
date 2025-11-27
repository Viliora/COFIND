# 🎠 Hero Swiper - Auto-Playing Carousel

## 📋 Overview

**Hero Swiper** adalah auto-playing carousel yang menampilkan foto-foto coffee shop terbaik di bagian atas homepage. Carousel ini menggunakan library **Swiper.js** yang powerful dan fully responsive.

---

## ✨ Fitur

### **1. Auto-Play**
- ⏱️ Otomatis berganti slide setiap 4 detik
- ⏸️ Pause saat mouse hover
- 🔄 Loop infinite (kembali ke slide pertama setelah terakhir)

### **2. Smooth Transitions**
- 🎨 Fade effect untuk transisi yang smooth
- ⚡ Durasi transisi 800ms
- 🌊 Cross-fade untuk seamless transition

### **3. Navigation**
- ◀️ ▶️ Arrow buttons (kiri/kanan)
- 🔘 Pagination dots (clickable)
- 📱 Touch/swipe support (mobile)
- ⌨️ Keyboard navigation (arrow keys)

### **4. Smart Selection**
- ⭐ Hanya menampilkan coffee shops dengan rating ≥ 4.0
- 📸 Hanya yang punya foto
- 🏆 Diurutkan berdasarkan rating dan popularitas
- 🎯 Maksimal 8 coffee shops terbaik

### **5. Responsive Design**
- 📱 Mobile: 300px height
- 💻 Tablet: 400px height
- 🖥️ Desktop: 500px height
- 🖥️ Large Desktop: 600px height

### **6. Rich Information**
- 🏷️ Featured badge dengan nomor urut
- ⭐ Rating display
- 👥 Review count
- 📍 Address dengan icon
- 🔗 Link ke detail page
- 🎨 Gradient overlay untuk readability

---

## 🎨 Design Features

### **Visual Elements:**

1. **Image Overlay**
   - Gradient dari hitam (bawah) ke transparan (atas)
   - Hover effect: scale 1.05 (zoom in)
   - Smooth transition 700ms

2. **Content Layout**
   - Badge: Featured #X, Rating, Reviews
   - Title: Large, bold, drop-shadow
   - Address: Icon + text, max 2 lines
   - CTA Button: "Lihat Detail" dengan arrow

3. **Navigation Buttons**
   - Circular design (50px diameter)
   - Semi-transparent background dengan blur
   - Hover effect: darker + scale 1.1
   - Hidden pada mobile kecil (< 480px)

4. **Pagination Dots**
   - Dynamic bullets (hanya 5 dots visible)
   - Active dot: indigo color + wider (32px)
   - Inactive dots: white + semi-transparent

---

## 🔧 Technical Details

### **Library:**
- **Swiper.js** v11+ (latest)
- Modules: Autoplay, Pagination, Navigation, EffectFade

### **Performance:**
- Lazy loading images via OptimizedImage component
- Fallback colors untuk loading state
- Efficient re-renders dengan useMemo/useEffect

### **Accessibility:**
- Keyboard navigation support
- ARIA labels (built-in Swiper)
- Clickable pagination
- Pausable autoplay

---

## 📝 Usage

### **Component Props:**

```jsx
<HeroSwiper coffeeShops={coffeeShops} />
```

**Props:**
- `coffeeShops` (array, required): Array of coffee shop objects dari API

**Coffee Shop Object Structure:**
```javascript
{
  place_id: string,
  name: string,
  photos: [url_string],
  rating: number,
  user_ratings_total: number,
  address: string
}
```

### **Integration Example:**

```jsx
import HeroSwiper from '../components/HeroSwiper';

function ShopList() {
  const [coffeeShops, setCoffeeShops] = useState([]);
  
  return (
    <div>
      {/* Hero Swiper */}
      {coffeeShops.length > 0 && (
        <HeroSwiper coffeeShops={coffeeShops} />
      )}
      
      {/* Rest of content */}
    </div>
  );
}
```

---

## ⚙️ Configuration

### **Autoplay Settings:**

```javascript
autoplay={{
  delay: 4000,              // 4 detik per slide
  disableOnInteraction: false,  // Tetap autoplay setelah interaksi
  pauseOnMouseEnter: true,      // Pause saat hover
}}
```

**Customize:**
- Ubah `delay` untuk durasi per slide (ms)
- Set `disableOnInteraction: true` untuk stop setelah user interact
- Set `pauseOnMouseEnter: false` untuk tidak pause saat hover

### **Transition Settings:**

```javascript
effect="fade"
fadeEffect={{ crossFade: true }}
speed={800}  // Durasi transisi (ms)
```

**Customize:**
- Ganti `effect` dengan: `'slide'`, `'cube'`, `'flip'`, `'coverflow'`
- Ubah `speed` untuk transisi lebih cepat/lambat

### **Selection Logic:**

```javascript
// Di HeroSwiper.jsx, line 19-31
const shopsWithPhotos = coffeeShops
  .filter(shop => 
    shop.photos && 
    shop.photos.length > 0 && 
    shop.rating >= 4.0  // Minimal rating
  )
  .sort((a, b) => {
    // Scoring: 60% rating + 40% popularity
    const scoreA = (a.rating || 0) * 0.6 + ((a.user_ratings_total || 0) / 1000) * 0.4;
    const scoreB = (b.rating || 0) * 0.6 + ((b.user_ratings_total || 0) / 1000) * 0.4;
    return scoreB - scoreA;
  })
  .slice(0, 8);  // Top 8
```

**Customize:**
- Ubah `rating >= 4.0` untuk threshold berbeda
- Ubah scoring formula (60/40 split)
- Ubah `.slice(0, 8)` untuk jumlah slides berbeda

---

## 🎨 Styling Customization

### **Height Adjustment:**

```jsx
// Di HeroSwiper.jsx, line 59
<div className="relative w-full 
  h-[300px]      // Mobile
  sm:h-[400px]   // Tablet
  md:h-[500px]   // Desktop
  lg:h-[600px]   // Large Desktop
">
```

### **Colors:**

```jsx
// Badge colors
bg-yellow-400 text-yellow-900  // Featured badge
bg-white/20                     // Rating/Reviews badge

// Button
bg-indigo-600 hover:bg-indigo-700

// Gradient overlay
bg-gradient-to-t from-black/80 via-black/40 to-transparent
```

### **Typography:**

```jsx
// Title sizes
text-2xl sm:text-3xl md:text-4xl lg:text-5xl

// Address sizes
text-sm sm:text-base md:text-lg
```

---

## 📱 Responsive Behavior

### **Mobile (< 640px):**
- Height: 300px
- Navigation buttons: 40px
- No navigation buttons pada < 480px
- Title: text-2xl
- Address: text-sm

### **Tablet (640px - 1024px):**
- Height: 400px
- Navigation buttons: 50px
- Title: text-3xl
- Address: text-base

### **Desktop (> 1024px):**
- Height: 500px - 600px
- Full navigation
- Title: text-4xl - text-5xl
- Address: text-lg

---

## 🐛 Troubleshooting

### **Problem 1: Swiper tidak muncul**

**Penyebab:** CSS Swiper tidak ter-import

**Solusi:**
```javascript
// Pastikan ada di HeroSwiper.jsx
import 'swiper/css';
import 'swiper/css/pagination';
import 'swiper/css/navigation';
import 'swiper/css/effect-fade';
```

### **Problem 2: Foto tidak muncul**

**Penyebab:** Coffee shops tidak punya foto atau backend belum di-restart

**Solusi:**
1. Check console: `[HeroSwiper] Found X shops with photos`
2. Verify API response punya field `photos` dengan URLs
3. Restart backend jika perlu

### **Problem 3: Autoplay tidak jalan**

**Penyebab:** Module Autoplay tidak di-import

**Solusi:**
```javascript
// Pastikan ada di import
import { Autoplay, Pagination, Navigation, EffectFade } from 'swiper/modules';

// Dan di modules prop
modules={[Autoplay, Pagination, Navigation, EffectFade]}
```

### **Problem 4: Navigation buttons tidak muncul**

**Penyebab:** Module Navigation tidak di-import atau CSS tidak loaded

**Solusi:**
1. Check import modules
2. Check CSS import: `import 'swiper/css/navigation';`
3. Check browser console untuk errors

### **Problem 5: Slides tidak smooth**

**Penyebab:** Effect fade tidak aktif atau speed terlalu cepat

**Solusi:**
```javascript
effect="fade"
fadeEffect={{ crossFade: true }}
speed={800}  // Increase untuk lebih smooth
```

---

## 🎯 Best Practices

### **✅ DO:**

1. **Gunakan foto berkualitas tinggi**
   - Minimal 800px width
   - Aspect ratio 16:9 atau 21:9

2. **Limit jumlah slides**
   - Maksimal 8-10 slides
   - Terlalu banyak = loading lambat

3. **Optimize images**
   - Gunakan OptimizedImage component
   - Lazy loading untuk performa

4. **Test di berbagai device**
   - Mobile, tablet, desktop
   - Portrait dan landscape

5. **Monitor performance**
   - Check loading time
   - Optimize jika perlu

### **❌ DON'T:**

1. **Jangan autoplay terlalu cepat**
   - Minimal 3-4 detik per slide
   - User perlu waktu baca content

2. **Jangan terlalu banyak text**
   - Keep it simple
   - Focus on visual

3. **Jangan disable navigation**
   - User harus bisa control
   - Accessibility penting

4. **Jangan gunakan foto low quality**
   - Blur/pixelated = bad UX
   - Gunakan fallback color

---

## 🚀 Advanced Features

### **Custom Transition Effects:**

```javascript
// Ganti fade dengan slide
effect="slide"
slidesPerView={1}
spaceBetween={30}

// Atau coverflow effect
effect="coverflow"
coverflowEffect={{
  rotate: 50,
  stretch: 0,
  depth: 100,
  modifier: 1,
  slideShadows: true,
}}
```

### **Parallax Effect:**

```javascript
import { Parallax } from 'swiper/modules';

modules={[Autoplay, Pagination, Navigation, Parallax]}
parallax={true}

// Di content
<div data-swiper-parallax="-300">
  <h2>{shop.name}</h2>
</div>
```

### **Thumbnail Navigation:**

```javascript
import { Thumbs } from 'swiper/modules';

const [thumbsSwiper, setThumbsSwiper] = useState(null);

<Swiper thumbs={{ swiper: thumbsSwiper }}>
  {/* Main slides */}
</Swiper>

<Swiper onSwiper={setThumbsSwiper}>
  {/* Thumbnail slides */}
</Swiper>
```

---

## 📊 Performance Metrics

### **Target Performance:**

- **First Paint:** < 1s
- **Fully Loaded:** < 2s
- **Autoplay Start:** Immediate
- **Transition Duration:** 800ms
- **Image Load:** Progressive (lazy)

### **Optimization Tips:**

1. **Preload first slide image**
2. **Lazy load subsequent slides**
3. **Use WebP format jika supported**
4. **Compress images (max 200KB per image)**
5. **Use CDN untuk Swiper library**

---

## 📚 Resources

### **Documentation:**
- Swiper.js: https://swiperjs.com/
- React Swiper: https://swiperjs.com/react

### **Examples:**
- Effect Demos: https://swiperjs.com/demos
- API Reference: https://swiperjs.com/swiper-api

### **Related Files:**
```
frontend-cofind/
├── src/
│   ├── components/
│   │   ├── HeroSwiper.jsx       ← Main component
│   │   └── OptimizedImage.jsx   ← Image optimization
│   └── pages/
│       └── ShopList.jsx          ← Integration
└── HERO_SWIPER_GUIDE.md          ← This file
```

---

## ✅ Summary

**Hero Swiper adalah auto-playing carousel yang:**

- 🎨 **Beautiful** - Modern design dengan smooth transitions
- ⚡ **Fast** - Optimized untuk performa
- 📱 **Responsive** - Bekerja di semua device
- ♿ **Accessible** - Keyboard navigation & ARIA labels
- 🎯 **Smart** - Hanya tampilkan coffee shops terbaik
- 🔧 **Customizable** - Easy to configure

**Perfect untuk showcase coffee shops di homepage! 🚀**

