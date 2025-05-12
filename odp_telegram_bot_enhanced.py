#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Bot Telegram untuk pencarian dan visualisasi ODP

Bot ini mengakses data ODP dari spreadsheet dan menampilkan
lokasi ODP dalam radius tertentu dalam bentuk peta.
Versi yang ditingkatkan dengan tampilan satelit Google Hybrid
yang menampilkan jalan dan bangunan dengan jelas.
"""

import os
import re
import uuid
import time
import math
import logging
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')  # Set backend non-interaktif sebelum import plt
import matplotlib.pyplot as plt
import matplotlib.patheffects as path_effects
import contextily as ctx
import openrouteservice as ors
import json
import sys
import requests
from io import BytesIO
from PIL import Image
from geopy.distance import geodesic
from telebot import TeleBot, types
import matplotlib.patches as mpatches
import matplotlib.lines as mlines
from matplotlib.patches import Circle

# Konfigurasi logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Baca token bot dan API keys dari lingkungan
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
ORS_API_KEY = os.environ.get('OPENROUTESERVICE_API_KEY')
MAPBOX_ACCESS_TOKEN = os.environ.get('MAPBOX_ACCESS_TOKEN')

# Inisialisasi API routing
ors_client = None
use_mapbox = False

# Coba inisialisasi OpenRouteService jika API key tersedia
if ORS_API_KEY:
    try:
        ors_client = ors.Client(key=ORS_API_KEY)
        logger.info("Berhasil inisialisasi OpenRouteService API")
    except Exception as e:
        logger.error(f"Gagal inisialisasi OpenRouteService API: {e}")

# Cek apakah Mapbox token tersedia
if MAPBOX_ACCESS_TOKEN:
    use_mapbox = True
    logger.info("Mapbox Access Token tersedia dan akan digunakan sebagai alternatif jika diperlukan")
else:
    logger.warning("MAPBOX_ACCESS_TOKEN tidak ditemukan dalam environment variables")

# Cache untuk menyimpan rute yang sudah dihitung
route_cache = {}

# Periksa apakah token Telegram tersedia
if not TELEGRAM_TOKEN:
    logger.error("Token Telegram tidak ditemukan! Set variabel lingkungan TELEGRAM_TOKEN.")
    raise ValueError("Token Telegram tidak ditemukan")

# URL spreadsheet publik
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/16PFuuwJjL-_hJKuopMJlktlwaNWLnKQdPUMZdX55pkQ/edit"
# Gunakan Sheet1 yang sudah diperbarui

# Kolom-kolom di spreadsheet
LAT_COLUMN = "LATITUDE"
LNG_COLUMN = "LONGITUDE"
NAME_COLUMN = "ODP NAME"
AVAI_COLUMN = "AVAI"
KATEGORI_COLUMN = "KATEGORI ODP"  # Kolom kategori ODP (HIJAU, KUNING, MERAH, HITAM)

# Default radius
DEFAULT_RADIUS = 250  # meter
SEARCH_MARGIN = 5  # Margin extra untuk mengatasi masalah presisi perhitungan jarak

# Direktori untuk menyimpan gambar peta
ODP_IMAGE_DIR = "static/odp_images"
os.makedirs(ODP_IMAGE_DIR, exist_ok=True)

# Inisialisasi bot
bot = TeleBot(TELEGRAM_TOKEN)

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
            
        # Ekstrak GID (sheet ID) jika ada di URL
        gid_match = re.search(r'gid=(\d+)', SPREADSHEET_URL)
        gid = gid_match.group(1) if gid_match else None
        
        # Konstruksi URL CSV dengan gid yang benar
        if gid:
            # Gunakan export=csv dengan gid untuk mendapatkan sheet yang tepat
            csv_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/export?format=csv&gid={gid}"
            logger.info(f"Mencoba memuat data dari spreadsheet dengan GID: {gid}")
        else:
            # Fallback ke Sheet1 jika tidak ada gid
            csv_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/gviz/tq?tqx=out:csv&sheet=Sheet1"
            logger.info(f"Mencoba memuat data dari Sheet1 (default)")
        
        # Muat data dari CSV
        df = pd.read_csv(csv_url)
        
        # Periksa apakah data berisi kolom yang dibutuhkan
        required_columns = [LAT_COLUMN, LNG_COLUMN, NAME_COLUMN]
        for col in required_columns:
            if col not in df.columns:
                logger.error(f"Kolom {col} tidak ditemukan dalam spreadsheet!")
                return None
                
        # Konversi kolom latitude dan longitude ke numerik
        df[LAT_COLUMN] = pd.to_numeric(df[LAT_COLUMN], errors='coerce')
        df[LNG_COLUMN] = pd.to_numeric(df[LNG_COLUMN], errors='coerce')
        
        # Buang baris dengan nilai latitude atau longitude yang tidak valid
        df = df.dropna(subset=[LAT_COLUMN, LNG_COLUMN])
        
        spreadsheet_data = df
        logger.info(f"Berhasil memuat {len(df)} baris data valid")
        
        return df
    except Exception as e:
        logger.error(f"Error saat memuat data: {e}")
        return None

def calculate_route_distance(ref_lat, ref_lng, dest_lat, dest_lng):
    """
    Hitung jarak berdasarkan rute jalan menggunakan OpenRouteService API atau Mapbox API.
    Termasuk caching untuk meminimalkan API calls.
    
    Returns:
        tuple: (jarak_meter, koordinat_rute) atau (None, None) jika gagal
    """
    global ors_client, route_cache, use_mapbox, MAPBOX_ACCESS_TOKEN
    
    # Buat key cache dari koordinat
    cache_key = f"{ref_lat:.6f}_{ref_lng:.6f}_{dest_lat:.6f}_{dest_lng:.6f}"
    
    # Cek apakah rute sudah ada di cache
    if cache_key in route_cache:
        return route_cache[cache_key]
    
    # Coba gunakan OpenRouteService
    if ors_client is not None:
        try:
            # Hitung rute menggunakan ORS API
            coords = [[ref_lng, ref_lat], [dest_lng, dest_lat]]
            routes = ors_client.directions(
                coordinates=coords,
                profile='driving-car',  # Opsi: driving-car, foot-walking, cycling-regular
                format='geojson',
                preference='shortest',  # Gunakan rute terpendek (bukan tercepat)
                instructions=False,
                geometry=True
            )
            
            # Ekstrak jarak dan koordinat rute
            if routes and 'features' in routes and routes['features']:
                route = routes['features'][0]
                distance = route['properties']['summary']['distance']  # dalam meter
                route_coords = route['geometry']['coordinates']
                
                # Simpan ke cache
                result = (distance, route_coords)
                route_cache[cache_key] = result
                logger.info(f"Menggunakan OpenRouteService API dengan jarak {distance:.1f}m")
                return result
                
            logger.warning("OpenRouteService API tidak mengembalikan rute valid")
        except Exception as e:
            logger.warning(f"Error OpenRouteService API: {e}. Mencoba alternatif...")
    else:
        logger.warning("OpenRouteService API tidak tersedia")
    
    # Coba gunakan Mapbox API sebagai alternatif
    if use_mapbox and MAPBOX_ACCESS_TOKEN:
        try:
            import requests
            
            # Buat URL untuk Mapbox Directions API
            url = f"https://api.mapbox.com/directions/v5/mapbox/driving/{ref_lng},{ref_lat};{dest_lng},{dest_lat}"
            params = {
                "access_token": MAPBOX_ACCESS_TOKEN,
                "geometries": "geojson",
                "overview": "full"
            }
            
            # Kirim permintaan ke Mapbox API
            response = requests.get(url, params=params)
            data = response.json()
            
            # Proses respons
            if 'routes' in data and data['routes']:
                route = data['routes'][0]
                distance = route['distance']  # dalam meter
                route_coords = route['geometry']['coordinates']
                
                # Simpan ke cache
                result = (distance, route_coords)
                route_cache[cache_key] = result
                logger.info(f"Menggunakan Mapbox API dengan jarak {distance:.1f}m")
                return result
                
            logger.warning("Mapbox API tidak mengembalikan rute valid")
        except Exception as e:
            logger.warning(f"Error Mapbox API: {e}. Menggunakan simulasi rute...")
    else:
        logger.warning("Mapbox API tidak tersedia")
    
    # Fallback: Gunakan simulasi rute yang lebih realistis mengikuti jalan
    try:
        # Hitung jarak lurus menggunakan geodesic (haversine)
        straight_distance = geodesic((ref_lat, ref_lng), (dest_lat, dest_lng)).meters
        
        # Buat rute yang lebih realistis dengan pola jalan yang alami
        num_points = 8  # Lebih banyak titik untuk rute yang lebih halus
        route_coords = []
        
        # Tambahkan titik awal
        route_coords.append([ref_lng, ref_lat])
        
        # Tentukan titik tengah untuk membuat rute berbentuk jalanan
        # Ambil 2 titik tengah utama untuk membuat belokan alami
        mid_point1_lat = ref_lat + (dest_lat - ref_lat) * 0.3
        mid_point1_lng = ref_lng + (dest_lng - ref_lng) * 0.3
        
        mid_point2_lat = ref_lat + (dest_lat - ref_lat) * 0.7
        mid_point2_lng = ref_lng + (dest_lng - ref_lng) * 0.7
        
        # Tambahkan variasi berdasarkan jarak untuk simulasi jalan
        # Semakin jauh, semakin besar kemungkinan belokan
        distance_factor = min(straight_distance / 1000, 1.0)  # Normalisasi jarak (maksimal 1km)
        
        # Buat kurva untuk simulasi jalan
        for i in range(1, num_points):
            # Bikin pembagian yang lebih natural untuk titik-titik antara
            if i < num_points/2:
                # Titik di bagian pertama rute - mendekati titik tengah pertama
                progress = i / (num_points/2)
                mid_lat = ref_lat + (mid_point1_lat - ref_lat) * progress
                mid_lng = ref_lng + (mid_point1_lng - ref_lng) * progress
            else:
                # Titik di bagian kedua rute - dari titik tengah kedua ke tujuan
                progress = (i - num_points/2) / (num_points/2)
                mid_lat = mid_point2_lat + (dest_lat - mid_point2_lat) * progress
                mid_lng = mid_point2_lng + (dest_lng - mid_point2_lng) * progress
            
            # Tambahkan variasi untuk mensimulasi jalan yang tidak lurus
            # Gunakan hash dari koordinat sebagai seed agar konsisten
            seed = int(abs(mid_lat*1000) + abs(mid_lng*1000) + i*10)
            lat_noise = ((seed % 10) - 5) / 2000 * distance_factor  # Variasi lat
            lng_noise = ((seed % 15) - 7) / 2000 * distance_factor  # Variasi lng
            
            route_coords.append([mid_lng + lng_noise, mid_lat + lat_noise])
            
        # Tambahkan titik akhir
        route_coords.append([dest_lng, dest_lat])
        
        # Buat jarak rute sedikit lebih panjang dari jarak lurus (faktor 1.2-1.5)
        # karena jalanan biasanya tidak lurus sempurna
        route_factor = 1.3  # Faktor perkiraan jalanan vs garis lurus
        route_distance = straight_distance * route_factor
        
        # Simpan hasil ke cache
        result = (route_distance, route_coords)
        route_cache[cache_key] = result
        
        logger.info(f"Menggunakan simulasi rute dengan jarak {route_distance:.1f}m")
        return result
        
    except Exception as e:
        logger.error(f"Error menghitung rute simulasi: {e}")
        # Tetap cache hasil error untuk menghindari perhitungan berulang yang akan gagal
        route_cache[cache_key] = (None, None)
        return None, None

def find_nearby_odps(ref_lat, ref_lng, radius_meters=DEFAULT_RADIUS, use_route_distance=True, only_available=False, direct_measurement=False):
    """
    Temukan ODP dalam radius tertentu.
    
    Args:
        ref_lat: Latitude titik referensi
        ref_lng: Longitude titik referensi
        radius_meters: Radius pencarian dalam meter
        use_route_distance: Jika True, akan menghitung jarak berdasarkan rute jalan
                         dan menambahkan kolom 'jarak_rute_meter' & 'koordinat_rute'
        only_available: Jika True, hanya menampilkan ODP dengan nilai AVAI > 0
        direct_measurement: Jika True, pengukuran jarak menggunakan jarak udara langsung, bukan rute
    
    Returns:
        DataFrame berisi semua ODP dalam radius yang ditentukan, dengan informasi jarak
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
        
        # Filter ODP yang tersedia (AVAI > 0) jika diminta
        if only_available and AVAI_COLUMN in df.columns:
            # Konversi kolom AVAI ke numerik
            df[AVAI_COLUMN] = pd.to_numeric(df[AVAI_COLUMN], errors='coerce').fillna(0)
            # Filter hanya ODP dengan AVAI > 0
            df = df[df[AVAI_COLUMN] > 0]
            logger.info(f"Menampilkan hanya ODP tersedia (AVAI > 0): {len(df)} ODP")
        
        # Hitung jarak lurus dalam meter (geodesic)
        ref_point = (ref_lat, ref_lng)
        df['jarak_meter'] = df.apply(
            lambda row: geodesic(ref_point, (row[LAT_COLUMN], row[LNG_COLUMN])).meters,
            axis=1
        )
        
        # Filter lokasi dalam radius geodesic - pastikan SEMUA ODP dalam radius udara ditampilkan
        # Tambahkan margin untuk menangani masalah presisi floating point dan perbedaan perhitungan jarak
        nearby = df[df['jarak_meter'] <= (radius_meters + SEARCH_MARGIN)].copy()
        logger.info(f"ODP dalam radius aerial {radius_meters}m (+{SEARCH_MARGIN}m margin): {len(nearby)} ODP")
        logger.info(f"Data titik referensi: {ref_lat}, {ref_lng}")
        
        # Diagnostic: tampilkan semua ODP yang dekat dengan batas 250m
        near_boundary = df[(df['jarak_meter'] > radius_meters - 10) & (df['jarak_meter'] <= radius_meters + 10)]
        if not near_boundary.empty:
            logger.info(f"ODP di sekitar batas radius ({radius_meters-10}m - {radius_meters+10}m): {len(near_boundary)}")
            for _, row in near_boundary.iterrows():
                logger.info(f"  ODP: {row.get(NAME_COLUMN, 'Unknown')}, jarak: {row['jarak_meter']:.2f}m")
        
        # Jika diminta, hitung jarak berdasarkan rute jalan untuk titik yang dalam radius
        if use_route_distance and not nearby.empty:
            # Inisialisasi kolom untuk jarak rute dan koordinat rute
            nearby['jarak_rute_meter'] = np.nan
            nearby['koordinat_rute'] = None
            nearby['rute_valid'] = False
            
            # Hitung jarak rute untuk setiap ODP terdekat
            for idx, row in nearby.iterrows():
                dest_lat = row[LAT_COLUMN]
                dest_lng = row[LNG_COLUMN]
                
                # Hitung jarak rute
                route_distance, route_coords = calculate_route_distance(ref_lat, ref_lng, dest_lat, dest_lng)
                
                if route_distance is not None:
                    nearby.at[idx, 'jarak_rute_meter'] = route_distance
                    nearby.at[idx, 'koordinat_rute'] = route_coords
                    nearby.at[idx, 'rute_valid'] = True
                    
            # Prioritaskan urutan berdasarkan jarak rute jika tersedia, kalau tidak gunakan estimasi jarak * faktor
            # Kita akan membuat kolom 'jarak_tampil' untuk menampilkan jarak yang dipilih
            nearby['jarak_tampil'] = nearby.apply(
                lambda row: row['jarak_rute_meter'] if not np.isnan(row.get('jarak_rute_meter', np.nan)) else row['jarak_meter'] * 1.3,
                axis=1
            )
            
            # Gunakan jarak rute untuk urutan dan tampilan jika tersedia
            # Urutkan berdasarkan jarak_tampil (ascending untuk mendapatkan dari terdekat ke terjauh)
            try:
                nearby = nearby.sort_values(by='jarak_tampil', ascending=True)
                logger.info(f"Berhasil mengurutkan {len(nearby)} ODP berdasarkan jarak_tampil")
            except Exception as sort_err:
                logger.error(f"Error saat mengurutkan data: {sort_err}")
                # Fallback sorting
                nearby = nearby.reset_index().sort_values(by='jarak_tampil', ascending=True)
                logger.info(f"Menggunakan fallback sorting untuk {len(nearby)} ODP")
            
            logger.info(f"Ditemukan {len(nearby)} ODP dalam radius {radius_meters}m")
            
            # Log informasi tentang jumlah ODP dengan rute valid
            valid_routes = nearby['rute_valid'].sum()
            logger.info(f"{valid_routes} dari {len(nearby)} ODP memiliki rute jalan yang valid")
            
        else:
            # Jika tidak menggunakan jarak rute, gunakan jarak lurus saja
            try:
                nearby = nearby.sort_values(by='jarak_meter', ascending=True)
                logger.info(f"Berhasil mengurutkan {len(nearby)} ODP berdasarkan jarak_meter")
            except Exception as sort_err:
                logger.error(f"Error saat mengurutkan data: {sort_err}")
                # Fallback sorting
                nearby = nearby.reset_index().sort_values(by='jarak_meter', ascending=True)
                logger.info(f"Menggunakan fallback sorting untuk {len(nearby)} ODP")
                
            # Untuk tampilan label dan garis ukur, gunakan estimasi jarak jalan (jarak udara * faktor)
            nearby['jarak_tampil'] = nearby['jarak_meter'] * 1.3
            logger.info(f"Ditemukan {len(nearby)} ODP dalam radius {radius_meters}m (jarak estimasi)")
        
        if nearby.empty:
            logger.info(f"Tidak ditemukan ODP dalam radius {radius_meters}m")
        
        # Pastikan indeks berjalan mulai dari 0 untuk memudahkan penomoran
        nearby = nearby.reset_index(drop=True)
            
        return nearby
    except Exception as e:
        logger.error(f"Error saat mencari ODP terdekat: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None

def create_odp_map(ref_lat, ref_lng, nearby_df, radius_meters=DEFAULT_RADIUS, max_display=30, with_routes=True, use_satellite=True):
    """
    Buat peta dengan ODP yang ditemukan.
    
    Args:
        ref_lat: Latitude titik referensi
        ref_lng: Longitude titik referensi
        nearby_df: DataFrame dengan ODP terdekat
        radius_meters: Radius pencarian dalam meter
        max_display: Maksimal ODP yang ditampilkan
        with_routes: Menampilkan rute dari titik referensi ke ODP terdekat
        use_satellite: Menggunakan citra satelit sebagai basemap
    """
    # Import modul yang diperlukan secara lokal untuk menghindari konflik
    import matplotlib
    # Menggunakan backend non-interaktif
    matplotlib.use('Agg')
    # Penting: Jika kita memiliki masalah dalam visualisasi, kita harus memberikan pesan yang informatif
    # dan pastikan gambar tetap bisa dihasilkan dan dikirim ke pengguna
    try:
        if nearby_df is None or nearby_df.empty:
            logger.warning("Tidak ada data ODP untuk divisualisasikan")
            return None
            
        # Tampilkan semua ODP dalam radius aerial terlepas dari jarak rute
        filtered_df = nearby_df.copy()
        logger.info(f"Menampilkan semua ODP dalam radius aerial {radius_meters}m: {len(filtered_df)} ODP")
        
        # Pastikan seluruh ODP memiliki kolom 'jarak_tampil'
        if 'jarak_tampil' not in filtered_df.columns:
            filtered_df['jarak_tampil'] = filtered_df['jarak_meter']
        
        # Tampilkan semua ODP dalam radius 250m terlepas dari batasan max_display
        display_df = filtered_df
        
        # Logging informasi jumlah ODP yang ditampilkan
        logger.info(f"Menampilkan {len(display_df)} ODP dari total {len(filtered_df)} ODP dalam radius {radius_meters}m")
            
        # Buat figure dan axis dengan ukuran dan resolusi tinggi
        fig, ax = plt.subplots(figsize=(15, 15), dpi=200)
        
        # Simpan plot awal untuk debugging
        plt.savefig('static/odp_images/debug_initial_plot.png', dpi=200, bbox_inches='tight')
        logger.info(f"Debug plot awal tersimpan")
        
        # Definisikan batas area peta yang proporsional
        # Gunakan rasio 1 derajat = 111 km (111.000 meter) pada garis equator
        # Untuk latitude (north-south): 1 derajat = ~111 km konstan
        # Untuk longitude (east-west): 1 derajat = ~111 km * cos(latitude)
        # Buffer untuk latitude tetap sama, buffer untuk longitude disesuaikan dengan latitude
        lat_buffer = radius_meters / 111000  # Buffer latitude dalam derajat
        lng_buffer = lat_buffer / math.cos(math.radians(abs(ref_lat)))  # Sesuaikan buffer longitude
        
        # Set batas plot
        ax.set_xlim(ref_lng - lng_buffer, ref_lng + lng_buffer)
        ax.set_ylim(ref_lat - lat_buffer, ref_lat + lat_buffer)
        
        # Log untuk debugging
        logger.info(f"Setting plot bounds: lng=[{ref_lng - lng_buffer:.6f}, {ref_lng + lng_buffer:.6f}], lat=[{ref_lat - lat_buffer:.6f}, {ref_lat + lat_buffer:.6f}]")
        
        # PENTING: ELIMINASI SISTEM KOREKSI KOORDINAT
        # Untuk menampilkan titik ODP persis sesuai koordinat di spreadsheet,
        # kita tidak lagi menggunakan sistem koreksi koordinat
        
        # Fungsi ini telah diubah untuk mengembalikan koordinat asli tanpa perubahan
        def apply_coordinate_correction(lat, lng):
            # Kembalikan koordinat asli tanpa modifikasi
            return lat, lng
            
        # Terapkan koreksi pada titik referensi untuk konsistensi
        ref_lat_corr, ref_lng_corr = apply_coordinate_correction(ref_lat, ref_lng)
        
        # Plot titik referensi sebagai bintang merah - menggunakan koordinat asli tanpa koreksi
        # Menggunakan scatter untuk ukuran yang lebih presisi dan kontrol yang lebih baik
        ax.scatter(ref_lng, ref_lat, color='red', marker='*', s=500, 
                  edgecolor='white', linewidth=1.5, zorder=100, alpha=1.0, label='Titik Referensi')
        
        # Log koordinat titik referensi untuk debugging
        logger.info(f"Plotting reference point at exact coordinates: ({ref_lng:.6f}, {ref_lat:.6f})")
        
        # Tambahkan label referensi dengan koordinat - gunakan koordinat asli
        ref_text = f"REF: {ref_lat:.6f}, {ref_lng:.6f}"
        t = ax.text(ref_lng, ref_lat, ref_text, 
                 color='red', fontsize=10, fontweight='bold',
                 verticalalignment='bottom',
                 horizontalalignment='center')
        t.set_path_effects([path_effects.withStroke(linewidth=3, foreground='white')])
        
        # Gambar lingkaran radius - gunakan koordinat asli
        radius_degrees = radius_meters / 111000  # Konversi meter ke derajat (perkiraan)
        
        # Lingkaran radius jangkauan - perbesar ukuran lingkaran pada tampilan satelit
        circle_edge_width = 2.5 if use_satellite else 2.0  # Lingkaran lebih tebal pada tampilan satelit
        circle_alpha = 0.8 if use_satellite else 0.7  # Lebih solid untuk tampilan satelit
        circle_color = 'blue' if use_satellite else 'red'  # Warna biru lebih mencolok pada satelit
        
        circle = plt.Circle((ref_lng, ref_lat), radius_degrees, 
                          fill=False, color=circle_color, linewidth=circle_edge_width, 
                          alpha=circle_alpha)
        ax.add_patch(circle)
        
        # Plot ODP dengan indikator marker sesuai kategori dan jarak berdasarkan rute
        for i, (idx, row) in enumerate(display_df.iterrows(), 1):
            lat = row[LAT_COLUMN]
            lng = row[LNG_COLUMN]
            
            # PENTING: Gunakan koordinat asli tepat seperti dalam spreadsheet
            # Tidak menerapkan koreksi apapun untuk menjamin presisi
            # Log koordinat ODP untuk analisis presisi
            logger.info(f"Plotting ODP marker {i} at exact coordinates: ({lng:.6f}, {lat:.6f})")
            
            # Selalu gunakan jarak rute untuk label dan garis ukur, bukan jarak udara
            # Jika jarak rute tersedia, gunakan itu. Jika tidak, gunakan jarak udara * 1.3 sebagai estimasi
            if 'jarak_rute_meter' in row and pd.notnull(row['jarak_rute_meter']):
                distance = row['jarak_rute_meter']  # Jarak berdasarkan rute jalan
            else:
                # Jika tidak ada jarak rute, estimasi dengan jarak udara * faktor
                distance = row['jarak_meter'] * 1.3  # Estimasi jarak jalan
                
            # Apakah memiliki rute valid
            has_route = row.get('rute_valid', False)
            route_coords = row.get('koordinat_rute', None)
            
            kategori = row.get(KATEGORI_COLUMN, "").upper() if KATEGORI_COLUMN in row else ""
            
            # Tentukan warna berdasarkan kategori ODP dengan warna yang lebih cerah
            if "HIJAU" in kategori:
                color = '#00CC00'  # Hijau lebih cerah
            elif "KUNING" in kategori:
                color = '#FFCC00'  # Kuning lebih cerah
            elif "MERAH" in kategori:
                color = '#FF3333'  # Merah lebih cerah
            elif "HITAM" in kategori:
                color = '#333333'  # Hitam sedikit lebih terang untuk visibility
            elif "BIRU" in kategori or "ORANGE" in kategori:
                color = '#FF9900'  # Orange cerah
            else:
                # Fallback: tentukan warna berdasarkan jarak jika kategori tidak dikenal
                if distance < radius_meters * 0.25:
                    color = '#00CC00'  # Hijau cerah
                elif distance < radius_meters * 0.5:
                    color = '#3399FF'  # Biru cerah
                elif distance < radius_meters * 0.75:
                    color = '#FF9900'  # Oranye cerah
                else:
                    color = '#CC66FF'  # Ungu cerah
            
            # Marker dasar - gunakan koordinat asli dari data spreadsheet
            ax.plot(lng, lat, '.', color=color, alpha=0, markersize=1)
            
            # Tambahkan rute dari referensi ke ODP berdasarkan rute jalan yang sebenarnya
            if with_routes and distance <= radius_meters:  # Hanya tampilkan rute untuk ODP dalam radius
                import numpy as np  # Import numpy di dalam fungsi untuk memastikan tersedia
                
                # Cek apakah rute tersedia dari API
                if has_route and route_coords is not None and len(route_coords) > 1:
                    # Konversi koordinat rute menjadi array untuk plotting
                    route_coords_array = np.array(route_coords)
                    
                    # Pastikan koordinat valid dan memiliki setidaknya dua titik
                    if route_coords_array.shape[0] >= 2 and route_coords_array.shape[1] == 2:
                        # Plot rute dengan warna sesuai kategori dan style garis yang tepat
                        x_coords = route_coords_array[:, 0]
                        y_coords = route_coords_array[:, 1]
                        
                        # Verifikasi bahwa titik awal dan akhir mendekati referensi dan ODP
                        # Pastikan rute ini memang dari referensi ke ODP
                        start_near_ref = geodesic((ref_lat, ref_lng), (y_coords[0], x_coords[0])).meters < 50
                        end_near_odp = geodesic((lat, lng), (y_coords[-1], x_coords[-1])).meters < 50
                        
                        if start_near_ref and end_near_odp:
                            # Menggunakan garis berbeda untuk peta jalan vs satelit
                            if not use_satellite:
                                # Pada peta jalan, gunakan garis putus-putus dengan outline lebih tebal
                                ax.plot(x_coords, y_coords, '--', 
                                      color=color, linewidth=3, alpha=0.9, 
                                      path_effects=[path_effects.withStroke(linewidth=5, foreground='#444444', alpha=0.4)],
                                      zorder=10)  # Pastikan rute muncul di atas lapisan lain
                            else:
                                # Pada peta satelit, gunakan garis normal dengan outline putih yang lebih tebal
                                ax.plot(x_coords, y_coords, '-', 
                                      color=color, linewidth=2.5, alpha=0.8,
                                      path_effects=[path_effects.withStroke(linewidth=4, foreground='white', alpha=0.5)],
                                      zorder=10)
                            
                            # Tambahkan panah di tengah untuk menunjukkan arah rute
                            mid_idx = len(x_coords) // 2
                            if len(x_coords) > 2 and mid_idx > 0:
                                arrow_color = color
                                ax.annotate('', 
                                         xy=(x_coords[mid_idx], y_coords[mid_idx]),
                                         xytext=(x_coords[mid_idx-1], y_coords[mid_idx-1]),
                                         arrowprops=dict(arrowstyle='->', color=arrow_color, lw=2),
                                         zorder=11)
                        else:
                            # Fallback: Jika rute tidak terhubung dengan benar, buat garis lurus sebagai solusi alternatif
                            logger.warning(f"Rute tidak terhubung dengan benar, menggunakan garis langsung: {row.get(NAME_COLUMN, 'Unknown')}")
                            # Perkecil ukuran garis ukur pada peta jalan
                            line_width = 0.5 if not use_satellite else 1.5  # Lebih kecil lagi untuk peta jalan
                            line_alpha = 0.3 if not use_satellite else 0.5  # Lebih transparan untuk peta jalan
                            stroke_width = 1.2 if not use_satellite else 3.0  # Stroke lebih kecil lagi untuk peta jalan
                            
                            ax.plot([ref_lng, lng], [ref_lat, lat], '-', 
                                  color=color, linewidth=line_width, alpha=line_alpha, linestyle=':',
                                  path_effects=[path_effects.withStroke(linewidth=stroke_width, foreground='white', alpha=0.25)],
                                  zorder=5)
                    else:
                        logger.warning(f"Format koordinat rute tidak valid: {row.get(NAME_COLUMN, 'Unknown')}")
                        # Fallback ke garis langsung jika format rute tidak valid
                        # Perkecil ukuran garis ukur pada peta jalan
                        line_width = 0.5 if not use_satellite else 1.5  # Lebih kecil lagi untuk peta jalan
                        line_alpha = 0.3 if not use_satellite else 0.5  # Lebih transparan untuk peta jalan
                        stroke_width = 1.2 if not use_satellite else 3.0  # Stroke lebih kecil lagi untuk peta jalan
                        
                        ax.plot([ref_lng, lng], [ref_lat, lat], '-', 
                              color=color, linewidth=line_width, alpha=line_alpha, linestyle=':',
                              path_effects=[path_effects.withStroke(linewidth=stroke_width, foreground='white', alpha=0.25)],
                              zorder=5)
                else:
                    # Fallback jika tidak ada koordinat rute
                    logger.debug(f"Tidak ada data rute valid, menggunakan garis langsung: {row.get(NAME_COLUMN, 'Unknown')}")
                    # Perkecil ukuran garis ukur pada peta jalan
                    line_width = 0.5 if not use_satellite else 1.5  # Lebih kecil lagi untuk peta jalan
                    line_alpha = 0.3 if not use_satellite else 0.5  # Lebih transparan untuk peta jalan
                    stroke_width = 1.2 if not use_satellite else 3.0  # Stroke lebih kecil lagi untuk peta jalan
                    
                    ax.plot([ref_lng, lng], [ref_lat, lat], '-', 
                          color=color, linewidth=line_width, alpha=line_alpha, linestyle=':',
                          path_effects=[path_effects.withStroke(linewidth=stroke_width, foreground='white', alpha=0.25)],
                          zorder=5)
            
            # Buat nomor urut ODP dalam lingkaran dengan warna sesuai kategori
            circle_radius = 0.025  # Radius lingkaran sedikit lebih besar
            
            # Tambahkan outline putih untuk marker dengan ketebalan lebih
            outline = plt.Circle((lng, lat), radius_degrees * 0.03, 
                             color='white', alpha=0.95, zorder=9)
            ax.add_patch(outline)
            
            # Tambahkan lingkaran warna cerah sesuai kategori
            circle = plt.Circle((lng, lat), radius_degrees * 0.025, 
                             color=color, alpha=0.95, zorder=10)
            ax.add_patch(circle)
            
            # Tambahkan nomor urut di dalam lingkaran dengan ukuran lebih besar dan ketebalan lebih
            num_text = ax.text(lng, lat, f"{i}", 
                            color='white', fontsize=10, fontweight='bold',
                            verticalalignment='center',
                            horizontalalignment='center',
                            zorder=11,  # Pastikan teks berada di atas lingkaran
                            path_effects=[path_effects.withStroke(linewidth=2.0, foreground='black')])
            
            # Tambahkan jarak di posisi yang tidak tertutupi marker
            dist_txt = f"{distance:.1f}m"
            
            # Gunakan offset yang lebih besar dan posisi lateral untuk menghindari tumpang tindih
            # Posisikan jarak di samping kanan bawah marker - gunakan koordinat asli
            t = ax.text(lng + (radius_degrees * 0.03), lat - (radius_degrees * 0.03), dist_txt, 
                     color=color, fontsize=8, fontweight='bold',
                     verticalalignment='top',
                     horizontalalignment='left',  # Rata kiri
                     bbox=dict(facecolor='white', alpha=0.9, boxstyle='round,pad=0.3', 
                              edgecolor=color, linewidth=1.5))
            t.set_path_effects([path_effects.withStroke(linewidth=2.0, foreground='white')])
        
        # Set judul dan label dengan informasi tambahan
        title_elements = [f'ODP dalam Radius {radius_meters}m dari Titik Referensi']
        if len(nearby_df) > max_display:
            title_elements.append(f'(Menampilkan {max_display} dari {len(nearby_df)} ODP)')
        if with_routes:
            title_elements.append('dengan Rute')
        
        title_text = '\n'.join(title_elements)
        
        # Tambahkan background putih transparan di belakang judul agar lebih terbaca
        ax.set_title(
            title_text, 
            fontsize=12, 
            fontweight='bold',
            bbox=dict(
                facecolor='white',
                alpha=0.7,
                edgecolor='none',
                boxstyle='round,pad=0.5'
            )
        )
        
        # Tambahkan basemap (citra satelit atau peta jalan) dengan Mapbox
        try:
            # Tetapkan batas-batas peta yang lebih luas untuk peta satelit agar semua ODP terlihat
            # Gunakan faktor pengali yang lebih besar untuk tampilan satelit
            view_factor = 1.5 if use_satellite else 1.2  # Faktor lebih besar untuk satelit
            ax.set_xlim(ref_lng - radius_degrees * view_factor, ref_lng + radius_degrees * view_factor)
            ax.set_ylim(ref_lat - radius_degrees * view_factor, ref_lat + radius_degrees * view_factor)
            
            # Non-aktifkan ticks
            ax.set_xticks([])
            ax.set_yticks([])
            
            # Tambahkan background yang menampilkan jalan dan bangunan
            global MAPBOX_ACCESS_TOKEN
            
            # Menambahkan latar belakang secara manual menggunakan Mapbox API
            if MAPBOX_ACCESS_TOKEN:
                logger.info("Menggunakan Mapbox Static API untuk gambar latar belakang")
                
                try:                    
                    # Tetapkan zoom level dan ukuran gambar
                    zoom_level = 17 if use_satellite else 17  # Sedikit zoom out untuk satelit
                    img_width = 1280  # piksel - meningkatkan resolusi untuk detail lebih baik
                    img_height = 1280  # piksel - meningkatkan resolusi untuk detail lebih baik
                    
                    # Hitung batas viewport untuk memastikan semua ODP terlihat dengan koordinat tepat
                    # Buffer untuk memastikan semua titik terlihat - menggunakan buffer minimal untuk presisi tinggi
                    bounds_buffer = 0.00001  # Buffer sangat kecil untuk presisi maksimal
                    
                    # Style map yang akan digunakan
                    if use_satellite:
                        mapbox_style = "satellite-streets-v11"  # Satelit dengan jalan
                        map_label = "Peta satelit dengan jalan dan titik ODP"
                    else:
                        mapbox_style = "streets-v11"  # Peta jalan original
                        map_label = "Peta jalan dengan titik ODP"
                    
                    # URL untuk Mapbox Static API
                    # Menambahkan parameter text-size untuk memperbesar ukuran teks dan text-halo-width untuk outline
                    # Parameter text-allow-overlap=false membuat teks tidak tumpang tindih
                    # Menerapkan filter agar jalan utama tetap terlihat
                    map_params = {
                        "text-size": 14,  # Memperbesar ukuran teks jalan
                        "text-halo-width": 2,  # Menambahkan outline pada teks jalan
                        "text-halo-color": "rgba(255,255,255,0.9)",  # Warna outline putih semi-transparan
                        "text-color": "#333",  # Warna teks jalan
                        "text-allow-overlap": "false",  # Mencegah teks tumpang tindih
                        "text-variable-anchor": "top,bottom,left,right",  # Posisi teks yang bervariasi
                        "icon-allow-overlap": "true",  # Icon tetap ditampilkan
                        "text-padding": 5,  # Padding teks
                        "text-max-width": 8  # Lebar maksimum teks
                    }
                    
                    params_str = ","
                    for key, value in map_params.items():
                        params_str += f"{key}:{value},"
                    
                    # Modifikasi URL untuk Mapbox Static API dengan parameter khusus untuk perbaikan label jalan
                    # Buat URL dengan parameter untuk meningkatkan visibilitas teks jalan
                    style_params = [
                        # Gunakan style yang sudah ada dengan parameter tambahan
                        f"{mapbox_style}",
                        # Perbesar teks jalan dan hindari tumpang tindih
                        "road-label-visibility=visible",
                        "text-field={name}",
                        "text-size=14",
                        "text-halo-width=2",
                        "text-halo-color=rgba(255,255,255,0.9)",
                        "text-anchor=center",
                        "text-allow-overlap=false",
                        "symbol-placement=point"
                    ]
                    
                    style_str = ",".join(style_params)
                    # Ubah ukuran gambar ke 1280x1280 dengan @2x untuk resolusi tinggi (DPI 2x)
                    mapbox_url = f"https://api.mapbox.com/styles/v1/mapbox/{mapbox_style}/static/geojson(%7B%22type%22%3A%22Point%22%2C%22coordinates%22%3A%5B{ref_lng}%2C{ref_lat}%5D%7D)/{ref_lng},{ref_lat},{zoom_level},0,0/1280x1280@2x?access_token={MAPBOX_ACCESS_TOKEN}"
                    logger.info(f"Menggunakan Mapbox Static API untuk gambar latar belakang dengan zoom={zoom_level}")
                    
                    # Ambil gambar latar belakang dari API Mapbox
                    response = requests.get(mapbox_url)
                    if response.status_code == 200:
                        try:
                            # Buka gambar dari respons
                            img_bytesio = BytesIO(response.content)
                            background_img = Image.open(img_bytesio)
                            
                            # Konversi ke array untuk matplotlib
                            import numpy as np
                            background_array = np.array(background_img)
                            
                            # Gunakan proyeksi yang sama persis antara Mapbox dan matplotlib
                            # Ini menjamin bahwa titik pada gambar latar belakang selaras dengan titik pada plot
                            
                            # PENDEKATAN BARU: Set up latar belakang dengan cara berbeda
                            # 1. Ambil batas plot saat ini
                            xlim = ax.get_xlim()
                            ylim = ax.get_ylim()
                            
                            # 2. Tampilkan gambar latar belakang dengan batas yang tepat sama dengan bounding box
                            # Gunakan parameter extent yang sangat presisi berdasarkan titik referensi
                            # Batas peta harus identik dengan bounding box dari plot matplotlib
                            
                            # PENDEKATAN BARU UNTUK PRESISI ABSOLUT:
                            # Gunakan formula Mapbox untuk menghitung skala yang tepat dari gambar API
                            # Di zoom level 0, seluruh dunia adalah 360° lebar
                            # Pada zoom level z, gambar mencakup 360°/(2^z) derajat
                            
                            # Kita menggunakan gambar 1280x1280@2x = 2560x2560 pixels aktual
                            # Mapbox menggunakan 512x512 (1024x1024@2x) tiles sebagai standar
                            # Jadi kita perlu menghitung yang tepat
                            
                            # Hitung lebar gambar dalam derajat
                            lng_coverage = 360 / (2 ** zoom_level) * (1280 / 512)
                            
                            # Latitude coverage bervariasi berdasarkan latitude lokasi
                            # Gunakan faktor koreksi berdasarkan proyeksi Mercator
                            lat_coverage = lng_coverage * math.cos(math.radians(abs(ref_lat)))
                            
                            # Tentukan batas-batas gambar dengan presisi tinggi
                            extent_bounds = (
                                ref_lng - lng_coverage/2,  # min longitude 
                                ref_lng + lng_coverage/2,  # max longitude
                                ref_lat - lat_coverage/2,  # min latitude
                                ref_lat + lat_coverage/2   # max latitude
                            )
                            
                            # Log batas untuk debugging
                            logger.info(f"Setting background image extent to: {extent_bounds}")
                            
                            # Penting: gunakan transformasi yang tepat untuk imshow
                            # 'extent' menentukan area koordinat tempat gambar akan dirender
                            # Kita harus menggunakan nilai yang sama persis dengan batas plot
                            # Untuk menjamin transformasi yang seragam antara gambar dan koordinat
                            ax.imshow(
                                background_array, 
                                extent=extent_bounds,
                                aspect='equal',  # Gunakan 'equal' untuk memastikan skala yang konsisten
                                zorder=0
                            )
                            # Log untuk debugging
                            logger.info(f"Background image placed with exact extent: {extent_bounds}")
                            
                            # PENTING: Jangan kembalikan batas plot ke nilai asli
                            # Kita gunakan nilai batas latar belakang secara konsisten
                            # Ini memastikan posisi marker tepat sama dengan koordinat asli
                            ax.set_xlim(extent_bounds[0], extent_bounds[1])
                            ax.set_ylim(extent_bounds[2], extent_bounds[3])
                            
                            # Log batas final untuk debugging
                            logger.info(f"Final plot bounds: x[{ax.get_xlim()[0]:.6f}, {ax.get_xlim()[1]:.6f}], y[{ax.get_ylim()[0]:.6f}, {ax.get_ylim()[1]:.6f}]")
                            
                            # 4. Log batas-batas untuk debugging
                            logger.info(f"Old plot bounds: x[{xlim[0]:.6f}, {xlim[1]:.6f}], y[{ylim[0]:.6f}, {ylim[1]:.6f}]")
                            
                            # 5. Verifikasi bahwa marker akan tepat pada posisi yang benar
                            # Verifikasi penempatan marker REF
                            logger.info(f"VERIFIKASI REF: Plotting marker at exact coordinates on map with bounds: x[{ax.get_xlim()[0]:.6f}, {ax.get_xlim()[1]:.6f}], y[{ax.get_ylim()[0]:.6f}, {ax.get_ylim()[1]:.6f}]")
                            
                            # Verifikasi bahwa marker tidak mengalami koreksi atau transformasi
                            logger.info(f"REF marker exact position: lng={ref_lng:.6f}, lat={ref_lat:.6f} - No correction applied")
                            
                            # Catat bahwa latar belakang berhasil ditampilkan
                            logger.info(f"Berhasil menggunakan Peta {'satelit' if use_satellite else 'jalan'} dengan titik ODP")
                        except Exception as e:
                            logger.error(f"Gagal menampilkan latar belakang: {str(e)}")
                        
                        # Tambahkan keterangan
                        fig.text(0.5, 0.97, map_label,
                               fontsize=14, color='black', 
                               ha='center', va='top',
                               bbox=dict(facecolor='white', alpha=0.7, boxstyle='round'))
                        
                        logger.info(f"Berhasil menggunakan {map_label}")
                    else:
                        raise Exception(f"Failed to get image from Mapbox API: {response.status_code}")
                except Exception as e:
                    logger.error(f"Gagal menggunakan Mapbox API: {e}")
                    # Fallback: gunakan latar belakang sederhana
                    if use_satellite:
                        ax.set_facecolor('#e6f7ff')  # Biru muda (simulasi air)
                    else:
                        ax.set_facecolor('white')
                        ax.grid(True, linestyle='-', alpha=0.3)
                    
                    fig.text(0.5, 0.97, f"Peta {'satelit' if use_satellite else 'jalan'} (gambar latar tidak tersedia)",
                           fontsize=14, color='black', 
                           ha='center', va='top',
                           bbox=dict(facecolor='white', alpha=0.7, boxstyle='round'))
            else:
                # Gunakan latar belakang sederhana jika tidak ada Mapbox token
                if use_satellite:
                    ax.set_facecolor('#e6f7ff')  # Biru muda (simulasi air)
                    label = "Peta satelit (gambar latar tidak tersedia)"
                else:
                    ax.set_facecolor('white')
                    ax.grid(True, linestyle='-', alpha=0.3)
                    label = "Peta jalan (gambar latar tidak tersedia)"
                
                fig.text(0.5, 0.97, label,
                       fontsize=14, color='black', 
                       ha='center', va='top',
                       bbox=dict(facecolor='white', alpha=0.7, boxstyle='round'))
                
        except Exception as e:
            logger.warning(f"Tidak dapat menambahkan basemap: {e}")
            # Buat latar belakang putih sebagai alternatif
            ax.set_facecolor('white')
            ax.grid(True, linestyle='--', alpha=0.7)
            
            # Tambahkan pesan error sebagai watermark
            fig.text(0.5, 0.5, "Citra Satelit Tidak Tersedia",
                   fontsize=20, color='gray', alpha=0.5,
                   ha='center', va='center', rotation=30)
        
        # Tambahkan legenda untuk kategori ODP
        lokasi_ref = mlines.Line2D([0], [0], marker='*', color='w', markerfacecolor='red', markersize=15)
        odp_hijau = mlines.Line2D([0], [0], marker='o', color='w', markerfacecolor='green', markersize=10)
        odp_kuning = mlines.Line2D([0], [0], marker='o', color='w', markerfacecolor='yellow', markersize=10)
        odp_merah = mlines.Line2D([0], [0], marker='o', color='w', markerfacecolor='red', markersize=10)
        odp_biru = mlines.Line2D([0], [0], marker='o', color='w', markerfacecolor='#FF9900', markersize=10)
        odp_hitam = mlines.Line2D([0], [0], marker='o', color='w', markerfacecolor='black', markersize=10)
        
        legend_items = [
            (lokasi_ref, 'Lokasi Referensi'),
            (odp_hijau, 'ODP Kategori HIJAU'),
            (odp_kuning, 'ODP Kategori KUNING'),
            (odp_merah, 'ODP Kategori MERAH'),
            (odp_biru, 'ODP Kategori ORANGE'),
            (odp_hitam, 'ODP Kategori HITAM')
        ]
        
        if with_routes:
            # Gunakan style rute yang sesuai dengan tipe peta
            if use_satellite:
                route_line = mlines.Line2D([0], [0], color='green', linestyle='-', linewidth=2)
            else:
                route_line = mlines.Line2D([0], [0], color='green', linestyle='--', linewidth=2.5)
            legend_items.append((route_line, 'Rute ke ODP'))
            
        # Buat legenda dari items
        ax.legend(
            [item[0] for item in legend_items],
            [item[1] for item in legend_items],
            loc='upper right',
            fancybox=True, framealpha=0.7
        )
        
        # Tambahkan informasi jumlah ODP
        info_text = f"Jumlah ODP: {len(nearby_df)}"
        info = ax.text(0.02, 0.02, info_text, transform=ax.transAxes, 
                     fontsize=12, fontweight='bold',
                     bbox=dict(facecolor='white', alpha=0.8, boxstyle='round'))
        
        # Buat ID unik untuk file
        map_type = "satellite" if use_satellite else "street"
        route_type = "with_routes" if with_routes else "no_routes"
        file_id = f"tg_{map_type}_{route_type}_{uuid.uuid4()}"
        file_path = os.path.join(ODP_IMAGE_DIR, f"{file_id}.png")
        
        # Simpan gambar dengan resolusi tinggi
        plt.savefig(file_path, bbox_inches='tight', dpi=200)
        plt.close(fig)
        
        logger.info(f"Peta berhasil disimpan di: {file_path}")
        
        return file_path
        
    except Exception as e:
        logger.error(f"Error saat membuat peta ODP: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None

def get_kategori_emoji(kategori):
    """Mendapatkan emoji berdasarkan kategori ODP"""
    kategori = str(kategori).upper() if kategori else ""
    if "HIJAU" in kategori:
        return "🟢"
    elif "KUNING" in kategori:
        return "🟡"
    elif "MERAH" in kategori:
        return "🔴"
    elif "HITAM" in kategori:
        return "⚫"
    elif "BIRU" in kategori:
        return "🔵"
    else:
        return "⚪"  # Default untuk kategori lainnya

def format_odp_list(nearby_odps, max_items=10):
    """Format daftar ODP untuk teks pesan"""
    result = []
    
    # Header hasil pencarian
    result.append(f"📍 Ditemukan {len(nearby_odps)} ODP dalam radius {DEFAULT_RADIUS}m:\n")
    
    # Daftar ODP dengan penomoran berurutan berdasarkan jarak
    for i, (idx, row) in enumerate(nearby_odps.head(max_items).iterrows(), 1):
        name = row.get(NAME_COLUMN, f"ODP #{idx+1}")
        
        # Extract nomor ODP jika ada dalam format standar (contoh: ODP-ABC-XYZ/123)
        odp_number = None
        if NAME_COLUMN in row:
            import re
            # Mencoba ekstrak nomor ODP dari pola standar
            match = re.search(r'/(\d+)', str(row[NAME_COLUMN]))
            if match:
                odp_number = match.group(1)  # Nomor setelah "/"
        
        # Tambahkan nomor ODP jika ditemukan
        if odp_number:
            name_display = f"{name} (#{odp_number})"
        else:
            name_display = name
        
        # Pilih jarak yang tepat untuk ditampilkan (rute jika tersedia, aerial jika tidak)
        if 'jarak_tampil' in row:
            distance = row['jarak_tampil']
            
            # Indikasikan jenis jarak yang ditampilkan
            if 'jarak_rute_meter' in row and not pd.isna(row['jarak_rute_meter']):
                distance_type = "rute"
            else:
                distance_type = "aerial"
        else:
            distance = row['jarak_meter']
            distance_type = "aerial"
            
        avai = row.get(AVAI_COLUMN, "N/A")
        kategori = row.get(KATEGORI_COLUMN, "")
        
        # Emoji kategori berdasarkan warna ODP
        emoji = get_kategori_emoji(kategori)
        
        # Format baris hasil dengan jenis jarak dan urutan berdasarkan kedekatan
        result.append(f"{i}. {emoji} {name_display} - {distance:.1f}m ({distance_type}) (Avai: {avai})")
    
    # Tambahkan informasi tentang ODP lainnya jika ada lebih banyak
    if len(nearby_odps) > max_items:
        result.append(f"\n...dan {len(nearby_odps) - max_items} ODP lainnya... ketik /more untuk melihat semua hasil")
    
    return "\n".join(result)

@bot.message_handler(commands=['start'])
def start(message):
    """Kirim pesan selamat datang."""
    bot.reply_to(message, 
                 f"👋 Halo {message.from_user.first_name}!\n\n"
                 f"Saya adalah bot pencari ODP berdasarkan koordinat.\n\n"
                 f"Gunakan perintah /help untuk melihat cara penggunaan.")

@bot.message_handler(commands=['more'])
def more_command(message):
    """Menampilkan semua ODP yang ditemukan."""
    chat_id = message.chat.id
    
    # Cari data dalam cache berdasarkan chat_id (fitur tambahan untuk pengembangan)
    bot.reply_to(message, "Fitur ini masih dalam pengembangan. Silakan gunakan perintah /cari <lat> <lng> untuk mencari ODP kembali.")

@bot.message_handler(commands=['help'])
def help_command(message):
    """Kirim informasi bantuan."""
    help_text = (
        "🤖 *Bot Pencari ODP*\n\n"
        "Bot ini membantu menemukan ODP (Optical Distribution Point) yang berada dalam radius tertentu dari koordinat yang diberikan.\n\n"
        "*Cara Penggunaan:*\n"
        "1. Kirim lokasi Anda dengan mengklik tombol 📎 dan pilih *Location*\n"
        "2. Kirim koordinat dengan format: `-3.292481, 114.592482`\n"
        "3. Gunakan perintah `/cari -3.292481 114.592482 250`\n\n"
        "*Perintah Tersedia:*\n"
        "/cari <lat> <lng> [radius] - Mencari ODP di sekitar koordinat tertentu\n"
        "/radius [nilai] - Melihat atau mengubah radius pencarian (default: 250m)\n"
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
    if len(args) == 1:
        # Tidak ada argumen, tampilkan radius default
        bot.reply_to(message, f"🔍 Radius pencarian default: {DEFAULT_RADIUS}m\n\nUntuk mengubah sementara, gunakan format:\n/radius [nilai dalam meter]\n\nAtau saat mencari:\n/cari <lat> <lng> [radius]")
    else:
        try:
            # Coba parse nilai radius
            radius = int(args[1])
            if radius < 10:
                radius = 10
                bot.reply_to(message, f"⚠️ Radius terlalu kecil, gunakan minimal 10m")
            elif radius > 2000:
                radius = 2000
                bot.reply_to(message, f"⚠️ Radius terlalu besar, gunakan maksimal 2000m")
            else:
                bot.reply_to(message, f"✅ Radius pencarian: {radius}m\n\nGunakan format:\n/cari <lat> <lng> {radius}")
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
        "   `/cari -3.3219 114.6034 250`\n\n"
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
        radius = DEFAULT_RADIUS  # Default radius
        
        if len(args) >= 4:
            radius = int(args[3])
            
        # Kirim pesan "sedang mencari"
        wait_msg = bot.send_message(message.chat.id, f"🔍 Mencari ODP dalam radius {radius}m dari koordinat {lat}, {lng}...")
        
        # Muat data jika belum dimuat
        if spreadsheet_data is None:
            load_spreadsheet_data()
            
        # Cari ODP terdekat (menampilkan semua titik dan dengan pengukuran berdasarkan rute)
        nearby_odps = find_nearby_odps(lat, lng, radius, use_route_distance=True, only_available=False)
        
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
        
        # Buat dan kirim peta dengan citra satelit dan rute
        map_file = create_odp_map(lat, lng, nearby_odps, radius, with_routes=True, use_satellite=True)
        
        if map_file:
            caption = f"🗺️ Peta satelit {len(nearby_odps)} ODP dalam radius {radius}m dengan rute"
            with open(map_file, 'rb') as photo:
                bot.send_photo(message.chat.id, photo, caption=caption)
                
            # Tambahkan opsi untuk melihat peta jalan juga
            keyboard = types.InlineKeyboardMarkup()
            btn_street = types.InlineKeyboardButton(text="🗺️ Lihat Peta Jalan", callback_data=f"street_{lat}_{lng}_{radius}")
            btn_satellite_no_route = types.InlineKeyboardButton(text="🛰️ Satelit Tanpa Rute", callback_data=f"sat_noroute_{lat}_{lng}_{radius}")
            keyboard.add(btn_street, btn_satellite_no_route)
            
            bot.send_message(message.chat.id, "Opsi tampilan peta lainnya:", reply_markup=keyboard)
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
    radius = DEFAULT_RADIUS  # Default
    
    # Kirim pesan "sedang mencari"
    wait_msg = bot.send_message(message.chat.id, f"🔍 Mencari ODP dalam radius {radius}m dari lokasi Anda...")
    
    # Muat data jika belum dimuat
    if spreadsheet_data is None:
        load_spreadsheet_data()
        
    # Cari ODP terdekat (menampilkan semua titik dan dengan pengukuran berdasarkan rute)
    nearby_odps = find_nearby_odps(lat, lng, radius, use_route_distance=True, only_available=False)
    
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
    
    # Buat dan kirim peta dengan citra satelit dan rute
    map_file = None
    caption = None
    
    try:
        map_file = create_odp_map(lat, lng, nearby_odps, radius, with_routes=True, use_satellite=True)
        caption = f"🗺️ Peta satelit {len(nearby_odps)} ODP dalam radius {radius}m dari lokasi Anda dengan rute"
    except Exception as e:
        logger.error(f"Error saat membuat peta awal: {e}")
        map_file = None
        
    if map_file:
        try:
            with open(map_file, 'rb') as photo:
                bot.send_photo(message.chat.id, photo, caption=caption)
        except Exception as e:
            logger.error(f"Error saat mengirim file peta: {e}")
            bot.send_message(message.chat.id, "❌ Gagal mengirim peta ODP.")
            
        # Tambahkan opsi untuk melihat peta jalan juga
        keyboard = types.InlineKeyboardMarkup()
        btn_street = types.InlineKeyboardButton(text="🗺️ Lihat Peta Jalan", callback_data=f"street_{lat}_{lng}_{radius}")
        btn_satellite_no_route = types.InlineKeyboardButton(text="🛰️ Satelit Tanpa Rute", callback_data=f"sat_noroute_{lat}_{lng}_{radius}")
        keyboard.add(btn_street, btn_satellite_no_route)
        
        bot.send_message(message.chat.id, "Opsi tampilan peta lainnya:", reply_markup=keyboard)
    else:
        bot.send_message(message.chat.id, "❌ Gagal membuat peta ODP.")

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    """Tangani callback dari tombol inline."""
    try:
        # Ekstrak data dari callback
        data = call.data
        
        if data.startswith("street_") or data.startswith("sat_noroute_") or data.startswith("satellite_"):
            # Format: "type_lat_lng_radius"
            parts = data.split("_")
            map_type = parts[0]
            lat = float(parts[1])
            lng = float(parts[2])
            radius = int(parts[3])
            
            # Kirim notifikasi "sedang memproses"
            bot.answer_callback_query(
                call.id, 
                text="Memproses permintaan peta...", 
                show_alert=False
            )
            
            # Pesan sesuai jenis peta yang diminta
            peta_msg = "jalan" if map_type == "street" else "satelit tanpa rute"
            if map_type == "satellite":
                peta_msg = "satelit dengan detail jalan & bangunan"
            
            # Kirim pesan "sedang membuat peta"
            wait_msg = bot.send_message(
                call.message.chat.id, 
                f"🔄 Membuat peta {peta_msg}..."
            )
            
            # Muat data jika belum dimuat
            if spreadsheet_data is None:
                load_spreadsheet_data()
                
            # Cari ODP terdekat (menampilkan semua titik dan dengan pengukuran berdasarkan rute)
            nearby_odps = find_nearby_odps(lat, lng, radius, use_route_distance=True, only_available=False)
            
            if nearby_odps is None or nearby_odps.empty:
                bot.edit_message_text(
                    "❌ Terjadi error saat mencari ODP.",
                    call.message.chat.id, 
                    wait_msg.message_id
                )
                return
                
            # Buat peta sesuai dengan tipe yang diminta
            map_file = None
            caption = None
            
            try:
                if map_type == "street":
                    # Peta jalan (OpenStreetMap)
                    map_file = create_odp_map(lat, lng, nearby_odps, radius, with_routes=True, use_satellite=False)
                    caption = f"🗺️ Peta jalan {len(nearby_odps)} ODP dalam radius {radius}m dengan rute"
                elif map_type == "sat_noroute":
                    # Peta satelit tanpa rute
                    map_file = create_odp_map(lat, lng, nearby_odps, radius, with_routes=False, use_satellite=True)
                    caption = f"🛰️ Peta satelit {len(nearby_odps)} ODP dalam radius {radius}m tanpa rute"
                elif map_type == "satellite":
                    # Peta satelit Google Hybrid (dengan jalan dan bangunan) dengan rute
                    map_file = create_odp_map(lat, lng, nearby_odps, radius, with_routes=True, use_satellite=True)
                    caption = f"🏘️ Peta satelit {len(nearby_odps)} ODP dalam radius {radius}m dengan jalan & bangunan"
            except Exception as e:
                logger.error(f"Error saat membuat peta {map_type}: {e}")
                map_file = None
                
            if map_file:
                # Hapus pesan tunggu
                bot.delete_message(call.message.chat.id, wait_msg.message_id)
                
                # Kirim gambar peta
                with open(map_file, 'rb') as photo:
                    bot.send_photo(call.message.chat.id, photo, caption=caption)
            else:
                bot.edit_message_text(
                    "❌ Gagal membuat peta ODP.", 
                    call.message.chat.id, 
                    wait_msg.message_id
                )
        
    except Exception as e:
        logger.error(f"Error saat menangani callback: {e}")
        bot.answer_callback_query(
            call.id, 
            text="Terjadi error saat memproses permintaan.", 
            show_alert=True
        )

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
        radius = DEFAULT_RADIUS  # Default
        
        # Kirim pesan "sedang mencari"
        wait_msg = bot.send_message(message.chat.id, f"🔍 Mencari ODP dalam radius {radius}m dari koordinat {lat}, {lng}...")
        
        # Muat data jika belum dimuat
        if spreadsheet_data is None:
            load_spreadsheet_data()
            
        # Cari ODP terdekat (menampilkan semua titik dan dengan pengukuran berdasarkan rute)
        nearby_odps = find_nearby_odps(lat, lng, radius, use_route_distance=True, only_available=False)
        
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
        
        # Buat dan kirim peta dengan citra satelit dan rute
        map_file = create_odp_map(lat, lng, nearby_odps, radius, with_routes=True, use_satellite=True)
        
        if map_file:
            caption = f"🗺️ Peta satelit {len(nearby_odps)} ODP dalam radius {radius}m dengan rute"
            with open(map_file, 'rb') as photo:
                bot.send_photo(message.chat.id, photo, caption=caption)
                
            # Tambahkan opsi untuk melihat peta jalan juga
            keyboard = types.InlineKeyboardMarkup()
            btn_street = types.InlineKeyboardButton(text="🗺️ Lihat Peta Jalan", callback_data=f"street_{lat}_{lng}_{radius}")
            btn_satellite_no_route = types.InlineKeyboardButton(text="🛰️ Satelit Tanpa Rute", callback_data=f"sat_noroute_{lat}_{lng}_{radius}")
            keyboard.add(btn_street, btn_satellite_no_route)
            
            bot.send_message(message.chat.id, "Opsi tampilan peta lainnya:", reply_markup=keyboard)
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
    
    # Jalankan bot dengan penanganan error dan keep_alive=True
    # Ini akan mencoba terus menjalankan bot bahkan jika terjadi error
    # Dan akan tetap berjalan meskipun Replit ditutup (dengan Always On)
    # Paramater waktu yang lebih pendek untuk mencegah koneksi hang
    bot.infinity_polling(timeout=30, long_polling_timeout=15, 
                        allowed_updates=None, skip_pending=True, 
                        none_stop=True, interval=2)

if __name__ == "__main__":
    main()