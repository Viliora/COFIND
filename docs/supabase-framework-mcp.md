# Supabase Framework (frontend) + MCP (Cursor)

## Frontend — `@supabase/supabase-js`

1. Dependency: `frontend-cofind/package.json` → `@supabase/supabase-js`
2. Client: `frontend-cofind/src/utils/supabase.js` → `getSupabaseClient()`
3. Env di **`frontend-cofind/.env`** (bukan root), contoh:

```env
VITE_SUPABASE_URL=https://rufmbfjiyudtxporekbq.supabase.co
VITE_SUPABASE_PUBLISHABLE_KEY=your-publishable-or-anon-key
```

Vite juga menerima alias `VITE_SUPABASE_ANON_KEY`.

Backend Cofind tetap memakai **`DATABASE_URL`** + `psycopg2` (`db_backend.py`). Client Supabase di browser **patuh RLS**; jangan expose `service_role` di frontend.

### Contoh query (ganti tabel; bukan pola utama app)

```js
import { getSupabaseClient } from './utils/supabase';

const supabase = getSupabaseClient();
if (supabase) {
  const { data, error } = await supabase.from('coffee_shops').select('place_id, name').limit(5);
}
```

## MCP — Cursor

File: **`.cursor/mcp.json`** (scoped ke proyek `rufmbfjiyudtxporekbq`, `read_only=true`).

**Autentikasi (wajib sekali):**

1. Restart Cursor atau buka **Settings → MCP** — pastikan server `supabase` terdeteksi.
2. Klik **Authenticate** / login OAuth untuk server Supabase MCP (bukan `claude /mcp` kecuali Anda memakai Claude Code CLI).

Alternatif Cursor CLI:

```bash
agent mcp enable supabase
agent mcp login supabase
```

## Agent Skills (opsional)

```bash
npx skills add supabase/agent-skills
```

Skills = panduan untuk AI; bukan koneksi runtime aplikasi.
