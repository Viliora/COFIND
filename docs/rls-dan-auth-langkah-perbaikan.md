# Langkah perbaikan RLS & auth (Cofind)

Masalah inti: **policy `auth.uid() = user_id` hanya valid untuk Supabase Auth + kolom `user_id uuid`**. Cofind memakai **Flask JWT + `public.users.id` (bigint) + tabel `sessions`**, sehingga template RLS Supabase **tidak otomatis berlaku**.

Migrasi skema **`003_schema_consistency_rls.sql`** sudah merapikan tipe/FK dan RLS katalog publik. Bagian **RLS per-user** butuh keputusan arsitektur di bawah.

---

## Pilih salah satu jalur

| Jalur | Cocok jika | RLS per-user `auth.uid()` |
|--------|------------|---------------------------|
| **A — Tetap Flask (disarankan untuk kondisi sekarang)** | Semua UI/API lewat Vercel → Flask → Postgres | **Tidak** (RLS hanya lapis ekstra PostgREST) |
| **B — Migrasi penuh ke Supabase Auth** | Ingin client langsung ke Supabase + RLS standar | **Ya** |
| **C — Hybrid** | Flask tetap, sebagian fitur lewat supabase-js | **Sebagian** (rumit) |

---

## Jalur A — Tetap Flask (minimal, aman untuk skripsi/produksi saat ini)

**Tujuan:** Data user dilindungi di **API Flask** (`require_authenticated_user`, validasi `user_id`), database tetap **deny-by-default** untuk `anon`/`authenticated` lewat PostgREST.

### Langkah

1. **Pastikan migrasi 003 sudah jalan di Supabase**
   - File: `scripts/migrations/003_schema_consistency_rls.sql`
   - Lokal (sudah pernah sukses):
     ```bash
     .venv\Scripts\python -c "from pathlib import Path; import os; from dotenv import load_dotenv; import psycopg2; load_dotenv(Path('.env')); psycopg2.connect(os.environ['DATABASE_URL']).cursor().execute(Path('scripts/migrations/003_schema_consistency_rls.sql').read_text()); ..."
     ```
   - Atau jalankan isi file di **SQL Editor** Supabase (satu transaksi).

2. **Jangan pasang policy `auth.uid() = user_id`** di tabel dengan `user_id bigint` — akan **error tipe** atau **tidak pernah match**.

3. **Dashboard Supabase → Settings → Data API**
   - Pastikan tabel sensitif **tidak** perlu di-expose ke REST jika app hanya Flask.
   - Jika REST tidak dipakai: **RLS tanpa policy = deny** sudah cukup untuk `anon`/`authenticated`.

4. **Jangan pernah** taruh **service role / `DATABASE_URL` penuh** di frontend (`VITE_*`).

5. **Verifikasi**
   - Supabase → **Database → Advisors → Security**: masih INFO “RLS enabled no policy” pada tabel privat → **OK** untuk jalur A.
   - Tes app: login, favorit, review, rekomendasi — semua lewat Flask.

6. **Dokumentasi skripsi**
   - Tulis: *Keamanan akses data user diimplementasi di lapisan API (JWT + otorisasi Flask); RLS Postgres aktif sebagai defense-in-depth untuk akses langsung PostgREST.*

**Selesai jalur A** — tidak ada langkah wajib lagi untuk “per-user RLS” kecuali Anda pindah ke Jalur B.

---

## Jalur B — Supabase Auth + RLS per-user (besar, multi-sprint)

**Tujuan:** Client pakai `supabase.auth`; baris milik user dilindungi policy standar Supabase.

### Fase 1 — Desain data

1. Tentukan **satu ID kanonik**: `auth.users.id` (**uuid**).
2. Tambah kolom **`auth_user_id uuid UNIQUE`** di `public.users` (atau ganti PK — breaking change besar).
3. Backfill: buat user Auth untuk setiap baris `public.users` atau migrasi user baru saja.
4. Ubah FK sensitif (`favorites.user_id`, dll.) menjadi **uuid → auth.users** *atau* policy memakai subquery ke `public.users` where `auth_user_id = auth.uid()` (lebih rumit).

### Fase 2 — Auth di frontend

1. Ganti `authService.js` (Flask login) dengan **`@supabase/supabase-js`** (`signInWithPassword`, `getSession`).
2. Hapus / kurangi ketergantungan tabel `sessions` (Supabase mengelola refresh token).
3. Set env: `VITE_SUPABASE_URL`, `VITE_SUPABASE_PUBLISHABLE_KEY` (bukan service key).

### Fase 3 — Backend

1. Flask verifikasi **JWT Supabase** (JWKS / `getUser`) alih-alih token custom di `sessions`.
2. Atau: **hapus Flask** untuk CRUD user-owned dan pindah ke supabase-js + RLS (arsitektur besar).

### Fase 4 — Policy SQL (baru valid)

Contoh untuk tabel dengan **`user_id uuid references auth.users(id)`**:

```sql
ALTER TABLE public.favorites ENABLE ROW LEVEL SECURITY;

CREATE POLICY "select_own" ON public.favorites
  FOR SELECT TO authenticated
  USING ((select auth.uid()) = user_id);

CREATE POLICY "insert_own" ON public.favorites
  FOR INSERT TO authenticated
  WITH CHECK ((select auth.uid()) = user_id);

CREATE POLICY "update_own" ON public.favorites
  FOR UPDATE TO authenticated
  USING ((select auth.uid()) = user_id)
  WITH CHECK ((select auth.uid()) = user_id);

CREATE POLICY "delete_own" ON public.favorites
  FOR DELETE TO authenticated
  USING ((select auth.uid()) = user_id);
```

Ulangi per tabel: `favorites`, `want_to_visit`, `review_likes`, `recommendation_feedback`, `preference_suggestions`, `shop_votes`, dll.

**Admin:** policy terpisah dengan `auth.jwt() -> 'app_metadata' ->> 'role' = 'admin'` (hanya di **`app_metadata`**, bukan `user_metadata`).

### Fase 5 — Tes & advisor

1. Login sebagai user A → hanya baris A via REST.
2. `get_advisors` security → kurangi lint RLS/no policy pada tabel yang sudah dipolicy-kan.
3. Regression tes Flask jika masih dipakai (service role bypass RLS).

---

## Jalur C — Hybrid (hanya jika benar-benar perlu)

1. Flask tetap untuk pipeline rekomendasi / admin / LLM.
2. Fitur terbatas (mis. baca ulasan) via supabase-js + policy baca publik (sudah ada di 003).
3. **Jangan** campur Flask token dengan `auth.uid()` tanpa bridge resmi.

Umumnya **tidak disarankan** untuk Cofind kecuali ada requirement khusus.

---

## Checklist cepat setelah perbaikan skema (003)

- [ ] `users.is_admin` / `is_active` bertipe **boolean** di Supabase Table Editor
- [ ] FK **`place_id`** ada di `reviews`, `shop_votes`, `shop_pros_cons`, `recommendation_feedback`
- [ ] `review_embeddings.review_id` = **bigint**
- [ ] `preference_suggestions` **tanpa** `preference_text` / `reason_text`
- [ ] Deploy ulang **Railway** (backend) jika env tidak berubah — cukup restart setelah migrasi DB
- [ ] Tes **Admin** filter user aktif/admin (query boolean di `admin_routes.py`)

---

## Rekomendasi praktis

- **Untuk menyelesaikan skripsi / app saat ini:** ikuti **Jalur A**; jelaskan di bab keamanan bahwa otorisasi per-user ada di **Flask**, RLS mengunci **akses REST langsung**.
- **Jika dosen/requirement wajib “RLS per-user auth.uid()”:** rencanakan **Jalur B** sebagai pekerjaan terpisah (estimasi: auth ulang frontend + backend + migrasi kolom uuid).

---

## Referensi di repo

- Migrasi: `scripts/migrations/003_schema_consistency_rls.sql`
- Auth frontend: `frontend-cofind/src/services/authService.js`
- Helper SQL boolean: `db_backend.sql_user_flag_true` / `sql_user_flag_false`
- Supabase client (opsional): `frontend-cofind/src/utils/supabase.js`
