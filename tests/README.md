# Tests & Debug Files

Folder ini berisi file-file untuk testing dan debugging aplikasi.

## File-file di folder ini:

### `app_debug.py`
Versi debug dari `app.py` dengan endpoint tambahan untuk debugging Google Places API.

**Penggunaan:**
```bash
python .\tests\app_debug.py
```

### `test_*.py`
File-file test untuk berbagai komponen:
- `test_detail_endpoint.py` - Test endpoint detail coffee shop
- `test_flask_mock.py` - Test server mock tanpa HF API
- `test_maps_url.py` - Test Google Maps URL generation
- `test_minimal_flask.py` - Test minimal Flask setup
- `test_no_caching.py` - Test tanpa caching system

**Penggunaan:**
```bash
python .\tests\test_*.py
```

### `chrome_diagnostics.html` & `dev-browser.html`
File HTML untuk debugging di browser Chrome dan development.

**Penggunaan:**
Buka langsung di browser untuk testing CORS, cache, dan API calls.

### `test_frontend_api.html`
File HTML untuk testing integrasi frontend dengan backend API.

**Penggunaan:**
Buka langsung di browser untuk test API endpoints.

## Catatan
- File-file ini hanya untuk development dan testing
- Tidak diperlukan untuk production deployment


