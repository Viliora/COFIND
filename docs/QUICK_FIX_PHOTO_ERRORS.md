# 🔧 Fix Remaining Photo URL Errors - ERR_NAME_NOT_RESOLVED

## 🚨 Problem

Still getting errors like:
```
Failed to load resource: net::ERR_NAME_NOT_RESOLVED
ChIJ6fOdoE8zHS4RcV3VfZzhYx0.webp:1
ChIJ9RWUkaZZHS4RYeuZOYAMQ-4.webp:1
```

## 🎯 Root Cause

Database `photo_url` column contains:
- ❌ Empty values (`NULL`)
- ❌ Old invalid URLs
- ❌ URLs from `storage.supabase.co` (generic domain)

## ✅ Solution

### Step 1: Update Photo URLs in Database

**Option A: From Browser Console (Recommended)**

1. Open browser DevTools (F12)
2. Go to Console tab
3. Paste and run:

```javascript
await window.updateAllPhotoUrlsV2()
```

You should see:
```
✅ Successfully updated 15/15 coffee shops
🔄 Refresh page to see updated photos
```

**Option B: From Python (if Option A doesn't work)**

```bash
cd C:\Users\User\cofind
& .\venv\Scripts\Activate.ps1
python .\update_photo_urls.py
```

### Step 2: Refresh Page

After updating, **refresh your browser** to load the corrected URLs.

## 🔍 Verification

Check that photos now load correctly:

1. Open DevTools → Network tab
2. Filter by "webp"
3. All URLs should start with:
   ```
   ✅ https://cpnzglvpqyugtacodwtr.supabase.co/storage/v1/object/public/coffee_shops/
   ```
   
   NOT:
   ```
   ❌ https://storage.supabase.co/storage/v1/object/public/coffee_shops/
   ```

## 📊 What Changed

| File | Change |
|------|--------|
| [src/lib/supabase.js](../frontend-cofind/src/lib/supabase.js) | ✅ Added `bulkUpdateAllPhotoUrls()` function |
| [src/utils/photoUrlHelper.js](../frontend-cofind/src/utils/photoUrlHelper.js) | ✅ Updated `getValidPhotoUrl()` to prioritize `getCoffeeShopPhotoUrl()` |
| [src/utils/consolePhotoUpdate_v2.js](../frontend-cofind/src/utils/consolePhotoUpdate_v2.js) | ✅ NEW: Console helper for easy bulk updates |

## 🎯 How It Works Now

**Flow for each coffee shop photo:**

```
1. Component calls getValidPhotoUrl(shop.photo_url, shop.place_id)
   ↓
2. PRIORITY 1: Call getCoffeeShopPhotoUrl(place_id)
   - Uses Supabase getPublicUrl() for accurate URL
   - Returns: https://cpnzglvpqyugtacodwtr.supabase.co/...
   ✅ Success! Use this URL
   
3. PRIORITY 2: Check database photo_url (if exists)
   - Try to validate and use it
   
4. PRIORITY 3: Fallback to template
   - Use hardcoded template with place_id
   - Returns: https://cpnzglvpqyugtacodwtr.supabase.co/...
```

**Result:** Photos now work **regardless** of what's in the database.

## 🚀 Complete Fix Steps

### From Browser (Easiest - Do This First!)

1. Open app in browser
2. Press F12 to open DevTools
3. Go to Console tab
4. Copy-paste and run:
   ```javascript
   await window.updateAllPhotoUrlsV2()
   ```
5. Wait for message: `✅ Successfully updated X/15 coffee shops`
6. Refresh page (F5)
7. Photos should now load ✅

### If Browser Method Fails

Run from PowerShell:

```powershell
cd C:\Users\User\cofind
& .\venv\Scripts\Activate.ps1
python update_photo_urls.py
```

Then refresh browser.

## 📝 Expected Console Output

**Before Fix:**
```
❌ Failed to load resource: net::ERR_NAME_NOT_RESOLVED
   ChIJ9RWUkaZZHS4RYeuZOYAMQ-4.webp:1
❌ Failed to load resource: net::ERR_NAME_NOT_RESOLVED
   ChIJPa6swGtZHS4RrbIlRvgBgok.webp:1
```

**After Fix:**
```
✅ [getValidPhotoUrl] Generated URL via getPublicUrl for ChIJ9RWUkaZZHS4RYeuZOYAMQ-4
✅ [getValidPhotoUrl] Generated URL via getPublicUrl for ChIJPa6swGtZHS4RrbIlRvgBgok
[HeroSwiper] Featured images preloaded successfully
```

And in Network tab:
```
✅ 200 OK
   https://cpnzglvpqyugtacodwtr.supabase.co/storage/v1/object/public/coffee_shops/ChIJ9RWUkaZZHS4RYeuZOYAMQ-4.webp
```

## ❓ Troubleshooting

**Q: Still getting ERR_NAME_NOT_RESOLVED after update?**
- A: Try hard refresh (Ctrl+Shift+R or Cmd+Shift+R)
- Clear browser cache or use Incognito mode

**Q: `window.updateAllPhotoUrlsV2 is undefined`?**
- A: Make sure you're in Development mode
- Check browser console for errors
- Try running Python script instead

**Q: Photos still not loading?**
- A: Check DevTools Network tab for exact error
- Verify Supabase is configured (check console for `[Supabase] ✅ Configured`)
- Check firewall/VPN isn't blocking Supabase domain

## 🎓 Why This Works

1. **`getPublicUrl()` is Supabase's Official API**
   - Always generates correct project-specific URLs
   - No hardcoding needed

2. **Database Now Has Correct URLs**
   - Future sessions won't need fallback logic
   - Faster loading

3. **Fallback Still Works**
   - If database is empty, generates URL from place_id
   - Never fails

---

**Status:** ✅ READY TO FIX  
**Action:** Run `await window.updateAllPhotoUrlsV2()` in browser console, then refresh page
