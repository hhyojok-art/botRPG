# Discord Bot — Dokumen & Panduan

> Ringkasan: bot Discord berbasis `discord.py` dengan fitur profile/XP, ekonomi/shop, RPG (adventure), inventory/equip dengan sistem slot, dan dashboard FastAPI.

## Fitur Utama
- Perintah hybrid (prefix & slash) — tiap command bisa dipanggil `!command` atau `/command`.
- Sistem XP & level (profil), leaderboard.
- Ekonomi: shop per-server, beli item pakai XP, inventory, equip/unequip.
- Sistem slot untuk equipment — hanya 1 item per slot aktif; auto-unequip saat memasang item baru di slot sama.
- RPG: `adventure` (cooldown 1 jam) untuk dapat XP, gold, dan chance drop item.
- Potions: sistem potion consumable — `!claim` untuk mendapatkan potion acak (cooldown 1 jam), dan `!use <potion_name>` untuk menggunakan potion yang berada di inventory.
- Owner tools: maintenance (Redis), shop management, monster management, reload cogs.
- FastAPI dashboard untuk health & toggle maintenance; frontend React opsional.

## Persyaratan
- Python 3.10+
- Dependencies di `requirements.txt` (jalankan: `pip install -r requirements.txt`).
- (Opsional) Redis untuk flag maintenance. Jika Redis tidak aktif bot tetap jalan (fallback).
- (Opsional) Node/npm untuk build frontend di `frontend/`.

## Environment Variables (.env)
- `TOKEN` — token bot Discord (wajib)
- `CLIENT_ID` — (opsional) untuk invite link di help
- `DASHBOARD_URL` — (opsional) URL eksternal dashboard
- `LOG_CHANNEL_ID` — (opsional) ID channel untuk notifikasi log
- `REDIS_URL` — (opsional) jika Anda tidak pakai `localhost:6379`

## Setup & Menjalankan
1. Install dependencies:
```bash
pip install -r requirements.txt
```
2. Buat file `.env` berisi `TOKEN` (dan variabel opsional lain).
3. Jalankan bot:
```bash
python main.py
```
4. (Opsional) Jalankan dashboard:
```bash
uvicorn dashboard.app:app --reload
```
5. (Opsional) Build frontend (jika ada):
```bash
cd frontend
npm install
npm run build
# Hasil build -> frontend/dist (Letakkan di repo supaya FastAPI bisa serve)
```

## Daftar Perintah (Ringkas)

Public:
- `ping` — cek latency
- `list` — daftar command interaktif (embed + tombol)

Profil / XP:
- `profile [member]` — lihat XP, level, progress
- `leaderboard [limit]` — top XP server

Ekonomi / Shop:
- `shop` — list item server
- `buy <item_name>` — beli item pakai XP
- `inventory` — lihat inventory, slot, equipped
- `equip <item_name>` — pasang item (menambah ATK/DEF sesuai item)
- `unequip <item_name>` — lepas item
Owner (shop mgmt):
- `shopadd <name> <price> [description]` — tambah/update item
- `shopremove <name>` — hapus item
- `shopseed` — seed beberapa item contoh

RPG:
- `adventure` — petualangan lawan monster (cooldown 1 jam)
- `rpgstats [member]` — lihat HP/ATK/DEF/Gold/Level
- `heal` — sembuh penuh (biaya 10 gold)

Potions:
- `claim` — klaim 1 potion acak (cooldown 1 jam)
- `use <potion_name>` — gunakan potion dari inventory (efek: restore HP, ubah `def`, atau efek lain tergantung potion)

Owner / Admin (bot owner):
- `maintenance on|off` — toggle maintenance (Redis)
- `setprefix <prefix>` — ubah prefix server
- `reload [cog]` — reload satu atau semua cogs
- `setxp <member> <xp>` — set XP user
- `setstat <member> <stat> <value>` — set stat (hp,max_hp,atk,def,gold)
- Monster mgmt: `listmonsters`, `addmonster`, `setmonster`, `removemonster`

## Database & Penyimpanan
- File DB: `bot.db` dibuat otomatis.
- Tabel penting: `user_xp`, `user_profile`, `shop_items`, `inventory`, `cooldowns`, `guild_config`, `permissions`.
- Migrasi otomatis menambahkan kolom `atk`, `def`, `slot` pada `shop_items` dan kolom `equipped`, `slot` pada `inventory`.

## Detail Teknis & Catatan
- Shop: harga disimpan sebagai XP cost. Membeli mengurangi XP user.
- Inventory & Equip: `inventory` menyimpan `(item_name, qty, equipped, slot)`. Equipping mengubah `user_profile` `atk`/`def` sesuai item.
- Slot: contoh slot values: `weapon`, `head`, `body`, `accessory`, atau `none`.
- Cooldown: `adventure` memakai tabel `cooldowns` (3600 detik).
- Maintenance: kunci `bot_enabled` di Redis (`true`/`false`). Jika Redis unreachable, bot defaults ke enabled.

## Troubleshooting
- Jika bot tidak merespon: periksa `logs/bot.log`.
- Redis connection error: bot tetap jalan, namun toggle maintenance mungkin gagal.
- Command permission errors: pastikan Anda owner bot atau role admin/mod terkonfigurasi (`permissions` table).

## Menambah Item Berstat
- Gunakan `!shopadd "Item Name" 200 Deskripsi` untuk menambah item. Untuk memasukkan `atk`, `def`, `slot` lewat DB langsung atau tambahkan util owner tambahan.

## Fitur Tambahan (detail yang mungkin belum tercantum di atas)

- Maintenance & Dashboard:
	- Maintenance dapat di-toggle oleh owner melalui command `maintenance on|off` atau dari dashboard.
	- Status maintenance disimpan di Redis (`bot_enabled`) jika tersedia. Jika Redis tidak tersedia, bot menggunakan fallback file lokal `bot_state.json` sehingga toggle tetap bekerja.
	- Dashboard FastAPI menyediakan endpoint `POST /maintenance/on` dan `POST /maintenance/off` untuk mengubah mode maintenance.

- Gambar Maintenance Otomatis & Kustomisasi:
	- Bot dapat mengirim gambar `Assets/background/maintenance.png` saat maintenance aktif. Jika file ada, bot mengirim file tersebut; jika tidak, bot membuat gambar dinamis sebagai fallback.
	- Ada script generator `scripts/update_maintenance_image.py` yang dapat menghasilkan gambar maintenance bergaya (termasuk preset `mario`).
	- Opsi konfigurasi lewat environment variables:
		- `MAINT_AUTO_GENERATE` (1/true/yes) — bila di-set, dashboard/owner akan memanggil generator saat mengaktifkan maintenance. Default: mati (agar file `maintenance.png` tetap permanen).
		- `MAINT_THEME` — preset tema untuk generator (mis. `mario`).
		- `MAINT_BG_COLOR` — warna latar belakang rounded rectangle (hex atau `r,g,b`).
		- `MAINT_TITLE_COLOR`, `MAINT_SUB_COLOR` — warna teks utama dan sub.
		- `MAINT_TITLE_SCALE`, `MAINT_SUB_SCALE` — skala ukuran font relatif terhadap tinggi gambar.
	- Icon: generator akan mencari ikon di `Assets/icons/mario.png` atau `Assets/background/mario_icon.png`, `mushroom.png`; jika tidak ada, generator membuat ikon topi Mario sederhana.
	- Untuk membuat gambar manual: jalankan
		```powershell
		$env:MAINT_THEME='mario'
		.venv\Scripts\python.exe scripts\update_maintenance_image.py
		```

- Skrip utilitas lain:
	- `scripts/repair_monsters_json.py` — memperbaiki dan mengekstrak objek monster dari file `data/monsters.json` yang korup.
	- `scripts/normalize_mobs.py` — menormalisasi HP monster yang terlalu tinggi agar rata-rata menjadi ~100 HP.

- Potions (Consumables):
	- `!claim` memberi player 1 potion acak dan disimpan di tabel `inventory`. Perintah ini memiliki cooldown 3600 detik (1 jam) yang disimpan di tabel `cooldowns`.
	- `!use <potion_name>` memakai potion dari inventory — efek berbeda tergantung tipe potion. Contoh potion bawaan:
		- `Small Health Potion`: restore HP kecil (mis. +20 HP)
		- `Large Health Potion`: restore HP besar (mis. +75 HP)
		- `Iron Tonic`: menambah `def` sementara atau permanen bergantung konfigurasi (implementasi saat ini mengubah stat di `user_profile`).
		- `Poison`: potion berbahaya yang mengurangi HP saat dipakai.
	- Inventory & DB: potions disimpan di tabel `inventory` sebagai item biasa; konsumsi memanggil helper `database.remove_item()` untuk mengurangi qty.
	- Pengujian & kustomisasi: jika Anda ingin menambah/mengubah daftar potion, edit `cogs/potions.py` atau tambahkan definisi potion di DB sesuai implementasi yang diinginkan.

- Perilaku dan perubahan teknis penting:
	- `redis_client.py` memiliki fallback lokal (`bot_state.json`) sehingga bot tetap berfungsi tanpa Redis.
	- `database.get_shop_item_with_stats` diperluas untuk pencarian case-insensitive dan slug-matching sehingga perintah `equip`/`unequip` lebih toleran terhadap nama item.
	- Dashboard memasang `SessionMiddleware` dan membutuhkan `itsdangerous` (pastikan `itsdangerous` ada di `requirements.txt` atau di-install jika menggunakan dashboard session).

## Contributing
- Buat issue / PR. Ikuti gaya codebase dan run tests manual.

---
File ini dibuat otomatis oleh asistensi pengembangan. Untuk penyesuaian tambahan, beri tahu saya jika mau saya tambahkan contoh screenshot, template `.env`, atau file `DOCS/COMMANDS.md`.
# Bot Discord (Siap Pakai)

Panduan singkat menjalankan bot ini.

Persyaratan:
- Python 3.10+
- Redis (opsional, dipakai untuk maintenance flag)

Instal dependensi:

```bash
pip install -r requirements.txt
```

Siapkan file `.env` (contoh `.env.example` ada di repo).

Menjalankan bot:

```bash
python main.py
```

Menjalankan dashboard FastAPI (opsional):

```bash
uvicorn dashboard.app:app --host 0.0.0.0 --port 8000
```

## Replit Troubleshooting

Jika Anda mengalami kegagalan deploy di Replit, periksa hal-hal berikut:

- Health checks Replit memanggil `/` secara default. Root sekarang merespons segera tanpa operasi I/O berat.
- Replit membutuhkan aplikasi membuka port dengan cepat. `run_repl.sh` sekarang menggunakan env `PORT` (jika tersedia) dan mengeksekusi `uvicorn` di foreground.
- Marker file: saat FastAPI siap, aplikasi menulis file `.uvicorn_bound` di root repo. Anda dapat memeriksa apakah server sudah bind dengan memeriksa file tersebut atau memanggil endpoint `/probe`.

Contoh pemeriksaan lokal (setelah deploy):

```bash
curl https://<your-replit-url>/probe
# atau
curl https://<your-replit-url>/health
```

- Jika Anda melihat status `not_bound` atau tidak mendapatkan respons dalam waktu singkat, pastikan `PORT` di Replit (jika tersedia) cocok dengan yang digunakan oleh `uvicorn`, dan tidak ada operasi panjang di startup.
- Untuk deployment stabil, tambahkan secret `TOKEN` di Replit Secrets agar bot berjalan; jika tidak ada `TOKEN`, hanya dashboard yang dijalankan.

Jika masih gagal, bagikan log Replit (console) dan saya bantu analisis lebih lanjut.

Fitur utama:
- Hybrid commands: slash dan prefix (`!` default)
- Per-server prefix (SQLite)
- Owner commands: `maintenance on/off`, `setprefix`, `stop`
- Async entrypoint (`asyncio.run(main())`)
- Auto-load semua cogs dari folder `cogs`
- Logging ke `logs/bot.log`

## Fitur Umum

- Dasar: `ping`, `help`, `about` — informasi bot dan status.
- Perintah Hybrid: dukungan `!` + slash commands.
- Profil & XP: `profile`, level, progress bar, `leaderboard`.
- Ekonomi: `shop`, `buy`, `inventory`, gold/XP balance.
- Inventory & Equip: `equip`/`unequip`, slot equipment (weapon/head/body/accessory).
- RPG / Combat: `adventure`, monster drops, HP/ATK/DEF, rewards XP & gold.
- Potions: `claim` dan `use` consumables dengan cooldown.
- Daily Quests: `quest` / `progress` — quest harian, auto-claim reward, dan penghapusan quest selesai.
- Crafting: `recipes`, `craft` — gabung item untuk membuat item baru.
- Buffs & Effects: temporary buffs yang memodifikasi stat.
- Achievements / Badges: earnable badges, `!badges`, `!badges show icon`, dan badge muncul di `!profile`.
- Moderasi & Admin: role checks, `setprefix`, reload cogs, maintenance on/off.
- Dashboard & Integrasi: FastAPI dashboard + optional React frontend.
- Persistence & Resilience: SQLite + optional Redis with local fallback.
- Assets: dynamic profile and congrats images (Pillow), badge icons di `Assets/badges/`.

Struktur:
```
bot/
├── main.py
├── cogs/
│   ├── public.py
│   └── owner.py
```

Silakan edit `requirements.txt` dan `.env` sesuai kebutuhan.