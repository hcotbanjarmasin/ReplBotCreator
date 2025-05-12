#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Server Flask sederhana untuk menjaga bot Telegram tetap berjalan di Replit.
Server ini bisa diakses oleh UptimeRobot untuk memastikan aplikasi tetap aktif.
"""

import os
import time
import signal
import logging
import subprocess
import threading
import requests
from flask import Flask, jsonify

# Konfigurasi logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("bot_keep_alive.log")
    ]
)

logger = logging.getLogger("KeepAliveServer")

# Inisialisasi Flask
app = Flask(__name__)
bot_process = None
bot_running = False

def run_bot_process():
    """Jalankan bot Telegram dalam proses terpisah."""
    global bot_process, bot_running
    
    if bot_running and bot_process and bot_process.poll() is None:
        logger.info("Bot sudah berjalan, tidak perlu memulai lagi")
        return
    
    logger.info("Menjalankan Bot Telegram ODP...")
    bot_process = subprocess.Popen(
        ["python", "odp_telegram_bot_enhanced.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True
    )
    bot_running = True
    
    # Thread untuk membaca output bot
    def monitor_output():
        while True:
            if not bot_process or bot_process.poll() is not None:
                break
                
            output = bot_process.stdout.readline()
            if output:
                print(f"[BOT] {output.strip()}")
            
            time.sleep(0.1)
    
    # Thread untuk memeriksa status bot
    def monitor_status():
        global bot_process, bot_running
        
        while True:
            if not bot_process:
                break
                
            # Periksa apakah bot masih berjalan
            if bot_process.poll() is not None:
                logger.warning(f"Bot berhenti dengan kode: {bot_process.returncode}")
                logger.info("Memulai ulang bot dalam 5 detik...")
                bot_running = False
                time.sleep(5)
                run_bot_process()
                break
            
            time.sleep(2)
    
    output_thread = threading.Thread(target=monitor_output, daemon=True)
    status_thread = threading.Thread(target=monitor_status, daemon=True)
    
    output_thread.start()
    status_thread.start()

# Jalankan bot saat server dimulai
@app.route('/init', methods=['GET'])
def init_bot():
    """Jalankan bot pada request pertama."""
    run_bot_process()
    return jsonify({
        "status": "initialized",
        "message": "Bot telah diinisialisasi"
    })

# Route untuk memeriksa status bot
@app.route('/')
def index():
    """Endpoint utama untuk memeriksa status bot."""
    global bot_process, bot_running
    
    status = "running" if bot_running and bot_process and bot_process.poll() is None else "stopped"
    
    if status == "stopped" and not bot_running:
        run_bot_process()
        status = "starting"
    
    return jsonify({
        "status": status,
        "bot": "ODP Telegram Bot",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    })

# Route untuk memulai bot (jika belum berjalan)
# Endpoint ping sudah didefinisikan di bawah

@app.route('/start')
def start():
    """Endpoint untuk memulai bot jika belum berjalan."""
    global bot_process, bot_running
    
    if bot_running and bot_process and bot_process.poll() is None:
        return jsonify({
            "status": "already_running",
            "message": "Bot sudah berjalan"
        })
    
    run_bot_process()
    return jsonify({
        "status": "starting",
        "message": "Bot sedang dimulai"
    })

# Route untuk memeriksa status secara terperinci
@app.route('/status')
def status():
    """Endpoint untuk memeriksa status bot secara terperinci."""
    global bot_process, bot_running
    
    is_running = bot_running and bot_process and bot_process.poll() is None
    exit_code = bot_process.returncode if bot_process and bot_process.poll() is not None else None
    
    return jsonify({
        "running": is_running,
        "exit_code": exit_code,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    })

# Handler ketika aplikasi dihentikan
def handle_exit(signum, frame):
    """Tangani sinyal untuk menghentikan bot dengan rapi."""
    global bot_process
    
    logger.info("Menerima sinyal untuk keluar, menghentikan bot dengan rapi...")
    
    if bot_process:
        bot_process.terminate()
        try:
            bot_process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            bot_process.kill()
    
    # Hentikan juga server Flask
    os._exit(0)

# Daftarkan handler untuk sinyal
signal.signal(signal.SIGINT, handle_exit)
signal.signal(signal.SIGTERM, handle_exit)

# Jalankan server Flask
if __name__ == "__main__":
    # Jalankan bot terlebih dahulu
    run_bot_process()
    
    # Pastikan thread keep-alive jalan untuk mem-ping diri sendiri
    # Ini akan menjaga server agar tidak idle bahkan tanpa UptimeRobot
    def self_ping_worker():
        """Fungsi untuk memastikan server tetap aktif dengan melakukan ping secara internal."""
        logger.info("Memulai self-ping thread untuk menjaga server tetap aktif")
        while True:
            try:
                # Ping setiap 2 menit (lebih cepat dari UptimeRobot)
                time.sleep(120)
                try:
                    # Ping server lokal agar tetap aktif
                    response = requests.get(f"http://127.0.0.1:{port}/ping")
                    logger.info(f"Self-ping berhasil: {response.status_code}")
                except Exception as e:
                    logger.error(f"Gagal melakukan self-ping: {e}")
                
                # Juga periksa apakah bot masih berjalan
                global bot_process, bot_running
                if bot_process and bot_process.poll() is not None:
                    logger.warning("Bot terdeteksi mati saat self-ping. Memulai ulang...")
                    run_bot_process()
            except Exception as e:
                logger.error(f"Error pada self-ping thread: {e}")
                time.sleep(30)  # Tunggu sebentar jika terjadi error
    
    # Tambahkan route untuk ping
    @app.route('/ping')
    def ping():
        """Endpoint untuk ping."""
        return jsonify({
            "status": "active",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        })
    
    # Jalankan thread self-ping
    self_ping_thread = threading.Thread(target=self_ping_worker, daemon=True)
    self_ping_thread.start()
    
    # Jalankan server Flask pada port 8080
    # Ini akan membuat endpoint yang dapat di-ping oleh UptimeRobot
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)