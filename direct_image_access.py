#!/usr/bin/env python3
"""
Script untuk mendapatkan gambar ODP secara langsung.
Jalankan dengan parameter koordinat untuk menghasilkan gambar statis.
"""

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
import argparse
import sys

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

def create_odp_map(ref_lat, ref_lng, nearby_df, radius_meters=500, output_filename=None, max_display=50):
    """
    Buat peta dengan ODP yang ditemukan.
    """
    try:
        if nearby_df is None or nearby_df.empty:
            logger.warning("Tidak ada data ODP untuk divisualisasikan")
            return None
            
        # Batasi jumlah ODP yang ditampilkan jika terlalu banyak
        display_df = nearby_df
        if len(nearby_df) > max_display:
            display_df = nearby_df.head(max_display)
            logger.info(f"Membatasi tampilan hingga {max_display} ODP terdekat dari {len(nearby_df)} total")
            print(f"CATATAN: Hanya menampilkan {max_display} ODP terdekat dari total {len(nearby_df)}")
            
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
        title_text = f'ODP dalam Radius {radius_meters}m dari Titik Referensi ({ref_lat:.6f}, {ref_lng:.6f})'
        if len(nearby_df) > max_display:
            title_text += f'\n(Menampilkan {max_display} dari {len(nearby_df)} ODP)'
        ax.set_title(title_text)
        
        # Tambahkan basemap dari OpenStreetMap (non-blocking dengan timeout)
        try:
            import contextily as ctx
            ctx.add_basemap(ax, source=ctx.providers.OpenStreetMap.Mapnik, zoom=16)
        except Exception as e:
            logger.warning(f"Tidak dapat menambahkan peta dasar: {e}")
            # Buat latar belakang putih sebagai alternatif
            ax.set_facecolor('white')
            ax.grid(True, linestyle='--', alpha=0.7)
        
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
        
        # Tentukan nama file output
        if output_filename:
            file_path = os.path.join(ODP_IMAGE_DIR, f"{output_filename}.png")
        else:
            file_path = os.path.join(ODP_IMAGE_DIR, f"odp_map_{uuid.uuid4()}.png")
        
        # Simpan gambar dengan resolusi tinggi
        plt.savefig(file_path, bbox_inches='tight', dpi=200)
        plt.close(fig)
        
        logger.info(f"Peta berhasil disimpan di: {file_path}")
        print(f"Peta berhasil disimpan di: {file_path}")
        
        return file_path
        
    except Exception as e:
        logger.error(f"Error saat membuat peta ODP: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None

def print_odp_info(nearby_odps, max_items=10):
    """Cetak informasi ODP ke konsol"""
    if nearby_odps is None or nearby_odps.empty:
        print("Tidak ditemukan ODP.")
        return
        
    print(f"\nDitemukan {len(nearby_odps)} ODP:")
    print("=" * 50)
    
    for idx, row in nearby_odps.head(max_items).iterrows():
        name = row.get(NAME_COLUMN, f"ODP #{idx+1}")
        distance = row['jarak_meter']
        lat = row[LAT_COLUMN]
        lng = row[LNG_COLUMN]
        avai = row.get(AVAI_COLUMN, "N/A")
        
        print(f"ODP: {name}")
        print(f"Koordinat: {lat}, {lng}")
        print(f"Jarak: {distance:.1f}m")
        print(f"Ketersediaan: {avai}")
        print("-" * 50)
    
    if len(nearby_odps) > max_items:
        print(f"... dan {len(nearby_odps) - max_items} ODP lainnya.")

def main():
    parser = argparse.ArgumentParser(description='Cari ODP berdasarkan koordinat dan hasilkan gambar peta')
    parser.add_argument('lat', type=float, help='Latitude (contoh: -3.292481)')
    parser.add_argument('lng', type=float, help='Longitude (contoh: 114.592482)')
    parser.add_argument('--radius', type=int, default=500, help='Radius pencarian dalam meter (default: 500)')
    parser.add_argument('--output', type=str, help='Nama file output (tanpa ekstensi)')
    parser.add_argument('--max-display', type=int, default=50, help='Maksimal ODP ditampilkan di peta (default: 50)')
    parser.add_argument('--nogrid', action='store_true', help='Tidak tampilkan grid pada peta')
    
    args = parser.parse_args()
    
    print(f"Mencari ODP dalam radius {args.radius}m dari koordinat {args.lat}, {args.lng}...")
    
    # Muat data
    data = load_spreadsheet_data()
    if data is None:
        print("Gagal memuat data. Silakan coba lagi.")
        sys.exit(1)
    
    # Cari ODP terdekat
    nearby_odps = find_nearby_odps(data, args.lat, args.lng, args.radius)
    
    if nearby_odps is None:
        print("Terjadi error saat mencari ODP.")
        sys.exit(1)
        
    if nearby_odps.empty:
        print(f"Tidak ditemukan ODP dalam radius {args.radius}m dari koordinat {args.lat}, {args.lng}.")
        sys.exit(0)
        
    # Cetak informasi ODP
    print_odp_info(nearby_odps)
    
    # Buat peta
    output_name = args.output or f"odp_{args.lat}_{args.lng}_{args.radius}m"
    map_file = create_odp_map(args.lat, args.lng, nearby_odps, args.radius, output_name, args.max_display)
    
    if not map_file:
        print("Gagal membuat peta ODP.")
        sys.exit(1)
        
    print(f"\nProses selesai. Peta berhasil dibuat dan disimpan di: {map_file}")
    
    # Tampilkan perintah untuk melihat gambar
    print("\nUntuk melihat hasil, gunakan perintah berikut:")
    print(f"open {map_file}  # Pada macOS")
    print(f"xdg-open {map_file}  # Pada Linux") 
    print(f"start {map_file}  # Pada Windows")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python direct_image_access.py LAT LNG [--radius RADIUS] [--output OUTPUT_NAME]")
        print("Example: python direct_image_access.py -3.292481 114.592482 --radius 100")
        sys.exit(1)
        
    main()