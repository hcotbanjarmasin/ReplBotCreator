import os
import logging
import pandas as pd
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from geopy.distance import geodesic
import folium
import io
from PIL import Image
import numpy as np
import matplotlib.pyplot as plt
import re

# Konfigurasi logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# URL spreadsheet publik (ganti dengan URL spreadsheet Anda)
SPREADSHEET_URL = "GANTI_DENGAN_URL_SPREADSHEET_ANDA"

# Kolom latitude dan longitude di spreadsheet (sesuaikan jika berbeda)
LAT_COLUMN = "latitude"
LNG_COLUMN = "longitude"

# Jarak radius pencarian dalam meter
DEFAULT_RADIUS = 250

class SpreadsheetHandler:
    def __init__(self, url=None):
        """Inisialisasi handler spreadsheet."""
        self.url = url
        self.data = None
        
    def load_from_url(self, url=None, sheet_name=0):
        """
        Muat data dari URL spreadsheet publik Google Sheets.
        
        Args:
            url: URL spreadsheet Google Sheets yang dibagikan secara publik
            sheet_name: Nama atau indeks worksheet (default: 0)
            
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
            
            # Buat URL untuk ekspor CSV
            csv_export_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/export?format=csv"
            if isinstance(sheet_name, int):
                csv_export_url += f"&gid={sheet_name}"
            
            # Muat data ke pandas DataFrame
            self.data = pd.read_csv(csv_export_url)
            logger.info(f"Berhasil memuat {len(self.data)} baris data dari spreadsheet")
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
    
    def save_map_as_html(self, map_obj, filename="map.html"):
        """Simpan objek peta folium ke file HTML."""
        map_obj.save(filename)
        return filename
    
    def convert_map_to_image(self, map_obj, output_path="map.png"):
        """
        Konversi peta folium menjadi gambar PNG.
        
        Catatan: Metode ini tidak berfungsi dalam lingkungan tanpa browser.
        Alternatif sederhana adalah simpan HTML dan arahkan user ke URL.
        """
        # Ini adalah placeholder. Konversi folium ke gambar statis
        # membutuhkan browser atau headless browser.
        # Untuk bot Telegram, biasanya lebih baik menyimpan HTML dan
        # membagikan link daripada mencoba membuat gambar statis.
        html_path = self.save_map_as_html(map_obj)
        return html_path

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
        "   Contoh: -6.1754, 106.8272\n\n"
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
        f"Sumber data: Google Spreadsheet\n"
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
            # Muat data dari spreadsheet (jika belum dimuat)
            sheet_handler = SpreadsheetHandler(SPREADSHEET_URL)
            data = sheet_handler.load_from_url()
            
            if data is None:
                await update.message.reply_text("Gagal memuat data dari spreadsheet. Pastikan URL spreadsheet valid dan dapat diakses secara publik.")
                return
            
            # Cari lokasi terdekat
            radius = context.bot_data.get('radius', DEFAULT_RADIUS)
            nearby = sheet_handler.find_nearby_locations(lat, lng, LAT_COLUMN, LNG_COLUMN, radius)
            
            if nearby is None:
                await update.message.reply_text(f"Terjadi kesalahan saat mencari lokasi. Pastikan kolom {LAT_COLUMN} dan {LNG_COLUMN} ada di spreadsheet.")
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
            map_obj = sheet_handler.generate_map(lat, lng, nearby, LAT_COLUMN, LNG_COLUMN, name_col)
            map_path = sheet_handler.save_map_as_html(map_obj)
            
            # Buat tautan ke peta
            # Catatan: Dalam deployment sebenarnya, Anda perlu mengunggah file HTML
            # ke server web dan membagikan URL. Ini hanya contoh.
            await update.message.reply_text(
                "Untuk melihat peta lokasi, buka file HTML yang dihasilkan."
                # Dalam implementasi sebenarnya, tambahkan tautan ke peta yang dihosting
                # contoh: "Lihat peta: https://your-server.com/maps/map_123.html"
            )
            
        except Exception as e:
            logger.error(f"Error saat memproses koordinat: {e}")
            await update.message.reply_text(f"Terjadi kesalahan: {e}")
    else:
        await update.message.reply_text(
            "Format koordinat tidak valid. Kirim dalam format 'latitude, longitude'.\n"
            "Contoh: -6.1754, 106.8272"
        )

def main():
    """Fungsi utama untuk menjalankan bot."""
    # Dapatkan token dari variabel lingkungan atau ganti dengan token Anda
    token = os.environ.get("TELEGRAM_TOKEN", "GANTI_DENGAN_TOKEN_BOT_ANDA")
    
    if token == "GANTI_DENGAN_TOKEN_BOT_ANDA":
        logger.warning("Token bot Telegram tidak diberikan! Gunakan token yang valid.")
    
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