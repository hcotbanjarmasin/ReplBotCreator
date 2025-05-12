import os
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from geopy.distance import geodesic
import json

class LocationBot:
    def __init__(self, credentials_path=None):
        """
        Inisialisasi bot lokasi.
        
        Args:
            credentials_path: Path ke file kredensial Google Sheets (JSON)
        """
        self.credentials_path = credentials_path
        self.client = None
        self.connect_to_sheets()
    
    def connect_to_sheets(self):
        """Hubungkan ke Google Sheets API."""
        try:
            if not self.credentials_path and os.path.exists('credentials.json'):
                self.credentials_path = 'credentials.json'
            
            if not self.credentials_path:
                print("Error: Tidak ditemukan file kredensial.")
                return False
            
            # Definisikan scope
            scope = ['https://spreadsheets.google.com/feeds',
                    'https://www.googleapis.com/auth/drive']
            
            # Tambahkan kredensial untuk mengakses API
            creds = ServiceAccountCredentials.from_json_keyfile_name(self.credentials_path, scope)
            self.client = gspread.authorize(creds)
            print("Berhasil terhubung ke Google Sheets API!")
            return True
        except Exception as e:
            print(f"Error saat menghubungkan ke Google Sheets: {e}")
            return False
    
    def load_spreadsheet(self, spreadsheet_name, worksheet_name=0):
        """
        Muat data dari spreadsheet.
        
        Args:
            spreadsheet_name: Nama spreadsheet
            worksheet_name: Nama worksheet (atau indeks)
            
        Returns:
            DataFrame dengan data spreadsheet
        """
        try:
            if not self.client:
                if not self.connect_to_sheets():
                    return None
            
            # Buka spreadsheet berdasarkan nama
            sheet = self.client.open(spreadsheet_name)
            
            # Pilih worksheet (lembar kerja)
            if isinstance(worksheet_name, int):
                worksheet = sheet.get_worksheet(worksheet_name)
            else:
                worksheet = sheet.worksheet(worksheet_name)
            
            # Ambil semua data
            data = worksheet.get_all_records()
            
            # Konversi ke pandas DataFrame untuk kemudahan manipulasi
            df = pd.DataFrame(data)
            
            print(f"Berhasil memuat {len(df)} baris data dari spreadsheet.")
            return df
        except Exception as e:
            print(f"Error saat memuat spreadsheet: {e}")
            return None
    
    def find_nearby_locations(self, df, lat_col, lng_col, ref_lat, ref_lng, radius_meters=250):
        """
        Temukan lokasi dalam radius tertentu dari titik referensi.
        
        Args:
            df: DataFrame dengan data lokasi
            lat_col: Nama kolom latitude
            lng_col: Nama kolom longitude
            ref_lat: Latitude titik referensi
            ref_lng: Longitude titik referensi
            radius_meters: Radius pencarian dalam meter
            
        Returns:
            DataFrame dengan lokasi-lokasi yang berada dalam radius
        """
        try:
            # Pastikan kolom lat dan lng ada di DataFrame
            if lat_col not in df.columns or lng_col not in df.columns:
                print(f"Error: Kolom {lat_col} atau {lng_col} tidak ditemukan di spreadsheet.")
                return None
            
            # Konversi nilai latitude dan longitude ke tipe numerik
            df[lat_col] = pd.to_numeric(df[lat_col], errors='coerce')
            df[lng_col] = pd.to_numeric(df[lng_col], errors='coerce')
            
            # Hapus data dengan lat/lng yang tidak valid
            df = df.dropna(subset=[lat_col, lng_col])
            
            # Titik referensi
            ref_point = (ref_lat, ref_lng)
            
            # Buat kolom jarak
            df['distance_meters'] = df.apply(
                lambda row: geodesic((row[lat_col], row[lng_col]), ref_point).meters,
                axis=1
            )
            
            # Filter lokasi dalam radius yang ditentukan
            nearby_locations = df[df['distance_meters'] <= radius_meters].copy()
            
            # Urutkan berdasarkan jarak
            nearby_locations = nearby_locations.sort_values('distance_meters')
            
            print(f"Ditemukan {len(nearby_locations)} lokasi dalam radius {radius_meters} meter.")
            return nearby_locations
        except Exception as e:
            print(f"Error saat mencari lokasi terdekat: {e}")
            return None

    def create_credentials_file(self, credentials_json):
        """
        Buat file kredensial dari string JSON.
        
        Args:
            credentials_json: String JSON kredensial
            
        Returns:
            Path ke file kredensial
        """
        try:
            # Tulis ke file
            with open('credentials.json', 'w') as f:
                f.write(credentials_json)
            
            self.credentials_path = 'credentials.json'
            print("File kredensial berhasil dibuat.")
            return self.credentials_path
        except Exception as e:
            print(f"Error saat membuat file kredensial: {e}")
            return None

# Contoh penggunaan
if __name__ == "__main__":
    # Cek apakah kredensial sudah ada atau perlu input
    if not os.path.exists('credentials.json'):
        print("File kredensial tidak ditemukan. Silakan ikuti instruksi berikut:")
        print("1. Buka https://console.developers.google.com/")
        print("2. Buat proyek baru dan aktifkan Google Sheets API dan Google Drive API")
        print("3. Buat Service Account dan unduh file JSON kredensial")
        print("4. Rename file tersebut menjadi 'credentials.json' dan upload ke Replit")
        print("5. Pastikan untuk membagikan spreadsheet Anda dengan email service account di file kredensial")
        exit()
    
    # Buat instance bot
    bot = LocationBot()
    
    # Contoh: Ambil input dari pengguna
    spreadsheet_name = input("Masukkan nama spreadsheet: ")
    worksheet_name = input("Masukkan nama worksheet (atau kosongkan untuk worksheet pertama): ")
    
    if not worksheet_name:
        worksheet_name = 0
    
    # Muat data dari spreadsheet
    data = bot.load_spreadsheet(spreadsheet_name, worksheet_name)
    
    if data is None:
        print("Gagal memuat data. Pastikan spreadsheet dan worksheet sudah benar.")
        exit()
    
    # Tampilkan kolom yang tersedia
    print("\nKolom-kolom yang tersedia:")
    for col in data.columns:
        print(f"- {col}")
    
    # Input kolom lat/lng
    lat_col = input("\nMasukkan nama kolom latitude: ")
    lng_col = input("Masukkan nama kolom longitude: ")
    
    # Input koordinat referensi
    ref_lat = float(input("\nMasukkan latitude titik referensi: "))
    ref_lng = float(input("Masukkan longitude titik referensi: "))
    
    # Tentukan radius pencarian
    radius = float(input("\nMasukkan radius pencarian (meter): ") or "250")
    
    # Cari lokasi terdekat
    nearby = bot.find_nearby_locations(data, lat_col, lng_col, ref_lat, ref_lng, radius)
    
    if nearby is not None and not nearby.empty:
        print("\nLokasi-lokasi dalam radius yang ditentukan:")
        # Cetak hasil dengan format yang bagus
        pd.set_option('display.max_columns', None)
        pd.set_option('display.width', 1000)
        print(nearby)
        
        print("\nStatistik jarak:")
        print(f"Jarak terdekat: {nearby['distance_meters'].min():.2f} meter")
        print(f"Jarak terjauh: {nearby['distance_meters'].max():.2f} meter")
        print(f"Jarak rata-rata: {nearby['distance_meters'].mean():.2f} meter")
        
        # Tanyakan apakah ingin menyimpan hasil
        save = input("\nApakah Anda ingin menyimpan hasil ke file CSV? (y/n): ")
        if save.lower() == 'y':
            filename = input("Masukkan nama file: ") or "nearby_locations.csv"
            nearby.to_csv(filename, index=False)
            print(f"Hasil berhasil disimpan ke {filename}")
    else:
        print("Tidak ditemukan lokasi dalam radius yang ditentukan.")