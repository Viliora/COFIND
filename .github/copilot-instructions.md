# COFIND - AI Coding Agent Instructions

**COFIND** is a full-stack coffee shop discovery app built with Flask (backend) + React/Vite (frontend), integrating Google Places API for location-based cafe search with offline support via caching.

## Architecture Overview

### Backend (Flask: `app.py`)
- **Port**: 5000 (development)
- **Key Endpoints**:
  - `GET /api/search/coffeeshops` - Search cafes by coordinates or location string
  - `GET /api/coffeeshops/detail/<place_id>` - Get detailed info (reviews, hours, photos)
- **External API**: Google Places API (Nearby Search, Text Search, Place Details, Place Photo)
- **CORS**: Enabled for all `/api/*` endpoints to allow frontend requests
- **Environment**: Uses `.env` for `GOOGLE_PLACES_API_KEY` (server-side key required)

### Frontend (React/Vite: `frontend-cofind/`)
- **Port**: 5173+ (dev server, Vite auto-increments if port busy)
- **Styling**: Tailwind CSS
- **Routing**: React Router v7 (App.jsx has main routes: `/`, `/shop/:id`, `/favorite`, `/about`)
- **State Management**: Local React hooks (useState, useRef)
- **Storage**: IndexedDB + Cache API for offline support
- **Data Flow**: Components fetch from `VITE_API_BASE` (defaults to `http://localhost:5000`)

### Key Data Structures
- **CoffeeShop**: `{ place_id, name, address/vicinity, rating, user_ratings_total, location, business_status, price_level, photos: [] }`
- **Photo**: Retrieved via `get_place_photo()` - returns Google Places photo URL with maxwidth=400

## Critical Developer Workflows

### 1. Setup & Running
```powershell
# Backend
& .\venv\Scripts\Activate.ps1
python .\app.py  # Runs on http://127.0.0.1:5000

# Frontend (new terminal)
cd .\frontend-cofind
npm run dev  # Auto-detects port 5173+
```

### 2. API Key Configuration
**CRITICAL**: Server-side API keys must NOT have "HTTP referrer" restrictions (causes REQUEST_DENIED).
```powershell
# Option A: .env file (preferred for persistence)
cp .env.example .env
# Edit .env, set GOOGLE_PLACES_API_KEY

# Option B: Environment variable (one-off)
Set-Item -Path Env:GOOGLE_PLACES_API_KEY -Value 'AIza...'
python .\app.py
```

### 3. Testing Endpoints
```
Backend: curl http://localhost:5000/
Search by coords: http://localhost:5000/api/search/coffeeshops?lat=0.0263303&lng=109.3425039&radius=5000
Search by text: http://localhost:5000/api/search/coffeeshops?location=Pontianak
```

### 4. Build & Deployment
```powershell
cd frontend-cofind
npm run build  # Output: dist/
npm run lint   # ESLint check
```

## Project-Specific Patterns & Conventions

### Frontend Component Structure
- **Page Components** (`src/pages/`): ShopList.jsx, ShopDetail.jsx - manage data fetching & routing
- **Reusable Components** (`src/components/`): CoffeeShopCard, SearchBar, Navbar - focus on presentation
- **Utilities** (`src/utils/`): apiCache.js, cacheManager.js, indexedDB.js - handle offline/caching logic
- **Data** (`src/data/`): places.json - fallback test data when API unavailable

### React Patterns in ShopList
```jsx
const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:5000';
const USE_API = import.meta.env.VITE_USE_API === 'true'; // Feature flag for API vs test data
```
- Use `import.meta.env.VITE_*` for frontend environment variables (Vite requirement)
- Components conditionally use API or `places.json` fallback based on feature flag
- Cache is initialized via `initAPICache()` on mount

### Cache Strategy
- **Network First** for API calls: fetch network, cache result, fallback to cache on error
- **Service Worker**: Automatically caches shell (App.jsx), static assets, and content
- **IndexedDB**: Stores userData with 24hr TTL for larger datasets
- See `src/utils/README_CACHE.md` for detailed cache management

### CoffeeShopCard Pattern
- Generates SVG placeholder inline (`data:image/svg+xml;base64,...`) if no photo available
- Formats business status → human-readable text with color-coded badges
- Uses `onError` handler to fallback from API photos to placeholder
- Maps price_level (1-4) to dollar signs: `{'$'.repeat(price_level)}`

### Common Issue: API Photo Retrieval
Google Places API returns photo references, NOT direct URLs. Backend converts via `get_place_photo()`:
```python
# In app.py
def get_place_photo(photo_reference):
    params = {'maxwidth': 400, 'photo_reference': photo_reference, 'key': GOOGLE_PLACES_API_KEY}
    response = requests.get("https://maps.googleapis.com/maps/api/place/photo", params=params)
    return response.url if response.status_code == 200 else None
```

## Integration Points & Dependencies

### External APIs
- **Google Places API** (3 endpoints used):
  - Nearby Search: Find cafes by lat/lng + radius
  - Text Search: Find cafes by location name
  - Place Details: Get hours, reviews, website, phone
  - Place Photo: Convert photo_reference → downloadable URL

### Frontend → Backend Communication
- Vite dev server at 5173+ proxies to backend 5000 via `VITE_API_BASE` env var
- CORS enabled on backend → frontend can fetch from different ports
- API responses follow: `{ status: 'success'|'error', data: [...], message?: '...' }`

### Offline Support
- Service Worker caches shell + static assets (cache-first strategy)
- IndexedDB stores API responses with timestamps (24hr expiry)
- `fetchWithCache()` implements network-first with 5-second timeout fallback
- When offline, React components render cached data with "Loaded from cache" indicator

### Environment Variables
**Backend** (.env):
- `GOOGLE_PLACES_API_KEY` - Required, server-side API key

**Frontend** (.env, frontend-cofind/):
- `VITE_API_BASE` - Backend URL (defaults to `http://localhost:5000`)
- `VITE_USE_API` - Set to 'true' to enable live API (defaults to false, uses places.json)
- `VITE_GOOGLE_MAPS_API_KEY` - For future Maps JS integration

## Common Maintenance Tasks

1. **Add New API Endpoint**: Define route in app.py, add to README testing section, update API_BASE in component
2. **Modify Cache TTL**: Edit `CACHE_EXPIRY` in `src/utils/apiCache.js` (currently 24 hours)
3. **Update Coffee Shop Fields**: Modify `coffee_shop = {...}` dict in `app.py:search_coffeeshops()` and CoffeeShopCard destructuring
4. **Fix REQUEST_DENIED Errors**: Check Google Cloud Console - verify API key restrictions, billing enabled, Places API active
5. **Clear Production Cache**: Use `clearCache()` from cacheManager.js, or via Service Worker DevTools

## File Reference Guide

| File | Purpose |
|------|---------|
| `app.py` | Flask server, Google Places API integration |
| `frontend-cofind/src/App.jsx` | Main router & layout (Navbar, main, Footer) |
| `frontend-cofind/src/pages/ShopList.jsx` | Coffee shop list + search, data fetching logic |
| `frontend-cofind/src/components/CoffeeShopCard.jsx` | Individual shop card UI + photo handling |
| `frontend-cofind/src/utils/apiCache.js` | Network-first fetch with IndexedDB caching |
| `frontend-cofind/src/data/places.json` | Fallback test data (10 coffee shops) |
| `.env.example` | Template for backend environment variables |

---

**Last Updated**: November 2025 | **Stack**: Flask, React 18, Vite 7, Tailwind CSS, Google Places API
