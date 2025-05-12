from flask import Flask, render_template, request, jsonify, send_file, send_from_directory
import pandas as pd
import folium
from folium.plugins import MarkerCluster
from geopy.distance import geodesic
import os
import uuid
import logging

# Konfigurasi logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Konstanta untuk spreadsheet
SPREADSHEET_URL = "16PFuuwJjL-_hJKuopMJlktlwaNWLnKQdPUMZdX55pkQ"
LAT_COLUMN = "LATITUDE"
LNG_COLUMN = "LONGITUDE"
NAME_COLUMN = "ODP NAME"
DEFAULT_RADIUS = 250  # meter

# Direktori untuk menyimpan file peta
MAPS_DIR = "maps"
if not os.path.exists(MAPS_DIR):
    os.makedirs(MAPS_DIR)

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
    
    def generate_map(self, ref_lat, lng, nearby_df, lat_col, lng_col, name_col=None, radius_meters=DEFAULT_RADIUS):
        """
        Hasilkan peta dengan titik referensi dan lokasi sekitarnya.
        
        Args:
            ref_lat: Latitude titik referensi
            lng: Longitude titik referensi
            nearby_df: DataFrame dengan lokasi sekitarnya
            lat_col: Nama kolom latitude
            lng_col: Nama kolom longitude
            name_col: Nama kolom untuk nama lokasi (opsional)
            radius_meters: Radius pencarian dalam meter
            
        Returns:
            Objek peta folium
        """
        # Buat peta berpusat di titik referensi
        m = folium.Map(location=[ref_lat, lng], zoom_start=16)
        
        # Tambahkan marker untuk titik referensi dengan popup yang lebih informatif
        folium.Marker(
            [ref_lat, lng],
            popup=f"""
            <div style="width: 250px">
                <h4 style="color: #d73027; margin: 0;">Lokasi Anda</h4>
                <hr style="margin: 5px 0">
                <p><b>Koordinat:</b> {ref_lat}, {lng}</p>
                <p><b>Radius pencarian:</b> {radius_meters}m</p>
                <p><b>Lokasi ditemukan:</b> {len(nearby_df) if nearby_df is not None else 0}</p>
            </div>
            """,
            tooltip="Lokasi Anda",
            icon=folium.Icon(color="red", icon="home")
        ).add_to(m)
        
        # Tambahkan circle untuk radius pencarian dengan style yang lebih jelas
        folium.Circle(
            radius=radius_meters,
            location=[ref_lat, lng],
            popup=f"Radius pencarian: {radius_meters}m",
            tooltip=f"Radius {radius_meters}m",
            color="#d73027",
            weight=3,
            fill=True,
            fill_color="#d73027",
            fill_opacity=0.1
        ).add_to(m)
        
        # Tambahkan fitur tambahan jika tersedia
        try:
            from folium.plugins import Fullscreen, MeasureControl, MiniMap
            
            # Tambahkan plugin untuk fullscreen
            Fullscreen(
                position="topright",
                title="Tampilkan peta penuh",
                title_cancel="Keluar dari tampilan penuh"
            ).add_to(m)
            
            # Tambahkan plugin pengukuran jarak
            MeasureControl(
                position="topleft",
                primary_length_unit="meters",
                secondary_length_unit="kilometers"
            ).add_to(m)
            
            # Tambahkan mini-map untuk orientasi yang lebih baik
            minimap = MiniMap(toggle_display=True)
            m.add_child(minimap)
        except ImportError:
            # Plugin tidak tersedia, lanjutkan tanpa fitur tambahan
            pass
        
        # Jika ada lokasi sekitar, tambahkan ke peta
        if nearby_df is not None and not nearby_df.empty:
            # Cari kolom nama jika tidak ditentukan
            if name_col is None:
                # Cari kolom yang namanya mengandung 'nama' atau 'name'
                name_columns = [col for col in nearby_df.columns if 'nama' in col.lower() or 'name' in col.lower()]
                if name_columns:
                    name_col = name_columns[0]
            
            # Buat cluster untuk marker
            marker_cluster = MarkerCluster().add_to(m)
            
            # Tambahkan marker untuk setiap lokasi
            for idx, row in nearby_df.iterrows():
                lat = row[lat_col]
                lng = row[lng_col]
                jarak = row['jarak_meter']
                
                # Tentukan warna berdasarkan jarak
                if jarak < radius_meters * 0.25:
                    icon_color = "green"  # Sangat dekat
                elif jarak < radius_meters * 0.5:
                    icon_color = "blue"   # Dekat
                elif jarak < radius_meters * 0.75:
                    icon_color = "orange" # Sedang
                else:
                    icon_color = "cadetblue" # Jauh
                
                # Siapkan popup dan tooltip
                if name_col and name_col in row:
                    name = row[name_col]
                    tooltip = f"{name} ({jarak:.1f}m)"
                    
                    # Siapkan popup dengan semua informasi
                    color_map = {'green': '4CAF50', 'blue': '2196F3', 'orange': 'FF9800', 'cadetblue': '5F9EA0'}
                    popup_html = f"""
                    <div style="width: 250px">
                        <h4 style="color: #{color_map[icon_color]}; margin: 0;">
                            {name}
                        </h4>
                        <hr style="margin: 5px 0">
                        <p><b>Jarak:</b> {jarak:.1f}m</p>
                        <p><b>Koordinat:</b> {lat}, {lng}</p>
                    """
                    
                    # Tambahkan info tambahan
                    for col in row.index:
                        if col not in [lat_col, lng_col, name_col, 'jarak_meter'] and pd.notna(row[col]):
                            popup_html += f"<p><b>{col}:</b> {row[col]}</p>"
                    
                    popup_html += "</div>"
                else:
                    tooltip = f"Lokasi {idx+1} ({jarak:.1f}m)"
                    
                    # Siapkan popup dengan semua informasi
                    color_map = {'green': '4CAF50', 'blue': '2196F3', 'orange': 'FF9800', 'cadetblue': '5F9EA0'}
                    popup_html = f"""
                    <div style="width: 250px">
                        <h4 style="color: #{color_map[icon_color]}; margin: 0;">
                            Lokasi {idx+1}
                        </h4>
                        <hr style="margin: 5px 0">
                        <p><b>Jarak:</b> {jarak:.1f}m</p>
                        <p><b>Koordinat:</b> {lat}, {lng}</p>
                    """
                    
                    # Tambahkan info tambahan
                    for col in row.index:
                        if col not in [lat_col, lng_col, 'jarak_meter'] and pd.notna(row[col]):
                            popup_html += f"<p><b>{col}:</b> {row[col]}</p>"
                    
                    popup_html += "</div>"
                
                # Tambahkan marker
                folium.Marker(
                    [lat, lng],
                    popup=folium.Popup(popup_html, max_width=300),
                    tooltip=tooltip,
                    icon=folium.Icon(color=icon_color, icon="info-sign")
                ).add_to(marker_cluster)
            
            # Tambahkan legend untuk memahami warna
            legend_html = '''
                <div style="position: fixed; 
                            bottom: 50px; right: 50px; width: 180px; height: 120px; 
                            border:2px solid grey; z-index:9999; font-size:12px;
                            background-color: white; padding: 5px; border-radius: 5px;">
                    <h6 style="margin-top: 0;">Keterangan Warna</h6>
                    <div><i class="fa fa-map-marker" style="color:green"></i> Sangat dekat (0-25%)</div>
                    <div><i class="fa fa-map-marker" style="color:blue"></i> Dekat (25-50%)</div>
                    <div><i class="fa fa-map-marker" style="color:orange"></i> Sedang (50-75%)</div>
                    <div><i class="fa fa-map-marker" style="color:cadetblue"></i> Jauh (75-100%)</div>
                </div>
            '''
            m.get_root().html.add_child(folium.Element(legend_html))
        
        return m
    
    def save_map_as_html(self, map_obj, map_id=None):
        """Simpan objek peta folium ke file HTML."""
        if map_id is None:
            map_id = str(uuid.uuid4())
        
        file_path = os.path.join(MAPS_DIR, f"{map_id}.html")
        map_obj.save(file_path)
        
        return map_id, file_path

@app.route('/')
def index():
    # Redirect ke halaman pencarian ODP langsung
    return send_file('static/search_direct.html')
    
@app.route('/direct')
def direct_search():
    # Redirect ke halaman pencarian ODP langsung
    return send_file('static/search_direct.html')
    
@app.route('/api')
def api_docs():
    # Halaman dokumentasi API
    return send_file('static/search_api.html')
    
@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory('static', filename)
    
@app.route('/image')
def latest_image():
    # Cari file gambar terbaru di direktori odp_images
    odp_image_dir = 'static/odp_images'
    if os.path.exists(odp_image_dir):
        image_files = [f for f in os.listdir(odp_image_dir) if f.endswith('.png')]
        if image_files:
            # Urutkan berdasarkan waktu modifikasi (terbaru dulu)
            latest_image = sorted(image_files, 
                               key=lambda x: os.path.getmtime(os.path.join(odp_image_dir, x)), 
                               reverse=True)[0]
            return send_file(os.path.join(odp_image_dir, latest_image), mimetype='image/png')
    # Fallback jika tidak ada gambar
    return "Tidak ada gambar yang tersedia", 404

@app.route('/search', methods=['GET', 'POST'])
def search():
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
                
            # Buat peta
            map_obj = sheet_handler.generate_map(lat, lng, nearby_locations, LAT_COLUMN, LNG_COLUMN, NAME_COLUMN, radius)
            map_id, _ = sheet_handler.save_map_as_html(map_obj)
            
            # Simpan info peta
            maps_info[map_id] = {
                "lat": lat, 
                "lng": lng, 
                "radius": radius,
                "count": len(nearby_locations)
            }
            
            # Siapkan URL peta dalam berbagai format
            direct_map_url = f"/maps/{map_id}"
            embed_map_url = f"/embed?id={map_id}"
            map_view_url = f"/map_view/{map_id}"
            alternative_map_url = f"/direct_map?id={map_id}"
            pure_map_url = f"/pure_map?id={map_id}"
            simple_map_url = f"/simple_map?id={map_id}"
            
            # Redirect ke halaman hasil
            return jsonify({
                "success": True,
                "map_id": map_id,
                "count": len(nearby_locations),
                "map_url": direct_map_url,
                "embed_url": embed_map_url,
                "map_view_url": map_view_url,
                "alternative_map_url": alternative_map_url,
                "pure_map_url": pure_map_url,
                "simple_map_url": simple_map_url,
                "download_map_url": f"/download_map?id={map_id}",
                "alternate_urls": [
                    direct_map_url,
                    embed_map_url,
                    map_view_url,
                    alternative_map_url, 
                    pure_map_url,
                    simple_map_url,
                    f"/download_map?id={map_id}"
                ]
            })
        except Exception as e:
            logger.error(f"Error saat mencari lokasi: {e}")
            return jsonify({"error": str(e)}), 500
    else:
        return render_template('search.html')

@app.route('/maps/<map_id>')
def show_map(map_id):
    file_path = os.path.join(MAPS_DIR, f"{map_id}.html")
    if os.path.exists(file_path):
        return send_file(file_path)
    else:
        return "Peta tidak ditemukan", 404
        
@app.route('/embed')
def embed_map():
    return send_file("static/embed.html")
    
@app.route('/direct_map')
def direct_map():
    return send_file("static/direct_map.html")
    
@app.route('/pure_map')
def pure_map():
    return send_file("static/pure_map_viewer.html")
    
@app.route('/simple_map')
def simple_map():
    return send_file("static/simple_map.html")
    
@app.route('/download_map')
def download_map():
    return send_file("static/download_map.html")

@app.route('/result/<map_id>')
def show_result(map_id):
    if map_id in maps_info:
        info = maps_info[map_id]
        return render_template('result.html', map_id=map_id, info=info)
    else:
        return "Data hasil pencarian tidak ditemukan", 404
        
@app.route('/map_view/<map_id>')
def map_view(map_id):
    """Menampilkan halaman khusus untuk melihat peta dengan berbagai opsi tautan."""
    if map_id in maps_info:
        info = maps_info[map_id]
        return render_template(
            'map_view.html', 
            map_id=map_id, 
            info=info,
            map_url=f"/maps/{map_id}",
            direct_url=f"/maps/{map_id}",
            embed_url=f"/embed?id={map_id}"
        )
    else:
        return "Data peta tidak ditemukan", 404

@app.route('/bot-types')
def bot_types():
    return render_template('bot_types.html')

@app.route('/hosting')
def hosting():
    return render_template('hosting.html')

@app.route('/languages')
def languages():
    return render_template('languages.html')

@app.route('/database')
def database():
    return render_template('database.html')

@app.route('/environment')
def environment():
    return render_template('environment.html')

@app.route('/examples')
def examples():
    return render_template('examples.html')

@app.route('/ping')
def ping():
    """Endpoint untuk pemantauan uptime. Mengembalikan status aktif dan timestamp."""
    from datetime import datetime
    return jsonify({
        "status": "active",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })

if __name__ == '__main__':
    # Pastikan direktori maps ada
    if not os.path.exists(MAPS_DIR):
        os.makedirs(MAPS_DIR)
    # Jalankan aplikasi
    app.run(host='0.0.0.0', port=5000, debug=True)
