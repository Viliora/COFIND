# 📁 Dokumentasi Struktur Project COFIND

## 🎯 Deskripsi Project
COFIND adalah aplikasi web untuk menemukan dan mengevaluasi coffee shop. Project ini menggunakan Flask sebagai backend dan React dengan Vite sebagai frontend.

---

## 📂 Struktur Root Folder

```
cofind/
├── 📁 frontend-cofind/          # Frontend React Application
├── 📄 app.py                    # Backend Flask API Server (Main)
├── 📄 auth_utils.py             # Utility untuk Authentication
├── 📄 favorites_utils.py        # Utility untuk Favorites Management
├── 📄 review_utils.py            # Utility untuk Review Management
├── 📄 want_to_visit_utils.py     # Utility untuk Want-to-Visit Management
├── 📄 requirements.txt           # Python Dependencies
├── 📄 start_backend.bat          # Script untuk menjalankan backend
├── 📄 .env                       # Environment Variables (konfigurasi)
├── 📄 .gitignore                 # Git ignore rules
├── 📄 cofind.db                  # SQLite Database (local)
└── 📄 test_*.py                  # File-file testing
```

---

## 📁 Penjelasan Folder dan File

### 🔹 **Root Directory (`/`)**

#### **Backend Files (Python)**

##### 📄 `app.py` - **Backend API Server (Main Application)**
**Fungsi:** File utama backend Flask yang menangani semua API endpoints.

**Fungsi-fungsi utama:**
- `home()` - Endpoint root untuk welcome message
- `test_api()` - Endpoint test untuk debugging
- `get_coffeeshops()` - GET semua coffee shops dari database
- `get_coffeeshop(shop_id)` - GET coffee shop berdasarkan ID
- `get_coffeeshop_by_place_id(place_id)` - GET coffee shop berdasarkan place_id
- `search_coffeeshops()` - Search coffee shops berdasarkan nama/alamat
- `signup()` - POST endpoint untuk registrasi user baru
- `login()` - POST endpoint untuk login user
- `logout()` - POST endpoint untuk logout user
- `verify_session()` - GET endpoint untuk verifikasi session token
- `get_profile()` - GET endpoint untuk mendapatkan profil user
- `update_profile()` - PUT endpoint untuk update profil user
- `change_password()` - POST endpoint untuk ganti password
- `create_review()` - POST endpoint untuk membuat review
- `get_reviews()` - GET endpoint untuk mendapatkan reviews
- `update_review()` - PUT endpoint untuk update review
- `delete_review()` - DELETE endpoint untuk hapus review
- `add_favorite()` - POST endpoint untuk menambah favorite
- `remove_favorite()` - DELETE endpoint untuk hapus favorite
- `get_favorites()` - GET endpoint untuk mendapatkan favorites
- `add_want_to_visit()` - POST endpoint untuk menambah want-to-visit
- `remove_want_to_visit()` - DELETE endpoint untuk hapus want-to-visit
- `get_want_to_visit()` - GET endpoint untuk mendapatkan want-to-visit
- `generate_review_summary()` - POST endpoint untuk generate summary review menggunakan LLM
- `analyze_review_sentiment()` - POST endpoint untuk analisis sentiment review

**Teknologi yang digunakan:**
- Flask (web framework)
- Flask-CORS (cross-origin resource sharing)
- SQLite3 (local database)
- Hugging Face Inference API (untuk LLM features)
- Google Places API (untuk data coffee shop)

---

##### 📄 `auth_utils.py` - **Authentication Utilities**
**Fungsi:** Modul utility untuk menangani autentikasi user menggunakan SQLite local database.

**Fungsi-fungsi utama:**
- `get_db_connection()` - Membuat koneksi ke database SQLite
- `hash_password(password)` - Hash password dengan SHA256 + salt
- `verify_password(password, password_hash)` - Verifikasi password
- `generate_token(length)` - Generate secure session token
- `signup(email, username, password, full_name)` - Registrasi user baru
- `login(email, password)` - Login user dan generate session token
- `verify_token(token)` - Verifikasi session token dan return user info
- `logout(token)` - Hapus session token (logout)
- `get_user_by_id(user_id)` - Get informasi user berdasarkan ID
- `update_user_profile(user_id, ...)` - Update profil user (full_name, bio, avatar_url, phone)
- `update_password(user_id, old_password, new_password)` - Update password user

**Database Tables yang digunakan:**
- `users` - Tabel user utama
- `user_profiles` - Tabel profil user
- `sessions` - Tabel session tokens

---

##### 📄 `favorites_utils.py` - **Favorites Management Utilities**
**Fungsi:** Modul utility untuk CRUD operations pada favorite coffee shops.

**Fungsi-fungsi utama:**
- `add_favorite(user_id, place_id)` - Menambah coffee shop ke favorites
- `remove_favorite(user_id, place_id)` - Menghapus coffee shop dari favorites
- `get_user_favorites(user_id, limit)` - Mendapatkan semua favorites user
- `is_favorite(user_id, place_id)` - Cek apakah shop sudah di-favorite
- `get_favorite_count(place_id)` - Mendapatkan jumlah user yang mem-favorite shop

**Database Tables yang digunakan:**
- `favorites` - Tabel favorites
- `coffee_shops` - Tabel coffee shops

---

##### 📄 `review_utils.py` - **Review Management Utilities**
**Fungsi:** Modul utility untuk CRUD operations pada coffee shop reviews.

**Fungsi-fungsi utama:**
- `create_review(user_id, place_id, rating, text, photos)` - Membuat review baru
- `get_review(review_id)` - Mendapatkan review berdasarkan ID
- `get_reviews_for_shop(place_id, limit)` - Mendapatkan semua reviews untuk suatu shop
- `get_user_reviews(user_id, limit)` - Mendapatkan semua reviews dari user
- `update_review(review_id, user_id, rating, text, photos)` - Update review
- `delete_review(review_id, user_id)` - Hapus review
- `get_average_rating(place_id)` - Mendapatkan rata-rata rating dan jumlah review

**Database Tables yang digunakan:**
- `reviews` - Tabel reviews
- `coffee_shops` - Tabel coffee shops
- `users` - Tabel users

---

##### 📄 `want_to_visit_utils.py` - **Want-to-Visit Management Utilities**
**Fungsi:** Modul utility untuk CRUD operations pada want-to-visit coffee shops.

**Fungsi-fungsi utama:**
- `add_want_to_visit(user_id, place_id)` - Menambah coffee shop ke want-to-visit
- `remove_want_to_visit(user_id, place_id)` - Menghapus coffee shop dari want-to-visit
- `get_user_want_to_visit(user_id, limit)` - Mendapatkan semua want-to-visit user
- `is_want_to_visit(user_id, place_id)` - Cek apakah shop sudah di want-to-visit

**Database Tables yang digunakan:**
- `want_to_visit` - Tabel want-to-visit
- `coffee_shops` - Tabel coffee shops

---

##### 📄 `requirements.txt` - **Python Dependencies**
**Fungsi:** File yang berisi daftar semua Python packages yang diperlukan.

**Dependencies:**
- `Flask>=2.0` - Web framework
- `flask-cors>=3.0` - CORS support
- `python-dotenv>=0.21` - Environment variables loader
- `requests>=2.0` - HTTP library
- `huggingface-hub>=0.20.0` - Hugging Face API client

---

##### 📄 `start_backend.bat` - **Backend Startup Script**
**Fungsi:** Script batch untuk menjalankan backend server di Windows.

**Isi script:**
- Mengubah direktori ke project root
- Menjalankan `python run_backend.py` (atau `app.py`)

---

##### 📄 `.env` - **Environment Variables**
**Fungsi:** File konfigurasi untuk menyimpan environment variables (API keys, URLs, dll).

**Variables yang digunakan:**
- `HF_API_TOKEN` - Hugging Face API token untuk LLM
- `VITE_API_BASE` - Base URL untuk API backend
- `SUPABASE_URL` - Supabase URL (jika digunakan)
- `SUPABASE_ANON_KEY` - Supabase anonymous key
- `GOOGLE_PLACES_API_KEY` - Google Places API key

---

##### 📄 `test_*.py` - **Test Files**
**Fungsi:** File-file untuk testing berbagai komponen:
- `test_featherless.py` - Test Featherless AI provider
- `test_llm.py` - Test LLM functionality
- `test_simple.py` - Test sederhana
- `diagnose.py` - Diagnostic tools

---

### 🔹 **Frontend Directory (`/frontend-cofind/`)**

#### **📁 `frontend-cofind/` - React Frontend Application**

##### **Root Files**

###### 📄 `package.json` - **Node.js Dependencies & Scripts**
**Fungsi:** File konfigurasi npm yang berisi dependencies dan scripts.

**Dependencies:**
- `react` & `react-dom` - React library
- `react-router-dom` - Routing untuk React
- `swiper` - Carousel/slider component

**DevDependencies:**
- `vite` - Build tool dan dev server
- `tailwindcss` - CSS framework
- `eslint` - Linter untuk code quality

**Scripts:**
- `npm run dev` - Menjalankan development server
- `npm run build` - Build untuk production
- `npm run lint` - Menjalankan linter

---

###### 📄 `vite.config.js` - **Vite Configuration**
**Fungsi:** Konfigurasi untuk Vite build tool.

---

###### 📄 `tailwind.config.js` - **Tailwind CSS Configuration**
**Fungsi:** Konfigurasi untuk Tailwind CSS styling.

---

###### 📄 `index.html` - **HTML Entry Point**
**Fungsi:** File HTML utama yang menjadi entry point aplikasi.

---

##### **📁 `src/` - Source Code Directory**

###### 📄 `main.jsx` - **React Entry Point**
**Fungsi:** File entry point untuk React application, melakukan render App component.

**Fitur:**
- Render App component ke DOM
- Setup BrowserRouter untuk routing
- Register Service Worker untuk PWA
- ErrorBoundary untuk error handling
- Suppress React DevTools warning di development

---

###### 📄 `App.jsx` - **Main App Component**
**Fungsi:** Component utama aplikasi yang mengatur routing dan layout.

**Fungsi-fungsi utama:**
- `App()` - Main component dengan AuthProvider
- `AppContent()` - Content wrapper dengan routing
- `PageLoadingFallback()` - Loading fallback untuk lazy-loaded pages

**Routes yang didefinisikan:**
- `/` - ShopList (halaman utama)
- `/shop/:id` - ShopDetail (detail coffee shop)
- `/favorite` - Favorite (daftar favorites)
- `/want-to-visit` - WantToVisit (daftar want-to-visit)
- `/about` - About (halaman about)
- `/login` - Login (halaman login)
- `/profile` - Profile (profil user, protected)
- `/admin` - Admin (admin panel, protected)

**Features:**
- Lazy loading untuk code splitting
- Protected routes untuk authentication
- Admin routes untuk admin access
- Session fix initialization

---

###### 📄 `App.css` - **Global App Styles**
**Fungsi:** File CSS global untuk styling aplikasi.

---

###### 📄 `index.css` - **Global Index Styles**
**Fungsi:** File CSS untuk styling global dan Tailwind imports.

---

##### **📁 `src/components/` - React Components**

###### 📄 `Navbar.jsx` - **Navigation Bar Component**
**Fungsi:** Component untuk navigation bar di bagian atas aplikasi.

**Fitur:**
- Logo/brand
- Navigation links
- User menu (jika logged in)
- Login/logout buttons

---

###### 📄 `CoffeeShopCard.jsx` - **Coffee Shop Card Component**
**Fungsi:** Component untuk menampilkan card coffee shop dalam list.

**Fitur:**
- Nama coffee shop
- Alamat
- Rating
- Gambar
- Favorite button
- Want-to-visit button

---

###### 📄 `OptimizedImage.jsx` - **Optimized Image Component**
**Fungsi:** Component untuk menampilkan gambar dengan optimasi (lazy loading, placeholder).

**Fitur:**
- Lazy loading
- Placeholder saat loading
- Error handling

---

###### 📄 `ProtectedRoute.jsx` - **Protected Route Component**
**Fungsi:** Component wrapper untuk melindungi routes yang memerlukan authentication.

**Fitur:**
- Cek apakah user sudah login
- Redirect ke login jika belum login
- Render children jika sudah login

---

###### 📄 `ReviewCard.jsx` - **Review Card Component**
**Fungsi:** Component untuk menampilkan card review individual.

**Fitur:**
- Username reviewer
- Rating (stars)
- Review text
- Tanggal review
- Edit/delete buttons (jika owner)

---

###### 📄 `ReviewForm.jsx` - **Review Form Component**
**Fungsi:** Component form untuk membuat atau edit review.

**Fitur:**
- Rating input (1-5 stars)
- Text area untuk review text
- Submit button
- Validation

---

###### 📄 `ReviewList.jsx` - **Review List Component**
**Fungsi:** Component untuk menampilkan list semua reviews.

**Fitur:**
- List semua reviews untuk suatu shop
- Pagination (jika ada)
- Sorting options

---

###### 📄 `SearchBar.jsx` - **Search Bar Component**
**Fungsi:** Component untuk search bar.

**Fitur:**
- Input search
- Search button
- Real-time search (jika diimplementasikan)

---

###### 📄 `SmartReviewSummary.jsx` - **Smart Review Summary Component**
**Fungsi:** Component untuk menampilkan summary review yang di-generate oleh LLM.

**Fitur:**
- Display AI-generated summary
- Loading state
- Error handling

---

###### 📄 `UserControls.jsx` - **User Controls Component**
**Fungsi:** Component untuk user controls (favorite, want-to-visit, dll).

**Fitur:**
- Favorite button
- Want-to-visit button
- User actions

---

###### 📄 `ErrorBoundary.jsx` - **Error Boundary Component**
**Fungsi:** Component untuk menangkap dan menangani errors di React component tree.

**Fitur:**
- Menangkap JavaScript errors di child components
- Menampilkan fallback UI saat error terjadi
- Error logging untuk debugging
- Reload button untuk refresh halaman
- Clear storage saat reload

**Methods:**
- `getDerivedStateFromError()` - Update state saat error terjadi
- `componentDidCatch(error, errorInfo)` - Log error details
- `handleReload()` - Clear storage dan reload halaman

---

###### 📄 `Footer.jsx` - **Footer Component**
**Fungsi:** Component untuk footer di bagian bawah aplikasi.

**Fitur:**
- Copyright information
- Responsive design
- Dark mode support

---

###### 📄 `AdminRoute.jsx` - **Admin Route Component**
**Fungsi:** Component wrapper untuk melindungi admin routes yang memerlukan admin access.

**Fitur:**
- Cek apakah user sudah login
- Cek apakah user adalah admin
- Redirect ke login jika belum authenticated
- Redirect ke home jika bukan admin
- Loading state saat checking authentication

---

###### 📄 `LLMAnalyzer.jsx` - **LLM Analyzer Component**
**Fungsi:** Component untuk analisis review menggunakan LLM.

---

###### 📄 `LLMChat.jsx` - **LLM Chat Component**
**Fungsi:** Component untuk chat interface dengan LLM.

---

##### **📁 `src/pages/` - Page Components**

###### 📄 `ShopList.jsx` - **Shop List Page**
**Fungsi:** Halaman utama yang menampilkan list semua coffee shops.

**Fitur:**
- List semua coffee shops
- Search functionality
- Filter options
- Pagination

---

###### 📄 `ShopDetail.jsx` - **Shop Detail Page**
**Fungsi:** Halaman detail untuk coffee shop tertentu.

**Fitur:**
- Detail informasi coffee shop
- Reviews list
- Review form
- Favorite/want-to-visit buttons
- Map (jika ada)

---

###### 📄 `Favorite.jsx` - **Favorite Page**
**Fungsi:** Halaman untuk menampilkan semua favorite coffee shops user.

**Fitur:**
- List favorites
- Remove favorite functionality

---

###### 📄 `WantToVisit.jsx` - **Want-to-Visit Page**
**Fungsi:** Halaman untuk menampilkan semua want-to-visit coffee shops user.

**Fitur:**
- List want-to-visit
- Remove want-to-visit functionality

---

###### 📄 `Login.jsx` - **Login Page**
**Fungsi:** Halaman untuk login user.

**Fitur:**
- Login form (email, password)
- Signup link
- Error handling

---

###### 📄 `Profile.jsx` - **Profile Page**
**Fungsi:** Halaman profil user (protected route).

**Fitur:**
- Display user info
- Edit profile form
- Change password form
- User reviews list

---

###### 📄 `Admin.jsx` - **Admin Page**
**Fungsi:** Halaman admin panel (protected route, admin only).

**Fitur:**
- Admin dashboard
- User management
- Coffee shop management
- Statistics

---

###### 📄 `About.jsx` - **About Page**
**Fungsi:** Halaman about/tentang aplikasi.

---

##### **📁 `src/utils/` - Utility Functions**

###### 📄 `errorTracker.js` - **Error Tracking Utility**
**Fungsi:** Utility untuk tracking dan logging errors.

---

###### 📄 `imagePreloader.js` - **Image Preloader Utility**
**Fungsi:** Utility untuk preload images untuk performa yang lebih baik.

---

###### 📄 `indexedDB.js` - **IndexedDB Utility**
**Fungsi:** Utility untuk menggunakan IndexedDB (browser storage).

---

###### 📄 `keywordMapping.js` - **Keyword Mapping Utility**
**Fungsi:** Utility untuk mapping keywords.

---

###### 📄 `personalizedRecommendations.js` - **Personalized Recommendations Utility**
**Fungsi:** Utility untuk memberikan rekomendasi personalisasi.

---

###### 📄 `recentlyViewed.js` - **Recently Viewed Utility**
**Fungsi:** Utility untuk tracking recently viewed coffee shops.

---

###### 📄 `reviewSummary.js` - **Review Summary Utility**
**Fungsi:** Utility untuk generate dan manage review summaries.

---

###### 📄 `sessionFix.js` - **Session Fix Utility**
**Fungsi:** Utility untuk fix session issues.

---

###### 📄 `storageCleanup.js` - **Storage Cleanup Utility**
**Fungsi:** Utility untuk cleanup browser storage.

---

###### 📄 `sw-dev-control.js` - **Service Worker Dev Control**
**Fungsi:** Utility untuk control service worker di development.

---

###### 📄 `sw-register.js` - **Service Worker Register**
**Fungsi:** Utility untuk register service worker.

---

##### **📁 `src/context/` - React Context**

###### 📄 `authContext.jsx` - **Authentication Context**
**Fungsi:** React Context untuk manage authentication state di seluruh aplikasi.

**Fitur:**
- User state management
- Login/logout functions
- Token management
- Session verification
- Admin check
- Loading states
- Initialization state

**Context Values:**
- `user` - User object (id, username, email, is_admin, dll)
- `isAuthenticated` - Boolean apakah user sudah login
- `isAdmin` - Boolean apakah user adalah admin
- `loading` - Boolean untuk loading state
- `initialized` - Boolean apakah context sudah di-initialize
- `login(email, password)` - Function untuk login
- `logout()` - Function untuk logout
- `signup(email, username, password, full_name)` - Function untuk signup
- `updateProfile(data)` - Function untuk update profile
- `changePassword(oldPassword, newPassword)` - Function untuk ganti password

---

##### **📁 `public/` - Public Assets**

###### 📄 `cofind.svg` - **Logo/Brand SVG**
**Fungsi:** Logo aplikasi dalam format SVG.

---

###### 📄 `manifest.json` - **PWA Manifest**
**Fungsi:** File manifest untuk Progressive Web App (PWA).

---

###### 📄 `sw.js` - **Service Worker**
**Fungsi:** Service worker untuk PWA features (offline support, caching).

---

---

## 🗄️ Database Structure (SQLite)

### **Tables:**

1. **`users`** - Tabel user utama
   - `id` (PRIMARY KEY)
   - `email` (UNIQUE)
   - `username` (UNIQUE)
   - `password_hash`
   - `is_admin` (BOOLEAN)
   - `is_active` (BOOLEAN)
   - `created_at` (TIMESTAMP)

2. **`user_profiles`** - Tabel profil user
   - `user_id` (FOREIGN KEY -> users.id)
   - `full_name`
   - `bio`
   - `avatar_url`
   - `phone`
   - `updated_at` (TIMESTAMP)

3. **`sessions`** - Tabel session tokens
   - `id` (PRIMARY KEY)
   - `user_id` (FOREIGN KEY -> users.id)
   - `token` (UNIQUE)
   - `expires_at` (TIMESTAMP)
   - `created_at` (TIMESTAMP)

4. **`coffee_shops`** - Tabel coffee shops
   - `id` (PRIMARY KEY)
   - `place_id` (UNIQUE)
   - `name`
   - `address`
   - `rating`
   - `user_ratings_total`
   - `photo_url`
   - `latitude`
   - `longitude`
   - `created_at` (TIMESTAMP)

5. **`reviews`** - Tabel reviews
   - `id` (PRIMARY KEY)
   - `user_id` (FOREIGN KEY -> users.id)
   - `shop_id` (FOREIGN KEY -> coffee_shops.id)
   - `place_id`
   - `rating` (1-5)
   - `review_text`
   - `created_at` (TIMESTAMP)
   - `updated_at` (TIMESTAMP)

6. **`favorites`** - Tabel favorites
   - `id` (PRIMARY KEY)
   - `user_id` (FOREIGN KEY -> users.id)
   - `shop_id` (FOREIGN KEY -> coffee_shops.id)
   - `place_id`
   - `added_at` (TIMESTAMP)

7. **`want_to_visit`** - Tabel want-to-visit
   - `id` (PRIMARY KEY)
   - `user_id` (FOREIGN KEY -> users.id)
   - `shop_id` (FOREIGN KEY -> coffee_shops.id)
   - `place_id`
   - `added_at` (TIMESTAMP)

---

## 🚀 Cara Menjalankan Project

### **Backend:**
```bash
# Install dependencies
pip install -r requirements.txt

# Setup .env file dengan API keys

# Jalankan server
python app.py
# atau
start_backend.bat
```

### **Frontend:**
```bash
cd frontend-cofind

# Install dependencies
npm install

# Jalankan dev server
npm run dev
```

---

## 📝 Catatan Penting

1. **Database:** Project menggunakan SQLite local database (`cofind.db`)
2. **Authentication:** Menggunakan local SQLite, bukan Supabase
3. **LLM Features:** Menggunakan Hugging Face Inference API dengan Featherless AI provider
4. **CORS:** Enabled untuk development
5. **Environment Variables:** Pastikan file `.env` sudah di-setup dengan benar

---

## 🔧 Teknologi Stack

### **Backend:**
- Python 3.x
- Flask (Web Framework)
- SQLite3 (Database)
- Hugging Face API (LLM)
- Google Places API (Coffee Shop Data)

### **Frontend:**
- React 18
- Vite (Build Tool)
- React Router (Routing)
- Tailwind CSS (Styling)
- Service Worker (PWA)

---

**Dokumentasi ini dibuat untuk membantu memahami struktur dan fungsi setiap file dalam project COFIND.**
