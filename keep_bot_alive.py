#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Script untuk menjaga bot Telegram tetap berjalan di Replit

Script ini dapat dijalankan oleh Replit sebagai titik masuk utama
untuk menjaga bot tetap berjalan bahkan ketika Replit ditutup.

Gunakan untuk deployment. Saat Replit ditutup, script ini akan
tetap berjalan di latar belakang dan menjaga bot Telegram aktif.
"""

import os
import time
import signal
import subprocess
import sys
import logging
import threading
import requests

# Konfigurasi logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("bot_keep_alive.log")
    ]
)

logger = logging.getLogger("KeepAliveBot")

# URL untuk ping diri sendiri agar tetap hidup (jika menggunakan Replit)
REPLIT_URL = os.environ.get("REPLIT_SLUG", "")
if REPLIT_URL:
    PING_URL = f"https://{REPLIT_URL}.replit.app"
else:
    PING_URL = None
    
# Interval ping dalam detik
PING_INTERVAL = 300  # 5 menit

def keep_alive():
    """Fungsi untuk ping URL Replit secara berkala agar tetap aktif."""
    if not PING_URL:
        logger.info("Tidak ada URL yang dikonfigurasi untuk ping, melewati...")
        return
        
    logger.info(f"Mulai ping ke {PING_URL} setiap {PING_INTERVAL} detik")
    
    while True:
        try:
            response = requests.get(PING_URL)
            logger.info(f"Ping berhasil: {response.status_code}")
        except Exception as e:
            logger.error(f"Gagal melakukan ping: {e}")
        
        time.sleep(PING_INTERVAL)

def run_bot():
    """Jalankan bot dan pastikan tetap berjalan."""
    logger.info("Menjalankan Bot Telegram ODP...")
    
    # Jalankan thread ping untuk menjaga Replit tetap hidup
    if PING_URL:
        ping_thread = threading.Thread(target=keep_alive, daemon=True)
        ping_thread.start()
        logger.info("Thread keep-alive mulai berjalan")
    
    # Jalankan bot dengan subprocess
    bot_process = subprocess.Popen(
        ["python", "odp_telegram_bot_enhanced.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True
    )
    
    # Tangani sinyal untuk menghentikan bot dengan rapi
    def handle_exit(signum, frame):
        logger.info("Menerima sinyal untuk keluar, menghentikan bot dengan rapi...")
        bot_process.terminate()
        try:
            bot_process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            bot_process.kill()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, handle_exit)
    signal.signal(signal.SIGTERM, handle_exit)
    
    # Monitor output bot
    try:
        while True:
            output = bot_process.stdout.readline()
            if output:
                print(output.strip())
            
            # Periksa apakah bot masih berjalan
            if bot_process.poll() is not None:
                logger.warning(f"Bot berhenti dengan kode: {bot_process.returncode}")
                logger.info("Memulai ulang bot dalam 5 detik...")
                time.sleep(5)
                return run_bot()  # Mulai ulang bot jika berhenti
            
            time.sleep(0.1)
    except Exception as e:
        logger.error(f"Error saat menjalankan bot: {e}")
        logger.info("Memulai ulang bot dalam 5 detik...")
        time.sleep(5)
        return run_bot()

if __name__ == "__main__":
    # Pastikan direktori kerja berada di lokasi script
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    run_bot()
