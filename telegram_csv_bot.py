import os
import logging
import pandas as pd
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
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

# File CSV data lokasi
CSV_FILE = "sample_locations.csv"

# Kolom latitude dan longitude di file CSV (sesuaikan jika berbeda)
LAT_COLUMN = "Latitude"
LNG_COLUMN = "Longitude"

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

class CsvLocationHandler:
    def __init__(self, csv_path=None):
        """
        Inisialisasi handler lokasi dari file CSV.
        
        Args:
            csv_path: Path ke file CSV dengan data lokasi
        """
        self.csv_path = csv_path
        self.data = None
        
        if csv_path:
            self.load_data(csv_path)
    
    def load_data(self, csv_path=None):
        """
        Muat data dari file CSV.
        
        Args:
            csv_path: Path ke file CSV
        
        Returns:
            DataFrame dengan data dari file CSV
        """
        try:
            if csv_path:
                self.csv_path = csv_path
                
            if not self.csv_path:
                logger.error("Path file CSV tidak diberikan")
                return None
                
            # Muat data ke pandas DataFrame
            self.data = pd.read_csv(self.csv_path)
            logger.info(f"Berhasil memuat {len(self.data)} baris data dari {self.csv_path}")
            return self.data
        except Exception as e:
            logger.error(f"Error saat memuat file CSV: {e}")
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
            logger.error("Data belum dimuat dari file CSV")
            return None
        
        # Pastikan kolom lat dan lng ada di DataFrame
        if lat_col not in self.data.columns or lng_col not in self.data.columns:
            logger.error(f"Kolom {lat_col} atau {lng_col} tidak ditemukan di file CSV")
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

# Handler for Telegram commands
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Kirim pesan saat perintah /start diterima."""
    user = update.effective_user
    await update.message.reply_text(
        f'Halo {user.mention_html()}! Saya bot pencari lokasi.\n'
        f'Kirim koordinat latitude dan longitude (misal: -6.1754, 106.8272) untuk menemukan lokasi dalam radius {DEFAULT_RADIUS}m.\n'
        f'Ketik /help untuk bantuan.',
        parse_mode='HTML'
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Kirim pesan saat perintah /help diterima."""
    help_text = (
        "Cara menggunakan bot ini:\n\n"
        "1. Kirim koordinat dalam format 'latitude, longitude'\n"
        "   Contoh: -6.2088, 106.8456\n\n"
        "2. Bot akan mencari lokasi dalam radius 250 meter dari koordinat tersebut\n\n"
        "3. Hasil pencarian akan ditampilkan beserta peta\n\n"
        "Perintah yang tersedia:\n"
        "/start - Mulai bot\n"
        "/help - Tampilkan bantuan ini\n"
        "/radius <angka> - Atur radius pencarian (dalam meter)\n"
        "/source - Tampilkan info sumber data"
    )
    await update.message.reply_text(help_text)

async def radius_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ubah radius pencarian."""
    if not context.args:
        await update.message.reply_text(
            f"Radius pencarian saat ini: {context.bot_data.get('radius', DEFAULT_RADIUS)} meter.\n"
            f"Untuk mengubah, ketik /radius <angka_meter>"
        )
        return
    
    try:
        radius = int(context.args[0])
        if radius <= 0:
            await update.message.reply_text("Radius harus lebih besar dari 0 meter.")
            return
        
        context.bot_data['radius'] = radius
        await update.message.reply_text(f"Radius pencarian diubah menjadi {radius} meter.")
    except ValueError:
        await update.message.reply_text("Format tidak valid. Gunakan /radius <angka_meter>")

async def source_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Tampilkan info sumber data."""
    await update.message.reply_text(
        f"Sumber data: File CSV lokal ({CSV_FILE})\n"
        f"Kolom latitude: {LAT_COLUMN}\n"
        f"Kolom longitude: {LNG_COLUMN}\n"
        f"Radius default: {DEFAULT_RADIUS} meter"
    )

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle pesan teks yang diterima."""
    text = update.message.text
    
    # Cek apakah pesan berisi koordinat
    coords_pattern = r'(-?\d+\.?\d*)[,\s]+(-?\d+\.?\d*)'
    match = re.search(coords_pattern, text)
    
    if match:
        # Ekstrak koordinat
        lat = float(match.group(1))
        lng = float(match.group(2))
        
        await update.message.reply_text(f"Mencari lokasi dalam radius {context.bot_data.get('radius', DEFAULT_RADIUS)}m dari koordinat ({lat}, {lng})...")
        
        try:
            # Muat data dari file CSV
            handler = CsvLocationHandler(CSV_FILE)
            data = handler.load_data()
            
            if data is None:
                await update.message.reply_text(f"Gagal memuat data dari file CSV {CSV_FILE}.")
                return
            
            # Cari lokasi terdekat
            radius = context.bot_data.get('radius', DEFAULT_RADIUS)
            nearby = handler.find_nearby_locations(lat, lng, LAT_COLUMN, LNG_COLUMN, radius)
            
            if nearby is None:
                await update.message.reply_text(f"Terjadi kesalahan saat mencari lokasi. Pastikan kolom {LAT_COLUMN} dan {LNG_COLUMN} ada di file CSV.")
                return
            
            if nearby.empty:
                await update.message.reply_text(f"Tidak ditemukan lokasi dalam radius {radius}m dari koordinat yang diberikan.")
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
            await update.message.reply_text(result_text)
            
            # Buat peta
            map_obj = handler.generate_map(lat, lng, nearby, LAT_COLUMN, LNG_COLUMN, name_col)
            map_id, _ = handler.save_map_as_html(map_obj)
            
            # Buat tautan ke peta
            map_url = f"{BASE_URL}/maps/{map_id}"
            
            # Buat keyboard inline dengan tautan
            keyboard = [
                [InlineKeyboardButton("Lihat Peta Lokasi", url=map_url)]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                "Klik tombol di bawah untuk melihat peta lokasi:",
                reply_markup=reply_markup
            )
            
        except Exception as e:
            logger.error(f"Error saat memproses koordinat: {e}")
            await update.message.reply_text(f"Terjadi kesalahan: {e}")
    else:
        await update.message.reply_text(
            "Format koordinat tidak valid. Kirim dalam format 'latitude, longitude'.\n"
            "Contoh: -6.2088, 106.8456 (Jakarta Pusat)"
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
    
    # Cek apakah file CSV ada
    if not os.path.exists(CSV_FILE):
        logger.error(f"File CSV {CSV_FILE} tidak ditemukan. Jalankan sample_data_generator.py terlebih dahulu.")
        return
    
    # Jalankan server Flask di thread terpisah
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    logger.info(f"Server Flask berjalan di port {WEB_SERVER_PORT}")
    
    # Buat aplikasi
    application = Application.builder().token(token).build()
    
    # Tambahkan handler perintah
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("radius", radius_command))
    application.add_handler(CommandHandler("source", source_command))
    
    # Handler untuk pesan teks
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    # Jalankan bot
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()