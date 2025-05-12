import os
import logging
import pandas as pd
import telebot
from telebot import types
from geopy.distance import geodesic
import folium
import tempfile
import re
import uuid
from flask import Flask, send_file, render_template_string, redirect
import threading

# Konfigurasi logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# URL spreadsheet publik (menggunakan ID spreadsheet dan GID worksheet Anda)
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/16PFuuwJjL-_hJKuopMJlktlwaNWLnKQdPUMZdX55pkQ/edit?gid=1933962208"

# Kolom-kolom di spreadsheet (disesuaikan dengan struktur spreadsheet Anda)
LAT_COLUMN = "LATITUDE"
LNG_COLUMN = "LONGITUDE"
NAME_COLUMN = "ODP NAME"
AVAI_COLUMN = "AVAI"

# Jarak radius pencarian dalam meter
DEFAULT_RADIUS = 250

# Port untuk web server
WEB_SERVER_PORT = 8080

# Base URL untuk server (ganti dengan URL publik jika ada)
BASE_URL = f"https://{os.environ.get('REPL_SLUG')}.{os.environ.get('REPL_OWNER')}.repl.co"  # URL Replit otomatis

# Direktori untuk menyimpan file peta
MAPS_DIR = "maps"
os.makedirs(MAPS_DIR, exist_ok=True)

# Inisialisasi Flask app
app = Flask(__name__)

# Dictionary untuk menyimpan informasi peta
maps_info = {}

# Dictionary untuk menyimpan radius pengguna
radius_data = {}

class SpreadsheetHandler:
    def __init__(self, url=None):
        """Inisialisasi handler spreadsheet."""
        self.url = url
        self.data = None
        
    def load_from_url(self, url=None, sheet_name="Sheet1"):
        """
        Muat data dari URL spreadsheet publik Google Sheets.
        
        Args:
            url: URL spreadsheet Google Sheets yang dibagikan secara publik
            sheet_name: Nama worksheet (default: "Sheet1")
            
        Returns:
            DataFrame dengan data dari spreadsheet
        """
        try:
            if url:
                self.url = url
                
            if not self.url:
                logger.error("URL spreadsheet tidak diberikan")
                return None
                
            # Ekstrak ID spreadsheet dari URL
            if "spreadsheets/d/" in self.url:
                parts = self.url.split("spreadsheets/d/")[1]
                spreadsheet_id = parts.split("/")[0]
            else:
                spreadsheet_id = self.url  # Asumsi user memasukkan ID langsung
            
            # Metode 1: Coba dengan nama sheet dulu
            try:
                # Buat URL untuk ekspor CSV dengan nama sheet
                csv_export_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/gviz/tq?tqx=out:csv&sheet={sheet_name}"
                logger.info(f"Mencoba akses dengan nama sheet: {sheet_name}")
                
                # Muat data ke pandas DataFrame
                self.data = pd.read_csv(csv_export_url)
                logger.info(f"Berhasil memuat {len(self.data)} baris data dari sheet {sheet_name}")
                return self.data
            except Exception as e:
                logger.warning(f"Gagal akses dengan nama sheet: {e}")
                
                # Metode 2: Jika gagal, coba dengan GID
                gid = 1933962208  # GID default dari URL
                if "gid=" in self.url:
                    gid_part = self.url.split("gid=")[1]
                    if "#" in gid_part:
                        gid = int(gid_part.split("#")[0])
                    else:
                        gid = int(gid_part)
                
                # Buat URL untuk ekspor CSV dengan GID
                csv_export_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/export?format=csv&gid={gid}"
                logger.info(f"Mencoba akses dengan GID: {gid}")
                
                # Muat data ke pandas DataFrame
                self.data = pd.read_csv(csv_export_url)
                logger.info(f"Berhasil memuat {len(self.data)} baris data menggunakan GID")
                return self.data

        except Exception as e:
            logger.error(f"Error saat memuat spreadsheet: {e}")
            return None
    
    def find_nearby_locations(self, lat, lng, lat_col, lng_col, radius_meters=DEFAULT_RADIUS):
        """
        Temukan lokasi dalam radius tertentu dari titik referensi.
        
        Args:
            lat: Latitude titik referensi
            lng: Longitude titik referensi
            lat_col: Nama kolom latitude di DataFrame
            lng_col: Nama kolom longitude di DataFrame
            radius_meters: Radius pencarian dalam meter
            
        Returns:
            DataFrame dengan lokasi-lokasi yang berada dalam radius
        """
        if self.data is None:
            logger.error("Data belum dimuat dari spreadsheet")
            return None
        
        # Pastikan kolom lat dan lng ada di DataFrame
        if lat_col not in self.data.columns or lng_col not in self.data.columns:
            logger.error(f"Kolom {lat_col} atau {lng_col} tidak ditemukan di spreadsheet")
            return None
        
        # Konversi nilai latitude dan longitude ke tipe numerik
        data_copy = self.data.copy()
        data_copy[lat_col] = pd.to_numeric(data_copy[lat_col], errors='coerce')
        data_copy[lng_col] = pd.to_numeric(data_copy[lng_col], errors='coerce')
        
        # Hapus data dengan lat/lng yang tidak valid
        valid_df = data_copy.dropna(subset=[lat_col, lng_col]).copy()
        
        # Titik referensi
        ref_point = (lat, lng)
        
        # Hitung jarak untuk setiap lokasi
        distances = []
        for _, row in valid_df.iterrows():
            location_point = (row[lat_col], row[lng_col])
            distance = geodesic(ref_point, location_point).meters
            distances.append(distance)
        
        # Tambahkan kolom jarak
        valid_df['jarak_meter'] = distances
        
        # Filter lokasi dalam radius yang ditentukan
        nearby_locations = valid_df[valid_df['jarak_meter'] <= radius_meters].copy()
        
        # Urutkan berdasarkan jarak
        nearby_locations = nearby_locations.sort_values('jarak_meter')
        
        return nearby_locations
    
    def generate_map(self, ref_lat, ref_lng, nearby_df, lat_col, lng_col, name_col=None):
        """
        Hasilkan peta dengan titik referensi dan lokasi sekitarnya.
        
        Args:
            ref_lat: Latitude titik referensi
            ref_lng: Longitude titik referensi
            nearby_df: DataFrame dengan lokasi sekitarnya
            lat_col: Nama kolom latitude
            lng_col: Nama kolom longitude
            name_col: Nama kolom untuk nama lokasi (opsional)
            
        Returns:
            Objek peta folium
        """
        # Buat peta berpusat di titik referensi
        m = folium.Map(location=[ref_lat, ref_lng], zoom_start=16)
        
        # Tambahkan marker untuk titik referensi
        folium.Marker(
            [ref_lat, ref_lng],
            popup="Lokasi Anda",
            tooltip="Lokasi Anda",
            icon=folium.Icon(color='red', icon='info-sign')
        ).add_to(m)
        
        # Tambahkan lingkaran untuk radius
        folium.Circle(
            [ref_lat, ref_lng],
            radius=DEFAULT_RADIUS,
            color='red',
            fill=True,
            fill_opacity=0.2
        ).add_to(m)
        
        # Jika ada lokasi sekitar, tambahkan ke peta
        if nearby_df is not None and not nearby_df.empty:
            # Cari kolom nama jika tidak ditentukan
            if name_col is None:
                # Cari kolom yang namanya mengandung 'nama' atau 'name'
                name_columns = [col for col in nearby_df.columns if 'nama' in col.lower() or 'name' in col.lower()]
                if name_columns:
                    name_col = name_columns[0]
            
            # Tambahkan marker untuk setiap lokasi
            for idx, row in nearby_df.iterrows():
                lat = row[lat_col]
                lng = row[lng_col]
                
                # Siapkan popup dan tooltip
                if name_col and name_col in row:
                    name = row[name_col]
                    tooltip = f"{name} ({row['jarak_meter']:.1f}m)"
                    
                    # Siapkan popup dengan semua informasi
                    popup_html = f"<b>{name}</b><br>Jarak: {row['jarak_meter']:.1f}m<br>"
                    for col in row.index:
                        if col not in [lat_col, lng_col, name_col, 'jarak_meter']:
                            popup_html += f"{col}: {row[col]}<br>"
                else:
                    tooltip = f"Lokasi {idx+1} ({row['jarak_meter']:.1f}m)"
                    
                    # Siapkan popup dengan semua informasi
                    popup_html = f"<b>Lokasi {idx+1}</b><br>Jarak: {row['jarak_meter']:.1f}m<br>"
                    for col in row.index:
                        if col not in [lat_col, lng_col, 'jarak_meter']:
                            popup_html += f"{col}: {row[col]}<br>"
                
                # Tambahkan marker
                folium.Marker(
                    [lat, lng],
                    popup=folium.Popup(popup_html, max_width=300),
                    tooltip=tooltip,
                    icon=folium.Icon(color='blue', icon='info-sign')
                ).add_to(m)
        
        return m
    
    def save_map_as_html(self, map_obj, map_id=None):
        """Simpan objek peta folium ke file HTML."""
        if map_id is None:
            map_id = str(uuid.uuid4())
        
        file_path = os.path.join(MAPS_DIR, f"{map_id}.html")
        map_obj.save(file_path)
        
        return map_id, file_path

# Flask routes
@app.route('/')
def home():
    return "Bot Pencari Lokasi Server"

@app.route('/maps/<map_id>')
def show_map(map_id):
    file_path = os.path.join(MAPS_DIR, f"{map_id}.html")
    if os.path.exists(file_path):
        return send_file(file_path)
    else:
        return "Peta tidak ditemukan", 404

# Handler untuk bot Telegram
def handle_start(message):
    """Kirim pesan saat perintah /start diterima."""
    bot.reply_to(message, 
        f'Halo {message.from_user.first_name}! Saya bot pencari lokasi.\n'
        f'Kirim koordinat latitude dan longitude (misal: -6.1754, 106.8272) untuk menemukan lokasi dalam radius {DEFAULT_RADIUS}m.\n'
        f'Ketik /help untuk bantuan.'
    )

def handle_help(message):
    """Kirim pesan saat perintah /help diterima."""
    help_text = (
        "Cara menggunakan bot ini:\n\n"
        "1. Kirim koordinat dalam format 'latitude, longitude'\n"
        "   Contoh: -6.1754, 106.8272\n\n"
        "2. Bot akan mencari lokasi dalam radius 250 meter dari koordinat tersebut\n\n"
        "3. Hasil pencarian akan ditampilkan beserta peta\n\n"
        "Perintah yang tersedia:\n"
        "/start - Mulai bot\n"
        "/help - Tampilkan bantuan ini\n"
        "/radius <angka> - Atur radius pencarian (dalam meter)\n"
        "/source - Tampilkan info sumber data"
    )
    bot.reply_to(message, help_text)

def handle_radius(message):
    """Ubah radius pencarian."""
    args = message.text.split()[1:]
    
    if not args:
        user_radius = radius_data.get(message.from_user.id, DEFAULT_RADIUS)
        bot.reply_to(message, 
            f"Radius pencarian saat ini: {user_radius} meter.\n"
            f"Untuk mengubah, ketik /radius <angka_meter>"
        )
        return
    
    try:
        radius = int(args[0])
        if radius <= 0:
            bot.reply_to(message, "Radius harus lebih besar dari 0 meter.")
            return
        
        radius_data[message.from_user.id] = radius
        bot.reply_to(message, f"Radius pencarian diubah menjadi {radius} meter.")
    except ValueError:
        bot.reply_to(message, "Format tidak valid. Gunakan /radius <angka_meter>")

def handle_source(message):
    """Tampilkan info sumber data."""
    bot.reply_to(message,
        f"Sumber data: Google Spreadsheet\n"
        f"Kolom latitude: {LAT_COLUMN}\n"
        f"Kolom longitude: {LNG_COLUMN}\n"
        f"Radius default: {DEFAULT_RADIUS} meter"
    )

def handle_text(message):
    """Handle pesan teks yang diterima."""
    text = message.text
    
    # Cek apakah pesan berisi koordinat
    coords_pattern = r'(-?\d+\.?\d*)[,\s]+(-?\d+\.?\d*)'
    match = re.search(coords_pattern, text)
    
    if match:
        # Ekstrak koordinat
        lat = float(match.group(1))
        lng = float(match.group(2))
        
        bot.reply_to(message, f"Mencari lokasi dalam radius {radius_data.get(message.from_user.id, DEFAULT_RADIUS)}m dari koordinat ({lat}, {lng})...")
        
        try:
            # Muat data dari spreadsheet (jika belum dimuat)
            sheet_handler = SpreadsheetHandler(SPREADSHEET_URL)
            data = sheet_handler.load_from_url()
            
            if data is None:
                bot.reply_to(message, "Gagal memuat data dari spreadsheet. Pastikan URL spreadsheet valid dan dapat diakses secara publik.")
                return
            
            # Cari lokasi terdekat
            radius = radius_data.get(message.from_user.id, DEFAULT_RADIUS)
            nearby = sheet_handler.find_nearby_locations(lat, lng, LAT_COLUMN, LNG_COLUMN, radius)
            
            if nearby is None:
                bot.reply_to(message, f"Terjadi kesalahan saat mencari lokasi. Pastikan kolom {LAT_COLUMN} dan {LNG_COLUMN} ada di spreadsheet.")
                return
            
            if nearby.empty:
                bot.reply_to(message, f"Tidak ditemukan lokasi dalam radius {radius}m dari koordinat yang diberikan.")
                return
            
            # Cari kolom nama (jika ada)
            name_col = None
            name_columns = [col for col in nearby.columns if 'nama' in col.lower() or 'name' in col.lower()]
            if name_columns:
                name_col = name_columns[0]
            
            # Format hasil
            result_text = f"Ditemukan {len(nearby)} lokasi dalam radius {radius}m:\n\n"
            
            for idx, row in nearby.head(10).iterrows():  # Ambil maksimal 10 lokasi terdekat
                if name_col:
                    result_text += f"{idx+1}. {row[name_col]}\n"
                else:
                    result_text += f"{idx+1}. Lokasi {idx+1}\n"
                
                result_text += f"   Jarak: {row['jarak_meter']:.1f}m\n"
                result_text += f"   Koordinat: {row[LAT_COLUMN]}, {row[LNG_COLUMN]}\n"
                
                # Tambahkan info tambahan (maks 3 kolom lain)
                other_cols = [col for col in nearby.columns if col not in [LAT_COLUMN, LNG_COLUMN, name_col, 'jarak_meter']][:3]
                for col in other_cols:
                    result_text += f"   {col}: {row[col]}\n"
                
                result_text += "\n"
            
            if len(nearby) > 10:
                result_text += f"... dan {len(nearby) - 10} lokasi lainnya.\n"
            
            # Tambahkan statistik
            result_text += f"\nJarak terdekat: {nearby['jarak_meter'].min():.1f}m\n"
            result_text += f"Jarak terjauh: {nearby['jarak_meter'].max():.1f}m\n"
            
            # Kirim pesan hasil
            bot.reply_to(message, result_text)
            
            # Buat peta
            map_obj = sheet_handler.generate_map(lat, lng, nearby, LAT_COLUMN, LNG_COLUMN, NAME_COLUMN)
            map_id, _ = sheet_handler.save_map_as_html(map_obj)
            
            # Buat tautan ke peta
            map_url = f"{BASE_URL}/maps/{map_id}"
            
            # Buat keyboard inline dengan tautan
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("Lihat Peta Lokasi", url=map_url))
            
            bot.reply_to(message, 
                "Klik tombol di bawah untuk melihat peta lokasi:",
                reply_markup=markup
            )
            
        except Exception as e:
            logger.error(f"Error saat memproses koordinat: {e}")
            bot.reply_to(message, f"Terjadi kesalahan: {e}")
    else:
        bot.reply_to(message,
            "Format koordinat tidak valid. Kirim dalam format 'latitude, longitude'.\n"
            "Contoh: -6.1754, 106.8272"
        )

def run_flask():
    """Jalankan server Flask di thread terpisah."""
    app.run(host='0.0.0.0', port=WEB_SERVER_PORT)

def main():
    """Fungsi utama untuk menjalankan bot."""
    # Dapatkan token dari variabel lingkungan
    token = os.environ.get("TELEGRAM_TOKEN")
    
    if not token:
        logger.warning("Token bot Telegram tidak ditemukan di variabel lingkungan.")
        return
    
    # Inisialisasi bot
    global bot
    bot = telebot.TeleBot(token)
    
    # Register handler
    bot.message_handler(commands=['start'])(handle_start)
    bot.message_handler(commands=['help'])(handle_help)
    bot.message_handler(commands=['radius'])(handle_radius)
    bot.message_handler(commands=['source'])(handle_source)
    bot.message_handler(func=lambda message: True)(handle_text)
    
    # Jalankan server Flask di thread terpisah
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    logger.info(f"Server Flask berjalan di port {WEB_SERVER_PORT}")
    
    # Jalankan bot
    logger.info("Bot Telegram mulai berjalan...")
    bot.infinity_polling()

if __name__ == "__main__":
    main()