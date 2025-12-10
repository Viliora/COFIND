# Panduan Membuka Localhost COFIND

## 🚀 Cara Cepat

### 1. Menggunakan Script PowerShell (Recommended)
```powershell
# Membuka frontend + backend sekaligus
.\open-localhost.ps1

# Hanya frontend
.\open-localhost.ps1 frontend

# Hanya backend
.\open-localhost.ps1 backend
```

### 2. Menggunakan Script Batch
```cmd
# Membuka frontend + backend sekaligus
open-localhost.bat

# Hanya frontend
open-localhost.bat frontend

# Hanya backend
open-localhost.bat backend
```

### 3. Menggunakan NPM Script (dari folder frontend-cofind)
```powershell
cd frontend-cofind

# Membuka frontend
npm run open

# Membuka backend
npm run open:backend
```

## 📍 URL Localhost

- **Frontend**: http://localhost:5173
- **Backend API**: http://localhost:5000
- **Backend Root**: http://localhost:5000/ (menampilkan `{"message":"Welcome to COFIND API"}`)

## 🔍 Testing Endpoints

Setelah backend berjalan, Anda bisa test endpoint berikut:

1. **Root Backend**:
   ```
   http://localhost:5000/
   ```

2. **Search Coffee Shops**:
   ```
   http://localhost:5000/api/search/coffeeshops?location=Pontianak
   ```

3. **Coffee Shop Detail**:
   ```
   http://localhost:5000/api/coffeeshop/details?place_id=ChIJ...
   ```

## ⚠️ Catatan Penting

1. **Pastikan server sudah berjalan** sebelum membuka localhost:
   - Backend: `python app.py` (dari root project)
   - Frontend: `npm run dev` (dari folder `frontend-cofind`)

2. **Jika port sudah digunakan**, Vite akan otomatis menggunakan port lain (misalnya 5174, 5175, dll). Cek terminal untuk melihat port yang digunakan.

3. **Browser akan terbuka otomatis** saat menggunakan script, tapi jika tidak, buka manual dengan URL di atas.

## 🛠️ Troubleshooting

### Port 5000 sudah digunakan
```powershell
# Cek proses yang menggunakan port 5000
netstat -ano | findstr :5000

# Atau ubah port di app.py (baris terakhir):
# app.run(debug=False, host='0.0.0.0', port=5001, threaded=True)
```

### Port 5173 sudah digunakan
Vite akan otomatis mencari port lain. Cek terminal untuk melihat port yang digunakan.

### Script tidak bisa dijalankan (PowerShell)
```powershell
# Set execution policy (hanya sekali)
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

