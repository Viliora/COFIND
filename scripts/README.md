# Scripts Utilitas

Folder ini berisi script-script utilitas untuk memudahkan development dan deployment.

## File-file di folder ini:

### `open-localhost.bat` & `open-localhost.ps1`
Script untuk membuka localhost di browser (frontend dan/atau backend).

**Penggunaan:**
- Windows Batch: `.\scripts\open-localhost.bat`
- PowerShell: `.\scripts\open-localhost.ps1 [frontend|backend|both]`

### `restart-backend.bat`
Script untuk restart backend Flask server.

**Penggunaan:**
```bash
.\scripts\restart-backend.bat
```

### `run_server.py`
Script alternatif untuk menjalankan Flask server (tanpa debug mode).

**Penggunaan:**
```bash
python .\scripts\run_server.py
```

## Catatan
- Script-script ini opsional dan hanya untuk convenience
- Untuk production, gunakan metode deployment yang sesuai (gunicorn, uwsgi, dll)


