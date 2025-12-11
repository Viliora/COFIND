# Cache Management Documentation

Dokumentasi untuk sistem cache management di aplikasi Cofind.

## Fitur Cache Storage

Aplikasi ini memiliki sistem cache storage yang lengkap dengan fitur:

1. **Service Worker Caching** - Cache otomatis untuk shell, static assets, dan content
2. **Cache Manager API** - API untuk menambah, memperbarui, dan menghapus cache
3. **IndexedDB** - Storage untuk data kompleks dan besar
4. **Manifest.json** - PWA support untuk install sebagai aplikasi

## Strategi Caching

### 1. Cache First (Shell & Static Assets)
- Digunakan untuk: Navbar, Footer, App.jsx, CSS, images, fonts
- Strategy: Cek cache dulu, jika ada gunakan cache. Jika tidak ada, fetch dan cache.

### 2. Network First (Content & API)
- Digunakan untuk: API responses, HTML pages, dynamic content
- Strategy: Fetch dari network dulu, jika gagal baru gunakan cache.

## Cara Menggunakan Cache Manager

### Import Cache Manager
```javascript
import { putCache, getCache, deleteCache, clearCache } from '../utils/cacheManager';
```

### Menyimpan Data ke Cache
```javascript
// Menyimpan data API response ke cache
const apiData = {
  status: 'success',
  data: [...]
};

await putCache('https://api.example.com/data', apiData, 'content');
```

### Mengambil Data dari Cache
```javascript
// Mengambil data dari cache
const cachedData = await getCache('https://api.example.com/data', 'content');
if (cachedData) {
  console.log('Data from cache:', cachedData);
}
```

### Menghapus Item dari Cache
```javascript
// Menghapus item spesifik
await deleteCache('https://api.example.com/data', 'content');
```

### Menghapus Semua Cache
```javascript
// Menghapus semua cache content
await clearCache('content');

// Menghapus semua cache
await clearCache();
```

## Tipe Cache

1. **shell** - Navbar, Footer, App.jsx, CSS (jarang berubah)
2. **static** - Images, fonts, static assets
3. **content** - API responses, dynamic data
4. **pages** - HTML pages

## IndexedDB

Untuk data yang lebih kompleks dan besar, gunakan IndexedDB:

```javascript
import { coffeeShopsDB, favoritesDB } from '../utils/indexedDB';

// Menyimpan coffee shops
await coffeeShopsDB.save(coffeeShopData);

// Mengambil semua coffee shops
const shops = await coffeeShopsDB.get();

// Menyimpan favorite
await favoritesDB.save(favoriteShop);
```

## Contoh Implementasi

### Di Komponen React
```javascript
import { getCache, putCache } from '../utils/cacheManager';

useEffect(() => {
  const fetchData = async () => {
    // Cek cache dulu
    const cached = await getCache(API_URL, 'content');
    if (cached) {
      setData(cached.data);
      setIsFromCache(true);
    }

    // Fetch dari network untuk update
    try {
      const response = await fetch(API_URL);
      const result = await response.json();
      
      // Simpan ke cache
      await putCache(API_URL, result, 'content');
      setData(result.data);
      setIsFromCache(false);
    } catch (error) {
      // Jika network error, gunakan cache yang sudah di-load
      if (!cached) {
        setError(error.message);
      }
    }
  };

  fetchData();
}, []);
```

## Cache Info

Untuk melihat informasi tentang cache:
```javascript
import { getCacheInfo } from '../utils/cacheManager';

const info = await getCacheInfo();
console.log('Cache info:', info);
```

Output:
```javascript
{
  available: true,
  cacheCount: 4,
  caches: {
    'cofind-shell-v2': { itemCount: 7, urls: [...] },
    'cofind-static-v2': { itemCount: 2, urls: [...] },
    'cofind-content-v2': { itemCount: 15, urls: [...] },
    'cofind-pages-v2': { itemCount: 4, urls: [...] }
  }
}
```

## Tips Optimasi

1. **Gunakan cache untuk data yang jarang berubah** - Shell dan static assets
2. **Update cache secara berkala** - Untuk content yang berubah
3. **Handle offline gracefully** - Gunakan cache sebagai fallback
4. **Clear cache lama** - Hapus cache yang tidak digunakan lagi
5. **Monitor cache size** - Gunakan `getCacheInfo()` untuk monitoring

