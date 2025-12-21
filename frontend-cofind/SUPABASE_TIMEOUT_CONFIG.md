# Konfigurasi Timeout Supabase

Dokumen ini menjelaskan konfigurasi timeout untuk Supabase di project ini.

## Client-Side Timeout

### Konfigurasi di `supabase.js`
- **Client-level timeout**: 20 detik (20000ms)
- **Query-level timeout**: 10 detik (di `ReviewList.jsx`)
- **Insert/Update timeout**: 8 detik (di `ReviewForm.jsx` dan `ReviewCard.jsx`)
- **Reply insert timeout**: 6 detik (di `ReviewCard.jsx`)
- **Profile fetch timeout**: 5 detik (di `ReviewList.jsx` dan `ReviewCard.jsx`)

### Cara Kerja
1. **Client-level timeout** (20s) - Menangkap semua request yang tidak memiliki timeout sendiri
2. **Query-level timeout** (10s) - Untuk fetch reviews (lebih pendek karena query harus cepat)
3. **Operation-level timeout** - Timeout khusus untuk insert/update operations

## Database-Level Timeout (Opsional)

Jika masih mengalami timeout, Anda bisa meningkatkan `statement_timeout` di database:

### Untuk Role `authenticated` (User yang login)
```sql
-- Set timeout menjadi 30 detik untuk authenticated users
ALTER ROLE authenticated SET statement_timeout = '30s';

-- Reload PostgREST untuk apply changes
NOTIFY pgrst, 'reload config';
```

### Untuk Role `anon` (Guest users)
```sql
-- Set timeout menjadi 20 detik untuk anon users
ALTER ROLE anon SET statement_timeout = '20s';

-- Reload PostgREST untuk apply changes
NOTIFY pgrst, 'reload config';
```

### Untuk Session Specific (Temporary)
```sql
-- Set timeout untuk session saat ini saja
SET statement_timeout = '60s';
```

## Monitoring Timeout

### Console Logs
- `[Supabase] ⏱️ Request timeout after XXXms` - Client-level timeout
- `[ReviewList] ⏱️ Timeout after XXXms` - Query-level timeout
- `[ReviewForm] ⚡ Review inserted in XXXms` - Insert operation duration
- `[ReviewCard] ⚡ Review updated in XXXms` - Update operation duration

### Tips
1. **Monitor slow queries** - Jika query > 5 detik, cek di Supabase Dashboard
2. **Check database performance** - Monitor CPU dan memory usage
3. **Optimize queries** - Gunakan EXPLAIN untuk analyze query performance
4. **Add indexes** - Pastikan ada index di:
   - `reviews.place_id`
   - `reviews.created_at`
   - `review_replies.review_id`
   - `profiles.id`

## Troubleshooting

### Masalah: Timeout masih terjadi setelah konfigurasi
1. **Cek database performance** di Supabase Dashboard
2. **Cek network bans** di Database > Settings > Network Bans
3. **Cek connection pooling** di Database > Settings > Connection Pooling
4. **Optimize queries** dengan EXPLAIN command
5. **Consider upgrading** compute add-on jika traffic tinggi

### Masalah: Query terlalu lambat
1. **Add database indexes** untuk columns yang sering di-query
2. **Optimize RLS policies** - Pastikan policies tidak terlalu kompleks
3. **Reduce data fetched** - Gunakan limit dan select hanya field yang diperlukan
4. **Use pagination** - Jangan fetch semua data sekaligus

## Referensi
- [Supabase Timeouts Documentation](https://supabase.com/docs/guides/database/postgres/timeouts)
- [PostgreSQL Statement Timeout](https://www.postgresql.org/docs/current/runtime-config-client.html#GUC-STATEMENT-TIMEOUT)
