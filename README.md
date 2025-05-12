# Bot Pencari Lokasi

Bot ini memungkinkan Anda untuk mencari lokasi dalam radius tertentu (default 250 meter) dari titik koordinat yang ditentukan. Bot ini menggunakan Google Sheets sebagai sumber data dan library geopy untuk perhitungan jarak.

## Fitur

- Hubungkan ke Google Sheets menggunakan API
- Muat data lokasi dari spreadsheet
- Temukan lokasi dalam radius tertentu dari titik yang ditentukan
- Hitung jarak antara lokasi dan titik referensi
- Simpan hasil ke file CSV

## Persyaratan

- Python 3.6+
- pandas
- gspread
- oauth2client
- geopy

## Petunjuk Penggunaan

### 1. Pengaturan Google Sheets API

Sebelum menjalankan bot, Anda perlu mengatur akses ke Google Sheets API:

1. Buka [Google Cloud Console](https://console.cloud.google.com/)
2. Buat proyek baru atau pilih proyek yang sudah ada
3. Aktifkan Google Sheets API dan Google Drive API
4. Buat Service Account Credentials:
   - Buka menu "Credentials"
   - Klik "Create Credentials" > "Service Account"
   - Isi detail yang diminta dan berikan peran "Editor"
   - Buat kunci baru dalam format JSON
   - Unduh file JSON credentials
5. Rename file credentials menjadi `credentials.json` dan upload ke proyek Replit Anda
6. Bagikan dokumen Google Sheets Anda dengan alamat email service account yang ada di file credentials

### 2. Persiapkan Data

Anda membutuhkan spreadsheet dengan minimal dua kolom untuk latitude dan longitude. Pastikan Anda telah membagikan spreadsheet ini dengan service account yang telah dibuat.

Jika Anda tidak memiliki data untuk pengujian, gunakan skrip `sample_data_generator.py` untuk membuat data sampel:

```bash
python sample_data_generator.py
```

Skrip ini akan menghasilkan file CSV dengan 50 lokasi acak di sekitar Jakarta Pusat. Anda dapat mengimpor file ini ke Google Sheets.

### 3. Jalankan Bot

Untuk menjalankan bot:

```bash
python location_bot.py
```

Bot akan meminta input berikut:
- Nama spreadsheet
- Nama worksheet (opsional)
- Nama kolom untuk latitude dan longitude
- Koordinat latitude dan longitude titik referensi
- Radius pencarian (meter)

### 4. Hasil

Bot akan menampilkan hasil berupa lokasi-lokasi yang berada dalam radius yang ditentukan, beserta jarak dari titik referensi. Anda dapat memilih untuk menyimpan hasil ini ke file CSV.

## Contoh Struktur Data Spreadsheet

| Nama       | Alamat             | Jenis      | Rating | Latitude  | Longitude   | Telepon      |
|------------|-------------------|------------|--------|-----------|-------------|--------------|
| Restoran 1 | Jalan Sudirman 45 | Restaurant | 4.5    | -6.208123 | 106.845678 | 021-5551234 |
| Café 12    | Jalan Thamrin 23  | Café       | 4.0    | -6.209234 | 106.843210 | 021-5557890 |
| Apotek 7   | Jalan Kebon Sirih | Apotek     | 3.5    | -6.207456 | 106.848765 | 021-5559876 |

## Penggunaan Lanjutan

### Modifikasi Radius Pencarian

Default radius pencarian adalah 250 meter, tetapi Anda dapat mengubahnya saat menjalankan bot.

### Integrasi dengan Aplikasi Lain

Bot ini dapat dimodifikasi untuk diintegrasikan dengan aplikasi lain seperti:
- Bot Telegram/Discord/WhatsApp
- Aplikasi web
- Sistem notifikasi

### Menambahkan Fitur Tambahan

Beberapa fitur yang dapat ditambahkan:
- Visualisasi peta dengan hasil pencarian
- Filter hasil berdasarkan kriteria tambahan (rating, jenis, dll)
- Pencarian berdasarkan alamat yang dikonversi menjadi koordinat dengan geocoding

## Troubleshooting

### Masalah Akses Spreadsheet

Jika Anda mendapatkan error akses, pastikan:
- File credentials.json sudah benar
- Anda telah membagikan spreadsheet dengan email service account
- Spreadsheet dan worksheet yang ditentukan sudah benar

### Masalah Format Data

Jika terjadi error saat perhitungan jarak, pastikan:
- Nilai latitude dan longitude disimpan sebagai angka di spreadsheet
- Nama kolom sudah benar