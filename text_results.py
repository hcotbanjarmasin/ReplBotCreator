import os
import pandas as pd
import folium
from geopy.distance import geodesic
import uuid
import logging
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

# Direktori untuk menyimpan file hasil
RESULTS_DIR = "results"
os.makedirs(RESULTS_DIR, exist_ok=True)

# Inisialisasi Flask app
app = Flask(__name__)

# Dictionary untuk menyimpan informasi hasil
results_info = {}

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
            
    def save_results_as_text(self, ref_lat, ref_lng, nearby_df, lat_col, lng_col, name_col=None, radius_meters=DEFAULT_RADIUS):
        """Simpan hasil pencarian sebagai file teks."""
        if nearby_df is None or nearby_df.empty:
            return "Tidak ditemukan lokasi dalam radius yang ditentukan."
            
        # Buat ID unik untuk hasil
        result_id = str(uuid.uuid4())
        
        # Buat konten teks
        lines = [
            "=" * 60,
            f"HASIL PENCARIAN LOKASI DALAM RADIUS {radius_meters}m",
            "=" * 60,
            f"Lokasi Referensi: {ref_lat}, {ref_lng}",
            f"Jumlah Lokasi Ditemukan: {len(nearby_df)}",
            "=" * 60,
            ""
        ]
        
        # Tambahkan informasi untuk setiap lokasi
        for idx, row in nearby_df.iterrows():
            lat = row[lat_col]
            lng = row[lng_col]
            jarak = row['jarak_meter']
            
            # Tentukan kategori jarak
            if jarak < radius_meters * 0.25:
                kategori = "Sangat dekat (0-25%)"
            elif jarak < radius_meters * 0.5:
                kategori = "Dekat (25-50%)"
            elif jarak < radius_meters * 0.75:
                kategori = "Sedang (50-75%)"
            else:
                kategori = "Jauh (75-100%)"
            
            # Tambahkan info lokasi
            if name_col and name_col in row:
                name = row[name_col]
                lines.append(f"Lokasi #{idx+1}: {name}")
            else:
                lines.append(f"Lokasi #{idx+1}")
                
            lines.append(f"  Koordinat: {lat}, {lng}")
            lines.append(f"  Jarak: {jarak:.1f}m ({kategori})")
            
            # Tambahkan kolom tambahan
            for col in row.index:
                if col not in [lat_col, lng_col, name_col, 'jarak_meter'] and pd.notna(row[col]):
                    lines.append(f"  {col}: {row[col]}")
                    
            lines.append("-" * 30)
            
        # Gabungkan semua baris
        text_content = "\n".join(lines)
        
        # Simpan ke file
        file_path = os.path.join(RESULTS_DIR, f"{result_id}.txt")
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(text_content)
            
        # Simpan info
        results_info[result_id] = {
            "lat": ref_lat,
            "lng": ref_lng,
            "radius": radius_meters,
            "count": len(nearby_df),
            "text": text_content
        }
        
        return result_id, file_path, text_content

@app.route('/')
def index():
    return render_template('text_search.html')

@app.route('/text_search', methods=['GET', 'POST'])
def text_search():
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
                
            # Simpan hasil
            result_id, _, text_content = sheet_handler.save_results_as_text(lat, lng, nearby_locations, LAT_COLUMN, LNG_COLUMN, NAME_COLUMN, radius)
            
            # Redirect ke halaman hasil
            return jsonify({
                "success": True,
                "result_id": result_id,
                "count": len(nearby_locations),
                "text": text_content,
                "download_url": f"/results/{result_id}"
            })
        except Exception as e:
            logger.error(f"Error saat mencari lokasi: {e}")
            return jsonify({"error": str(e)}), 500
    else:
        return render_template('text_search.html')

@app.route('/results/<result_id>')
def show_results(result_id):
    if result_id in results_info:
        return render_template('text_result.html', 
                               result_id=result_id,
                               info=results_info[result_id])
    else:
        return "Hasil pencarian tidak ditemukan", 404

@app.route('/download_results/<result_id>')
def download_results(result_id):
    file_path = os.path.join(RESULTS_DIR, f"{result_id}.txt")
    if os.path.exists(file_path):
        return send_file(file_path, as_attachment=True, download_name="hasil_pencarian.txt")
    else:
        return "File hasil tidak ditemukan", 404

if __name__ == '__main__':
    # Pastikan direktori hasil ada
    if not os.path.exists(RESULTS_DIR):
        os.makedirs(RESULTS_DIR)
    # Jalankan aplikasi
    app.run(host='0.0.0.0', port=5001, debug=True)