# Bot Telegram ODP dengan Tampilan Satelit Google Hybrid

Bot Telegram ini dirancang untuk mencari ODP (Optical Distribution Point) dalam jarak tertentu dari koordinat yang diberikan dan menampilkannya dalam bentuk peta satelit Google Hybrid yang memperlihatkan jalan dan bangunan dengan jelas.

## Fitur Utama

- **Pencarian ODP dalam Radius**: Mencari ODP dalam radius tertentu (default 250m) dari koordinat yang diberikan
- **Tampilan Peta Satelit Google Hybrid**: Menampilkan citra satelit dengan jalan dan bangunan yang sangat jelas
- **Tampilan Multiple Map**: Pengguna dapat memilih antara peta jalan, satelit tanpa rute, atau satelit Google Hybrid dengan jalan dan bangunan
- **Visualisasi Rute**: Menampilkan rute/jalur dari titik referensi ke lokasi ODP
- **Kode Warna Jarak**: ODP ditampilkan dengan warna berbeda berdasarkan jaraknya (hijau, biru, orange)
- **Informasi ODP pada Peta**: Menampilkan nama ODP, jarak, dan nilai AVAI langsung pada peta dengan ukuran kecil
- **Daftar Teks ODP**: Menampilkan daftar teks ODP terdekat dengan detailnya
- **Koneksi Langsung ke Spreadsheet**: Mengakses data ODP langsung dari spreadsheet Google
- **Pemuatan Data Tangguh**: Sistem fallback pemuatan data untuk antisipasi masalah koneksi

## Cara Penggunaan

1. **Mulai Percakapan**: Gunakan `/start` untuk memulai percakapan dengan bot
2. **Kirim Koordinat**: Kirim koordinat dalam format `-3.292481, 114.592482` atau gunakan fitur Share Location Telegram
3. **Lihat Hasil**: Bot akan mencari ODP terdekat dan menampilkan hasilnya dalam bentuk daftar dan peta interaktif
4. **Pilih Tampilan Peta**: Pilih antara tampilan peta jalan, satelit tanpa rute, atau satelit dengan jalan dan bangunan
5. **Atur Radius**: Gunakan perintah `/radius [nilai]` untuk mengubah radius pencarian (misalnya `/radius 300`)

## Perintah Bot

- `/start` - Memulai bot
- `/help` - Menampilkan informasi bantuan
- `/radius [nilai]` - Melihat atau mengubah radius pencarian
- `/examples` - Menampilkan contoh koordinat
- `/status` - Menampilkan status bot dan data
- `/reload` - Muat ulang data (admin)
- `/search [koordinat]` - Mencari ODP berdasarkan koordinat

## Opsi Tampilan Peta

Bot ini menawarkan tiga opsi tampilan peta yang dapat dipilih:

1. **🗺️ Peta Jalan**: Menampilkan peta OpenStreetMap dengan rute ke ODP
2. **🛰️ Satelit Tanpa Rute**: Menampilkan citra satelit tanpa garis rute
3. **🏘️ Satelit dengan Jalan & Bangunan**: Menampilkan citra satelit Google Hybrid dengan jalan dan bangunan yang jelas, serta rute ke ODP

## Menjalankan Bot

Untuk menjalankan bot, gunakan:

```bash
python odp_telegram_bot_enhanced.py
```

Bot ini memerlukan token Telegram yang harus diatur sebagai variabel lingkungan `TELEGRAM_TOKEN`.

## Requirement

- Python 3.7+
- pandas
- numpy
- matplotlib
- contextily
- geopy
- pyTelegramBotAPI

## Catatan Implementasi

- Bot menggunakan tampilan Google Hybrid sebagai default untuk memberikan visualisasi terbaik dengan jalan dan bangunan yang jelas
- Sistem pemuatan data memiliki fallback untuk mengatasi masalah konektivitas
- Gambar peta dibuat secara real-time dan dikirim langsung ke Telegram tanpa perlu hosting web
- UI tombol telah diorganisasi untuk memudahkan navigasi antar jenis tampilan peta