import pandas as pd
import csv
from geopy.distance import geodesic

class CsvLocationBot:
    def __init__(self, csv_path=None):
        """
        Inisialisasi bot lokasi dengan data dari file CSV.
        
        Args:
            csv_path: Path ke file CSV dengan data lokasi
        """
        self.csv_path = csv_path
        self.locations_df = None
        
        if csv_path:
            self.load_data(csv_path)
    
    def load_data(self, csv_path):
        """
        Muat data dari file CSV.
        
        Args:
            csv_path: Path ke file CSV
        
        Returns:
            True jika berhasil, False jika gagal
        """
        try:
            self.locations_df = pd.read_csv(csv_path)
            print(f"Berhasil memuat {len(self.locations_df)} baris data dari {csv_path}.")
            return True
        except Exception as e:
            print(f"Error saat memuat file CSV: {e}")
            return False
    
    def find_nearby_locations(self, lat_col, lng_col, ref_lat, ref_lng, radius_meters=250):
        """
        Temukan lokasi dalam radius tertentu dari titik referensi.
        
        Args:
            lat_col: Nama kolom latitude
            lng_col: Nama kolom longitude
            ref_lat: Latitude titik referensi
            ref_lng: Longitude titik referensi
            radius_meters: Radius pencarian dalam meter
            
        Returns:
            DataFrame dengan lokasi-lokasi yang berada dalam radius
        """
        if self.locations_df is None:
            print("Error: Data belum dimuat. Gunakan metode load_data() terlebih dahulu.")
            return None
        
        # Pastikan kolom lat dan lng ada di DataFrame
        if lat_col not in self.locations_df.columns or lng_col not in self.locations_df.columns:
            print(f"Error: Kolom {lat_col} atau {lng_col} tidak ditemukan di data.")
            return None
        
        # Konversi nilai latitude dan longitude ke tipe numerik
        self.locations_df[lat_col] = pd.to_numeric(self.locations_df[lat_col], errors='coerce')
        self.locations_df[lng_col] = pd.to_numeric(self.locations_df[lng_col], errors='coerce')
        
        # Hapus data dengan lat/lng yang tidak valid
        valid_df = self.locations_df.dropna(subset=[lat_col, lng_col]).copy()
        
        # Titik referensi
        ref_point = (ref_lat, ref_lng)
        
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
        
        print(f"Ditemukan {len(nearby_locations)} lokasi dalam radius {radius_meters} meter.")
        return nearby_locations

def export_spreadsheet_to_csv():
    """
    Fungsi untuk mengekspor spreadsheet ke CSV.
    
    Instruksi untuk pengguna:
    1. Buka spreadsheet Anda di Google Sheets
    2. Klik File > Download > Comma-separated values (.csv)
    3. Upload file CSV tersebut ke Replit
    """
    print("Untuk mengekspor spreadsheet Anda ke format CSV:")
    print("1. Buka spreadsheet Anda di Google Sheets")
    print("2. Klik File > Download > Comma-separated values (.csv)")
    print("3. Upload file CSV tersebut ke Replit")
    print("4. Gunakan file CSV tersebut dengan bot ini")
    print()

def print_header():
    """Tampilkan header aplikasi."""
    print("=" * 60)
    print("           BOT PENCARI LOKASI DALAM RADIUS")
    print("=" * 60)
    print("Bot ini membantu menemukan lokasi dari file CSV")
    print("yang berada dalam radius tertentu dari titik yang ditentukan.")
    print("=" * 60)
    print()

def format_result(df):
    """Format dan tampilkan hasil pencarian."""
    if len(df) == 0:
        print("Tidak ada lokasi yang ditemukan dalam radius yang ditentukan.")
        return
    
    print(f"\nDitemukan {len(df)} lokasi:")
    print("-" * 80)
    
    # Tampilkan semua kolom, tapi prioritaskan kolom penting
    columns_to_show = list(df.columns)
    
    # Cek apakah ada kolom nama atau serupa
    name_cols = [col for col in df.columns if 'nama' in col.lower() or 'name' in col.lower()]
    lat_cols = [col for col in df.columns if 'lat' in col.lower()]
    lng_cols = [col for col in df.columns if 'lon' in col.lower() or 'lng' in col.lower()]
    
    important_cols = name_cols + lat_cols + lng_cols + ['jarak_meter']
    other_cols = [col for col in df.columns if col not in important_cols]
    
    # Format daftar kolom untuk ditampilkan
    display_cols = important_cols + other_cols
    
    # Cetak header
    header = "No  "
    for col in display_cols:
        if col == 'jarak_meter':
            header += f"{'Jarak (m)':<12}"
        else:
            header += f"{col:<20}"
    print(header)
    print("-" * 80)
    
    # Cetak data
    for idx, row in df.iterrows():
        line = f"{idx+1:<4}"
        for col in display_cols:
            value = row[col]
            if col == 'jarak_meter':
                line += f"{value:<12.2f}"
            elif isinstance(value, float):
                line += f"{value:<20.6f}"
            else:
                line += f"{str(value):<20}"
        print(line)
    
    print("-" * 80)
    print(f"Jarak terdekat: {df['jarak_meter'].min():.2f} meter")
    print(f"Jarak terjauh: {df['jarak_meter'].max():.2f} meter")
    print(f"Jarak rata-rata: {df['jarak_meter'].mean():.2f} meter")

def main():
    print_header()
    
    # Cetak instruksi ekspor spreadsheet
    export_spreadsheet_to_csv()
    
    # Minta path file CSV
    csv_path = input("Masukkan nama file CSV (contoh: locations.csv): ")
    
    # Buat instance bot
    bot = CsvLocationBot()
    
    # Coba muat data
    if not bot.load_data(csv_path):
        print("Gagal memuat data. Program berhenti.")
        return
    
    # Tampilkan kolom-kolom yang tersedia
    print("\nKolom-kolom yang tersedia di file CSV:")
    for col in bot.locations_df.columns:
        print(f"- {col}")
    
    # Minta nama kolom lat/lng
    lat_col = input("\nMasukkan nama kolom latitude: ")
    lng_col = input("Masukkan nama kolom longitude: ")
    
    # Minta koordinat referensi
    try:
        ref_lat = float(input("\nMasukkan latitude titik referensi: "))
        ref_lng = float(input("Masukkan longitude titik referensi: "))
        radius = float(input("\nMasukkan radius pencarian (meter) [default: 250]: ") or "250")
    except ValueError:
        print("Error: Koordinat harus berupa angka.")
        return
    
    # Cari lokasi terdekat
    nearby = bot.find_nearby_locations(lat_col, lng_col, ref_lat, ref_lng, radius)
    
    if nearby is not None:
        # Tampilkan hasil
        format_result(nearby)
        
        # Tanya jika ingin menyimpan hasil
        save = input("\nApakah Anda ingin menyimpan hasil ke file CSV? (y/n): ")
        if save.lower() == 'y':
            output_file = input("Masukkan nama file output [default: nearby_locations.csv]: ") or "nearby_locations.csv"
            nearby.to_csv(output_file, index=False)
            print(f"Hasil berhasil disimpan ke {output_file}")

if __name__ == "__main__":
    main()