# Performance Optimization Guide - COFIND

## 📊 Current Issues (dari Lighthouse Audit)

| Metric | Current | Target | Status |
|--------|---------|--------|--------|
| **FCP** (First Contentful Paint) | 14.7s | < 1.8s | 🔴 Critical |
| **LCP** (Largest Contentful Paint) | 34.5s | < 2.5s | 🔴 Critical |
| **Speed Index** | 17.5s | < 3.5s | 🔴 Critical |
| **TBT** (Total Blocking Time) | 580ms | < 200ms | 🟠 Needs Fix |
| **Performance Score** | 40 | 90+ | 🔴 Very Low |

---

## 🎯 Root Causes & Solutions

### 1. **Heavy Images Blocking Initial Load** (FCP/LCP issue)

**Problem**: Hero image (`1R modern cafe 1.5.jpg`) dan profile photos dari Supabase blokir initial paint.

**Current Status**:
- ✅ `OptimizedImage` component sudah implement lazy loading dengan Intersection Observer
- ✅ Image preloading strategy sudah ada
- ❌ Tapi hero image masih load synchronously di critical render path

**Solution**:
```jsx
// Current (BLOCKING):
import heroBgImage from '../assets/1R modern cafe 1.5.jpg';
style={{ backgroundImage: `url(${heroBgImage})` }}

// Solution - Defer hero image load:
// Option A: Delay dengan requestIdleCallback
useEffect(() => {
  requestIdleCallback(() => {
    setHeroImageLoaded(true);
  });
}, []);

// Option B: Use <picture> with WebP + lazy loading
<picture>
  <source srcSet={heroBgImageWebP} type="image/webp" />
  <img src={heroBgImageJpg} loading="lazy" ... />
</picture>

// Option C: Skip hero image pada first paint, load later
{heroImageReady && <HeroSection />}
```

**ACTION ITEMS**:
- [ ] Convert `1R modern cafe 1.5.jpg` → `.webp` format (~60% size reduction)
- [ ] Add `loading="lazy"` to all CoffeeShopCard images
- [ ] Defer hero section rendering sampai page paint selesai

---

### 2. **Large JavaScript Bundle** (affecting TBT)

**Problem**: React + Supabase + dependencies = large bundle size, parsing/execution blocking main thread.

**Current Status**:
- ✅ Vite sudah setup dengan code splitting via `rollupOptions`
- ❌ Tapi components tidak lazy loaded
- ❌ All pages loaded on app start

**Solution - Code Splitting**:
```jsx
// Use React.lazy() untuk page components:
import { lazy, Suspense } from 'react';

const ShopList = lazy(() => import('./pages/ShopList'));
const ShopDetail = lazy(() => import('./pages/ShopDetail'));
const Admin = lazy(() => import('./pages/Admin'));
const Profile = lazy(() => import('./pages/Profile'));

// Router dengan Suspense fallback
<Routes>
  <Route path="/" element={<Suspense fallback={<LoadingSpinner />}><ShopList /></Suspense>} />
  <Route path="/shop/:id" element={<Suspense fallback={<LoadingSpinner />}><ShopDetail /></Suspense>} />
</Routes>
```

**ACTION ITEMS**:
- [ ] Add `React.lazy()` untuk all page components
- [ ] Create loading fallback component
- [ ] Verify in DevTools Network → JS files > 50KB chunk uploaded separately

---

### 3. **Fonts Blocking Render** (FCP delay)

**Problem**: System fonts bisa berada di critical render path.

**Solution - Font Optimization**:
```css
/* In App.css or index.css */
@font-face {
  font-family: 'Custom';
  src: url('/fonts/custom.woff2') format('woff2');
  font-display: swap; /* CRITICAL: Show fallback while loading */
  font-weight: 400;
  font-style: normal;
}

/* Use system font stack as fallback */
body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
}
```

**ACTION ITEMS**:
- [ ] Add `font-display: swap` jika ada custom fonts
- [ ] Preload critical fonts: `<link rel="preload" href="font.woff2" as="font">`
- [ ] Use system fonts untuk body text (faster)

---

### 4. **IndexedDB Operations Slowing Down Initial Load**

**Problem**: Database operations di AuthContext init bisa block render.

**Current Code Issue** (AuthContext):
```jsx
// This runs on mount and could delay initialization
const validation = await validateSession(); // IndexedDB read?
const profileData = await getUserProfile(userId); // DB read?
```

**Solution - Async IndexedDB**:
```jsx
// Option A: Defer IndexedDB operations
useEffect(() => {
  // Priority: Return cached user ASAP, load fresh data in background
  setUser(cachedUser); // Instant
  
  // Then fetch fresh in background (non-blocking)
  validateSessionAsync();
  fetchProfileAsync();
}, []);

// Option B: Remove unnecessary IndexedDB calls
// If data already in Supabase, don't cache redundantly
```

**ACTION ITEMS**:
- [ ] Audit IndexedDB usage in AuthContext - remove if not needed
- [ ] Move DB operations off critical path (use background tasks)
- [ ] Clear old IndexedDB data regularly

---

### 5. **Disable Development Cache** ✅ (Already Done)

**Status**: Development cache disabled, now all requests fetch fresh. This prevents stale data but doesn't help performance.

**Note**: This was needed for auth/session fixes, not performance. Performance should improve in production with Supabase caching.

---

## 🚀 Development Mode vs Production Mode

### **Development Mode** (`npm run dev`)
- ✅ Hot Module Replacement (HMR) - instant updates
- ✅ Source maps untuk debugging
- ✅ Console logs visible
- ❌ **NO code minification**
- ❌ **NO tree shaking**
- ❌ **NO bundling optimization**
- ❌ **Large bundle size** (~500KB+)
- ❌ **Slow initial load**
- **Performance Score**: 40-60 (because of above)

### **Production Mode** (`npm run build`)
- ✅ Full minification & tree-shaking
- ✅ Code splitting
- ✅ Asset optimization (WebP, compression)
- ✅ Bundling optimization
- ✅ **Small bundle** (~150KB gzip)
- ✅ **Fast load**
- ❌ Hard to debug (source maps optional)
- **Performance Score**: 80-95 (typical)

---

## ❓ Apakah Anda Memerlukan Development Mode?

### **YES, use development mode when:**
- 🛠️ Actively developing features
- 🐛 Debugging issues
- 🔄 Want HMR (instant refresh)
- 📝 Making frequent code changes

### **NO, use production mode when:**
- 📊 Testing performance
- 👀 Showcasing to users
- 📱 Testing on actual devices
- 🎯 Checking Lighthouse score

---

## 📋 Optimization Checklist - Priority Order

### 🔴 **CRITICAL** (Do First - Will have 2-3x impact)
- [ ] **Convert images to WebP** (hero image, fallback images)
  - Reduces image size by 60%
  - Add: `<picture>` tag with WebP + JPG fallback
  
- [ ] **Implement code splitting**
  - Wrap all pages with `React.lazy()`
  - Create loading fallback
  - Reduces initial JS by 50%+

- [ ] **Defer hero image loading**
  - Don't load on first render
  - Load after initial paint completes
  - Or use low-res placeholder + progressive enhancement

### 🟠 **HIGH** (Do Second)
- [ ] **Audit & remove IndexedDB ops from critical path**
  - Move to background/idle callbacks
  - OR cache in memory only (clear on logout)

- [ ] **Add preload hints** for critical resources
  ```html
  <link rel="preload" href="critical-font.woff2" as="font" />
  <link rel="preload" href="app-chunk.js" />
  ```

- [ ] **Enable compression** on backend
  - Add gzip/brotli to Flask app

### 🟡 **MEDIUM** (Nice to have)
- [ ] **Service Worker caching strategy** optimization
  - Cache network responses
  - Implement stale-while-revalidate

- [ ] **Font optimization** (if custom fonts used)
  - Add `font-display: swap`
  - Preload critical fonts

### 🟢 **LOW** (Minimal impact but good practice)
- [ ] Add `<link rel="dns-prefetch">` for external APIs
- [ ] Minify CSS/HTML (Vite does automatically)
- [ ] Update react/react-dom to latest

---

## 🧪 How to Test Performance

### **Development Mode (Current - DON'T test here)**
```bash
npm run dev
# ❌ Performance will be SLOW (expected)
# ✅ Only for development workflow
```

### **Production Mode (TEST here)**
```bash
npm run build
npm run preview
# Open http://localhost:4173
# 
# Run Lighthouse:
# - Chrome DevTools → Lighthouse tab
# - Throttling: "Slow 4G" + "4x CPU slowdown"
# - Generate report
```

### **Key Metrics to Watch**
```
✅ FCP < 1.8s
✅ LCP < 2.5s
✅ Speed Index < 3.5s
✅ TBT < 200ms
✅ CLS < 0.1
```

---

## 📝 Implementation Guide - WebP Conversion

### Step 1: Install Image Converter
```powershell
# Using ImageMagick (recommended)
choco install imagemagick

# Or online: https://convertio.co/jpg-webp/
```

### Step 2: Convert Images
```powershell
# Convert JPG → WebP
magick convert "1R modern cafe 1.5.jpg" "1R modern cafe 1.5.webp"

# Verify size reduction
ls -la "1R modern cafe*"
```

### Step 3: Update Code
```jsx
// In ShopList.jsx
import heroBgImageJpg from '../assets/1R modern cafe 1.5.jpg';
import heroBgImageWebP from '../assets/1R modern cafe 1.5.webp';

<picture>
  <source srcSet={heroBgImageWebP} type="image/webp" />
  <img src={heroBgImageJpg} alt="Hero" />
</picture>
```

---

## 📊 Expected Performance Improvement

**Before Optimization**:
```
FCP: 14.7s → LCP: 34.5s
Performance: 40
```

**After Code Splitting + WebP + Lazy Loading**:
```
FCP: ~2s → LCP: ~5s
Performance: 75-80
```

**With Production Build + All Optimizations**:
```
FCP: ~0.8s → LCP: ~2s
Performance: 85-95
```

---

## 🎯 Summary

1. **You DO need development mode** for active development
2. **You DON'T test performance in development mode** - it's inherently slow
3. **To fix performance, focus on:**
   - ✅ Convert images to WebP
   - ✅ Code splitting (lazy load pages)
   - ✅ Defer non-critical resources
   - ✅ Test in production mode

4. **This will improve Lighthouse score from 40 → 85+ significantly**

---

**Recommendation**: Implement code splitting first (biggest impact), then WebP conversion, then tackle IndexedDB optimization.

