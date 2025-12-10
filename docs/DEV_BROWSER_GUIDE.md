# 🌐 Development Browser Guide

## 📋 Apa Itu Development Browser?

**Development Browser** adalah tool untuk mempermudah development web dengan menampilkan semua halaman aplikasi dalam satu window dengan tab navigation.

### ✨ Fitur:

1. **Multi-Tab Interface** - Lihat semua halaman dalam satu window
2. **Quick Refresh** - Refresh satu tab atau semua tab sekaligus
3. **Cache Control** - Clear development cache dengan mudah
4. **Status Monitor** - Monitor status frontend & backend real-time
5. **Keyboard Shortcuts** - Navigasi cepat dengan keyboard
6. **URL Bar** - Lihat URL current page
7. **External Open** - Buka halaman di browser eksternal

---

## 🚀 Cara Menggunakan

### **1. Start Development Servers**

```bash
# Terminal 1: Start Backend
cd C:\Users\User\cofind
python app.py

# Terminal 2: Start Frontend
cd frontend-cofind
npm run dev
```

### **2. Buka Development Browser**

```
file:///C:/Users/User/cofind/dev-browser.html
```

Atau double-click file `dev-browser.html` di File Explorer.

### **3. Navigasi Antar Tab**

Klik tab untuk berpindah halaman:
- 🏠 **Beranda** - Halaman utama dengan list coffee shops
- ❤️ **Favorite** - Halaman favorite coffee shops
- 📄 **Detail** - Halaman detail coffee shop (contoh)
- ℹ️ **About** - Halaman about
- 🔧 **API Test** - Test endpoint backend API

---

## ⌨️ Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl/Cmd + R` | Refresh current tab |
| `Ctrl/Cmd + Shift + R` | Refresh all tabs |
| `Ctrl/Cmd + 1` | Switch to Beranda |
| `Ctrl/Cmd + 2` | Switch to Favorite |
| `Ctrl/Cmd + 3` | Switch to Detail |
| `Ctrl/Cmd + 4` | Switch to About |
| `Ctrl/Cmd + 5` | Switch to API Test |

---

## 🔧 Toolbar Buttons

### **🔄 Refresh All**
Refresh semua tabs sekaligus. Berguna saat:
- Backend code berubah
- Ingin melihat perubahan di semua halaman

### **↻ Refresh Current**
Refresh hanya tab yang sedang aktif. Berguna saat:
- Testing perubahan di satu halaman
- Ingin reload cepat

### **🗑️ Clear Cache**
Clear development cache dan reload semua tabs. Berguna saat:
- Data tidak update
- Melihat data lama dari cache
- Backend API response berubah

### **↗ Open External**
Buka halaman current tab di browser eksternal. Berguna saat:
- Ingin inspect dengan DevTools penuh
- Testing di browser berbeda
- Debugging lebih detail

---

## 📊 Status Bar

Status bar di bawah menampilkan:

### **Frontend Status**
- 🟢 **Running** - Frontend server aktif di `localhost:5173`
- 🔴 **Offline** - Frontend server tidak berjalan

### **Backend Status**
- 🟢 **Running** - Backend server aktif di `localhost:5000`
- 🔴 **Offline** - Backend server tidak berjalan

### **Current Time**
Menampilkan waktu real-time untuk tracking development session.

---

## 🎯 Use Cases

### **1. Testing Perubahan UI**

```
1. Edit component di VSCode
2. Klik "↻ Refresh Current" di dev browser
3. Lihat perubahan langsung tanpa switch window
```

### **2. Testing Multi-Page Flow**

```
1. Test flow: Beranda → Detail → Favorite
2. Switch tab dengan Ctrl+1, Ctrl+2, Ctrl+3
3. Lihat semua halaman tanpa navigasi manual
```

### **3. Debugging API Issues**

```
1. Buka tab "🔧 API Test"
2. Check backend status
3. Jika error, fix backend code
4. Klik "🔄 Refresh All"
```

### **4. Cache Testing**

```
1. Load data pertama kali
2. Klik "🗑️ Clear Cache"
3. Reload untuk test fresh data fetch
```

---

## 🛠️ Customization

### **Menambah Tab Baru**

Edit `dev-browser.html`, tambahkan di section tabs:

```html
<div class="tab" data-page="new-page" onclick="switchTab('new-page')">
    <span class="tab-icon">🆕</span>
    <span>New Page</span>
</div>
```

Dan tambahkan iframe container:

```html
<div class="iframe-container" id="new-page">
    <iframe src="http://localhost:5173/new-page" id="iframe-new-page"></iframe>
</div>
```

### **Mengubah Default URLs**

Edit di bagian script:

```javascript
const BASE_URL = 'http://localhost:5173';  // Frontend URL
const API_URL = 'http://localhost:5000';   // Backend URL
```

### **Mengubah Detail Page ID**

Ganti place_id di iframe detail:

```html
<iframe src="http://localhost:5173/shop/YOUR_PLACE_ID" id="iframe-detail"></iframe>
```

---

## 🐛 Troubleshooting

### **Tab tidak load / blank**

**Penyebab:** Server tidak running

**Solusi:**
1. Check status bar (harus hijau)
2. Start frontend: `npm run dev`
3. Start backend: `python app.py`
4. Refresh browser

### **CORS Error**

**Penyebab:** Browser blocking iframe dari localhost

**Solusi:**
1. Gunakan same origin (localhost)
2. Atau buka dengan `--disable-web-security` flag (development only)

### **Cache tidak clear**

**Penyebab:** Browser cache atau dev cache masih ada

**Solusi:**
1. Klik "🗑️ Clear Cache"
2. Hard reload browser (Ctrl+Shift+R)
3. Clear browser cache manual

### **Status selalu Offline**

**Penyebab:** CORS atau server tidak responding

**Solusi:**
1. Check console untuk error
2. Test URL manual di browser
3. Restart servers

---

## 💡 Tips & Tricks

### **1. Dual Monitor Setup**

```
Monitor 1: VSCode (code editor)
Monitor 2: Dev Browser (preview)
```

Workflow:
- Edit code di Monitor 1
- Lihat hasil di Monitor 2
- No window switching!

### **2. Quick Testing**

```
Ctrl+S (save) → Ctrl+R (refresh) → See changes instantly
```

### **3. Multi-Page Testing**

```
Open multiple tabs → Test user flow → Switch with Ctrl+1-5
```

### **4. API Debugging**

```
Tab 5 (API Test) → Check backend response → Fix → Refresh
```

---

## 📝 Best Practices

### ✅ DO:
- Use keyboard shortcuts untuk efisiensi
- Clear cache saat backend berubah
- Monitor status bar untuk server health
- Refresh current tab untuk perubahan kecil
- Refresh all tabs untuk perubahan besar

### ❌ DON'T:
- Jangan lupa start servers sebelum buka dev browser
- Jangan edit code di iframe (edit di VSCode)
- Jangan open terlalu banyak dev browser (1 cukup)
- Jangan lupa clear cache saat data tidak update

---

## 🎨 Theme & Styling

Development browser menggunakan **VS Code Dark Theme** untuk:
- ✅ Konsisten dengan IDE
- ✅ Nyaman untuk mata
- ✅ Professional look
- ✅ Easy to customize

---

## 🚀 Advanced Features

### **Auto-Refresh on Save**

Untuk auto-refresh saat file save, gunakan:
- Vite HMR (sudah built-in)
- Browser extension (Live Server)
- Custom script dengan file watcher

### **Multiple Environments**

Buat multiple dev browser untuk:
- Development (localhost:5173)
- Staging (staging.example.com)
- Production preview (build preview)

### **Integration dengan Testing**

Gunakan dev browser untuk:
- Manual testing
- Visual regression testing
- User flow testing
- API integration testing

---

## 📚 Related Files

```
cofind/
├── dev-browser.html           ← Development browser
├── DEV_BROWSER_GUIDE.md       ← This file
├── frontend-cofind/
│   ├── DEVELOPMENT_OPTIMIZATION.md
│   └── QUICK_START_DEV.md
└── app.py                     ← Backend server
```

---

## ✅ Summary

**Development Browser membuat development lebih cepat dan efisien:**

- 🚀 **Multi-tab interface** - Semua halaman dalam satu window
- ⚡ **Quick refresh** - Keyboard shortcuts untuk speed
- 💾 **Cache control** - Clear cache dengan mudah
- 📊 **Status monitoring** - Real-time server status
- 🎨 **Professional UI** - VS Code inspired theme

**Happy coding! 🎉**

