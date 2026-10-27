# Jalankan HANYA saat working tree bersih (semua WIP sudah di-commit atau di-stash).
# Mengubah pesan commit lama di GitHub (bukan isi file). Backup otomatis.
$ErrorActionPreference = "Stop"
Set-Location (git rev-parse --show-toplevel)

$dirty = git status --porcelain
if ($dirty) {
    Write-Host "DITOLAK: masih ada perubahan belum commit. Simpan dulu pekerjaan Anda, lalu jalankan ulang." -ForegroundColor Yellow
    Write-Host $dirty
    exit 1
}

$backup = "backup/pre-coauthor-strip-2026-10-27"
if (-not (git show-ref --verify --quiet "refs/heads/$backup")) {
    git branch $backup
    Write-Host "Backup branch: $backup"
}

python -m pip install --user git-filter-repo 2>$null
if (-not (Get-Command git-filter-repo -ErrorAction SilentlyContinue)) {
    Write-Host "Install git-filter-repo: pip install git-filter-repo" -ForegroundColor Red
    exit 1
}

Write-Host "Dry-run dulu..."
python scripts/git/strip_cursor_coauthor_history.py
$ok = Read-Host "Lanjut rewrite pesan commit + force push? (ketik ya)"
if ($ok -ne "ya") { exit 0 }

python scripts/git/strip_cursor_coauthor_history.py --apply
$treeBefore = git rev-parse "${backup}:HEAD"
$treeAfter = git rev-parse "HEAD^{tree}"
if ($treeBefore -ne $treeAfter) {
    Write-Host "DITOLAK: isi file berubah — reset ke $backup" -ForegroundColor Red
    git reset --hard $backup
    exit 1
}

Write-Host "Isi repo identik; hanya SHA/pesan berubah."
if (-not (git remote get-url origin 2>$null)) {
    git remote add origin https://github.com/Viliora/COFIND.git
}
git push --force-with-lease origin main
Write-Host "Selesai. Contributor graph GitHub bisa butuh beberapa jam refresh."
