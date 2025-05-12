# Panduan Akses Direct dan Menjaga Bot Telegram Tetap Berjalan

## Solusi Profesional dengan Flask + UptimeRobot

Untuk memastikan bot Telegram ODP tetap berjalan bahkan saat tab Replit ditutup, kami telah menerapkan solusi yang stabil dan resmi menggunakan Flask dan UptimeRobot.

### Cara Kerja
1. Server Flask ringan berjalan pada port 8080
2. UptimeRobot melakukan ping setiap 5 menit untuk menjaga Replit tetap aktif
3. Flask server otomatis mengelola proses bot Telegram di background
4. Jika bot crash, server akan otomatis me-restart

### Langkah Setup

#### 1. Jalankan Server Flask
```
python keep_alive_server.py
```

Server akan secara otomatis:
- Menjalankan bot Telegram
- Menyediakan endpoint API untuk memantau status bot
- Menangani error dan auto-restart

#### 2. Setup UptimeRobot
1. Buat akun gratis di [UptimeRobot](https://uptimerobot.com)
2. Tambahkan monitor baru dengan jenis "HTTP(s)"
3. Masukkan URL Replit Anda: `https://nama-replit-anda.replit.app`
4. Atur interval monitor ke 5 menit
5. Aktifkan monitor tersebut

### Endpoint API

Server Flask menyediakan beberapa endpoint untuk memantau dan mengelola bot:

- `/` - Cek status bot dan auto-restart jika bot mati
- `/start` - Mulai bot secara manual jika belum berjalan
- `/status` - Cek status detail tentang bot

### Keunggulan Solusi Ini

1. **Lebih Stabil**: Pendekatan ini memanfaatkan HTTP request yang lebih andal dibanding watchdog
2. **Terpusat**: Satu server mengelola semuanya, tidak perlu banyak script
3. **Termonitor**: UptimeRobot memberikan notifikasi jika server down
4. **Hemat Sumber Daya**: Konsumsi RAM dan CPU lebih rendah
5. **Dapat Diakses**: Endpoint API memungkinkan pengecekan status jarak jauh

### Penggunaan Harian

Jika menggunakan Replit dengan fitur Always-On, kombinasi Flask + UptimeRobot akan menjaga bot tetap berjalan 24/7, tanpa perlu intervensi manual.

Untuk pengguna tanpa fitur Always-On, server Flask tetap akan berjalan selama Replit sesi aktif, dan UptimeRobot akan mencegah sesi timeout dengan ping berkala.

### Pemecahan Masalah

Jika bot tidak merespons:
1. Cek status server Flask di `https://nama-replit-anda.replit.app/status`
2. Lihat log di `bot_keep_alive.log`
3. Restart server Flask jika diperlukan

### Catatan Penting

- UptimeRobot gratis mendukung hingga 50 monitor dengan interval 5 menit
- Untuk penggunaan paling andal, gunakan fitur Always-On dari Replit bersamaan dengan UptimeRobot
- Server Flask akan memeriksa dan memastikan hanya satu instance bot yang berjalan