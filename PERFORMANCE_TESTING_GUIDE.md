# Performance Testing Guide - COFIND

## 🚀 Quick Start to Test Performance Improvements

### Step 1: Build Production Version
```powershell
cd frontend-cofind
npm run build
```

**What happens**:
- ✅ Code splitting: Each page becomes separate JS file
- ✅ Minification: All code minified and uglified
- ✅ Tree shaking: Unused code removed
- ✅ Bundle size: ~500KB dev → ~150KB production (gzip)

**Output**:
```
frontend-cofind/dist/
├── assets/
│   ├── index-[hash].js          (main app shell - small)
│   ├── ShopList-[hash].js        (ShopList page - loaded on demand)
│   ├── ShopDetail-[hash].js      (ShopDetail page - loaded on demand)
│   ├── Admin-[hash].js           (Admin page - loaded on demand)
│   ├── style-[hash].css          (all CSS minified)
│   └── ...
├── index.html                     (entry point)
└── (other assets)
```

---

### Step 2: Run Production Preview Server
```powershell
npm run preview
```

**Output**:
```
  ➜  Local:   http://localhost:4173/
  ➜  press h + enter to show help
```

---

### Step 3: Test Performance with Lighthouse

#### Using Chrome DevTools (Recommended)

1. Open `http://localhost:4173` in Chrome
2. Press `F12` → Open DevTools
3. Go to **Lighthouse** tab (rightmost)
4. Click **Analyze page load**

**Optional - Simulate Slow Network**:
1. DevTools → **Network** tab
2. Throttling dropdown → Select **Slow 4G**
3. CPU Throttling → Select **4x slowdown**
4. Then run Lighthouse audit

---

#### Using Lighthouse CLI

```powershell
# Install if not already
npm install -g @lhci/cli@latest

# Run audit
lhci autorun --config="./lighthouserc.json"
```

---

### Step 4: Measure Improvements

**Run before and after each optimization**:

| Metric | Target | How to Check |
|--------|--------|-------------|
| **FCP** | < 1.8s | Lighthouse → Metrics |
| **LCP** | < 2.5s | Lighthouse → Metrics |
| **TBT** | < 200ms | Lighthouse → Metrics |
| **Bundle** | < 200KB | DevTools → Network → JS |
| **Score** | 80+ | Lighthouse → Performance |

---

## 📊 Expected Results After Code Splitting

### Before (without lazy loading)
```
Initial Bundle: ~500KB (all pages included)
FCP: 2-3s
Performance: 40-50
Time to Interactive: 5-8s
```

### After (with code splitting)
```
Initial Bundle: ~150KB (only ShopList + core)
FCP: 0.8-1.2s
Performance: 75-85
Time to Interactive: 2-3s
Additional pages: 50-80KB each (loaded on demand)
```

---

## 🔄 Development vs Production Mode

### Commands
```powershell
# DEVELOPMENT - for local development
npm run dev
# 💻 HMR enabled, fast refresh, slow performance (EXPECTED)
# ❌ DON'T test performance here

# PRODUCTION - for testing & deployment
npm run build
npm run preview
# ✅ Full optimization, production-ready
# ✅ TEST PERFORMANCE HERE
```

---

## ✅ Checklist - Code Splitting Complete

- [x] All page components wrapped with `React.lazy()`
- [x] All routes wrapped with `<Suspense>`
- [x] Loading fallback component created (`PageLoadingFallback`)
- [x] Vite auto-splits code at chunk boundaries
- [x] Ready for production build

---

## 📝 Next Steps (Optional Optimizations)

### If still want faster:

1. **Convert Hero Image to WebP** (60% size reduction)
   ```bash
   magick convert "1R modern cafe 1.5.jpg" "1R modern cafe 1.5.webp"
   ```
   Then update code to use WebP with JPG fallback.

2. **Preload Critical Resources**
   ```html
   <!-- In index.html -->
   <link rel="preload" href="/assets/index-[hash].js" as="script" />
   ```

3. **Add Service Worker Caching** (already setup, just optimize)
   - Implement cache-first strategy for images
   - Implement stale-while-revalidate for API

---

## 🐛 Troubleshooting

### **Preview server shows blank page**
```powershell
# Clear cache and rebuild
rm -r dist
npm run build
npm run preview
```

### **Performance still slow**
1. Check DevTools **Network** tab - see which files are slow
2. Check DevTools **Performance** tab - see where time is spent
3. Look for:
   - Large images (use WebP)
   - Unneeded libraries (check bundle size)
   - Blocking JavaScript (use `async` or `defer`)

### **Code splitting not working**
1. Check browser DevTools **Network** tab
2. Should see separate JS files per page
3. If not, check console for errors

---

## 📞 Support

- **Lighthouse Docs**: https://developers.google.com/web/tools/lighthouse
- **Vite Code Splitting**: https://vitejs.dev/guide/features.html#code-splitting
- **React.lazy() Docs**: https://react.dev/reference/react/lazy

---

**Remember**: Always test performance in **production mode** (`npm run build`), not development mode!
