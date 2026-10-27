# Git hooks — strip Cursor co-author

Menghapus baris `Co-authored-by: Cursor <cursoragent@cursor.com>` dari pesan commit **sebelum** commit dibuat, agar Cursor tidak muncul sebagai contributor di GitHub.

## Aktivasi (sekali per clone)

Dari root repo:

```powershell
git config core.hooksPath scripts/githooks
```

Di Windows, Git for Windows menjalankan hook via `sh`; pastikan `python` ada di PATH.

## Hook

| File | Peran |
|------|--------|
| `prepare-commit-msg` | Menyaring trailer saat commit / merge message disusun |
| `commit-msg` | Pass kedua (jika trailer masih tersisa) |
| `strip_cursor_coauthor.py` | Logika penghapusan (bisa dipakai standalone) |

Uji manual pada file pesan:

```powershell
python scripts/githooks/strip_cursor_coauthor.py path\to\COMMIT_EDITMSG
```

## Riwayat commit lama (sudah di GitHub)

GitHub contributor graph membaca **Co-authored-by** di pesan commit yang sudah ter-push. Hook **tidak** mengubah history.

Lihat commit terdampak:

```powershell
python scripts/git/strip_cursor_coauthor_history.py
```

Rewrite (berisiko — baca di bawah):

```powershell
pip install git-filter-repo
python scripts/git/strip_cursor_coauthor_history.py --apply
git push --force-with-lease origin main
```

### Risiko rewrite history

- Semua SHA commit berubah → **force push** wajib.
- Collaborator harus **re-clone** atau `git fetch` + reset hard ke remote baru.
- PR branch lama jadi outdated.
- Merge commit + branch aktif memperbesar dampak; backup branch dulu.
- Contributor graph GitHub bisa butuh waktu untuk refresh setelah force push.

Commit **belum push** (mis. 1 commit ahead): cukup `git commit --amend` setelah `core.hooksPath` aktif — hook akan membersihkan pesan.

## Langkah minimal (tanpa membingungkan)

| Sudah selesai otomatis | Anda (nanti, saat aman) |
|------------------------|-------------------------|
| Hook aktif (`core.hooksPath`) | — |
| Commit lokal terakhir tanpa trailer Cursor | — |
| Branch backup `backup/pre-coauthor-strip-2026-10-27` | — |
| Commit **baru** ke depan bebas trailer | — |

**7 commit lama masih di GitHub** → contributor Cursor hilang hanya setelah rewrite + push.

1. Selesaikan dulu semua perubahan di editor (commit atau stash).
2. Jalankan dari root repo:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/git/bersihkan-coauthor-github.ps1
```

Skrip menolak jalan jika working tree kotor, membandingkan **isi file** sebelum/sesudah, dan hanya push jika identik.
