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
from flask import Flask, request, send_file, jsonify
import argparse

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

app = Flask(__name__)

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

def create_odp_map(ref_lat, ref_lng, nearby_df, radius_meters=500, with_coords=True, with_name=True, max_display=50):
    """
    Buat peta dengan ODP yang ditemukan.
    """
    try:
        if nearby_df is None or nearby_df.empty:
            logger.warning("Tidak ada data ODP untuk divisualisasikan")
            return None, None, 0
            
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
        map_id = str(uuid.uuid4())
        file_path = os.path.join(ODP_IMAGE_DIR, f"{map_id}.png")
        
        # Simpan gambar dengan resolusi tinggi
        plt.savefig(file_path, bbox_inches='tight', dpi=200)
        plt.close(fig)
        
        return map_id, file_path, len(nearby_df)
        
    except Exception as e:
        logger.error(f"Error saat membuat peta ODP: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None, None, 0

@app.route('/search_odp')
def search_odp_route():
    """API endpoint untuk mencari ODP"""
    try:
        # Dapatkan parameter dari URL
        lat = float(request.args.get('lat', -3.292481))
        lng = float(request.args.get('lng', 114.592482))
        radius = int(request.args.get('radius', 500))
        with_coords = request.args.get('coords', 'true').lower() == 'true'
        with_name = request.args.get('name', 'true').lower() == 'true'
        max_display = int(request.args.get('max', 50))
        
        # Parameter tambahan 
        as_json = request.args.get('json', 'false').lower() == 'true'
        
        # Muat data
        data = load_spreadsheet_data()
        if data is None:
            return jsonify({"error": "Gagal memuat data dari spreadsheet"}), 500
            
        # Cari ODP terdekat
        nearby_odps = find_nearby_odps(data, lat, lng, radius)
        
        if nearby_odps is None or nearby_odps.empty:
            # Kembalikan respons sesuai format yang diminta
            if as_json:
                return jsonify({
                    "status": "not_found",
                    "message": f"Tidak ditemukan ODP dalam radius {radius}m dari koordinat {lat}, {lng}",
                    "count": 0,
                    "coordinates": {"lat": lat, "lng": lng},
                    "radius": radius
                })
            else:
                # Buat peta kosong
                map_id, file_path, _ = create_odp_map(lat, lng, pd.DataFrame(), radius, with_coords, with_name, max_display)
                return send_file(file_path, mimetype='image/png')
                
        # Buat peta
        map_id, file_path, count = create_odp_map(lat, lng, nearby_odps, radius, with_coords, with_name, max_display)
        
        # Kembalikan hasil sesuai format yang diminta
        if as_json:
            # Siapkan data ODP untuk respons JSON
            odp_list = []
            for _, row in nearby_odps.iterrows():
                odp_data = {
                    "name": row.get(NAME_COLUMN, f"ODP #{_+1}"),
                    "latitude": row[LAT_COLUMN],
                    "longitude": row[LNG_COLUMN],
                    "distance": row['jarak_meter'],
                    "availability": row.get(AVAI_COLUMN, "N/A")
                }
                odp_list.append(odp_data)
                
            # Kembalikan respons JSON
            return jsonify({
                "status": "success",
                "count": count,
                "coordinates": {"lat": lat, "lng": lng},
                "radius": radius,
                "odps": odp_list,
                "image_path": file_path,
                "map_id": map_id
            })
        else:
            # Kembalikan gambar peta
            return send_file(file_path, mimetype='image/png')
    
    except Exception as e:
        logger.error(f"Error saat memproses permintaan: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500

@app.route('/')
def index():
    """Halaman utama dengan form untuk mencari ODP"""
    return '''
    <!DOCTYPE html>
    <html lang="id">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Pencarian ODP</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                max-width: 800px;
                margin: 0 auto;
                padding: 20px;
            }
            .form-group {
                margin-bottom: 15px;
            }
            label {
                display: block;
                margin-bottom: 5px;
                font-weight: bold;
            }
            input, select {
                width: 100%;
                padding: 8px;
                border: 1px solid #ddd;
                border-radius: 4px;
            }
            button {
                background-color: #4CAF50;
                color: white;
                padding: 10px 15px;
                border: none;
                border-radius: 4px;
                cursor: pointer;
            }
            .result {
                margin-top: 20px;
            }
            img {
                max-width: 100%;
                height: auto;
                border: 1px solid #ddd;
                border-radius: 5px;
            }
            .examples {
                margin-top: 20px;
                padding: 15px;
                background-color: #f8f9fa;
                border-radius: 5px;
            }
            .examples a {
                display: block;
                margin-bottom: 5px;
                color: #1a73e8;
                text-decoration: none;
            }
            .examples a:hover {
                text-decoration: underline;
            }
        </style>
    </head>
    <body>
        <h1>Pencarian ODP</h1>
        <p>Masukkan koordinat untuk mencari ODP dalam radius tertentu.</p>
        
        <form id="searchForm" action="/search_odp" method="get">
            <div class="form-group">
                <label for="lat">Latitude:</label>
                <input type="number" id="lat" name="lat" step="0.000001" value="-3.292481" required>
            </div>
            
            <div class="form-group">
                <label for="lng">Longitude:</label>
                <input type="number" id="lng" name="lng" step="0.000001" value="114.592482" required>
            </div>
            
            <div class="form-group">
                <label for="radius">Radius Pencarian (meter):</label>
                <input type="number" id="radius" name="radius" min="10" max="10000" value="500">
            </div>
            
            <div class="form-group">
                <label for="max">Maksimal ODP yang Ditampilkan:</label>
                <input type="number" id="max" name="max" min="5" max="100" value="50">
            </div>
            
            <div class="form-group">
                <label>Opsi Tampilan:</label>
                <div>
                    <input type="checkbox" id="coords" name="coords" value="true" checked>
                    <label for="coords" style="display: inline;">Tampilkan koordinat</label>
                </div>
                <div>
                    <input type="checkbox" id="name" name="name" value="true" checked>
                    <label for="name" style="display: inline;">Tampilkan nama ODP</label>
                </div>
            </div>
            
            <button type="submit">Cari ODP</button>
        </form>
        
        <div class="examples">
            <h3>Contoh Koordinat:</h3>
            <a href="/search_odp?lat=-3.292481&lng=114.592482&radius=100">ODP di sekitar -3.292481, 114.592482 (radius 100m)</a>
            <a href="/search_odp?lat=-3.8159&lng=114.7505&radius=500">ODP di sekitar ODP-PLE-FM/002 (-3.8159, 114.7505) (radius 500m)</a>
            <a href="/search_odp?lat=-3.3251&lng=114.5917&radius=750">ODP di sekitar GCL-BJM-F01/001 (-3.3251, 114.5917) (radius 750m)</a>
            <a href="/search_odp?lat=-3.4908&lng=114.8299&radius=1000">ODP di sekitar BBR-01JAKSA-G01 (-3.4908, 114.8299) (radius 1000m)</a>
            <a href="/search_odp?lat=-3.3219&lng=114.6034&radius=1500&max=100">Area dengan banyak ODP (-3.3219, 114.6034) (radius 1500m, max 100)</a>
        </div>
        
        <div class="result" id="result"></div>
        
        <script>
            document.getElementById('searchForm').addEventListener('submit', function(e) {
                e.preventDefault();
                var form = this;
                var url = form.action + '?' + new URLSearchParams(new FormData(form)).toString();
                
                // Tampilkan gambar hasil
                var resultDiv = document.getElementById('result');
                resultDiv.innerHTML = '<h2>Hasil Pencarian</h2><img src="' + url + '" alt="Peta ODP">';
                
                // Scroll ke hasil
                resultDiv.scrollIntoView({behavior: 'smooth'});
            });
        </script>
    </body>
    </html>
    '''

def run_server():
    """Jalankan server"""
    app.run(host='0.0.0.0', port=5001, debug=True)

def find_odp_cli(lat, lng, radius=500, output=None):
    """Versi CLI untuk pencarian ODP"""
    # Muat data
    data = load_spreadsheet_data()
    if data is None:
        print("Gagal memuat data dari spreadsheet.")
        return False
        
    # Cari ODP terdekat
    nearby_odps = find_nearby_odps(data, lat, lng, radius)
    
    if nearby_odps is None or nearby_odps.empty:
        print(f"Tidak ditemukan ODP dalam radius {radius}m dari koordinat {lat}, {lng}")
        return False
        
    # Tampilkan beberapa hasil pertama
    print(f"Ditemukan {len(nearby_odps)} ODP dalam radius {radius}m:")
    for idx, row in nearby_odps.head(5).iterrows():
        print(f"  {row.get(NAME_COLUMN, f'ODP #{idx}')} - Jarak: {row['jarak_meter']:.1f}m")
        
    if len(nearby_odps) > 5:
        print(f"  ... dan {len(nearby_odps) - 5} ODP lainnya.")
        
    # Buat peta
    map_id, file_path, _ = create_odp_map(lat, lng, nearby_odps, radius)
    
    if map_id:
        if output:
            file_path = os.path.join(ODP_IMAGE_DIR, f"{output}.png")
            plt.savefig(file_path, bbox_inches='tight', dpi=200)
        
        print(f"Peta berhasil dibuat dan disimpan di: {file_path}")
        return True
    else:
        print("Gagal membuat peta ODP.")
        return False

@app.route('/ping')
def ping():
    """Endpoint untuk pemantauan uptime."""
    from datetime import datetime
    return jsonify({
        "status": "active",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })

if __name__ == "__main__":
    # Parse argumen command line
    parser = argparse.ArgumentParser(description='Pencarian ODP berdasarkan koordinat')
    parser.add_argument('--lat', type=float, help='Latitude titik referensi')
    parser.add_argument('--lng', type=float, help='Longitude titik referensi')
    parser.add_argument('--radius', type=int, default=500, help='Radius pencarian dalam meter (default: 500)')
    parser.add_argument('--output', type=str, help='Nama file output (tanpa ekstensi)')
    parser.add_argument('--server', action='store_true', help='Jalankan sebagai server web')
    
    args = parser.parse_args()
    
    # Jalankan sebagai server web atau CLI
    if args.server:
        print("Menjalankan server pencarian ODP di port 5001...")
        run_server()
    elif args.lat is not None and args.lng is not None:
        find_odp_cli(args.lat, args.lng, args.radius, args.output)
    else:
        print("Gunakan --lat dan --lng untuk mencari ODP, atau --server untuk menjalankan server web.")
        print("Contoh: python search_odp.py --lat -3.292481 --lng 114.592482 --radius 100")
        print("        python search_odp.py --server")