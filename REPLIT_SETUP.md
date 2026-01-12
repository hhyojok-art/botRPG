# Replit deployment instructions

Langkah cepat untuk menjalankan proyek ini di Replit:

- Tambahkan secret environment variable `TOKEN` di Replit (Settings → Secrets). Nilai `TOKEN` adalah token bot Discord Anda.
- (Opsional) jika Anda memakai Redis untuk toggle maintenance, tambahkan `REDIS_URL` di Secrets.
- Aktifkan "Always On" (atau gunakan Replit paid) agar bot tetap berjalan.

Cara kerja start script (`run_repl.sh`):

- Meng-install dependency dari `requirements.txt`.
- Jika `TOKEN` tidak diset, script hanya menjalankan dashboard FastAPI di port 8000.
- Jika `TOKEN` diset, script menjalankan `python main.py` di background lalu menjalankan `uvicorn dashboard.app:app --host 0.0.0.0 --port 8000` di foreground.

Tips:
- Pastikan `Assets/background/maintenance.png` tersedia jika Anda ingin gambar maintenance kustom.
- Jika frontend React ingin digunakan, build hasilkan folder `frontend/dist` dan simpan di repo sebelum start.

Jika ada masalah, lihat log Replit console untuk pesan error dan pastikan Secrets terisi dengan benar.
