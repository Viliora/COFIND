# Migration: Move Coffee Shop Photos to Supabase Storage (2026-01-07)

## Summary
Implemented hybrid photo solution:
- **Primary**: Supabase Storage (`photo_url` column in `places` table)
- **Fallback**: Local assets from `src/assets/` (for offline support)

## What Changed

### New Files
1. **src/utils/supabasePhotoUpload.js** - Utilities untuk upload foto ke Supabase Storage
   - `uploadCoffeeShopPhoto(placeId, file)` - Upload file
   - `updateCoffeeShopPhotoUrl(placeId, photoUrl)` - Update DB
   - `uploadAndUpdateCoffeeShopPhoto(placeId, file)` - Combined operation

2. **supabase_add_photo_url.sql** - Migration script
   - Adds `photo_url` column to `places` table

### Restored Files
- **src/utils/coffeeShopImages.js** - Restored from backup untuk fallback

### Updated Components (Hybrid Photo Logic)
1. **ShopDetail.jsx**
   - `src={shop.photo_url || getCoffeeShopImage(...)}`
   - Tries Supabase first, falls back to local assets

2. **HeroSwiper.jsx**
   - Same hybrid logic
   - Preload uses fallback correctly

3. **CoffeeShopCard.jsx**
   - Hybrid photo resolution

## How to Use

### Step 1: Add column to Supabase
```sql
-- Run in Supabase SQL Editor
ALTER TABLE places ADD COLUMN IF NOT EXISTS photo_url TEXT;
```

### Step 2: Upload photos to Supabase Storage

Create bucket: `coffee_shops`

```javascript
// In your admin/upload page
import { uploadAndUpdateCoffeeShopPhoto } from '../utils/supabasePhotoUpload';

// Upload and update DB in one call
await uploadAndUpdateCoffeeShopPhoto(placeId, imageFile);
```

### Step 3: Update photos in table

After uploading all photos to Supabase Storage:

```sql
UPDATE places 
SET photo_url = 'https://storage.supabase.co/...coffee_shops/{place_id}.webp'
WHERE photo_url IS NULL;
```

## PWA Offline Support

| Scenario | Status |
|----------|--------|
| Pages load offline | ✅ Cached by Service Worker |
| Images show offline | ✅ Fallback to local assets |
| Coffee shop info loads offline | ✅ Cached from IndexedDB |
| Search works offline | ✅ Uses cached data |

## Photo Resolution Priority
1. **Supabase Storage** (primary) → High quality, cloud-hosted
2. **Local Assets** (fallback) → Offline support, always available
3. **Placeholder** → If both fail

## Restore Backup
If you want to revert to local-only photos:
```bash
# Delete photo_url column
ALTER TABLE places DROP COLUMN photo_url;

# Use getCoffeeShopImage() only in components
```
