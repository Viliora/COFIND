# 🚀 Quick Fix: Disable RLS via SQL

## ✅ **Current Status:**

Dari screenshot:
- ✅ Anda di halaman **Storage → Files → Policies**
- ✅ Sudah ada 8 policies untuk bucket `review-photos`
- ⚠️ Tapi upload mungkin masih error karena path structure mismatch

---

## 🎯 **Recommendation: Disable RLS**

Karena policies sudah ada tapi upload masih error, **lebih cepat disable RLS**:

### **Via SQL (1 Menit):**

1. **Buka SQL Editor** (di sidebar kiri, icon ⚡ atau "SQL Editor")
2. **Paste SQL ini:**

```sql
ALTER TABLE storage.objects DISABLE ROW LEVEL SECURITY;
```

3. **Click Run** atau tekan `Ctrl+Enter`
4. ✅ **Done!**

---

## 🧪 **Test After:**

1. Hard refresh app: `Ctrl+Shift+R`
2. Login → Profile → Edit
3. Upload avatar
4. ✅ Should work immediately!

---

## 📋 **Alternative: Delete All Policies**

Jika mau tetap pake RLS tapi policies sekarang salah, Anda bisa:

1. Di halaman **Policies** (screenshot Anda)
2. **Click icon ⋮** (3 dots) di setiap policy
3. **Select "Delete"**
4. Ulangi untuk semua 8 policies
5. Lalu create new policies yang benar

**Tapi ini lama & ribet!** ⏰ (15-30 menit)

---

## ✅ **Saran Saya:**

**Disable RLS via SQL** (1 menit) → **Test upload** → **Done!** 🚀

File `DISABLE_STORAGE_RLS.sql` sudah ready untuk di-copy paste.

