# BOT TELEGRAM PENCARI ODP

Bot Telegram ini memungkinkan pencarian ODP (Optical Distribution Point) berdasarkan koordinat geografis dan menampilkan hasil dalam bentuk teks dan gambar peta yang detil.

## Fitur Utama

1. **Pencarian ODP berdasarkan Koordinat**:
   - Lewat perintah: `/cari -3.292481 114.592482 100`
   - Input langsung: `-3.292481, 114.592482`
   - Berbagi lokasi langsung via Telegram

2. **Tampilan Peta Interaktif**:
   - Peta Satelit dengan rute (default)
   - Peta Jalan (OpenStreetMap)
   - Opsi tampilan dengan atau tanpa rute jalan

3. **Informasi ODP**:
   - Nama ODP, koordinat, dan jarak dari titik referensi
   - Ketersediaan (availability) ODP
   - Kode warna berdasarkan jarak (hijau, biru, oranye, ungu)

4. **Navigasi Mudah**:
   - Tombol untuk beralih antara tampilan peta
   - Radius pencarian yang dapat disesuaikan
   - Contoh koordinat yang siap pakai

## Cara Menggunakan Bot

1. **Mulai Percakapan**:
   ```
   /start - Memulai bot dan melihat sambutan
   /help - Menampilkan bantuan penggunaan
   ```

2. **Cari ODP**:
   ```
   /cari -3.292481 114.592482 250
   ```
   Parameter: latitude, longitude, radius (opsional, default 250m)

3. **Pencarian Langsung**:
   Cukup kirim koordinat dengan format:
   ```
   -3.292481, 114.592482
   ```

4. **Berbagi Lokasi**:
   Gunakan fitur "Location" di Telegram (ikon clip → Location)

5. **Mengubah Tampilan Peta**:
   Gunakan tombol yang muncul setelah pencarian:
   - "Lihat Peta Jalan" - tampilan peta jalan (OpenStreetMap)
   - "Satelit Tanpa Rute" - tampilan satelit tanpa garis rute

6. **Mengubah Radius Pencarian**:
   ```
   /radius 500
   ```
   Mengubah radius default menjadi 500 meter

## Perintah yang Tersedia

- `/start` - Memulai bot
- `/help` - Menampilkan bantuan
- `/cari <lat> <lng> [radius]` - Mencari ODP di sekitar koordinat
- `/radius [nilai]` - Melihat/mengubah radius pencarian
- `/contoh` - Menampilkan contoh koordinat
- `/status` - Melihat status bot dan data
- `/reload` - Memuat ulang data dari spreadsheet

## Contoh Koordinat

1. **Area ODP-BJM-FAP/012**:
   `-3.292481, 114.592482` (radius 100m)

2. **Area ODP-PLE-FM/002**:
   `-3.8159, 114.7505` (radius 500m)

3. **Area GCL-BJM-F01/001**:
   `-3.3251, 114.5917` (radius 750m)

4. **Area dengan Banyak ODP**:
   `-3.3219, 114.6034` (radius 250m)

## Cara Menjalankan Bot

1. **Set Token Telegram**:
   ```bash
   export TELEGRAM_TOKEN="token_anda_di_sini"
   ```

2. **Jalankan Bot**:
   ```bash
   python odp_telegram_bot.py
   ```

## Kode Warna Pada Peta

- **Hijau**: ODP sangat dekat (0-25% dari radius)
- **Biru**: ODP dekat (25-50% dari radius)
- **Oranye**: ODP sedang (50-75% dari radius)
- **Ungu**: ODP jauh (75-100% dari radius)
- **Garis Putus**: Rute dari titik referensi ke ODP

## Fitur Teknis

- Akses data dari Google Spreadsheet publik
- Caching data untuk operasi yang lebih cepat
- Visualisasi peta menggunakan matplotlib dan contextily
- Dukungan dua jenis basemap: satelit dan peta jalan
- Interaksi melalui tombol inline keyboard di Telegram