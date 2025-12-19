# Perbaikan: Leaked Password Protection Disabled

## 🔧 Masalah yang Diperbaiki

### **Masalah:**
Leaked Password Protection untuk Supabase Auth saat ini **disabled**. Ini berarti user bisa menggunakan password yang sudah pernah muncul di data breach (seperti yang dilaporkan oleh Have I Been Pwned). Tanpa proteksi ini, akun lebih rentan terhadap credential-stuffing dan account takeover.

### **Risiko:**
- ⚠️ **Peningkatan kemungkinan account compromise** via password yang sudah pernah bocor
- ⚠️ **Biaya operasional dan support lebih tinggi** dari account recovery dan fraud
- ⚠️ **Reduced security posture** dan peningkatan exposure regulatory/compliance

---

## 🔄 Perbaikan yang Direkomendasikan

### **⚠️ PENTING: Cek Plan Supabase Anda**

**Status Fitur:**
- **Leaked Password Protection** hanya tersedia di **Pro Plan** ($25/bulan) atau lebih tinggi
- Jika project Anda menggunakan **Free Plan**, fitur ini **TIDAK TERSEDIA**
- Warning ini **TIDAK DAPAT DIPERBAIKI** tanpa upgrade ke Pro Plan

**Rekomendasi:**
- Jika menggunakan **Free Plan**: Abaikan warning ini atau upgrade ke Pro Plan
- Jika menggunakan **Pro Plan**: Enable fitur ini (langkah di bawah)
- **Tetap penting**: Update frontend error handling untuk prepare jika upgrade atau handle error yang lebih baik

---

### **1. Enable Supabase's Built-in Leaked Password Protection (Jika Pro Plan)**

**Langkah:**
1. Buka **Supabase Dashboard** → **Authentication** → **Settings**
2. Cari opsi **"Leaked Password Protection"** atau **"Password Protection"**
3. **Enable** fitur ini
4. Konfigurasi behavior:
   - **Reject password outright** dengan pesan jelas ke user (RECOMMENDED)
   - Atau allow tapi require stronger alternative

**Manfaat:**
- ✅ Otomatis check password terhadap Have I Been Pwned database
- ✅ Block password yang sudah pernah bocor
- ✅ Built-in integration, tidak perlu setup tambahan

---

### **2. Update Frontend Error Handling**

**Masalah:**
- Frontend perlu handle error ketika password ditolak karena leaked
- User perlu mendapat pesan error yang jelas dan user-friendly

**Perbaikan:**
Update `src/pages/Login.jsx` dan `src/components/ReviewForm.jsx` (jika ada password change) untuk handle error leaked password.

**Contoh Error Handling:**
```javascript
// Di Login.jsx atau komponen signup
try {
  const { data, error } = await supabase.auth.signUp({
    email: `${username}@cofind.app`,
    password: password,
    options: {
      data: {
        username: username,
        full_name: fullName
      }
    }
  });

  if (error) {
    // Handle leaked password error
    if (error.message?.includes('password') || error.message?.includes('breach') || error.message?.includes('pwned')) {
      setError('Password ini telah ditemukan dalam data breach. Silakan pilih password yang berbeda dan lebih kuat.');
    } else {
      setError(error.message || 'Gagal mendaftar');
    }
    return;
  }
} catch (err) {
  console.error('Signup error:', err);
  setError('Terjadi kesalahan. Silakan coba lagi.');
}
```

**Error Codes dari Supabase:**
- Supabase mungkin return error code khusus untuk leaked password
- Check error message untuk keywords: "breach", "pwned", "compromised", "leaked"

---

### **3. Enforce Stronger Password Rules (Complementary)**

**Rekomendasi:**
- Minimum 12 karakter
- Mix of character classes (uppercase, lowercase, numbers, symbols)
- Password strength meter di UI
- Clear guidance untuk user

**Implementasi:**
```javascript
// Password validation function
const validatePassword = (password) => {
  const errors = [];
  
  if (password.length < 12) {
    errors.push('Password minimal 12 karakter');
  }
  
  if (!/[a-z]/.test(password)) {
    errors.push('Password harus mengandung huruf kecil');
  }
  
  if (!/[A-Z]/.test(password)) {
    errors.push('Password harus mengandung huruf besar');
  }
  
  if (!/[0-9]/.test(password)) {
    errors.push('Password harus mengandung angka');
  }
  
  if (!/[^a-zA-Z0-9]/.test(password)) {
    errors.push('Password harus mengandung karakter khusus');
  }
  
  return {
    isValid: errors.length === 0,
    errors: errors
  };
};
```

---

### **4. Add Rate Limiting dan Monitoring**

**Rekomendasi:**
- Rate-limit password change dan sign-in attempts
- Monitor auth logs untuk repeated failed attempts
- Alert untuk unusual IP/geolocation patterns

**Implementasi:**
- Supabase sudah memiliki built-in rate limiting
- Bisa tambahkan custom rate limiting via Edge Functions jika diperlukan
- Monitor via Supabase Dashboard → Logs → Auth Logs

---

### **5. Encourage/Enforce Multi-Factor Authentication (MFA)**

**Rekomendasi:**
- Enable optional MFA untuk semua user
- Consider require MFA untuk admin atau sensitive roles
- Reduce impact jika password tetap compromised

**Implementasi:**
- Supabase Dashboard → Authentication → Settings → Enable MFA
- Update frontend untuk support MFA flow

---

### **6. Communicate to Existing Users (Optional)**

**Rekomendasi:**
- Consider prompt user untuk reset password jika mereka menggunakan weak/breached password
- Optionally require password rotation untuk accounts yang match known breaches
- **HATI-HATI**: Jangan terlalu aggressive untuk avoid user friction

---

## 📋 Langkah Implementasi

### **Langkah 1: Enable di Supabase Dashboard (Hanya jika Pro Plan)**

**⚠️ PENTING: Fitur ini hanya tersedia di Pro Plan atau lebih tinggi**

1. Login ke **Supabase Dashboard**
2. Pilih project **COFIND**
3. **Cek Plan Anda**: Dashboard → Settings → Billing
4. Jika menggunakan **Free Plan**: 
   - Fitur tidak tersedia, skip langkah ini
   - Fokus pada perbaikan frontend error handling (Langkah 2)
5. Jika menggunakan **Pro Plan** atau lebih tinggi:
   - Navigate ke **Authentication** → **Settings**
   - Cari section **"Password Protection"** atau **"Leaked Password Protection"**
   - **Enable** toggle untuk "Leaked Password Protection"
   - Save changes

**Expected Result:**
- Warning di Security Advisor akan hilang setelah enabled (jika Pro Plan)
- Password yang leaked akan otomatis ditolak saat signup/password change
- Jika Free Plan, warning tetap ada tapi tidak memengaruhi fungsionalitas

---

### **Langkah 2: Update Frontend Error Handling**

**File yang Perlu Diupdate:**
- `src/pages/Login.jsx` - Handle error saat signup/signin
- (Jika ada) Password change component

**Contoh Update:**
```javascript
// Di Login.jsx, update handleSignUp function
const handleSignUp = async (e) => {
  e.preventDefault();
  setIsSubmitting(true);
  setError(null);

  try {
    // Validate password strength
    const passwordValidation = validatePassword(password);
    if (!passwordValidation.isValid) {
      setError(passwordValidation.errors.join(', '));
      setIsSubmitting(false);
      return;
    }

    const { data, error } = await supabase.auth.signUp({
      email: `${username}@cofind.app`,
      password: password,
      options: {
        data: {
          username: username,
          full_name: fullName
        }
      }
    });

    if (error) {
      // Handle leaked password error specifically
      if (error.message?.toLowerCase().includes('breach') || 
          error.message?.toLowerCase().includes('pwned') ||
          error.message?.toLowerCase().includes('compromised') ||
          error.message?.toLowerCase().includes('leaked')) {
        setError('Password ini telah ditemukan dalam data breach. Silakan pilih password yang berbeda dan lebih kuat untuk keamanan akun Anda.');
      } else if (error.message?.includes('Password')) {
        setError('Password tidak memenuhi persyaratan keamanan. ' + error.message);
      } else {
        setError(error.message || 'Gagal mendaftar. Silakan coba lagi.');
      }
      setIsSubmitting(false);
      return;
    }

    // Success handling...
  } catch (err) {
    console.error('Signup error:', err);
    setError('Terjadi kesalahan. Silakan coba lagi.');
    setIsSubmitting(false);
  }
};
```

---

### **Langkah 3: Add Password Strength Validation (Optional tapi Recommended)**

**File Baru:** `src/utils/passwordValidation.js`

```javascript
/**
 * Password validation utility
 * Validates password strength and provides user-friendly error messages
 */
export const validatePassword = (password) => {
  const errors = [];
  
  if (!password) {
    return {
      isValid: false,
      errors: ['Password tidak boleh kosong'],
      strength: 'weak'
    };
  }
  
  if (password.length < 12) {
    errors.push('Password minimal 12 karakter');
  }
  
  if (!/[a-z]/.test(password)) {
    errors.push('Password harus mengandung huruf kecil');
  }
  
  if (!/[A-Z]/.test(password)) {
    errors.push('Password harus mengandung huruf besar');
  }
  
  if (!/[0-9]/.test(password)) {
    errors.push('Password harus mengandung angka');
  }
  
  if (!/[^a-zA-Z0-9]/.test(password)) {
    errors.push('Password harus mengandung karakter khusus (!@#$%^&*)');
  }
  
  // Calculate strength
  let strength = 'weak';
  if (password.length >= 12 && errors.length === 0) {
    strength = 'strong';
  } else if (password.length >= 8 && errors.length <= 2) {
    strength = 'medium';
  }
  
  return {
    isValid: errors.length === 0,
    errors: errors,
    strength: strength
  };
};

/**
 * Get password strength indicator color
 */
export const getPasswordStrengthColor = (strength) => {
  switch (strength) {
    case 'strong':
      return 'text-green-600 dark:text-green-400';
    case 'medium':
      return 'text-yellow-600 dark:text-yellow-400';
    case 'weak':
      return 'text-red-600 dark:text-red-400';
    default:
      return 'text-gray-600 dark:text-gray-400';
  }
};
```

**Update Login.jsx:**
```javascript
import { validatePassword, getPasswordStrengthColor } from '../utils/passwordValidation';

// Di component
const [passwordStrength, setPasswordStrength] = useState(null);

// Di handlePasswordChange
const handlePasswordChange = (e) => {
  const newPassword = e.target.value;
  setPassword(newPassword);
  
  if (newPassword) {
    const validation = validatePassword(newPassword);
    setPasswordStrength(validation.strength);
  } else {
    setPasswordStrength(null);
  }
};

// Di JSX, tambahkan password strength indicator
{password && passwordStrength && (
  <div className="mt-1">
    <div className="flex items-center gap-2">
      <span className={`text-xs font-medium ${getPasswordStrengthColor(passwordStrength)}`}>
        Kekuatan: {passwordStrength === 'strong' ? 'Kuat' : passwordStrength === 'medium' ? 'Sedang' : 'Lemah'}
      </span>
    </div>
  </div>
)}
```

---

## ✅ Hasil Setelah Perbaikan

### Sebelum:
- ❌ Leaked Password Protection disabled
- ❌ User bisa menggunakan password yang sudah pernah bocor
- ❌ Tidak ada error handling untuk leaked password
- ❌ Tidak ada password strength validation

### Sesudah:
- ✅ Leaked Password Protection enabled
- ✅ Password yang leaked otomatis ditolak
- ✅ Error handling yang jelas untuk user
- ✅ Password strength validation (optional)
- ✅ Warning di Security Advisor hilang

---

## 🧪 Testing

### Test Case 1: Leaked Password Rejection
1. Enable Leaked Password Protection di Supabase Dashboard
2. Coba signup dengan password yang diketahui leaked (contoh: "password123", "12345678")
3. **Expected**: 
   - Password ditolak dengan error message yang jelas
   - Error message menjelaskan bahwa password telah ditemukan di data breach
   - User bisa mencoba password lain

### Test Case 2: Strong Password Acceptance
1. Coba signup dengan password yang kuat dan unik
2. **Expected**:
   - Signup berhasil
   - Tidak ada error

### Test Case 3: Error Message Display
1. Coba signup dengan leaked password
2. **Expected**:
   - Error message muncul di UI
   - Message user-friendly dan jelas
   - User tahu apa yang harus dilakukan

### Test Case 4: Password Strength Indicator (Jika diimplementasikan)
1. Ketik password di form signup
2. **Expected**:
   - Password strength indicator muncul
   - Indicator menunjukkan kekuatan password (weak/medium/strong)
   - Color coding sesuai strength

---

## 📝 Catatan Penting

1. **User Experience**:
   - Blocking leaked password akan meningkatkan friction saat signup
   - Pastikan error message jelas dan user-friendly
   - Consider provide password suggestions atau generator

2. **Performance**:
   - Have I Been Pwned checks mungkin menambah sedikit latency
   - Supabase built-in integration sudah optimized untuk ini
   - Latency biasanya minimal (< 100ms)

3. **Custom Auth Flows**:
   - Jika ada custom auth flows atau external identity providers
   - Pastikan leaked-password checks tetap applied di semua tempat password diterima/disimpan

4. **Rate Limiting**:
   - Supabase sudah memiliki built-in rate limiting
   - Monitor auth logs untuk detect unusual patterns
   - Consider tambahkan custom rate limiting jika diperlukan

---

## 🔗 Related Files

- `frontend-cofind/src/pages/Login.jsx` - Update error handling untuk leaked password
- `frontend-cofind/src/utils/passwordValidation.js` - Password validation utility (NEW, optional)
- Supabase Dashboard → Authentication → Settings - Enable Leaked Password Protection

---

## 🎯 Action Items

1. **Enable di Supabase Dashboard** - Authentication → Settings → Enable Leaked Password Protection (PENTING)
2. **Update Frontend Error Handling** - Handle leaked password error dengan pesan yang jelas
3. **Test dengan Leaked Password** - Verify bahwa password leaked ditolak dengan benar
4. **Optional: Add Password Strength Validation** - Improve UX dengan password strength indicator
5. **Optional: Enable MFA** - Consider enable MFA untuk additional security

---

## 📚 Referensi

- [Supabase Auth Documentation](https://supabase.com/docs/guides/auth)
- [Have I Been Pwned](https://haveibeenpwned.com/)
- [OWASP Password Guidelines](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html)
