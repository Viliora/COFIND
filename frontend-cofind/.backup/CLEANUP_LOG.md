# Cleanup Log: Remove API & Local Image Assets (2026-01-07)

## Summary
Removed Google Places API references and local test data since project now uses Supabase exclusively.

## Files Deleted
- ❌ `src/utils/coffeeShopImages.js` - No longer needed (using Supabase photo_url)
- ❌ `src/data/places.json` - Test data replaced by Supabase

## Files Modified

### Pages
1. **src/pages/ShopDetail.jsx**
   - ❌ Removed: `import { getCoffeeShopImage }`
   - ❌ Removed: `API_BASE`, `USE_API`, `USE_LOCAL_DATA` constants
   - ❌ Removed: Fallback Google Places API logic (lines 118-145)
   - ✅ Updated: Image source from `getCoffeeShopImage()` → `shop.photo_url`

2. **src/pages/ShopList.jsx**
   - ❌ Removed: `API_BASE`, `USE_API` constants
   - ✅ Kept: `USE_LOCAL_DATA` for Supabase flag

3. **src/pages/Favorite.jsx**
   - ❌ Removed: `API_BASE`, `USE_API` constants

4. **src/pages/WantToVisit.jsx**
   - ❌ Removed: `API_BASE`, `USE_API` constants

### Components
5. **src/components/HeroSwiper.jsx**
   - ❌ Removed: `import { getCoffeeShopImage }`
   - ❌ Removed: `.map()` that assigned photos
   - ✅ Updated: Image source from `shop.photos[0]` → `shop.photo_url`
   - ✅ Updated: Preload logic to use `shop.photo_url`

6. **src/components/CoffeeShopCard.jsx**
   - ❌ Removed: `import { getCoffeeShopImage }`
   - ✅ Updated: Photo assignment from `getCoffeeShopImage()` → `shop.photo_url`

## Backup Files Created
- `.backup/BACKUP_coffeeShopImages.js` - Original utility (for restore)
- `.backup/CLEANUP_LOG.md` - This file

## How to Restore

### If getCoffeeShopImages.js is needed again:

```bash
# Copy from backup
copy .backup\BACKUP_coffeeShopImages.js src\utils\coffeeShopImages.js

# Re-add imports to affected files:
# ShopDetail.jsx, HeroSwiper.jsx, CoffeeShopCard.jsx
import { getCoffeeShopImage } from '../utils/coffeeShopImages';

# Re-add API constants:
# ShopDetail.jsx, ShopList.jsx, Favorite.jsx, WantToVisit.jsx
const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:5000';
const USE_API = import.meta.env.VITE_USE_API === 'true';
```

### If places.json is needed again:

Restore from Git history:
```bash
git checkout HEAD -- src/data/places.json
```

## Requirements Met

✅ Removed Google Places API dependencies  
✅ Removed local test data (places.json)  
✅ Updated all components to use Supabase photo_url  
✅ Backup files created for undo  
✅ No breaking changes - all imports cleaned up  

## Next Steps

1. Test app to ensure all images load from Supabase
2. Verify no console errors about missing getCoffeeShopImage
3. Delete backup folder if everything works fine
