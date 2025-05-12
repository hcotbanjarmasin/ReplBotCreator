import os
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import uuid
import logging
import re
from geopy.distance import geodesic
import contextily as ctx
from matplotlib.offsetbox import OffsetImage, AnnotationBbox
import matplotlib.patheffects as path_effects
from flask import Flask, request, jsonify, render_template, send_file

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

# Jarak radius pencarian dalam meter
DEFAULT_RADIUS = 250

# Direktori untuk menyimpan gambar peta
ODP_IMAGE_DIR = "static/odp_images"
os.makedirs(ODP_IMAGE_DIR, exist_ok=True)

# Inisialisasi Flask app
app = Flask(__name__)

# Dictionary untuk menyimpan informasi peta
odp_maps_info = {}

class ODPMapGenerator:
    def __init__(self, url=None):
        """Inisialisasi generator peta ODP."""
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
            if url is None:
                url = self.url
                
            if url is None:
                raise ValueError("URL spreadsheet tidak ditentukan")
                
            # Ekstrak ID spreadsheet dari URL
            match = re.search(r'/d/([a-zA-Z0-9-_]+)', url)
            if match:
                spreadsheet_id = match.group(1)
            else:
                spreadsheet_id = url  # Anggap URL adalah ID langsung jika bukan format URL lengkap
                
            # Konstruksi URL CSV
            csv_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/gviz/tq?tqx=out:csv&sheet={sheet_name}"
            
            # Muat data dari CSV
            logger.info(f"Mencoba akses dengan nama sheet: {sheet_name}")
            df = pd.read_csv(csv_url)
            logger.info(f"Berhasil memuat {len(df)} baris data dari sheet {sheet_name}")
            
            # Simpan data
            self.data = df
            return df
            
        except Exception as e:
            logger.error(f"Error saat memuat data dari spreadsheet: {e}")
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
        try:
            if self.data is None:
                raise ValueError("Data belum dimuat")
                
            # Pastikan kolom latitude dan longitude ada
            if lat_col not in self.data.columns or lng_col not in self.data.columns:
                raise ValueError(f"Kolom {lat_col} atau {lng_col} tidak ditemukan di data")
                
            # Buat salinan data
            df = self.data.copy()
            
            # Filter baris dengan data latitude dan longitude yang valid
            df = df.dropna(subset=[lat_col, lng_col])
            
            # Konversi ke numerik jika string
            df[lat_col] = pd.to_numeric(df[lat_col], errors='coerce')
            df[lng_col] = pd.to_numeric(df[lng_col], errors='coerce')
            df = df.dropna(subset=[lat_col, lng_col])
            
            # Hitung jarak dalam meter
            ref_point = (lat, lng)
            df['jarak_meter'] = df.apply(
                lambda row: geodesic(ref_point, (row[lat_col], row[lng_col])).meters,
                axis=1
            )
            
            # Filter lokasi dalam radius
            nearby = df[df['jarak_meter'] <= radius_meters].copy()
            
            # Urutkan berdasarkan jarak
            if not nearby.empty:
                nearby = nearby.sort_values('jarak_meter')
                
            return nearby
            
        except Exception as e:
            logger.error(f"Error saat mencari lokasi terdekat: {e}")
            return None
            
    def create_odp_map(self, ref_lat, ref_lng, nearby_df, lat_col, lng_col, name_col=None, radius_meters=DEFAULT_RADIUS):
        """
        Hasilkan peta ODP dengan koordinat ditampilkan pada marker.
        
        Args:
            ref_lat: Latitude titik referensi
            ref_lng: Longitude titik referensi
            nearby_df: DataFrame dengan lokasi sekitarnya
            lat_col: Nama kolom latitude
            lng_col: Nama kolom longitude
            name_col: Nama kolom untuk nama lokasi (opsional)
            radius_meters: Radius pencarian dalam meter
            
        Returns:
            Path ke file gambar yang dihasilkan
        """
        try:
            if nearby_df is None or nearby_df.empty:
                return None, None
                
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
                lat = row[lat_col]
                lng = row[lng_col]
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
                if name_col and name_col in row:
                    name = row[name_col]
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
            ax.set_title(f'ODP dalam Radius {radius_meters}m dari Titik Referensi')
            
            # Tambahkan basemap dari OpenStreetMap dengan zoom level yang valid
            try:
                # Gunakan import terpisah dan zoom level yang valid (1-19)
                import contextily.tile as ctx_tile
                # Tetapkan zoom level yang optimal (15) untuk mencegah kesalahan inferensi yang menghasilkan level 33
                ctx.add_basemap(
                    ax, 
                    source=ctx_tile.providers['OpenStreetMap']['Mapnik'], 
                    zoom=15
                )
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
            
            # Simpan info peta
            odp_maps_info[map_id] = {
                "lat": ref_lat,
                "lng": ref_lng,
                "radius": radius_meters,
                "count": len(nearby_df),
                "image_path": file_path
            }
            
            return map_id, file_path
            
        except Exception as e:
            logger.error(f"Error saat membuat peta ODP: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None, None

def find_odps(lat, lng, radius=DEFAULT_RADIUS):
    """
    Fungsi untuk mencari ODP dan menghasilkan peta.
    
    Args:
        lat: Latitude titik referensi
        lng: Longitude titik referensi
        radius: Radius pencarian dalam meter
    
    Returns:
        Tuple (map_id, file_path, count) atau None jika gagal
    """
    try:
        # Cari lokasi terdekat
        generator = ODPMapGenerator(SPREADSHEET_URL)
        data = generator.load_from_url()
        
        if data is None:
            logger.error("Gagal memuat data dari spreadsheet")
            return None
            
        nearby_locations = generator.find_nearby_locations(lat, lng, LAT_COLUMN, LNG_COLUMN, radius)
        
        if nearby_locations is None or nearby_locations.empty:
            logger.info("Tidak ditemukan ODP dalam radius yang ditentukan")
            return None
            
        # Buat gambar peta
        map_id, file_path = generator.create_odp_map(lat, lng, nearby_locations, LAT_COLUMN, LNG_COLUMN, NAME_COLUMN, radius)
        
        if map_id is None:
            logger.error("Gagal membuat gambar peta ODP")
            return None
            
        return map_id, file_path, len(nearby_locations)
        
    except Exception as e:
        logger.error(f"Error dalam find_odps: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None

if __name__ == "__main__":
    # Koordinat di Kalimantan berdasarkan data sampel
    locations = [
        # Berdasarkan sampel data
        {"lat": -3.8159, "lng": 114.7505, "radius": 500, "name": "ODP-PLE-FM/002"},
        {"lat": -3.3251, "lng": 114.5917, "radius": 750, "name": "GCL-BJM-F01/001"},
        {"lat": -3.4908, "lng": 114.8299, "radius": 1000, "name": "BBR-01JAKSA-G01"},
        # Area utara
        {"lat": -3.1441, "lng": 114.5007, "radius": 1000, "name": "GCL-KYG-F12/016"},
        # Area dengan cluster
        {"lat": -3.3219, "lng": 114.6034, "radius": 1500, "name": "GCL-ULI-F29/004"}
    ]
    
    success = False
    
    # Coba beberapa lokasi sampai berhasil
    for loc in locations:
        print(f"\nMencoba lokasi: {loc['name']} ({loc['lat']}, {loc['lng']}) dengan radius {loc['radius']}m")
        result = find_odps(loc['lat'], loc['lng'], loc['radius'])
        
        if result:
            map_id, file_path, count = result
            print(f"BERHASIL: Menemukan {count} ODP di sekitar {loc['name']}.")
            print(f"Gambar peta disimpan di: {file_path}")
            success = True
            break
    
    if not success:
        print("\nTIDAK BERHASIL menemukan ODP dari semua lokasi yang dicoba.")