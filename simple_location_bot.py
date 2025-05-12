import math
import pandas as pd
from geopy.distance import geodesic

class SimpleLocationBot:
    def __init__(self):
        """Inisialisasi bot dengan data lokasi contoh dari Jakarta."""
        # Data lokasi contoh (nama, latitude, longitude, jenis)
        self.locations_data = [
            {"nama": "Monas", "latitude": -6.1754, "longitude": 106.8272, "jenis": "Landmark"},
            {"nama": "Istana Merdeka", "latitude": -6.1701, "longitude": 106.8235, "jenis": "Pemerintahan"},
            {"nama": "Masjid Istiqlal", "latitude": -6.1699, "longitude": 106.8308, "jenis": "Tempat Ibadah"},
            {"nama": "Stasiun Gambir", "latitude": -6.1766, "longitude": 106.8307, "jenis": "Transportasi"},
            {"nama": "Museum Nasional", "latitude": -6.1763, "longitude": 106.8222, "jenis": "Museum"},
            {"nama": "Gedung Pancasila", "latitude": -6.1702, "longitude": 106.8313, "jenis": "Pemerintahan"},
            {"nama": "Bundaran HI", "latitude": -6.1950, "longitude": 106.8232, "jenis": "Landmark"},
            {"nama": "Grand Indonesia", "latitude": -6.1951, "longitude": 106.8208, "jenis": "Mall"},
            {"nama": "Plaza Indonesia", "latitude": -6.1934, "longitude": 106.8233, "jenis": "Mall"},
            {"nama": "Hotel Indonesia", "latitude": -6.1943, "longitude": 106.8244, "jenis": "Hotel"},
            {"nama": "Thamrin City", "latitude": -6.1925, "longitude": 106.8206, "jenis": "Mall"},
            {"nama": "Sarinah", "latitude": -6.1871, "longitude": 106.8242, "jenis": "Mall"},
            {"nama": "Kantor Pos Jakarta Pusat", "latitude": -6.1675, "longitude": 106.8295, "jenis": "Layanan"},
            {"nama": "RS Jakarta", "latitude": -6.1743, "longitude": 106.8331, "jenis": "Rumah Sakit"},
            {"nama": "Katedral Jakarta", "latitude": -6.1695, "longitude": 106.8317, "jenis": "Tempat Ibadah"},
            {"nama": "Pasar Baru", "latitude": -6.1654, "longitude": 106.8361, "jenis": "Pasar"},
            {"nama": "Gedung Kesenian Jakarta", "latitude": -6.1712, "longitude": 106.8289, "jenis": "Kesenian"},
            {"nama": "Kedutaan Amerika Serikat", "latitude": -6.1819, "longitude": 106.8302, "jenis": "Kedutaan"},
            {"nama": "Stasiun Juanda", "latitude": -6.1667, "longitude": 106.8317, "jenis": "Transportasi"},
            {"nama": "Taman Suropati", "latitude": -6.1998, "longitude": 106.8388, "jenis": "Taman"},
            {"nama": "Taman Menteng", "latitude": -6.1962, "longitude": 106.8302, "jenis": "Taman"},
            {"nama": "Plaza Senayan", "latitude": -6.2256, "longitude": 106.7992, "jenis": "Mall"},
            {"nama": "Senayan City", "latitude": -6.2272, "longitude": 106.7981, "jenis": "Mall"},
            {"nama": "Roxy Square", "latitude": -6.1612, "longitude": 106.8013, "jenis": "Mall"},
            {"nama": "Museum Gajah", "latitude": -6.1763, "longitude": 106.8222, "jenis": "Museum"},
            {"nama": "Perpustakaan Nasional", "latitude": -6.1869, "longitude": 106.8238, "jenis": "Pendidikan"},
            {"nama": "RS Cipto Mangunkusumo", "latitude": -6.1904, "longitude": 106.8508, "jenis": "Rumah Sakit"},
            {"nama": "Gedung MPR/DPR", "latitude": -6.2080, "longitude": 106.8022, "jenis": "Pemerintahan"},
            {"nama": "Stasiun Sudirman", "latitude": -6.2019, "longitude": 106.8228, "jenis": "Transportasi"},
            {"nama": "Pacific Place", "latitude": -6.2243, "longitude": 106.8100, "jenis": "Mall"}
        ]
        
        # Konversi ke DataFrame
        self.locations_df = pd.DataFrame(self.locations_data)
    
    def find_nearby_locations(self, ref_lat, ref_lng, radius_meters=250):
        """
        Temukan lokasi dalam radius tertentu dari titik referensi.
        
        Args:
            ref_lat: Latitude titik referensi
            ref_lng: Longitude titik referensi
            radius_meters: Radius pencarian dalam meter
            
        Returns:
            DataFrame dengan lokasi-lokasi yang berada dalam radius
        """
        # Titik referensi
        ref_point = (ref_lat, ref_lng)
        
        # Hitung jarak untuk setiap lokasi
        distances = []
        for _, row in self.locations_df.iterrows():
            location_point = (row['latitude'], row['longitude'])
            distance = geodesic(ref_point, location_point).meters
            distances.append(distance)
        
        # Tambahkan kolom jarak
        result_df = self.locations_df.copy()
        result_df['jarak_meter'] = distances
        
        # Filter lokasi dalam radius yang ditentukan
        nearby_locations = result_df[result_df['jarak_meter'] <= radius_meters].copy()
        
        # Urutkan berdasarkan jarak
        nearby_locations = nearby_locations.sort_values('jarak_meter')
        
        return nearby_locations

    def list_locations(self):
        """Tampilkan daftar semua lokasi yang tersedia."""
        for idx, row in self.locations_df.iterrows():
            print(f"{idx+1}. {row['nama']} ({row['jenis']}) - Koordinat: {row['latitude']}, {row['longitude']}")
    
    def get_location_info(self, location_name):
        """Dapatkan informasi lokasi berdasarkan nama."""
        location = self.locations_df[self.locations_df['nama'].str.lower() == location_name.lower()]
        if len(location) > 0:
            row = location.iloc[0]
            print(f"\nInformasi Lokasi:")
            print(f"Nama: {row['nama']}")
            print(f"Jenis: {row['jenis']}")
            print(f"Koordinat: {row['latitude']}, {row['longitude']}")
            return row['latitude'], row['longitude']
        else:
            print(f"Lokasi '{location_name}' tidak ditemukan.")
            return None

def print_header():
    """Tampilkan header aplikasi."""
    print("=" * 60)
    print("           BOT PENCARI LOKASI DALAM RADIUS")
    print("=" * 60)
    print("Bot ini membantu menemukan lokasi yang berada dalam")
    print("radius tertentu dari titik koordinat yang ditentukan.")
    print("=" * 60)
    print()

def format_result(df):
    """Format dan tampilkan hasil pencarian."""
    if len(df) == 0:
        print("Tidak ada lokasi yang ditemukan dalam radius yang ditentukan.")
        return
    
    print(f"\nDitemukan {len(df)} lokasi:")
    print("-" * 80)
    print(f"{'No':3} {'Nama':<25} {'Jenis':<15} {'Jarak (m)':<10} {'Koordinat'}")
    print("-" * 80)
    
    for idx, row in df.iterrows():
        coord = f"{row['latitude']}, {row['longitude']}"
        print(f"{idx+1:3} {row['nama']:<25} {row['jenis']:<15} {row['jarak_meter']:<10.2f} {coord}")
    
    print("-" * 80)
    print(f"Jarak terdekat: {df['jarak_meter'].min():.2f} meter")
    print(f"Jarak terjauh: {df['jarak_meter'].max():.2f} meter")
    print(f"Jarak rata-rata: {df['jarak_meter'].mean():.2f} meter")

def search_by_coordinates():
    """Pencarian berdasarkan koordinat yang dimasukkan pengguna."""
    try:
        ref_lat = float(input("\nMasukkan latitude titik referensi: "))
        ref_lng = float(input("Masukkan longitude titik referensi: "))
        radius = float(input("\nMasukkan radius pencarian (meter) [default: 250]: ") or "250")
        
        bot = SimpleLocationBot()
        results = bot.find_nearby_locations(ref_lat, ref_lng, radius)
        
        print(f"\nHasil pencarian dalam radius {radius}m dari koordinat ({ref_lat}, {ref_lng}):")
        format_result(results)
    except ValueError:
        print("Error: Masukan tidak valid. Pastikan koordinat dalam format angka desimal.")

def search_by_location_name():
    """Pencarian berdasarkan nama lokasi yang sudah ada di daftar."""
    bot = SimpleLocationBot()
    
    print("\nDaftar lokasi yang tersedia:")
    bot.list_locations()
    
    location_name = input("\nMasukkan nama lokasi referensi: ")
    location_coords = bot.get_location_info(location_name)
    
    if location_coords:
        ref_lat, ref_lng = location_coords
        radius = float(input("\nMasukkan radius pencarian (meter) [default: 250]: ") or "250")
        
        results = bot.find_nearby_locations(ref_lat, ref_lng, radius)
        
        print(f"\nHasil pencarian dalam radius {radius}m dari {location_name}:")
        format_result(results)

def filter_by_type():
    """Filter lokasi berdasarkan jenisnya."""
    bot = SimpleLocationBot()
    
    # Dapatkan jenis-jenis yang tersedia
    jenis_list = bot.locations_df['jenis'].unique()
    
    print("\nJenis lokasi yang tersedia:")
    for idx, jenis in enumerate(jenis_list):
        print(f"{idx+1}. {jenis}")
    
    try:
        jenis_idx = int(input("\nPilih nomor jenis lokasi: ")) - 1
        selected_jenis = jenis_list[jenis_idx]
        
        # Filter berdasarkan jenis
        filtered = bot.locations_df[bot.locations_df['jenis'] == selected_jenis]
        
        print(f"\nDaftar lokasi dengan jenis '{selected_jenis}':")
        for idx, row in filtered.iterrows():
            print(f"{idx+1}. {row['nama']} - Koordinat: {row['latitude']}, {row['longitude']}")
    except (ValueError, IndexError):
        print("Error: Pilihan tidak valid.")

def main_menu():
    """Tampilkan menu utama aplikasi."""
    while True:
        print_header()
        
        print("MENU UTAMA:")
        print("1. Cari lokasi berdasarkan koordinat")
        print("2. Cari lokasi berdasarkan nama lokasi")
        print("3. Filter lokasi berdasarkan jenis")
        print("0. Keluar")
        print()
        
        choice = input("Pilih menu (0-3): ")
        
        if choice == '1':
            search_by_coordinates()
        elif choice == '2':
            search_by_location_name()
        elif choice == '3':
            filter_by_type()
        elif choice == '0':
            print("\nTerima kasih telah menggunakan Bot Pencari Lokasi!")
            break
        else:
            print("\nPilihan tidak valid. Silakan coba lagi.")
        
        input("\nTekan Enter untuk kembali ke menu utama...")

if __name__ == "__main__":
    main_menu()