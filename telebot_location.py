import os
import logging
import pandas as pd
import telebot
from telebot import types
from geopy.distance import geodesic
import tempfile
import re
import uuid
import threading
import folium
from flask import Flask, send_file, request, render_template_string
from threading import Thread

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

# Bot data
user_radius = {}  # Untuk menyimpan radius pencarian per user

# Port untuk web server
WEB_SERVER_PORT = 5000

# Base URL untuk server (menggunakan URL dinamis dari variabel lingkungan)
REPL_SLUG = os.environ.get('REPL_SLUG', 'workspace')
REPL_OWNER = os.environ.get('REPL_OWNER', 'hcotbanjarmasin')
REPL_ID = os.environ.get('REPL_ID', 'ee57a504-e102-4aff-8c9a-6457e53f0217')

# Coba berbagai opsi URL
BASE_URL = f"https://{REPL_SLUG}.{REPL_OWNER}.repl.co"

# Direktori untuk menyimpan file peta
MAPS_DIR = "maps"
os.makedirs(MAPS_DIR, exist_ok=True)

# Inisialisasi Flask app
app = Flask(__name__)

# Tambahkan route default
@app.route('/')
def index():
    return """
    <html>
    <head>
        <title>Bot Pencari Lokasi</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                max-width: 800px;
                margin: 0 auto;
                padding: 20px;
                line-height: 1.6;
            }
            h1 {
                color: #2c3e50;
            }
            .card {
                background: #f9f9f9;
                border-radius: 5px;
                padding: 15px;
                margin-bottom: 20px;
                border-left: 5px solid #3498db;
            }
            code {
                background: #eee;
                padding: 2px 5px;
                border-radius: 3px;
            }
            .button {
                display: inline-block;
                background-color: #3498db;
                color: white;
                padding: 10px 15px;
                text-decoration: none;
                border-radius: 4px;
                margin-top: 10px;
            }
            .button:hover {
                background-color: #2980b9;
            }
        </style>
    </head>
    <body>
        <h1>Bot Pencari Lokasi</h1>
        <div class="card">
            <h2>Cara Menggunakan</h2>
            <p>Bot ini membantu menemukan lokasi terdekat dalam radius tertentu dari koordinat yang diberikan.</p>
            <p>Fitur utama:</p>
            <ul>
                <li>Pencarian lokasi dalam radius yang dapat diatur</li>
                <li>Menampilkan hasil pencarian dalam bentuk daftar dan peta interaktif</li>
                <li>Integrasi dengan Telegram</li>
            </ul>
        </div>

        <div class="card">
            <h2>Demo Maps</h2>
            <p>Semua peta yang dihasilkan oleh bot akan tersedia di URL <code>/maps/[id_peta]</code></p>
            <p>Atau gunakan halaman embed dengan format: <code>/embed?id=[id_peta]</code></p>
        </div>

        <div class="card">
            <h2>Telegram Bot</h2>
            <p>Gunakan bot Telegram untuk mencari lokasi. Kirim koordinat dalam format:</p>
            <code>-6.1754, 106.8272</code>
        </div>
        
        <div class="card">
            <h2>Coba Langsung</h2>
            <p>Masukkan koordinat di bawah ini untuk mencoba:</p>
            <form action="/search" method="get">
                <input type="text" name="coords" placeholder="-6.1754, 106.8272" required style="padding: 8px; width: 200px; margin-right: 10px;">
                <button type="submit" class="button">Cari Lokasi</button>
            </form>
        </div>
    </body>
    </html>
    """

# Route untuk halaman embed peta
@app.route('/embed')
def embed_map():
    return send_file('static/embed.html')

# Route untuk pencarian langsung dari web
@app.route('/search')
def web_search():
    coords = request.args.get('coords', '')
    
    # Cek apakah koordinat valid
    coords_pattern = r'(-?\d+\.?\d*)[,\s]+(-?\d+\.?\d*)'
    match = re.search(coords_pattern, coords)
    
    if not match:
        return render_template_string("""
        <html>
            <head>
                <title>Pencarian Gagal</title>
                <style>
                    body { font-family: Arial, sans-serif; max-width: 800px; margin: 20px auto; padding: 20px; }
                    h1 { color: #e74c3c; }
                    .error-box { background: #f9f9f9; border-left: 5px solid #e74c3c; padding: 15px; }
                    .button { display: inline-block; background-color: #3498db; color: white; 
                             padding: 10px 15px; text-decoration: none; border-radius: 4px; margin-top: 10px; }
                </style>
            </head>
            <body>
                <h1>Format Koordinat Tidak Valid</h1>
                <div class="error-box">
                    <p>Format koordinat yang dimasukkan tidak valid. Gunakan format 'latitude, longitude'.</p>
                    <p>Contoh: -6.1754, 106.8272</p>
                </div>
                <a href="/" class="button">Kembali ke Beranda</a>
            </body>
        </html>
        """)

    try:
        # Ekstrak koordinat
        lat = float(match.group(1))
        lng = float(match.group(2))
        radius = DEFAULT_RADIUS
        
        # Muat data dari spreadsheet
        sheet_handler = SpreadsheetHandler(SPREADSHEET_URL)
        data = sheet_handler.load_from_url()
        
        if data is None:
            return "Gagal memuat data dari spreadsheet. Pastikan URL spreadsheet valid dan dapat diakses secara publik.", 500
        
        # Cari lokasi terdekat
        nearby = sheet_handler.find_nearby_locations(lat, lng, LAT_COLUMN, LNG_COLUMN, radius)
        
        if nearby is None:
            return f"Terjadi kesalahan saat mencari lokasi. Pastikan kolom {LAT_COLUMN} dan {LNG_COLUMN} ada di spreadsheet.", 500
        
        if nearby.empty:
            return render_template_string("""
            <html>
                <head>
                    <title>Tidak Ada Hasil</title>
                    <style>
                        body { font-family: Arial, sans-serif; max-width: 800px; margin: 20px auto; padding: 20px; }
                        h1 { color: #e67e22; }
                        .info-box { background: #f9f9f9; border-left: 5px solid #e67e22; padding: 15px; }
                        .button { display: inline-block; background-color: #3498db; color: white; 
                                padding: 10px 15px; text-decoration: none; border-radius: 4px; margin-top: 10px; }
                    </style>
                </head>
                <body>
                    <h1>Tidak Ada Hasil</h1>
                    <div class="info-box">
                        <p>Tidak ditemukan lokasi dalam radius {{ radius }}m dari koordinat ({{ lat }}, {{ lng }}).</p>
                    </div>
                    <a href="/" class="button">Kembali ke Beranda</a>
                </body>
            </html>
            """, radius=radius, lat=lat, lng=lng)
        
        # Buat peta dari hasil pencarian
        map_obj = sheet_handler.generate_map(lat, lng, nearby, LAT_COLUMN, LNG_COLUMN, NAME_COLUMN)
        
        # Buat UUID unik untuk peta
        map_id = uuid.uuid4().hex
        
        # Simpan peta ke file
        map_path = sheet_handler.save_map_as_html(map_obj, f"{map_id}.html")
        
        # Tampilkan hasil
        return render_template_string("""
        <html>
            <head>
                <title>Hasil Pencarian Lokasi</title>
                <style>
                    body { font-family: Arial, sans-serif; max-width: 800px; margin: 20px auto; padding: 20px; line-height: 1.6; }
                    h1 { color: #2c3e50; }
                    .card { background: #f9f9f9; border-radius: 5px; padding: 15px; margin-bottom: 20px; 
                           border-left: 5px solid #3498db; }
                    .location-item { margin-bottom: 15px; padding-bottom: 15px; border-bottom: 1px solid #eee; }
                    .location-name { font-weight: bold; color: #2c3e50; }
                    .location-distance { color: #7f8c8d; }
                    .location-coords { font-size: 0.9em; color: #7f8c8d; }
                    .button { display: inline-block; background-color: #3498db; color: white; 
                             padding: 10px 15px; text-decoration: none; border-radius: 4px; margin-right: 10px; }
                    .button-secondary { background-color: #2ecc71; }
                    .button:hover { opacity: 0.9; }
                    iframe { width: 100%; height: 500px; border: none; margin-top: 20px; }
                </style>
            </head>
            <body>
                <h1>Hasil Pencarian Lokasi</h1>
                
                <div class="card">
                    <h2>Informasi Pencarian</h2>
                    <p>Koordinat: {{ lat }}, {{ lng }}</p>
                    <p>Radius pencarian: {{ radius }}m</p>
                    <p>Ditemukan {{ total_locations }} lokasi</p>
                </div>
                
                <div class="card">
                    <h2>Peta Hasil</h2>
                    <iframe src="/maps/{{ map_id }}"></iframe>
                    <div style="margin-top: 10px;">
                        <a href="/maps/{{ map_id }}" target="_blank" class="button">Buka Peta di Tab Baru</a>
                        <a href="/embed?id={{ map_id }}" target="_blank" class="button button-secondary">Buka di Halaman Embed</a>
                    </div>
                </div>
                
                <div class="card">
                    <h2>Lokasi Terdekat ({{ displayed_count }}{% if more_available %} dari {{ total_locations }}{% endif %})</h2>
                    {% for i in range(displayed_count) %}
                    <div class="location-item">
                        <div class="location-name">{{ i+1 }}. {{ locations[i].name }}</div>
                        <div class="location-distance">Jarak: {{ "%.1f"|format(locations[i].distance) }}m</div>
                        <div class="location-coords">Koordinat: {{ locations[i].lat }}, {{ locations[i].lng }}</div>
                        {% if locations[i].avai %}
                        <div>Tersedia: {{ locations[i].avai }}</div>
                        {% endif %}
                    </div>
                    {% endfor %}
                    
                    {% if more_available %}
                    <p>... dan {{ total_locations - displayed_count }} lokasi lainnya dalam radius {{ radius }}m.</p>
                    {% endif %}
                </div>
                
                <a href="/" class="button">Kembali ke Beranda</a>
            </body>
        </html>
        """, 
        lat=lat, 
        lng=lng, 
        radius=radius,
        map_id=map_id,
        total_locations=len(nearby),
        displayed_count=min(10, len(nearby)),
        more_available=len(nearby) > 10,
        locations=[{
            'name': row[NAME_COLUMN],
            'distance': row['jarak_meter'],
            'lat': row[LAT_COLUMN],
            'lng': row[LNG_COLUMN],
            'avai': row[AVAI_COLUMN] if AVAI_COLUMN in nearby.columns else None
        } for _, row in nearby.head(10).iterrows()]
        )
    
    except Exception as e:
        logger.error(f"Error saat melakukan pencarian web: {e}")
        return f"Terjadi kesalahan: {e}", 500

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
        nearby_locations = nearby_locations.sort_values(by='jarak_meter')
        
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
        # Buat peta dengan pusat di titik referensi
        m = folium.Map(location=[ref_lat, ref_lng], zoom_start=16)
        
        # Tambahkan marker untuk titik referensi dengan ikon berbeda
        folium.Marker(
            [ref_lat, ref_lng],
            popup='Lokasi Anda',
            tooltip='Lokasi Anda',
            icon=folium.Icon(color='red', icon='user', prefix='fa')
        ).add_to(m)
        
        # Tambahkan titik untuk setiap lokasi yang ditemukan
        for idx, row in nearby_df.iterrows():
            lat = row[lat_col]
            lng = row[lng_col]
            
            # Tentukan popup dan tooltip
            if name_col and name_col in row:
                popup_text = f"{row[name_col]}"
                tooltip_text = f"{row[name_col]}"
            else:
                popup_text = f"Lokasi {idx+1}"
                tooltip_text = f"Lokasi {idx+1}"
            
            # Tambahkan jarak
            popup_text += f"<br>Jarak: {row['jarak_meter']:.1f}m"
            
            # Tambahkan info tambahan (maksimal 3 kolom)
            other_cols = [col for col in row.index if col not in [lat_col, lng_col, name_col, 'jarak_meter']][:3]
            for col in other_cols:
                popup_text += f"<br>{col}: {row[col]}"
            
            # Tambahkan marker ke peta
            folium.Marker(
                [lat, lng],
                popup=popup_text,
                tooltip=tooltip_text,
                icon=folium.Icon(color='blue', icon='info-sign')
            ).add_to(m)
        
        # Tambahkan lingkaran untuk menunjukkan radius pencarian
        folium.Circle(
            [ref_lat, ref_lng],
            radius=float(nearby_df['jarak_meter'].max()) if not nearby_df.empty else DEFAULT_RADIUS,
            color='red',
            fill=True,
            fill_opacity=0.1
        ).add_to(m)
        
        return m
    
    def save_map_as_html(self, map_obj, filename=None):
        """
        Simpan objek peta folium ke file HTML.
        
        Args:
            map_obj: Objek peta folium
            filename: Nama file untuk disimpan (opsional)
            
        Returns:
            Path ke file HTML
        """
        if filename is None:
            # Buat nama file unik jika tidak diberikan
            filename = f"{uuid.uuid4().hex}.html"
        
        # Pastikan file disimpan di direktori maps
        map_path = os.path.join(MAPS_DIR, filename)
        
        # Simpan peta ke file HTML
        map_obj.save(map_path)
        
        return map_path

# Dapatkan token dari variabel lingkungan
token = os.environ.get("TELEGRAM_TOKEN")
if not token:
    logger.error("Token bot Telegram tidak ditemukan di variabel lingkungan.")
    exit(1)

# Buat instance bot
bot = telebot.TeleBot(token)

# Handler untuk perintah /start
@bot.message_handler(commands=['start'])
def handle_start(message):
    bot.reply_to(message, 
        f"Halo {message.from_user.first_name}! Saya bot pencari lokasi.\n"
        f"Kirim koordinat latitude dan longitude (misal: -6.1754, 106.8272) "
        f"untuk menemukan lokasi dalam radius {DEFAULT_RADIUS}m.\n"
        f"Ketik /help untuk bantuan."
    )

# Handler untuk perintah /help
@bot.message_handler(commands=['help'])
def handle_help(message):
    help_text = (
        "Cara menggunakan bot ini:\n\n"
        "1. Kirim koordinat dalam format 'latitude, longitude'\n"
        "   Contoh: -6.1754, 106.8272\n\n"
        "2. Bot akan mencari lokasi dalam radius 250 meter dari koordinat tersebut\n\n"
        "3. Hasil pencarian akan ditampilkan\n\n"
        "Perintah yang tersedia:\n"
        "/start - Mulai bot\n"
        "/help - Tampilkan bantuan ini\n"
        "/radius <angka> - Atur radius pencarian (dalam meter)\n"
        "/source - Tampilkan info sumber data"
    )
    bot.reply_to(message, help_text)

# Handler untuk perintah /radius
@bot.message_handler(commands=['radius'])
def handle_radius(message):
    parts = message.text.split()
    user_id = message.from_user.id
    
    if len(parts) == 1:
        # Perintah tanpa argumen, tampilkan radius saat ini
        radius = user_radius.get(user_id, DEFAULT_RADIUS)
        bot.reply_to(message, 
            f"Radius pencarian saat ini: {radius} meter.\n"
            f"Untuk mengubah, ketik /radius <angka_meter>"
        )
        return
    
    try:
        radius = int(parts[1])
        if radius <= 0:
            bot.reply_to(message, "Radius harus lebih besar dari 0 meter.")
            return
        
        user_radius[user_id] = radius
        bot.reply_to(message, f"Radius pencarian diubah menjadi {radius} meter.")
    except ValueError:
        bot.reply_to(message, "Format tidak valid. Gunakan /radius <angka_meter>")

# Handler untuk perintah /source
@bot.message_handler(commands=['source'])
def handle_source(message):
    bot.reply_to(message,
        f"Sumber data: Google Spreadsheet\n"
        f"Kolom latitude: {LAT_COLUMN}\n"
        f"Kolom longitude: {LNG_COLUMN}\n"
        f"Radius default: {DEFAULT_RADIUS} meter"
    )

# Flask route untuk menampilkan peta
@app.route('/maps/<map_id>')
def show_map(map_id):
    # Hapus ekstensi .html jika ada
    if map_id.endswith('.html'):
        map_id = map_id[:-5]
    
    map_path = os.path.join(MAPS_DIR, f"{map_id}.html")
    if os.path.exists(map_path):
        return send_file(map_path)
    else:
        # Jika file peta tidak ditemukan, cek apakah ada file yang serupa
        for filename in os.listdir(MAPS_DIR):
            if map_id in filename:
                return send_file(os.path.join(MAPS_DIR, filename))
        
        # Tampilkan pesan error yang lebih informatif
        return f"""
        <html>
            <head>
                <title>Peta Tidak Ditemukan</title>
                <style>
                    body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 20px auto; padding: 20px; }}
                    h1 {{ color: #e74c3c; }}
                    .error-box {{ background: #f9f9f9; border-left: 5px solid #e74c3c; padding: 15px; }}
                    .maps-list {{ margin-top: 20px; }}
                    .maps-list a {{ display: block; padding: 5px 0; text-decoration: none; color: #3498db; }}
                    .maps-list a:hover {{ text-decoration: underline; }}
                </style>
            </head>
            <body>
                <h1>Peta Tidak Ditemukan</h1>
                <div class="error-box">
                    <p>Maaf, peta dengan ID <strong>{map_id}</strong> tidak dapat ditemukan.</p>
                </div>
                
                <div class="maps-list">
                    <h2>Peta yang tersedia:</h2>
                    {''.join([f'<a href="/maps/{os.path.splitext(f)[0]}">{f}</a>' for f in os.listdir(MAPS_DIR) if f.endswith('.html')]) or 'Tidak ada peta tersedia'}
                </div>
            </body>
        </html>
        """, 404

# Route tambahan untuk mengakses file .html
@app.route('/maps/<map_id>.html')
def show_map_with_extension(map_id):
    return show_map(map_id)

# Handler untuk pesan teks biasa (koordinat)
@bot.message_handler(func=lambda message: True)
def handle_text(message):
    text = message.text
    
    # Cek apakah pesan berisi koordinat
    coords_pattern = r'(-?\d+\.?\d*)[,\s]+(-?\d+\.?\d*)'
    match = re.search(coords_pattern, text)
    
    if match:
        # Ekstrak koordinat
        lat = float(match.group(1))
        lng = float(match.group(2))
        
        # Dapatkan radius untuk user ini
        user_id = message.from_user.id
        radius = user_radius.get(user_id, DEFAULT_RADIUS)
        
        bot.reply_to(message, f"Mencari lokasi dalam radius {radius}m dari koordinat ({lat}, {lng})...")
        
        try:
            # Muat data dari spreadsheet
            sheet_handler = SpreadsheetHandler(SPREADSHEET_URL)
            data = sheet_handler.load_from_url()
            
            if data is None:
                bot.reply_to(message, "Gagal memuat data dari spreadsheet. Pastikan URL spreadsheet valid dan dapat diakses secara publik.")
                return
            
            # Cari lokasi terdekat
            nearby = sheet_handler.find_nearby_locations(lat, lng, LAT_COLUMN, LNG_COLUMN, radius)
            
            if nearby is None:
                bot.reply_to(message, f"Terjadi kesalahan saat mencari lokasi. Pastikan kolom {LAT_COLUMN} dan {LNG_COLUMN} ada di spreadsheet.")
                return
            
            if nearby.empty:
                bot.reply_to(message, f"Tidak ditemukan lokasi dalam radius {radius}m dari koordinat yang diberikan.")
                return
            
            # Format hasil
            result_text = f"Ditemukan {len(nearby)} lokasi dalam radius {radius}m:\n\n"
            
            for idx, row in nearby.head(10).iterrows():  # Ambil maksimal 10 lokasi terdekat
                result_text += f"{idx+1}. {row[NAME_COLUMN]}\n"
                result_text += f"   Jarak: {row['jarak_meter']:.1f}m\n"
                result_text += f"   Koordinat: {row[LAT_COLUMN]}, {row[LNG_COLUMN]}\n"
                
                # Tambahkan info ketersediaan
                if AVAI_COLUMN in nearby.columns:
                    result_text += f"   Tersedia: {row[AVAI_COLUMN]}\n"
                
                result_text += "\n"
            
            if len(nearby) > 10:
                result_text += f"... dan {len(nearby) - 10} lokasi lainnya.\n"
            
            # Tambahkan statistik
            result_text += f"\nJarak terdekat: {nearby['jarak_meter'].min():.1f}m\n"
            result_text += f"Jarak terjauh: {nearby['jarak_meter'].max():.1f}m\n"
            
            # Buat peta dari hasil pencarian
            map_obj = sheet_handler.generate_map(lat, lng, nearby, LAT_COLUMN, LNG_COLUMN, NAME_COLUMN)
            
            # Buat UUID unik untuk peta
            map_id = uuid.uuid4().hex
            
            # Simpan peta ke file
            map_path = sheet_handler.save_map_as_html(map_obj, f"{map_id}.html")
            
            # Tambahkan link ke peta dengan beberapa opsi URL yang mungkin
            main_url = f"{BASE_URL}/maps/{map_id}"
            embed_url = f"{BASE_URL}/embed?id={map_id}"
            
            # Opsi URL cadangan jika URL utama tidak berfungsi
            alt_url_1 = f"https://workspace.{REPL_OWNER}.repl.co/maps/{map_id}"
            alt_url_2 = f"https://{REPL_ID}-5000.{REPL_OWNER}.repl.co/maps/{map_id}"
            
            # Tambahkan semua URL ke hasil teks
            result_text += f"\nLihat hasil pada peta:"
            result_text += f"\n• Peta langsung: {main_url}"
            result_text += f"\n• Peta dalam frame: {embed_url}"
            result_text += f"\n• URL alternatif (jika di atas tidak berfungsi):"
            result_text += f"\n  - {alt_url_1}"
            result_text += f"\n  - {alt_url_2}"
            
            # Kirim pesan hasil
            bot.reply_to(message, result_text)
            
        except Exception as e:
            logger.error(f"Error saat memproses koordinat: {e}")
            bot.reply_to(message, f"Terjadi kesalahan: {e}")
    else:
        bot.reply_to(message, 
            "Format koordinat tidak valid. Kirim dalam format 'latitude, longitude'.\n"
            "Contoh: -6.1754, 106.8272"
        )

# Fungsi untuk menjalankan server Flask
def run_flask():
    """Jalankan server Flask di thread terpisah."""
    app.run(host='0.0.0.0', port=WEB_SERVER_PORT)

# Main function
def main():
    # Jalankan Flask di thread terpisah
    flask_thread = Thread(target=run_flask)
    flask_thread.daemon = True  # Thread akan berhenti saat program utama berhenti
    flask_thread.start()
    
    logger.info(f"Server Flask berjalan di port {WEB_SERVER_PORT}")
    logger.info(f"URL server: {BASE_URL}")
    logger.info("Bot Telegram mulai berjalan...")
    
    # Jalankan bot Telegram
    bot.infinity_polling()

if __name__ == "__main__":
    main()