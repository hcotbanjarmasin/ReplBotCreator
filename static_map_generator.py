import os
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import uuid
import logging
import re
from geopy.distance import geodesic
import contextily as ctx
from io import BytesIO
from PIL import Image
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
IMAGE_DIR = "static/images"
os.makedirs(IMAGE_DIR, exist_ok=True)

# Inisialisasi Flask app
app = Flask(__name__)

# Dictionary untuk menyimpan informasi peta
maps_info = {}

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
            
    def generate_static_map(self, ref_lat, ref_lng, nearby_df, lat_col, lng_col, name_col=None, radius_meters=DEFAULT_RADIUS):
        """
        Hasilkan gambar peta statis dengan matplotlib dan contextily.
        
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
                return None
                
            # Buat figure dan axis
            fig, ax = plt.subplots(figsize=(12, 12), dpi=150)
            
            # Plot titik referensi
            ax.plot(ref_lng, ref_lat, 'ro', markersize=10, label='Lokasi Referensi')
            
            # Gambar lingkaran radius
            radius_degrees = radius_meters / 111000  # Konversi meter ke derajat (perkiraan)
            circle = plt.Circle((ref_lng, ref_lat), radius_degrees, 
                              fill=False, color='red', linewidth=2, alpha=0.7)
            ax.add_patch(circle)
            
            # Plot titik-titik lokasi sekitar dengan warna berdasarkan jarak
            for _, row in nearby_df.iterrows():
                lat = row[lat_col]
                lng = row[lng_col]
                distance = row['jarak_meter']
                
                # Tentukan warna berdasarkan jarak
                if distance < radius_meters * 0.25:
                    color = 'green'  # Sangat dekat
                    label = 'Sangat dekat (0-25%)'
                elif distance < radius_meters * 0.5:
                    color = 'blue'   # Dekat
                    label = 'Dekat (25-50%)'
                elif distance < radius_meters * 0.75:
                    color = 'orange' # Sedang
                    label = 'Sedang (50-75%)'
                else:
                    color = 'purple' # Jauh
                    label = 'Jauh (75-100%)'
                
                ax.plot(lng, lat, 'o', color=color, markersize=8)
                
                # Tambahkan label jika diperlukan
                if name_col and name_col in row:
                    ax.annotate(row[name_col], (lng, lat), fontsize=6, 
                              xytext=(5, 5), textcoords='offset points')
            
            # Set judul dan label
            ax.set_title(f'Lokasi dalam Radius {radius_meters}m dari ({ref_lat:.6f}, {ref_lng:.6f})')
            
            # Tambahkan basemap dari OpenStreetMap
            try:
                ctx.add_basemap(ax, source=ctx.providers.OpenStreetMap.Mapnik)
            except Exception as e:
                logger.warning(f"Tidak dapat menambahkan peta dasar: {e}")
            
            # Tambahkan legenda
            handles, labels = ax.get_legend_handles_labels()
            
            # Tambahkan marker untuk kategori jarak
            green_marker = plt.Line2D([0], [0], marker='o', color='w', markerfacecolor='green', markersize=8)
            blue_marker = plt.Line2D([0], [0], marker='o', color='w', markerfacecolor='blue', markersize=8)
            orange_marker = plt.Line2D([0], [0], marker='o', color='w', markerfacecolor='orange', markersize=8)
            purple_marker = plt.Line2D([0], [0], marker='o', color='w', markerfacecolor='purple', markersize=8)
            
            handles.extend([green_marker, blue_marker, orange_marker, purple_marker])
            labels.extend(['Sangat dekat (0-25%)', 'Dekat (25-50%)', 'Sedang (50-75%)', 'Jauh (75-100%)'])
            
            ax.legend(handles, labels, loc='upper right')
            
            # Tambahkan informasi tambahan
            info_text = f"Jumlah Lokasi: {len(nearby_df)}"
            ax.text(0.02, 0.02, info_text, transform=ax.transAxes, 
                  bbox=dict(facecolor='white', alpha=0.7))
            
            # Buat ID unik untuk file
            map_id = str(uuid.uuid4())
            file_path = os.path.join(IMAGE_DIR, f"{map_id}.png")
            
            # Simpan gambar dengan resolusi tinggi
            plt.savefig(file_path, bbox_inches='tight', dpi=150)
            plt.close(fig)
            
            # Simpan info peta
            maps_info[map_id] = {
                "lat": ref_lat,
                "lng": ref_lng,
                "radius": radius_meters,
                "count": len(nearby_df),
                "image_path": file_path
            }
            
            return map_id, file_path
            
        except Exception as e:
            logger.error(f"Error saat membuat gambar peta: {e}")
            return None, None

@app.route('/')
def index():
    return render_template('static_map_search.html')

@app.route('/static_map_search', methods=['GET', 'POST'])
def static_map_search():
    if request.method == 'POST':
        try:
            # Ambil data dari form
            lat = float(request.form.get('latitude'))
            lng = float(request.form.get('longitude'))
            radius = int(request.form.get('radius', DEFAULT_RADIUS))
            
            # Cari lokasi terdekat
            sheet_handler = SpreadsheetHandler(SPREADSHEET_URL)
            data = sheet_handler.load_from_url()
            
            if data is None:
                return jsonify({"error": "Gagal memuat data dari spreadsheet"}), 500
                
            nearby_locations = sheet_handler.find_nearby_locations(lat, lng, LAT_COLUMN, LNG_COLUMN, radius)
            
            if nearby_locations is None or nearby_locations.empty:
                return jsonify({"message": "Tidak ditemukan lokasi dalam radius yang ditentukan"}), 404
                
            # Buat gambar peta
            map_id, _ = sheet_handler.generate_static_map(lat, lng, nearby_locations, LAT_COLUMN, LNG_COLUMN, NAME_COLUMN, radius)
            
            if map_id is None:
                return jsonify({"error": "Gagal membuat gambar peta"}), 500
                
            return jsonify({
                "success": True,
                "map_id": map_id,
                "count": len(nearby_locations),
                "image_url": f"/static_map/{map_id}"
            })
        except Exception as e:
            logger.error(f"Error saat mencari lokasi: {e}")
            return jsonify({"error": str(e)}), 500
    else:
        return render_template('static_map_search.html')

@app.route('/static_map/<map_id>')
def show_static_map(map_id):
    if map_id in maps_info:
        info = maps_info[map_id]
        image_filename = os.path.basename(info['image_path'])
        return render_template('static_map_result.html', 
                             map_id=map_id, 
                             info=info,
                             image_url=f"/static/images/{image_filename}")
    else:
        return "Peta tidak ditemukan", 404

@app.route('/download_map_image/<map_id>')
def download_map_image(map_id):
    if map_id in maps_info:
        file_path = maps_info[map_id]['image_path']
        if os.path.exists(file_path):
            return send_file(file_path, mimetype='image/png', as_attachment=True, download_name=f"peta_{map_id}.png")
    return "Gambar peta tidak ditemukan", 404

if __name__ == '__main__':
    # Pastikan direktori gambar ada
    if not os.path.exists(IMAGE_DIR):
        os.makedirs(IMAGE_DIR)
    # Jalankan aplikasi
    app.run(host='0.0.0.0', port=5002, debug=True)