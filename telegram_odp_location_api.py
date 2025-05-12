import telebot
import logging
import requests
import re
import os
import sys
from telebot import types
import pandas as pd
import matplotlib.pyplot as plt
from geopy.distance import geodesic
import contextily as ctx
import matplotlib.patheffects as path_effects
import uuid
from matplotlib.offsetbox import OffsetImage, AnnotationBbox

# Konfigurasi logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Baca token bot dari lingkungan
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
if not TELEGRAM_TOKEN:
    logger.error("Token Telegram tidak ditemukan! Set variabel lingkungan TELEGRAM_TOKEN.")
    sys.exit(1)

# URL spreadsheet publik
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/16PFuuwJjL-_hJKuopMJlktlwaNWLnKQdPUMZdX55pkQ/edit?gid=1933962208"

# Kolom-kolom di spreadsheet
LAT_COLUMN = "LATITUDE"
LNG_COLUMN = "LONGITUDE"
NAME_COLUMN = "ODP NAME"
AVAI_COLUMN = "AVAI"

# Direktori untuk menyimpan gambar peta
ODP_IMAGE_DIR = "static/odp_images"
os.makedirs(ODP_IMAGE_DIR, exist_ok=True)

# Inisialisasi bot
bot = telebot.TeleBot(TELEGRAM_TOKEN)

# Data spreadsheet cache
spreadsheet_data = None

def load_spreadsheet_data():
    """
    Muat data dari spreadsheet dan simpan ke cache.
    """
    global spreadsheet_data
    try:
        # Ekstrak ID spreadsheet dari URL
        match = re.search(r'/d/([a-zA-Z0-9-_]+)', SPREADSHEET_URL)
        if match:
            spreadsheet_id = match.group(1)
        else:
            spreadsheet_id = SPREADSHEET_URL  # Anggap URL adalah ID langsung
            
        # Konstruksi URL CSV
        csv_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/gviz/tq?tqx=out:csv&sheet=Sheet1"
        
        # Muat data dari CSV
        logger.info(f"Mencoba memuat data dari spreadsheet")
        df = pd.read_csv(csv_url)
        spreadsheet_data = df
        logger.info(f"Berhasil memuat {len(df)} baris data")
        
        return df
    except Exception as e:
        logger.error(f"Error saat memuat data: {e}")
        return None

def find_nearby_odps(ref_lat, ref_lng, radius_meters=500):
    """
    Temukan ODP dalam radius tertentu.
    """
    global spreadsheet_data
    try:
        # Muat data jika belum dimuat
        if spreadsheet_data is None:
            spreadsheet_data = load_spreadsheet_data()
            
        if spreadsheet_data is None or spreadsheet_data.empty:
            logger.error("Data tidak tersedia")
            return None
            
        # Buat salinan data
        df = spreadsheet_data.copy()
        
        # Filter baris dengan data latitude dan longitude yang valid
        df = df.dropna(subset=[LAT_COLUMN, LNG_COLUMN])
        
        # Konversi ke numerik jika string
        df[LAT_COLUMN] = pd.to_numeric(df[LAT_COLUMN], errors='coerce')
        df[LNG_COLUMN] = pd.to_numeric(df[LNG_COLUMN], errors='coerce')
        df = df.dropna(subset=[LAT_COLUMN, LNG_COLUMN])
        
        # Hitung jarak dalam meter
        ref_point = (ref_lat, ref_lng)
        df['jarak_meter'] = df.apply(
            lambda row: geodesic(ref_point, (row[LAT_COLUMN], row[LNG_COLUMN])).meters,
            axis=1
        )
        
        # Filter lokasi dalam radius
        nearby = df[df['jarak_meter'] <= radius_meters].copy()
        
        # Urutkan berdasarkan jarak
        if not nearby.empty:
            nearby = nearby.sort_values('jarak_meter')
            logger.info(f"Ditemukan {len(nearby)} ODP dalam radius {radius_meters}m")
        else:
            logger.info(f"Tidak ditemukan ODP dalam radius {radius_meters}m")
            
        return nearby
    except Exception as e:
        logger.error(f"Error saat mencari ODP terdekat: {e}")
        return None

def create_odp_map(ref_lat, ref_lng, nearby_df, radius_meters=500, with_coords=True, with_name=True, max_display=30):
    """
    Buat peta dengan ODP yang ditemukan.
    """
    try:
        if nearby_df is None or nearby_df.empty:
            logger.warning("Tidak ada data ODP untuk divisualisasikan")
            return None, 0
            
        # Batasi jumlah ODP yang ditampilkan
        display_df = nearby_df
        if len(nearby_df) > max_display:
            display_df = nearby_df.head(max_display)
            logger.info(f"Membatasi tampilan hingga {max_display} ODP terdekat dari {len(nearby_df)} total")
            
        # Buat figure dan axis
        fig, ax = plt.subplots(figsize=(15, 15), dpi=200)
        
        # Plot titik referensi sebagai bintang merah
        ax.plot(ref_lng, ref_lat, 'r*', markersize=15, label='Titik Referensi')
        
        # Tambahkan label referensi dengan koordinat
        ref_text = f"REF: {ref_lat:.6f}, {ref_lng:.6f}"
        t = ax.text(ref_lng, ref_lat, ref_text, 
                 color='red', fontsize=10, fontweight='bold',
                 verticalalignment='bottom',
                 horizontalalignment='center')
        t.set_path_effects([path_effects.withStroke(linewidth=3, foreground='white')])
        
        # Gambar lingkaran radius
        radius_degrees = radius_meters / 111000  # Konversi meter ke derajat (perkiraan)
        circle = plt.Circle((ref_lng, ref_lat), radius_degrees, 
                          fill=False, color='red', linewidth=2, alpha=0.7)
        ax.add_patch(circle)
        
        # Plot ODP dengan koordinat ditampilkan
        for idx, row in display_df.iterrows():
            lat = row[LAT_COLUMN]
            lng = row[LNG_COLUMN]
            distance = row['jarak_meter']
            
            # Tentukan warna berdasarkan jarak
            if distance < radius_meters * 0.25:
                color = 'green'  # Sangat dekat
            elif distance < radius_meters * 0.5:
                color = 'blue'   # Dekat
            elif distance < radius_meters * 0.75:
                color = 'orange' # Sedang
            else:
                color = 'purple' # Jauh
            
            # Plot marker
            ax.plot(lng, lat, 'o', color=color, markersize=10)
            
            # Tambahkan label ODP dengan koordinat
            if with_name and NAME_COLUMN and NAME_COLUMN in row:
                name = row[NAME_COLUMN]
                if with_coords:
                    label_text = f"{name}\n{lat:.6f}, {lng:.6f}"
                else:
                    label_text = f"{name}"
            else:
                if with_coords:
                    label_text = f"ODP #{idx+1}\n{lat:.6f}, {lng:.6f}"
                else:
                    label_text = f"ODP #{idx+1}"
            
            # Tambahkan stroke putih untuk keterbacaan
            t = ax.text(lng, lat, label_text, 
                     color='black', fontsize=8, fontweight='bold',
                     verticalalignment='top',
                     horizontalalignment='center')
            t.set_path_effects([path_effects.withStroke(linewidth=2, foreground='white')])
            
            # Tambahkan info jarak
            dist_txt = f"{distance:.1f}m"
            t2 = ax.text(lng, lat, dist_txt, 
                      color=color, fontsize=8, fontweight='bold',
                      verticalalignment='bottom',
                      horizontalalignment='center')
            t2.set_path_effects([path_effects.withStroke(linewidth=2, foreground='white')])
        
        # Set judul dan label
        title_text = f'ODP dalam Radius {radius_meters}m dari Titik Referensi ({ref_lat:.6f}, {ref_lng:.6f})'
        if len(nearby_df) > max_display:
            title_text += f'\n(Menampilkan {max_display} dari {len(nearby_df)} ODP)'
        ax.set_title(title_text)
        
        # Tambahkan basemap dari OpenStreetMap
        try:
            ctx.add_basemap(ax, source=ctx.providers.OpenStreetMap.Mapnik)
        except Exception as e:
            logger.warning(f"Tidak dapat menambahkan peta dasar: {e}")
        
        # Tambahkan legenda untuk kategori jarak
        green_marker = plt.Line2D([0], [0], marker='o', color='w', markerfacecolor='green', markersize=10)
        blue_marker = plt.Line2D([0], [0], marker='o', color='w', markerfacecolor='blue', markersize=10)
        orange_marker = plt.Line2D([0], [0], marker='o', color='w', markerfacecolor='orange', markersize=10)
        purple_marker = plt.Line2D([0], [0], marker='o', color='w', markerfacecolor='purple', markersize=10)
        ref_marker = plt.Line2D([0], [0], marker='*', color='w', markerfacecolor='red', markersize=15)
        
        ax.legend(
            [green_marker, blue_marker, orange_marker, purple_marker, ref_marker],
            ['Sangat dekat (0-25%)', 'Dekat (25-50%)', 'Sedang (50-75%)', 'Jauh (75-100%)', 'Titik Referensi'],
            loc='upper right'
        )
        
        # Tambahkan informasi jumlah ODP
        info_text = f"Jumlah ODP: {len(nearby_df)}"
        info = ax.text(0.02, 0.02, info_text, transform=ax.transAxes, 
                     fontsize=12, fontweight='bold',
                     bbox=dict(facecolor='white', alpha=0.8, boxstyle='round'))
        
        # Buat ID unik untuk file
        file_path = os.path.join(ODP_IMAGE_DIR, f"tg_{uuid.uuid4()}.png")
        
        # Simpan gambar dengan resolusi tinggi
        plt.savefig(file_path, bbox_inches='tight', dpi=200)
        plt.close(fig)
        
        return file_path, len(nearby_df)
        
    except Exception as e:
        logger.error(f"Error saat membuat peta ODP: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None, 0

def format_odp_list(nearby_odps, max_items=10):
    """Format daftar ODP untuk teks pesan"""
    result = []
    for idx, row in nearby_odps.head(max_items).iterrows():
        name = row.get(NAME_COLUMN, f"ODP #{idx+1}")
        distance = row['jarak_meter']
        lat = row[LAT_COLUMN]
        lng = row[LNG_COLUMN]
        result.append(f"🔹 {name} - {distance:.1f}m\n   📍 {lat}, {lng}")
    
    if len(nearby_odps) > max_items:
        result.append(f"... dan {len(nearby_odps) - max_items} ODP lainnya.")
    
    return "\n".join(result)

@bot.message_handler(commands=['start'])
def start(message):
    """Kirim pesan selamat datang."""
    bot.reply_to(message, 
                 f"👋 Halo {message.from_user.first_name}!\n\n"
                 f"Saya adalah bot pencari ODP berdasarkan koordinat.\n\n"
                 f"Gunakan perintah /help untuk melihat cara penggunaan.")

@bot.message_handler(commands=['help'])
def help_command(message):
    """Kirim informasi bantuan."""
    help_text = (
        "🤖 *Bot Pencari ODP*\n\n"
        "Bot ini membantu menemukan ODP (Optical Distribution Point) yang berada dalam radius tertentu dari koordinat yang diberikan.\n\n"
        "*Cara Penggunaan:*\n"
        "1. Kirim lokasi Anda dengan mengklik tombol 📎 dan pilih *Location*\n"
        "2. Kirim koordinat dengan format: `-3.292481, 114.592482`\n"
        "3. Gunakan perintah `/cari -3.292481 114.592482 [radius]`\n\n"
        "*Perintah Tersedia:*\n"
        "/cari <lat> <lng> [radius] - Mencari ODP di sekitar koordinat tertentu\n"
        "/radius [nilai] - Melihat atau mengubah radius pencarian (default: 500m)\n"
        "/contoh - Menampilkan beberapa contoh koordinat\n"
        "/status - Melihat status bot dan data\n"
        "/help - Menampilkan bantuan ini\n\n"
        "*Contoh:*\n"
        "`/cari -3.292481 114.592482 100`\n"
        "Akan mencari ODP dalam radius 100m dari koordinat tersebut."
    )
    
    bot.send_message(message.chat.id, help_text, parse_mode='Markdown')

@bot.message_handler(commands=['radius'])
def radius_command(message):
    """Melihat atau mengubah radius pencarian."""
    args = message.text.split()
    
    # Default radius
    default_radius = 500
    
    if len(args) == 1:
        # Tidak ada argumen, tampilkan radius default
        bot.reply_to(message, f"🔍 Radius pencarian saat ini: {default_radius}m\n\nUntuk mengubah, gunakan format:\n/radius [nilai dalam meter]")
    else:
        try:
            # Coba parse nilai radius
            radius = int(args[1])
            if radius < 10:
                radius = 10
                bot.reply_to(message, f"⚠️ Radius terlalu kecil, diatur ke minimum 10m")
            elif radius > 10000:
                radius = 10000
                bot.reply_to(message, f"⚠️ Radius terlalu besar, diatur ke maksimum 10000m")
            
            bot.reply_to(message, f"✅ Radius pencarian diatur ke {radius}m")
        except ValueError:
            # Nilai radius tidak valid
            bot.reply_to(message, f"❌ Nilai radius tidak valid. Gunakan angka, misalnya: /radius 250")

@bot.message_handler(commands=['contoh'])
def examples_command(message):
    """Menampilkan contoh koordinat."""
    examples = (
        "📍 *Contoh Koordinat ODP:*\n\n"
        "1. ODP di Sekitar BJM-FAP/012:\n"
        "   `-3.292481, 114.592482`\n"
        "   `/cari -3.292481 114.592482 100`\n\n"
        "2. ODP di Area ODP-PLE-FM/002:\n"
        "   `-3.8159, 114.7505`\n"
        "   `/cari -3.8159 114.7505 500`\n\n"
        "3. ODP di Area GCL-BJM-F01/001:\n"
        "   `-3.3251, 114.5917`\n"
        "   `/cari -3.3251 114.5917 750`\n\n"
        "4. Area dengan Banyak ODP:\n"
        "   `-3.3219, 114.6034`\n"
        "   `/cari -3.3219 114.6034 1500`\n\n"
        "Klik salah satu perintah di atas untuk mencoba, atau kirim koordinat dengan format `latitude, longitude`"
    )
    
    bot.send_message(message.chat.id, examples, parse_mode='Markdown')

@bot.message_handler(commands=['status'])
def status_command(message):
    """Menampilkan status bot dan data."""
    global spreadsheet_data
    
    # Cek data spreadsheet
    if spreadsheet_data is None:
        data = load_spreadsheet_data()
        if data is None:
            bot.reply_to(message, "❌ Status: Data tidak tersedia.\nCoba muat ulang dengan /reload")
            return
    
    # Tampilkan status
    status_text = (
        "✅ *Status Bot:* Bot berjalan\n"
        f"📊 *Jumlah Data:* {len(spreadsheet_data)} ODP\n"
        f"🔄 *Terakhir Dimuat:* Terbaru\n\n"
        f"💡 Gunakan perintah /help untuk bantuan."
    )
    
    bot.send_message(message.chat.id, status_text, parse_mode='Markdown')

@bot.message_handler(commands=['reload'])
def reload_command(message):
    """Muat ulang data dari spreadsheet."""
    bot.send_message(message.chat.id, "🔄 Memuat ulang data dari spreadsheet...")
    
    # Muat ulang data
    data = load_spreadsheet_data()
    
    if data is not None:
        bot.send_message(message.chat.id, f"✅ Berhasil memuat {len(data)} baris data.")
    else:
        bot.send_message(message.chat.id, f"❌ Gagal memuat data dari spreadsheet.")

@bot.message_handler(commands=['cari'])
def search_command(message):
    """Mencari ODP berdasarkan koordinat."""
    args = message.text.split()
    
    if len(args) < 3:
        bot.reply_to(message, "❌ Format tidak valid.\nGunakan:\n/cari <lat> <lng> [radius]")
        return
    
    try:
        # Parse koordinat dan radius
        lat = float(args[1])
        lng = float(args[2])
        radius = 500  # Default
        
        if len(args) >= 4:
            radius = int(args[3])
            
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
        map_file, count = create_odp_map(lat, lng, nearby_odps, radius)
        
        if map_file:
            caption = f"🗺️ Peta {count} ODP dalam radius {radius}m"
            with open(map_file, 'rb') as photo:
                bot.send_photo(message.chat.id, photo, caption=caption)
        else:
            bot.send_message(message.chat.id, "❌ Gagal membuat peta ODP.")
            
    except ValueError:
        bot.reply_to(message, "❌ Format koordinat tidak valid.\nGunakan angka untuk latitude dan longitude.")
    except Exception as e:
        logger.error(f"Error: {e}")
        bot.reply_to(message, f"❌ Terjadi error: {str(e)}")

@bot.message_handler(content_types=['location'])
def handle_location(message):
    """Tangani saat pengguna mengirim lokasi."""
    lat = message.location.latitude
    lng = message.location.longitude
    radius = 500  # Default
    
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
    
    # Buat dan kirim peta
    map_file, count = create_odp_map(lat, lng, nearby_odps, radius)
    
    if map_file:
        caption = f"🗺️ Peta {count} ODP dalam radius {radius}m dari lokasi Anda"
        with open(map_file, 'rb') as photo:
            bot.send_photo(message.chat.id, photo, caption=caption)
    else:
        bot.send_message(message.chat.id, "❌ Gagal membuat peta ODP.")

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
        radius = 500  # Default
        
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
        map_file, count = create_odp_map(lat, lng, nearby_odps, radius)
        
        if map_file:
            caption = f"🗺️ Peta {count} ODP dalam radius {radius}m"
            with open(map_file, 'rb') as photo:
                bot.send_photo(message.chat.id, photo, caption=caption)
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