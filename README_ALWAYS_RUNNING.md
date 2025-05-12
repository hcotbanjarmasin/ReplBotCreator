# Panduan Menjaga Bot Telegram Berjalan di Replit

Agar bot Telegram ODP tetap berjalan meskipun tab Replit ditutup, ikuti langkah-langkah berikut:

## 1. Mengaktifkan Fitur "Always On" Replit

Replit menyediakan fitur berbayar bernama "Always On" yang memungkinkan aplikasi tetap berjalan:

1. Dari dashboard Replit, klik project Anda
2. Klik menu settings (⚙️)
3. Scroll ke bawah hingga Anda menemukan bagian "Always On"
4. Aktifkan tombol "Always On"

Anda memerlukan langganan Replit Hacker/Pro untuk menggunakan fitur ini.

## 2. Menggunakan Script Keep-Alive

Kami telah membuat script khusus yang bisa memastikan bot tetap berjalan:

1. Script `keep_bot_alive.py` yang telah dibuat akan otomatis me-restart bot jika terjadi crash
2. Script ini juga melakukan ping ke URL Replit secara berkala untuk mencegah server tertidur
3. Gunakan workflow "BotAlwaysOn" untuk menjalankan script ini

## 3. Deploy Bot

Untuk deploy bot sehingga tetap berjalan di server Replit:

1. Pastikan Anda sudah mengaktifkan fitur "Always On" (bila berlangganan)
2. Jalankan workflow "BotAlwaysOn" dari panel Replit
3. Verifikasi bahwa bot berjalan dengan mengirim pesan ke bot Anda di Telegram

## 4. Memulai Ulang Bot

Jika bot berhenti bekerja, Anda bisa memulainya kembali dengan cara:

1. Buka project Replit Anda
2. Klik tombol ▶️ Run
3. Pilih workflow "BotAlwaysOn" dari dropdown
4. Bot akan dimulai ulang dan tetap berjalan di latar belakang

## 5. Konfigurasi Tambahan

Bot ini dirancang untuk tetap berjalan meskipun terjadi error:

- Script akan otomatis memulai ulang bot jika crash
- Menggunakan penanganan error yang kuat
- Polling infinity dengan parameter `none_stop=True`
- Keep-alive thread yang melakukan ping ke server Replit secara berkala

## Pemecahan Masalah

Jika bot masih berhenti bekerja setelah tab ditutup:

1. Pastikan Anda sudah mengaktifkan "Always On" (jika memiliki langganan)
2. Periksa log error di file `bot_keep_alive.log`
3. Pastikan tidak ada error di script bot utama

Jika mengalami kesulitan, hubungi kami untuk bantuan lebih lanjut.