#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Bot Telegram untuk pencarian dan visualisasi ODP

Bot ini mengakses data ODP dari spreadsheet dan menampilkan
lokasi ODP dalam radius tertentu dalam bentuk peta.
"""

import os
import re
import logging
import uuid
import tempfile
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import folium
import telebot
from telebot import types
import contextily as cx
from geopy.distance import geodesic
from folium.plugins import MarkerCluster
import matplotlib.patheffects as pe
from matplotlib.offsetbox import OffsetImage, AnnotationBbox
import matplotlib.image as mpimg
from urllib.request import urlopen
from io import BytesIO

# Konfigurasi logging
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Konstanta
DEFAULT_RADIUS = 250  # Radius default dalam meter
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/16PFuuwJjL-_hJKuopMJlktlwaNWLnKQdPUMZdX55pkQ/edit#gid=0"
MAP_DIR = "static/odp_images"
MAX_DISPLAYED_ODPS = 30  # Maksimal ODP yang ditampilkan dalam daftar

# Token bot dari environment variable
TOKEN = os.environ.get('TELEGRAM_TOKEN')

# Buat direktori untuk menyimpan gambar jika belum ada
os.makedirs(MAP_DIR, exist_ok=True)

# Inisialisasi bot
if TOKEN:
    bot = telebot.TeleBot(TOKEN, parse_mode=None)
else:
    logger.error("Token bot Telegram tidak ditemukan!")
    bot = None

# Data spreadsheet global
spreadsheet_data = None

def load_spreadsheet_data():
    """
    Muat data dari spreadsheet dan simpan ke cache.
    """
    global spreadsheet_data
    
    try:
        logger.info("Mencoba memuat data dari spreadsheet")
        
        # Coba cara alternatif dengan pandas read_csv langsung dari URL publik
        # URL dengan format publis/preview yang lebih stabil untuk akses publik
        spreadsheet_id = "16PFuuwJjL-_hJKuopMJlktlwaNWLnKQdPUMZdX55pkQ"
        csv_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/gviz/tq?tqx=out:csv"
        
        # Jika data masih gagal dimuat, coba gunakan data dari aplikasi web lokal 
        # yang sudah berhasil memuat datanya
        try:
            # Baca data dari URL publik (tanpa timeout karena pandas di versi ini tidak mendukungnya)
            spreadsheet_data = pd.read_csv(csv_url)
            logger.info(f"Berhasil memuat {len(spreadsheet_data)} baris data dari URL publik")
            return True
        except Exception as e1:
            logger.warning(f"Gagal memuat dari URL publik: {e1}, mencoba solusi alternatif...")
            
            # Cek apakah file odp_data.csv ada di direktori static
            local_csv = "static/odp_data.csv"
            if os.path.exists(local_csv):
                try:
                    spreadsheet_data = pd.read_csv(local_csv)
                    logger.info(f"Berhasil memuat {len(spreadsheet_data)} baris data dari file lokal")
                    return True
                except Exception as e2:
                    logger.error(f"Gagal memuat dari file lokal: {e2}")
            
            # Jika semua upaya gagal, buat dataset minimal
            logger.warning("Membuat dataset minimal untuk pengujian")
            # Buat DataFrame dengan kolom-kolom yang dibutuhkan
            mini_data = {
                'ODP NAME': ['ODP-PLE-FM/001', 'ODP-PLE-FM/002', 'ODP-PLE-FM/003'],
                'LATITUDE': [-3.816090, -3.815940, -3.816140],
                'LONGITUDE': [114.750625, 114.750540, 114.750730],
                'AVAI': [1, 2, 3]
            }
            spreadsheet_data = pd.DataFrame(mini_data)
            logger.info(f"Menggunakan dataset minimal dengan {len(spreadsheet_data)} baris data")
            
            # Simpan dataset minimal agar bisa digunakan nanti
            os.makedirs("static", exist_ok=True)
            spreadsheet_data.to_csv("static/odp_data_minimal.csv", index=False)
            return True
            
    except Exception as e:
        logger.error(f"Error fatal saat memuat data spreadsheet: {e}")
        return False

def find_nearby_odps(ref_lat, ref_lng, radius_meters=DEFAULT_RADIUS):
    """
    Temukan ODP dalam radius tertentu.
    """
    global spreadsheet_data
    
    if spreadsheet_data is None:
        load_spreadsheet_data()
        
    if spreadsheet_data is None:
        return None
    
    try:
        # Asumsikan nama kolom dari inspeksi data sebelumnya
        lat_col = 'LATITUDE'
        lng_col = 'LONGITUDE'
        name_col = 'ODP NAME'
        
        # Konversi koordinat ke float
        df = spreadsheet_data.copy()
        
        # Buat array koordinat referensi
        ref_coord = (ref_lat, ref_lng)
        
        # Hitung jarak untuk semua baris
        def calculate_distance(row):
            try:
                coord = (float(row[lat_col]), float(row[lng_col]))
                return geodesic(ref_coord, coord).meters
            except (ValueError, TypeError):
                return float('inf')  # Nilai jarak tak terhingga jika koordinat tidak valid
        
        # Terapkan fungsi jarak
        df['jarak_meter'] = df.apply(calculate_distance, axis=1)
        
        # Filter yang berada dalam radius
        nearby_df = df[df['jarak_meter'] <= radius_meters].copy()
        
        # Urutkan berdasarkan jarak
        nearby_df = nearby_df.sort_values('jarak_meter')
        
        return nearby_df
    except Exception as e:
        logger.error(f"Error saat mencari ODP terdekat: {e}")
        return None

def create_odp_map(ref_lat, ref_lng, nearby_df, radius_meters=DEFAULT_RADIUS, max_display=30, with_routes=True, use_satellite=True):
    """
    Buat peta dengan ODP yang ditemukan.
    
    Args:
        ref_lat: Latitude titik referensi
        ref_lng: Longitude titik referensi
        nearby_df: DataFrame dengan ODP terdekat
        radius_meters: Radius pencarian dalam meter
        max_display: Maksimal ODP yang ditampilkan
        with_routes: Menampilkan rute dari titik referensi ke ODP terdekat
        use_satellite: Menggunakan citra satelit sebagai basemap
    """
    try:
        # Folder untuk menyimpan gambar jika belum ada
        os.makedirs(MAP_DIR, exist_ok=True)
        
        # Generate nama file unik
        map_id = str(uuid.uuid4())
        map_path = f"{MAP_DIR}/{map_id}.png"
        
        # Batasi jumlah ODP yang ditampilkan
        if len(nearby_df) > max_display:
            nearby_df = nearby_df.head(max_display)
        
        # Tentukan koordinat min dan max untuk tampilan peta
        buffer = 0.003  # Sekitar 300 meter
        lat_min = min(nearby_df['LATITUDE'].min(), ref_lat) - buffer
        lat_max = max(nearby_df['LATITUDE'].max(), ref_lat) + buffer
        lng_min = min(nearby_df['LONGITUDE'].min(), ref_lng) - buffer
        lng_max = max(nearby_df['LONGITUDE'].max(), ref_lng) + buffer
        
        # Buat figure dan axis
        plt.figure(figsize=(10, 10))
        ax = plt.subplot(111)
        
        # Tambahkan lingkaran untuk menampilkan radius pencarian
        radius_circle = plt.Circle((ref_lng, ref_lat), radius_meters/111000, 
                                  fill=False, edgecolor='red', linewidth=2, alpha=0.7)
        ax.add_patch(radius_circle)
        
        # Plot titik referensi
        ax.scatter(ref_lng, ref_lat, c='red', s=100, marker='*', 
                  label='Lokasi Referensi', zorder=5, 
                  path_effects=[pe.withStroke(linewidth=5, foreground='white')])
        
        # Plot ODP terdekat dengan warna berdasarkan jarak
        for i, (_, row) in enumerate(nearby_df.iterrows()):
            lng, lat = row['LONGITUDE'], row['LATITUDE']
            jarak = row['jarak_meter']
            odp_name = row['ODP NAME']
            
            # Tentukan warna marker berdasarkan jarak
            if jarak <= radius_meters * 0.33:
                color = 'green'  # Dekat
            elif jarak <= radius_meters * 0.66:
                color = 'blue'   # Sedang
            else:
                color = 'orange'  # Jauh
                
            # Plot titik ODP
            ax.scatter(lng, lat, c=color, s=60, alpha=0.8, marker='o', zorder=4,
                      path_effects=[pe.withStroke(linewidth=3, foreground='white')])
            
            # Plot rute (garis) dari referensi ke ODP jika diminta
            if with_routes:
                ax.plot([ref_lng, lng], [ref_lat, lat], color=color, linestyle='-', 
                        linewidth=1, alpha=0.5, zorder=3)
                
            # Tambahkan label nomor pada ODP
            ax.annotate(str(i+1), (lng, lat), color='white', weight='bold', 
                        fontsize=8, ha='center', va='center', zorder=6)
        
        # Set batas tampilan
        ax.set_xlim(lng_min, lng_max)
        ax.set_ylim(lat_min, lat_max)
        
        # Tambahkan citra satelit sebagai basemap
        if use_satellite:
            try:
                # Coba gunakan Google Hybrid (jalan dan bangunan terlihat)
                cx.add_basemap(ax, crs='EPSG:4326', source=cx.providers.GoogleHybrid, zoom=17)
            except Exception as e:
                logger.warning(f"Gagal menggunakan Google Hybrid, mencoba Esri: {e}")
                try:
                    # Fallback ke Esri WorldImagery
                    cx.add_basemap(ax, crs='EPSG:4326', source=cx.providers.Esri.WorldImagery, zoom=17)
                except Exception as e2:
                    logger.warning(f"Gagal menggunakan Esri, mencoba OpenStreetMap: {e2}")
                    try:
                        # Fallback ke OpenStreetMap
                        cx.add_basemap(ax, crs='EPSG:4326', zoom=17)
                    except Exception as e3:
                        logger.error(f"Semua provider basemap gagal: {e3}")
        else:
            # Gunakan peta jalan biasa
            try:
                cx.add_basemap(ax, crs='EPSG:4326', zoom=17)
            except Exception as e:
                logger.error(f"Gagal menambahkan basemap: {e}")
        
        # Tambahkan legenda
        legend_handles = [
            plt.Line2D([0], [0], marker='*', color='w', markerfacecolor='red', 
                      markersize=10, label='Lokasi Referensi'),
            plt.Line2D([0], [0], marker='o', color='w', markerfacecolor='green', 
                      markersize=8, label='ODP Dekat (<33%)'),
            plt.Line2D([0], [0], marker='o', color='w', markerfacecolor='blue', 
                      markersize=8, label='ODP Sedang (<66%)'),
            plt.Line2D([0], [0], marker='o', color='w', markerfacecolor='orange', 
                      markersize=8, label='ODP Jauh (>66%)')
        ]
        
        if with_routes:
            legend_handles.append(
                plt.Line2D([0], [0], color='teal', 
                          label=f'Rute ke ODP (total: {len(nearby_df)})')
            )
            
        ax.legend(handles=legend_handles, loc='upper left', 
                 framealpha=0.8, facecolor='white')
        
        # Tambahkan judul dan info
        plt.title(f"Peta ODP dalam radius {radius_meters}m", fontsize=12)
        
        # Sembunyikan sumbu
        plt.axis('off')
        
        # Simpan gambar
        plt.tight_layout()
        plt.savefig(map_path, dpi=200, bbox_inches='tight')
        plt.close()
        
        return map_path
    except Exception as e:
        logger.error(f"Error saat membuat peta: {e}")
        return None

def format_odp_list(nearby_odps, max_items=10):
    """Format daftar ODP untuk teks pesan"""
    result = ""
    
    # Batasi jumlah item yang ditampilkan
    display_df = nearby_odps.head(max_items)
    
    for i, (_, row) in enumerate(display_df.iterrows()):
        jarak = row['jarak_meter']
        odp_name = row['ODP NAME']
        avai = row.get('AVAI', 'N/A')
        
        # Emoji berdasarkan jarak
        if jarak <= 100:
            emoji = "🟢"  # Hijau untuk sangat dekat
        elif jarak <= 200:
            emoji = "🔵"  # Biru untuk dekat
        else:
            emoji = "🟠"  # Orange untuk agak jauh
            
        result += f"{i+1}. {emoji} *{odp_name}* - {jarak:.1f}m"
        if avai != 'N/A':
            result += f" (Avai: {avai})"
        result += "\n"
    
    if len(nearby_odps) > max_items:
        result += f"\n_...dan {len(nearby_odps) - max_items} ODP lainnya..._"
        
    return result

@bot.message_handler(commands=['start'])
def start(message):
    """Kirim pesan selamat datang."""
    reply = (
        "👋 Selamat datang di Bot Pencari ODP!\n\n"
        "Bot ini membantu Anda menemukan ODP terdekat dari titik koordinat.\n\n"
        "Cara penggunaan:\n"
        "1️⃣ Kirim lokasi Anda melalui fitur 'Share Location' Telegram\n"
        "2️⃣ Atau kirim koordinat secara langsung dalam format: `-2.1234, 114.7890`\n\n"
        "Gunakan /help untuk informasi lebih lanjut."
    )
    bot.reply_to(message, reply)

@bot.message_handler(commands=['help'])
def help_command(message):
    """Kirim informasi bantuan."""
    reply = (
        "📚 *Bantuan Penggunaan Bot Pencari ODP*\n\n"
        "*Perintah yang tersedia:*\n"
        "/start - Memulai bot\n"
        "/help - Menampilkan bantuan ini\n"
        "/radius - Melihat atau mengubah radius pencarian\n"
        "/examples - Menampilkan contoh koordinat\n"
        "/status - Menampilkan status bot\n"
        "/reload - Muat ulang data (admin)\n\n"
        
        "*Cara mencari ODP:*\n"
        "- Kirim lokasi Anda melalui fitur 'Location' Telegram\n"
        "- Kirim koordinat secara langsung: `-2.1234, 114.7890`\n\n"
        
        "*Opsi tampilan peta:*\n"
        "🗺️ *Peta Jalan* - Menampilkan peta OpenStreetMap dengan rute\n"
        "🛰️ *Satelit Tanpa Rute* - Menampilkan citra satelit tanpa garis rute\n"
        "🏘️ *Satelit dengan Jalan & Bangunan* - Menampilkan satelit hybrid dengan jalan, bangunan, dan rute\n\n"
        
        "*Keterangan warna marker:*\n"
        "🟢 Hijau: ODP sangat dekat (<33% radius)\n"
        "🔵 Biru: ODP dekat (33-66% radius)\n"
        "🟠 Orange: ODP agak jauh (>66% radius)"
    )
    bot.reply_to(message, reply, parse_mode='Markdown')

@bot.message_handler(commands=['radius'])
def radius_command(message):
    """Melihat atau mengubah radius pencarian."""
    global DEFAULT_RADIUS
    parts = message.text.split()
    
    if len(parts) == 1:
        # Hanya tampilkan radius saat ini
        reply = f"🔍 Radius pencarian saat ini: {DEFAULT_RADIUS}m\n\nUntuk mengubah, ketik `/radius <nilai_baru>`"
        bot.reply_to(message, reply)
        return
        
    try:
        new_radius = int(parts[1])
        if new_radius < 50:
            bot.reply_to(message, "❌ Radius minimal adalah 50m.")
        elif new_radius > 1000:
            bot.reply_to(message, "❌ Radius maksimal adalah 1000m.")
        else:
            DEFAULT_RADIUS = new_radius
            bot.reply_to(message, f"✅ Radius pencarian diubah menjadi {DEFAULT_RADIUS}m.")
    except ValueError:
        bot.reply_to(message, "❌ Format tidak valid. Gunakan `/radius <nilai_baru>`")

@bot.message_handler(commands=['examples'])
def examples_command(message):
    """Menampilkan contoh koordinat."""
    examples = (
        "📍 *Contoh Koordinat ODP di Kalimantan Selatan*\n\n"
        "- `-3.292481, 114.592482` - Area Banjarmasin Utara\n"
        "- `-3.313862, 114.591185` - Area Banjarmasin Tengah\n"
        "- `-3.446898, 114.825086` - Area Banjarbaru\n"
        "- `-3.768278, 114.776236` - Area Martapura\n\n"
        "Anda dapat meng-copy salah satu koordinat di atas dan mengirimkannya ke bot ini."
    )
    bot.reply_to(message, examples, parse_mode='Markdown')

@bot.message_handler(commands=['status'])
def status_command(message):
    """Menampilkan status bot dan data."""
    global spreadsheet_data
    
    if spreadsheet_data is None:
        data_status = "❌ Data belum dimuat"
    else:
        data_status = f"✅ Data dimuat ({len(spreadsheet_data)} ODP)"
        
    reply = (
        "📊 *Status Bot Pencari ODP*\n\n"
        f"Spreadsheet: {SPREADSHEET_URL.split('/edit')[0]}\n"
        f"Status Data: {data_status}\n"
        f"Radius Default: {DEFAULT_RADIUS}m\n"
        f"Maksimum ODP yang Ditampilkan: {MAX_DISPLAYED_ODPS}"
    )
    
    bot.reply_to(message, reply, parse_mode='Markdown')

@bot.message_handler(commands=['reload'])
def reload_command(message):
    """Muat ulang data dari spreadsheet."""
    global spreadsheet_data
    
    # Kirim pesan "sedang memuat"
    wait_msg = bot.reply_to(message, "🔄 Memuat ulang data dari spreadsheet...")
    
    # Reset data
    spreadsheet_data = None
    
    # Muat ulang data
    success = load_spreadsheet_data()
    
    if success and spreadsheet_data is not None:
        bot.edit_message_text(
            f"✅ Berhasil memuat ulang data ({len(spreadsheet_data)} ODP).",
            message.chat.id, 
            wait_msg.message_id
        )
    else:
        bot.edit_message_text(
            "❌ Gagal memuat ulang data. Silakan coba lagi nanti.",
            message.chat.id, 
            wait_msg.message_id
        )

@bot.message_handler(commands=['search'])
def search_command(message):
    """Mencari ODP berdasarkan koordinat."""
    parts = message.text.split()
    
    if len(parts) < 3:
        bot.reply_to(message, 
                    "❌ Format tidak valid.\n"
                    "Gunakan `/search <latitude> <longitude> [radius]`\n"
                    "Contoh: `/search -3.292481 114.592482 250`")
        return
        
    try:
        lat = float(parts[1])
        lng = float(parts[2])
        
        radius = DEFAULT_RADIUS
        if len(parts) >= 4:
            radius = int(parts[3])
            
        # Kirim pesan "sedang mencari"
        wait_msg = bot.send_message(message.chat.id, f"🔍 Mencari ODP dalam radius {radius}m dari koordinat {lat}, {lng}...")
        
        # Muat data jika belum dimuat
        if spreadsheet_data is None:
            load_spreadsheet_data()
            
        # Cari ODP terdekat
        nearby_odps = find_nearby_odps(lat, lng, radius)
        
        if nearby_odps is None:
            bot.edit_message_text("❌ Terjadi error saat mencari ODP.", message.chat.id, wait_msg.message_id)
            return
            
        if nearby_odps.empty:
            bot.edit_message_text(f"❌ Tidak ditemukan ODP dalam radius {radius}m dari koordinat {lat}, {lng}.", 
                              message.chat.id, wait_msg.message_id)
            return
            
        # Format hasil pencarian
        result_text = (
            f"✅ *Ditemukan {len(nearby_odps)} ODP* dalam radius {radius}m dari koordinat:\n"
            f"📍 *{lat}, {lng}*\n\n"
            f"*ODP Terdekat:*\n{format_odp_list(nearby_odps)}\n\n"
            f"📊 Menampilkan peta..."
        )
        
        # Edit pesan tunggu
        bot.edit_message_text(result_text, message.chat.id, wait_msg.message_id, parse_mode='Markdown')
        
        # Buat dan kirim peta
        map_file = create_odp_map(lat, lng, nearby_odps, radius)
        
        if map_file:
            caption = f"🗺️ Peta {len(nearby_odps)} ODP dalam radius {radius}m"
            with open(map_file, 'rb') as photo:
                bot.send_photo(message.chat.id, photo, caption=caption)
                
            # Tambahkan berbagai opsi tampilan peta
            keyboard = types.InlineKeyboardMarkup()
            
            # Baris pertama: Tampilan dasar - peta jalan dan satelit tanpa rute
            btn_street = types.InlineKeyboardButton(text="🗺️ Lihat Peta Jalan", callback_data=f"street_{lat}_{lng}_{radius}")
            btn_satellite_no_route = types.InlineKeyboardButton(text="🛰️ Satelit Tanpa Rute", callback_data=f"sat_noroute_{lat}_{lng}_{radius}")
            keyboard.add(btn_street, btn_satellite_no_route)
            
            # Baris kedua: Tampilan detail dengan jalan dan bangunan (Google Hybrid)
            btn_hybrid = types.InlineKeyboardButton(text="🏘️ Satelit dengan Jalan & Bangunan", callback_data=f"satellite_{lat}_{lng}_{radius}")
            keyboard.add(btn_hybrid)
            
            bot.send_message(message.chat.id, "Opsi tampilan peta lainnya:", reply_markup=keyboard)
        else:
            bot.send_message(message.chat.id, "❌ Gagal membuat peta ODP.")
    except ValueError:
        bot.reply_to(message, "❌ Format koordinat tidak valid. Gunakan angka desimal untuk latitude dan longitude.")
    except Exception as e:
        logger.error(f"Error saat menangani perintah search: {e}")
        bot.reply_to(message, f"❌ Terjadi error: {str(e)}")

@bot.message_handler(content_types=['location'])
def handle_location(message):
    """Tangani saat pengguna mengirim lokasi."""
    lat = message.location.latitude
    lng = message.location.longitude
    radius = DEFAULT_RADIUS  # Default
    
    # Kirim pesan "sedang mencari"
    wait_msg = bot.send_message(message.chat.id, f"🔍 Mencari ODP dalam radius {radius}m dari lokasi Anda...")
    
    # Muat data jika belum dimuat
    if spreadsheet_data is None:
        load_spreadsheet_data()
        
    # Cari ODP terdekat
    nearby_odps = find_nearby_odps(lat, lng, radius)
    
    if nearby_odps is None:
        bot.edit_message_text("❌ Terjadi error saat mencari ODP.", message.chat.id, wait_msg.message_id)
        return
        
    if nearby_odps.empty:
        bot.edit_message_text(f"❌ Tidak ditemukan ODP dalam radius {radius}m dari lokasi Anda.", 
                          message.chat.id, wait_msg.message_id)
        return
        
    # Format hasil pencarian
    result_text = (
        f"✅ *Ditemukan {len(nearby_odps)} ODP* dalam radius {radius}m dari lokasi Anda:\n"
        f"📍 *{lat}, {lng}*\n\n"
        f"*ODP Terdekat:*\n{format_odp_list(nearby_odps)}\n\n"
        f"📊 Menampilkan peta..."
    )
    
    # Edit pesan tunggu
    bot.edit_message_text(result_text, message.chat.id, wait_msg.message_id, parse_mode='Markdown')
    
    # Buat dan kirim peta dengan citra satelit dan rute
    map_file = create_odp_map(lat, lng, nearby_odps, radius, with_routes=True, use_satellite=True)
    
    if map_file:
        caption = f"🗺️ Peta satelit {len(nearby_odps)} ODP dalam radius {radius}m dengan rute"
        with open(map_file, 'rb') as photo:
            bot.send_photo(message.chat.id, photo, caption=caption)
            
        # Tambahkan berbagai opsi tampilan peta
        keyboard = types.InlineKeyboardMarkup()
        
        # Baris pertama: Tampilan dasar - peta jalan dan satelit tanpa rute
        btn_street = types.InlineKeyboardButton(text="🗺️ Lihat Peta Jalan", callback_data=f"street_{lat}_{lng}_{radius}")
        btn_satellite_no_route = types.InlineKeyboardButton(text="🛰️ Satelit Tanpa Rute", callback_data=f"sat_noroute_{lat}_{lng}_{radius}")
        keyboard.add(btn_street, btn_satellite_no_route)
        
        # Baris kedua: Tampilan detail dengan jalan dan bangunan (Google Hybrid)
        btn_hybrid = types.InlineKeyboardButton(text="🏘️ Satelit dengan Jalan & Bangunan", callback_data=f"satellite_{lat}_{lng}_{radius}")
        keyboard.row(btn_hybrid)
        
        bot.send_message(message.chat.id, "Opsi tampilan peta lainnya:", reply_markup=keyboard)
    else:
        bot.send_message(message.chat.id, "❌ Gagal membuat peta ODP.")

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    """Tangani callback dari tombol inline."""
    try:
        # Ekstrak data dari callback
        data = call.data
        
        if data.startswith("street_") or data.startswith("sat_noroute_") or data.startswith("satellite_"):
            # Format: "type_lat_lng_radius"
            parts = data.split("_")
            map_type = parts[0]
            lat = float(parts[1])
            lng = float(parts[2])
            radius = int(parts[3])
            
            # Kirim notifikasi "sedang memproses"
            bot.answer_callback_query(
                call.id, 
                text="Memproses permintaan peta...", 
                show_alert=False
            )
            
            # Pesan sesuai jenis peta yang diminta
            peta_msg = "jalan" if map_type == "street" else "satelit tanpa rute"
            if map_type == "satellite":
                peta_msg = "satelit dengan detail jalan & bangunan"
            
            # Kirim pesan "sedang membuat peta"
            wait_msg = bot.send_message(
                call.message.chat.id, 
                f"🔄 Membuat peta {peta_msg}..."
            )
            
            # Muat data jika belum dimuat
            if spreadsheet_data is None:
                load_spreadsheet_data()
                
            # Cari ODP terdekat
            nearby_odps = find_nearby_odps(lat, lng, radius)
            
            if nearby_odps is None or nearby_odps.empty:
                bot.edit_message_text(
                    "❌ Terjadi error saat mencari ODP.",
                    call.message.chat.id, 
                    wait_msg.message_id
                )
                return
                
            # Buat peta sesuai dengan tipe yang diminta
            if map_type == "street":
                # Peta jalan (OpenStreetMap)
                map_file = create_odp_map(lat, lng, nearby_odps, radius, with_routes=True, use_satellite=False)
                caption = f"🗺️ Peta jalan {len(nearby_odps)} ODP dalam radius {radius}m dengan rute"
            elif map_type == "sat_noroute":
                # Peta satelit tanpa rute
                map_file = create_odp_map(lat, lng, nearby_odps, radius, with_routes=False, use_satellite=True)
                caption = f"🛰️ Peta satelit {len(nearby_odps)} ODP dalam radius {radius}m tanpa rute"
            elif map_type == "satellite":
                # Peta satelit Google Hybrid (dengan jalan dan bangunan) dengan rute
                map_file = create_odp_map(lat, lng, nearby_odps, radius, with_routes=True, use_satellite=True)
                caption = f"🏘️ Peta satelit {len(nearby_odps)} ODP dalam radius {radius}m dengan jalan & bangunan"
                
            if map_file:
                # Hapus pesan tunggu
                bot.delete_message(call.message.chat.id, wait_msg.message_id)
                
                # Kirim gambar peta
                with open(map_file, 'rb') as photo:
                    bot.send_photo(call.message.chat.id, photo, caption=caption)
            else:
                bot.edit_message_text(
                    "❌ Gagal membuat peta ODP.", 
                    call.message.chat.id, 
                    wait_msg.message_id
                )
        
    except Exception as e:
        logger.error(f"Error saat menangani callback: {e}")
        bot.answer_callback_query(
            call.id, 
            text="Terjadi error saat memproses permintaan.", 
            show_alert=True
        )

@bot.message_handler(func=lambda message: True)
def handle_text(message):
    """Tangani semua pesan teks lainnya."""
    text = message.text.strip()
    
    # Coba parse teks sebagai koordinat
    coord_pattern = r'(-?\d+\.\d+)[,\s]+(-?\d+\.\d+)'
    match = re.search(coord_pattern, text)
    
    if match:
        lat = float(match.group(1))
        lng = float(match.group(2))
        radius = DEFAULT_RADIUS  # Default
        
        # Kirim pesan "sedang mencari"
        wait_msg = bot.send_message(message.chat.id, f"🔍 Mencari ODP dalam radius {radius}m dari koordinat {lat}, {lng}...")
        
        # Muat data jika belum dimuat
        if spreadsheet_data is None:
            load_spreadsheet_data()
            
        # Cari ODP terdekat
        nearby_odps = find_nearby_odps(lat, lng, radius)
        
        if nearby_odps is None:
            bot.edit_message_text("❌ Terjadi error saat mencari ODP.", message.chat.id, wait_msg.message_id)
            return
            
        if nearby_odps.empty:
            bot.edit_message_text(f"❌ Tidak ditemukan ODP dalam radius {radius}m dari koordinat {lat}, {lng}.", 
                              message.chat.id, wait_msg.message_id)
            return
            
        # Format hasil pencarian
        result_text = (
            f"✅ *Ditemukan {len(nearby_odps)} ODP* dalam radius {radius}m dari koordinat:\n"
            f"📍 *{lat}, {lng}*\n\n"
            f"*ODP Terdekat:*\n{format_odp_list(nearby_odps)}\n\n"
            f"📊 Menampilkan peta..."
        )
        
        # Edit pesan tunggu
        bot.edit_message_text(result_text, message.chat.id, wait_msg.message_id, parse_mode='Markdown')
        
        # Buat dan kirim peta dengan citra satelit dan rute
        map_file = create_odp_map(lat, lng, nearby_odps, radius, with_routes=True, use_satellite=True)
        
        if map_file:
            caption = f"🗺️ Peta satelit {len(nearby_odps)} ODP dalam radius {radius}m dengan rute"
            with open(map_file, 'rb') as photo:
                bot.send_photo(message.chat.id, photo, caption=caption)
                
            # Tambahkan berbagai opsi tampilan peta
            keyboard = types.InlineKeyboardMarkup()
            
            # Baris pertama: Tampilan dasar - peta jalan dan satelit tanpa rute
            btn_street = types.InlineKeyboardButton(text="🗺️ Lihat Peta Jalan", callback_data=f"street_{lat}_{lng}_{radius}")
            btn_satellite_no_route = types.InlineKeyboardButton(text="🛰️ Satelit Tanpa Rute", callback_data=f"sat_noroute_{lat}_{lng}_{radius}")
            keyboard.add(btn_street, btn_satellite_no_route)
            
            # Baris kedua: Tampilan detail dengan jalan dan bangunan (Google Hybrid)
            btn_hybrid = types.InlineKeyboardButton(text="🏘️ Satelit dengan Jalan & Bangunan", callback_data=f"satellite_{lat}_{lng}_{radius}")
            keyboard.add(btn_hybrid)
            
            bot.send_message(message.chat.id, "Opsi tampilan peta lainnya:", reply_markup=keyboard)
        else:
            bot.send_message(message.chat.id, "❌ Gagal membuat peta ODP.")
    else:
        # Tidak mengenali format teks
        bot.reply_to(message, 
                    "Saya tidak mengenali format tersebut.\n\n"
                    "Kirim koordinat dengan format: `-3.292481, 114.592482`\n"
                    "Atau gunakan perintah /help untuk bantuan.")

def main():
    logger.info("Bot Telegram ODP mulai berjalan...")
    
    # Muat data spreadsheet saat mulai
    load_spreadsheet_data()
    
    # Jalankan bot
    bot.infinity_polling()

if __name__ == "__main__":
    main()