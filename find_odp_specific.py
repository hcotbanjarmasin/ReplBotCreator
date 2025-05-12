import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import os
import uuid
import logging
import re
from geopy.distance import geodesic
import contextily as ctx
from matplotlib.offsetbox import OffsetImage, AnnotationBbox
import matplotlib.patheffects as path_effects

# Konfigurasi logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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

def load_spreadsheet_data(url=SPREADSHEET_URL, sheet_name="Sheet1"):
    """
    Muat data dari spreadsheet.
    """
    try:
        # Ekstrak ID spreadsheet dari URL
        match = re.search(r'/d/([a-zA-Z0-9-_]+)', url)
        if match:
            spreadsheet_id = match.group(1)
        else:
            spreadsheet_id = url  # Anggap URL adalah ID langsung
            
        # Konstruksi URL CSV
        csv_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/gviz/tq?tqx=out:csv&sheet={sheet_name}"
        
        # Muat data dari CSV
        logger.info(f"Mencoba akses dengan nama sheet: {sheet_name}")
        df = pd.read_csv(csv_url)
        logger.info(f"Berhasil memuat {len(df)} baris data dari sheet {sheet_name}")
        
        return df
    except Exception as e:
        logger.error(f"Error saat memuat data: {e}")
        return None

def find_nearby_odps(data, ref_lat, ref_lng, radius_meters=500):
    """
    Temukan ODP dalam radius tertentu.
    """
    try:
        if data is None or data.empty:
            logger.error("Data tidak tersedia")
            return None
            
        # Buat salinan data
        df = data.copy()
        
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

def create_odp_map(ref_lat, ref_lng, nearby_df, radius_meters=500):
    """
    Buat peta dengan ODP yang ditemukan.
    """
    try:
        if nearby_df is None or nearby_df.empty:
            logger.warning("Tidak ada data ODP untuk divisualisasikan")
            return None
            
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
        for idx, row in nearby_df.iterrows():
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
            if NAME_COLUMN and NAME_COLUMN in row:
                name = row[NAME_COLUMN]
                label_text = f"{name}\n{lat:.6f}, {lng:.6f}"
            else:
                label_text = f"ODP #{idx+1}\n{lat:.6f}, {lng:.6f}"
            
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
        ax.set_title(f'ODP dalam Radius {radius_meters}m dari Titik Referensi ({ref_lat:.6f}, {ref_lng:.6f})')
        
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
        map_id = str(uuid.uuid4())
        file_path = os.path.join(ODP_IMAGE_DIR, f"{map_id}.png")
        
        # Simpan gambar dengan resolusi tinggi
        plt.savefig(file_path, bbox_inches='tight', dpi=200)
        plt.close(fig)
        
        return map_id, file_path
        
    except Exception as e:
        logger.error(f"Error saat membuat peta ODP: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None, None

if __name__ == "__main__":
    # Koordinat yang diberikan pengguna
    REF_LAT = -3.292481
    REF_LNG = 114.592482
    
    # Coba dengan beberapa radius yang berbeda
    for radius in [100, 250, 500, 1000]:
        print(f"\nMencari ODP dalam radius {radius}m dari koordinat {REF_LAT}, {REF_LNG}...")
        
        # Muat data
        data = load_spreadsheet_data()
        if data is None:
            print("Gagal memuat data dari spreadsheet.")
            break
            
        # Cari ODP terdekat
        nearby_odps = find_nearby_odps(data, REF_LAT, REF_LNG, radius)
        
        if nearby_odps is not None and not nearby_odps.empty:
            # Tampilkan beberapa hasil pertama
            print(f"Ditemukan {len(nearby_odps)} ODP dalam radius {radius}m:")
            for idx, row in nearby_odps.head(5).iterrows():
                print(f"  {row.get(NAME_COLUMN, f'ODP #{idx}')} - Jarak: {row['jarak_meter']:.1f}m")
                
            if len(nearby_odps) > 5:
                print(f"  ... dan {len(nearby_odps) - 5} ODP lainnya.")
                
            # Buat peta
            map_result = create_odp_map(REF_LAT, REF_LNG, nearby_odps, radius)
            
            if map_result:
                map_id, file_path = map_result
                print(f"Peta berhasil dibuat dan disimpan di: {file_path}")
                break
            else:
                print("Gagal membuat peta ODP.")
        else:
            print(f"Tidak ditemukan ODP dalam radius {radius}m.")
            
    print("\nProses selesai.")