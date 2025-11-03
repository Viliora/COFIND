# Hot Module Replacement (HMR) Setup

## Cara Agar Tidak Perlu Refresh Website Setiap Ada Pembaruan

Sistem ini sudah dikonfigurasi untuk **Hot Module Replacement (HMR)** bekerja otomatis di development mode.

### ✅ Yang Sudah Dikonfigurasi:

1. **Service Worker Auto-Disable di Development**
   - Service Worker otomatis di-unregister saat development mode
   - Cache otomatis di-clear untuk memastikan update terbaru
   - Ini memungkinkan HMR bekerja tanpa gangguan

2. **Vite HMR Configuration**
   - Fast Refresh enabled untuk React components
   - Error overlay aktif untuk debugging
   - File watching configured untuk detect changes

### 🚀 Cara Menggunakan:

1. **Pastikan dev server running:**
   ```bash
   npm run dev
   # atau
   yarn dev
   ```

2. **Edit file di `src/`:**
   - Perubahan akan otomatis terdeteksi
   - Browser akan update tanpa refresh (HMR)
   - Tidak perlu tekan F5 atau refresh manual

### 🔧 Jika HMR Tidak Berfungsi:

1. **Clear browser cache:**
   - Buka DevTools (F12)
   - Application tab → Clear storage → Clear site data

2. **Unregister Service Worker:**
   - DevTools → Application → Service Workers
   - Klik "Unregister" pada service worker yang aktif

3. **Restart dev server:**
   ```bash
   # Stop server (Ctrl+C)
   npm run dev
   ```

4. **Hard refresh browser:**
   - Windows/Linux: `Ctrl + Shift + R` atau `Ctrl + F5`
   - Mac: `Cmd + Shift + R`

### 📝 Catatan:

- **Development mode**: Service Worker **disabled**, HMR **enabled**
- **Production mode**: Service Worker **enabled**, HMR **disabled**
- Service Worker hanya aktif saat build production atau deploy

### 🐛 Troubleshooting:

Jika perubahan tidak terdeteksi:
1. Pastikan file disimpan (Ctrl+S)
2. Cek console browser untuk error
3. Pastikan tidak ada service worker yang masih aktif
4. Cek terminal dev server untuk error messages

