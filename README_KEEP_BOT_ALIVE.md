# Panduan Penggunaan FlaskKeepAliveServer untuk ODP Bot

## Solusi untuk Bot yang Berhenti Setelah Beberapa Jam

Jika Anda mengalami masalah bot berhenti merespons setelah beberapa jam meskipun sudah menggunakan UptimeRobot, berikut adalah solusinya:

### 1. Server Flask dengan Self-Ping

Kami telah meningkatkan server Flask untuk melakukan **self-ping internal setiap 2 menit** (lebih cepat dari interval UptimeRobot 5 menit). Ini berfungsi sebagai mekanisme backup dan membantu:

- Menjaga server Flask tetap aktif
- Memastikan bot dijalankan ulang jika terjadi crash
- Menghindari timeout session dari Replit

### 2. Parameter Koneksi Telegram yang Dioptimalkan

Kami telah mengubah parameter polling infinity pada bot Telegram:

```python
bot.infinity_polling(
    timeout=30,              # Dikurangi dari 60 untuk respons lebih cepat
    long_polling_timeout=15, # Dikurangi dari 30 untuk menghindari hang
    allowed_updates=None, 
    skip_pending=True,       # Diubah untuk mengatasi backlog pesan saat bot berhenti
    none_stop=True, 
    interval=2               # Ditambahkan interval polling untuk mengurangi beban server
)
```

Parameter ini menghindari koneksi hang dan memastikan bot dapat pulih dengan cepat saat terjadi gangguan koneksi.

### 3. Monitoring dan Auto-Recovery

Flask server sekarang dilengkapi dengan beberapa endpoint baru:

- **/ping** - Digunakan oleh self-ping thread internal untuk menjaga server tetap aktif
- **/status** - Untuk memeriksa status bot (aktif/tidak)
- **/start** - Untuk memulai bot secara manual jika diperlukan

Server juga akan otomatis mendeteksi jika bot berhenti dan merestart-nya.

### 4. Cara Menggunakan

1. **Pastikan workflow "FlaskKeepAliveServer" berjalan (bukan lagi "BotAlwaysOn")**
2. **Konfigurasikan UptimeRobot untuk mem-ping URL Replit Anda**
3. **Untuk pengujian manual, buka endpoint `/status` untuk melihat status bot**

### 5. Pemecahan Masalah

Jika bot masih berhenti setelah beberapa jam:

1. **Periksa log bot_keep_alive.log** untuk melihat pesan error
2. **Restart workflow FlaskKeepAliveServer** secara manual
3. **Pastikan UptimeRobot masih aktif** dan mem-ping server Anda

### 6. Penyebab Umum Bot Berhenti

Bot Telegram biasanya berhenti karena beberapa alasan:

- **Connection pooling timeout** - Koneksi TCP idle terlalu lama
- **Replit resource limits** - Server idle terlalu lama dan sumber daya diambil kembali
- **Telegram API rate limiting** - Terlalu banyak request dalam waktu singkat
- **Network issues** - Masalah jaringan sementara

Solusi yang kami terapkan mengatasi semua masalah di atas dengan kombinasi self-ping, parameter koneksi optimal, dan mekanisme auto-recovery.

### 7. Monitoring Jangka Panjang

Untuk memastikan bot tetap berjalan:

1. **Cek secara berkala setiap hari**
2. **Setup notifikasi UptimeRobot** untuk memberi tahu jika server down
3. **Pantau log** untuk mendeteksi masalah potensial lebih awal