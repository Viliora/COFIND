# 🔐 Setup Storage RLS Policies via Supabase Dashboard UI

## ❌ **SQL Error Fixed**

**Error saat run SQL:**
```
ERROR: 42501: must be owner of table objects
```

**Root Cause:**
- SQL Editor biasa **tidak punya permission** untuk create policies di `storage.objects`
- `storage.objects` adalah system table yang di-manage oleh Supabase
- Harus menggunakan **Dashboard UI** untuk create storage policies, bukan SQL

---

## ✅ **Solution: Use Dashboard UI**

### **Step-by-Step Guide dengan Screenshot Reference**

---

## 📝 **Part 1: Setup Avatar Upload Policies**

### **1. Go to Storage Policies**

1. **Open Supabase Dashboard**: https://supabase.com/dashboard
2. **Select your project**: `cofind` (atau project name Anda)
3. **Klik "Storage"** di sidebar kiri
4. **Klik "Policies"** tab

---

### **2. Create Policy: Upload Avatars (INSERT)**

**Click "New Policy"** → **For FULL CUSTOMIZATION** → Buat policy ini:

```
Policy Name: Allow authenticated users to upload avatars

Allowed Operations: [✓] INSERT

Target Roles: authenticated

USING Expression: (leave empty for INSERT)

WITH CHECK Expression:
```
```sql
(bucket_id = 'review-photos'::text) 
AND ((storage.foldername(name))[1] = 'avatars'::text) 
AND (auth.uid()::text = (storage.foldername(name))[2])
```

**Klik "Review"** → **Klik "Save Policy"**

---

### **3. Create Policy: View Avatars (SELECT)**

**Click "New Policy"** → **For FULL CUSTOMIZATION** → Buat policy ini:

```
Policy Name: Allow public to view avatars

Allowed Operations: [✓] SELECT

Target Roles: public

USING Expression:
```
```sql
(bucket_id = 'review-photos'::text) 
AND ((storage.foldername(name))[1] = 'avatars'::text)
```

**WITH CHECK Expression: (leave empty for SELECT)**

**Klik "Review"** → **Klik "Save Policy"**

---

### **4. Create Policy: Update Own Avatars (UPDATE)**

**Click "New Policy"** → **For FULL CUSTOMIZATION** → Buat policy ini:

```
Policy Name: Allow users to update own avatars

Allowed Operations: [✓] UPDATE

Target Roles: authenticated

USING Expression:
```
```sql
(bucket_id = 'review-photos'::text) 
AND ((storage.foldername(name))[1] = 'avatars'::text) 
AND (auth.uid()::text = (storage.foldername(name))[2])
```

**WITH CHECK Expression:**
```sql
(bucket_id = 'review-photos'::text) 
AND ((storage.foldername(name))[1] = 'avatars'::text) 
AND (auth.uid()::text = (storage.foldername(name))[2])
```

**Klik "Review"** → **Klik "Save Policy"**

---

### **5. Create Policy: Delete Own Avatars (DELETE)**

**Click "New Policy"** → **For FULL CUSTOMIZATION** → Buat policy ini:

```
Policy Name: Allow users to delete own avatars

Allowed Operations: [✓] DELETE

Target Roles: authenticated

USING Expression:
```
```sql
(bucket_id = 'review-photos'::text) 
AND ((storage.foldername(name))[1] = 'avatars'::text) 
AND (auth.uid()::text = (storage.foldername(name))[2])
```

**WITH CHECK Expression: (leave empty for DELETE)**

**Klik "Review"** → **Klik "Save Policy"**

---

## 📝 **Part 2: Setup Review Photos Upload Policies**

### **6. Create Policy: Upload Review Photos (INSERT)**

**Click "New Policy"** → **For FULL CUSTOMIZATION** → Buat policy ini:

```
Policy Name: Allow authenticated users to upload review photos

Allowed Operations: [✓] INSERT

Target Roles: authenticated

USING Expression: (leave empty for INSERT)

WITH CHECK Expression:
```
```sql
(bucket_id = 'review-photos'::text) 
AND ((storage.foldername(name))[1] = 'reviews'::text)
```

**Klik "Review"** → **Klik "Save Policy"**

---

### **7. Create Policy: View Review Photos (SELECT)**

**Click "New Policy"** → **For FULL CUSTOMIZATION** → Buat policy ini:

```
Policy Name: Allow public to view review photos

Allowed Operations: [✓] SELECT

Target Roles: public

USING Expression:
```
```sql
(bucket_id = 'review-photos'::text) 
AND ((storage.foldername(name))[1] = 'reviews'::text)
```

**WITH CHECK Expression: (leave empty for SELECT)**

**Klik "Review"** → **Klik "Save Policy"**

---

### **8. Create Policy: Update Own Review Photos (UPDATE)**

**Click "New Policy"** → **For FULL CUSTOMIZATION** → Buat policy ini:

```
Policy Name: Allow users to update own review photos

Allowed Operations: [✓] UPDATE

Target Roles: authenticated

USING Expression:
```
```sql
(bucket_id = 'review-photos'::text) 
AND ((storage.foldername(name))[1] = 'reviews'::text) 
AND (auth.uid()::text = (storage.foldername(name))[2])
```

**WITH CHECK Expression:**
```sql
(bucket_id = 'review-photos'::text) 
AND ((storage.foldername(name))[1] = 'reviews'::text) 
AND (auth.uid()::text = (storage.foldername(name))[2])
```

**Klik "Review"** → **Klik "Save Policy"**

---

### **9. Create Policy: Delete Own Review Photos (DELETE)**

**Click "New Policy"** → **For FULL CUSTOMIZATION** → Buat policy ini:

```
Policy Name: Allow users to delete own review photos

Allowed Operations: [✓] DELETE

Target Roles: authenticated

USING Expression:
```
```sql
(bucket_id = 'review-photos'::text) 
AND ((storage.foldername(name))[1] = 'reviews'::text) 
AND (auth.uid()::text = (storage.foldername(name))[2])
```

**WITH CHECK Expression: (leave empty for DELETE)**

**Klik "Review"** → **Klik "Save Policy"**

---

## ✅ **Verification**

**Setelah buat semua 8 policies:**

1. **Go to Storage → Policies** tab
2. **You should see 8 policies listed:**
   - ✅ Allow authenticated users to upload avatars (INSERT)
   - ✅ Allow public to view avatars (SELECT)
   - ✅ Allow users to update own avatars (UPDATE)
   - ✅ Allow users to delete own avatars (DELETE)
   - ✅ Allow authenticated users to upload review photos (INSERT)
   - ✅ Allow public to view review photos (SELECT)
   - ✅ Allow users to update own review photos (UPDATE)
   - ✅ Allow users to delete own review photos (DELETE)

---

## 📋 **Quick Copy-Paste Reference**

### **For Avatar Policies:**

**INSERT - WITH CHECK:**
```sql
(bucket_id = 'review-photos'::text) AND ((storage.foldername(name))[1] = 'avatars'::text) AND (auth.uid()::text = (storage.foldername(name))[2])
```

**SELECT - USING:**
```sql
(bucket_id = 'review-photos'::text) AND ((storage.foldername(name))[1] = 'avatars'::text)
```

**UPDATE - USING & WITH CHECK:**
```sql
(bucket_id = 'review-photos'::text) AND ((storage.foldername(name))[1] = 'avatars'::text) AND (auth.uid()::text = (storage.foldername(name))[2])
```

**DELETE - USING:**
```sql
(bucket_id = 'review-photos'::text) AND ((storage.foldername(name))[1] = 'avatars'::text) AND (auth.uid()::text = (storage.foldername(name))[2])
```

---

### **For Review Photo Policies:**

**INSERT - WITH CHECK:**
```sql
(bucket_id = 'review-photos'::text) AND ((storage.foldername(name))[1] = 'reviews'::text)
```

**SELECT - USING:**
```sql
(bucket_id = 'review-photos'::text) AND ((storage.foldername(name))[1] = 'reviews'::text)
```

**UPDATE - USING & WITH CHECK:**
```sql
(bucket_id = 'review-photos'::text) AND ((storage.foldername(name))[1] = 'reviews'::text) AND (auth.uid()::text = (storage.foldername(name))[2])
```

**DELETE - USING:**
```sql
(bucket_id = 'review-photos'::text) AND ((storage.foldername(name))[1] = 'reviews'::text) AND (auth.uid()::text = (storage.foldername(name))[2])
```

---

## 🎯 **Policy Summary Table**

| # | Policy Name | Operation | Role | Folder | Owner Check |
|---|-------------|-----------|------|--------|-------------|
| 1 | Upload avatars | INSERT | authenticated | avatars | ✅ Yes |
| 2 | View avatars | SELECT | public | avatars | ❌ No |
| 3 | Update avatars | UPDATE | authenticated | avatars | ✅ Yes |
| 4 | Delete avatars | DELETE | authenticated | avatars | ✅ Yes |
| 5 | Upload review photos | INSERT | authenticated | reviews | ❌ No* |
| 6 | View review photos | SELECT | public | reviews | ❌ No |
| 7 | Update review photos | UPDATE | authenticated | reviews | ✅ Yes |
| 8 | Delete review photos | DELETE | authenticated | reviews | ✅ Yes |

*\*Review photos INSERT tidak check owner karena path: `reviews/{userId}/...` sudah di-handle di code*

---

## 🔍 **UI Navigation Path**

```
Supabase Dashboard
    ↓
Select Project (cofind)
    ↓
Storage (sidebar)
    ↓
Policies (tab)
    ↓
New Policy (button)
    ↓
For FULL CUSTOMIZATION (option)
    ↓
Fill in:
  - Policy Name
  - Allowed Operations (checkboxes)
  - Target Roles (dropdown)
  - USING Expression (SQL)
  - WITH CHECK Expression (SQL)
    ↓
Review → Save Policy
```

---

## 💡 **Tips**

### **Copy-Paste SQL:**
- ✅ Copy dari section "Quick Copy-Paste Reference" di atas
- ✅ Paste langsung ke field "USING Expression" atau "WITH CHECK Expression"
- ✅ Jangan modify apapun - paste as-is

### **Field Mapping:**
- **INSERT**: Only use "WITH CHECK Expression"
- **SELECT**: Only use "USING Expression"
- **UPDATE**: Use both "USING" and "WITH CHECK"
- **DELETE**: Only use "USING Expression"

### **Target Roles:**
- **authenticated**: User yang sudah login
- **public**: Semua orang (termasuk guest)

---

## ⚠️ **Common Mistakes**

### **❌ WRONG:**
```sql
-- Missing ::text casting
bucket_id = 'review-photos'

-- Wrong folder syntax
foldername(name)[1] = 'avatars'

-- Missing auth casting
auth.uid() = foldername(name)[2]
```

### **✅ CORRECT:**
```sql
-- Proper casting
bucket_id = 'review-photos'::text

-- Proper syntax with storage schema
(storage.foldername(name))[1] = 'avatars'::text

-- Proper casting and syntax
auth.uid()::text = (storage.foldername(name))[2]
```

---

## 🧪 **Testing After Setup**

### **1. Test Avatar Upload:**
1. Hard refresh app (Ctrl+Shift+R)
2. Login
3. Profile → Edit → Upload avatar
4. Click "Simpan"
5. ✅ Should work without RLS error!

### **2. Check Console:**
```
[uploadAvatar] Uploading to path: avatars/{userId}/1234567890.jpg
[uploadAvatar] Upload successful
```

### **3. Verify in Storage:**
- Supabase Dashboard → Storage → review-photos
- Should see: `avatars/{userId}/` folder with uploaded file

---

## 📸 **Visual Guide Summary**

**Step 1: Navigate**
```
Dashboard → Storage → Policies → New Policy
```

**Step 2: Choose Template**
```
Click: "For FULL CUSTOMIZATION"
```

**Step 3: Fill Form**
```
Policy Name: [name from guide]
Operations: [✓] [operation type]
Target Roles: [authenticated/public]
USING: [SQL from guide]
WITH CHECK: [SQL from guide]
```

**Step 4: Save**
```
Review → Save Policy
```

**Repeat 8 times** (untuk 8 policies)

---

## ✅ **Checklist**

Setelah selesai, verify:

- [ ] ✅ 8 policies visible di Storage → Policies tab
- [ ] ✅ Avatar upload works (test di Profile)
- [ ] ✅ Review photos upload works (test add review)
- [ ] ✅ No RLS errors in console
- [ ] ✅ Images visible di app

---

## 🆘 **Need Help?**

**If stuck:**
1. Screenshot the error
2. Check which policy failed
3. Verify SQL syntax exactly matches guide
4. Make sure bucket name is `review-photos` (correct spelling)
5. Make sure folder names are `avatars` and `reviews` (lowercase, plural)

---

**Status:** ✅ **UI METHOD - NO SQL ERROR**

**Time to complete:** ~10 minutes (8 policies × ~1 min each)

**Difficulty:** 🟢 Easy (just copy-paste & click)

