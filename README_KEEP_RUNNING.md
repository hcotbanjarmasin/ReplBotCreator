# Panduan Agar Bot Telegram Tetap Berjalan

Agar bot Telegram ODP tetap berjalan bahkan setelah Anda menutup tab Replit, ikuti langkah-langkah berikut:

## 1. Menggunakan Fitur "Always On" Replit

Replit menyediakan fitur "Always On" yang memungkinkan aplikasi tetap berjalan di server mereka bahkan setelah Anda menutup browser.

1. Pastikan Anda sudah login ke akun Replit
2. Di panel kanan, aktifkan fitur "Always On"
3. Tunggu hingga status menjadi "Enabled"

## 2. Menggunakan Script Keep-Alive Khusus

Kami telah membuat script khusus yang bisa digunakan untuk menjaga bot tetap berjalan:

1. Workflow `BotAlwaysOn` sudah dikonfigurasi untuk menjalankan script keep_bot_alive.py
2. Script ini akan menjalankan bot dan secara otomatis me-restart jika terjadi error
3. Secara default, Replit akan menjalankan perintah di file .replit saat deployment

## 3. Cara Menjalankan Bot Secara Manual

Jika bot berhenti, Anda bisa menjalankannya secara manual dengan cara:

1. Jalankan workflow "BotAlwaysOn" dari panel Replit
2. Atau jalankan perintah di terminal: `python keep_bot_alive.py`

## 4. Pemecahan Masalah

Jika bot masih berhenti:

1. Periksa log error di konsol Replit
2. Pastikan fitur "Always On" telah diaktifkan
3. Coba restart Replit dan jalankan kembali workflow "BotAlwaysOn"
4. Pastikan bot tidak mengalami error saat berjalan (lihat log)

## Catatan Penting

- Fitur "Always On" membutuhkan akun Replit premium/hacker plan
- Bot mungkin akan restart setiap 24 jam karena kebijakan Replit
- Pastikan semua environment variables (token Telegram, dll) sudah dikonfigurasi dengan benar

Jika mengalami masalah, hubungi kami untuk bantuan lebih lanjut.