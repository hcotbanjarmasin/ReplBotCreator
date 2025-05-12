import os
import logging
import pandas as pd
import telegram
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
from geopy.distance import geodesic
import tempfile
import re
import uuid
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

# Handler for Telegram commands
def start(update, context):
    """Kirim pesan saat perintah /start diterima."""
    user = update.effective_user
    update.message.reply_text(
        f'Halo {user.first_name}! Saya bot pencari lokasi.\n'
        f'Kirim koordinat latitude dan longitude (misal: -6.1754, 106.8272) untuk menemukan lokasi dalam radius {DEFAULT_RADIUS}m.\n'
        f'Ketik /help untuk bantuan.'
    )

def help_command(update, context):
    """Kirim pesan saat perintah /help diterima."""
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
    update.message.reply_text(help_text)

def radius_command(update, context):
    """Ubah radius pencarian."""
    args = context.args
    if not args:
        update.message.reply_text(
            f"Radius pencarian saat ini: {context.bot_data.get('radius', DEFAULT_RADIUS)} meter.\n"
            f"Untuk mengubah, ketik /radius <angka_meter>"
        )
        return
    
    try:
        radius = int(args[0])
        if radius <= 0:
            update.message.reply_text("Radius harus lebih besar dari 0 meter.")
            return
        
        context.bot_data['radius'] = radius
        update.message.reply_text(f"Radius pencarian diubah menjadi {radius} meter.")
    except ValueError:
        update.message.reply_text("Format tidak valid. Gunakan /radius <angka_meter>")

def source_command(update, context):
    """Tampilkan info sumber data."""
    update.message.reply_text(
        f"Sumber data: Google Spreadsheet\n"
        f"Kolom latitude: {LAT_COLUMN}\n"
        f"Kolom longitude: {LNG_COLUMN}\n"
        f"Radius default: {DEFAULT_RADIUS} meter"
    )

def handle_text(update, context):
    """Handle pesan teks yang diterima."""
    text = update.message.text
    
    # Cek apakah pesan berisi koordinat
    coords_pattern = r'(-?\d+\.?\d*)[,\s]+(-?\d+\.?\d*)'
    match = re.search(coords_pattern, text)
    
    if match:
        # Ekstrak koordinat
        lat = float(match.group(1))
        lng = float(match.group(2))
        
        update.message.reply_text(f"Mencari lokasi dalam radius {context.bot_data.get('radius', DEFAULT_RADIUS)}m dari koordinat ({lat}, {lng})...")
        
        try:
            # Muat data dari spreadsheet (jika belum dimuat)
            sheet_handler = SpreadsheetHandler(SPREADSHEET_URL)
            data = sheet_handler.load_from_url()
            
            if data is None:
                update.message.reply_text("Gagal memuat data dari spreadsheet. Pastikan URL spreadsheet valid dan dapat diakses secara publik.")
                return
            
            # Cari lokasi terdekat
            radius = context.bot_data.get('radius', DEFAULT_RADIUS)
            nearby = sheet_handler.find_nearby_locations(lat, lng, LAT_COLUMN, LNG_COLUMN, radius)
            
            if nearby is None:
                update.message.reply_text(f"Terjadi kesalahan saat mencari lokasi. Pastikan kolom {LAT_COLUMN} dan {LNG_COLUMN} ada di spreadsheet.")
                return
            
            if nearby.empty:
                update.message.reply_text(f"Tidak ditemukan lokasi dalam radius {radius}m dari koordinat yang diberikan.")
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
            update.message.reply_text(result_text)
            
        except Exception as e:
            logger.error(f"Error saat memproses koordinat: {e}")
            update.message.reply_text(f"Terjadi kesalahan: {e}")
    else:
        update.message.reply_text(
            "Format koordinat tidak valid. Kirim dalam format 'latitude, longitude'.\n"
            "Contoh: -6.1754, 106.8272"
        )

def main():
    """Fungsi utama untuk menjalankan bot."""
    # Dapatkan token dari variabel lingkungan
    token = os.environ.get("TELEGRAM_TOKEN")
    
    if not token:
        logger.warning("Token bot Telegram tidak ditemukan di variabel lingkungan.")
        return
    
    # Buat Updater dan dispatcher
    updater = Updater(token=token, use_context=True)
    dispatcher = updater.dispatcher
    
    # Tambahkan handler perintah
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("help", help_command))
    dispatcher.add_handler(CommandHandler("radius", radius_command))
    dispatcher.add_handler(CommandHandler("source", source_command))
    
    # Handler untuk pesan teks
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_text))
    
    # Jalankan bot
    updater.start_polling()
    logger.info("Bot berjalan...")
    
    # Tetap jalankan bot sampai menerima Ctrl-C atau sinyal lain
    updater.idle()

if __name__ == "__main__":
    main()