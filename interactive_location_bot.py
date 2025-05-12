import os
import json
import pandas as pd
from location_bot import LocationBot
from geopy.geocoders import Nominatim

def clear_screen():
    """Bersihkan layar terminal."""
    os.system('cls' if os.name == 'nt' else 'clear')

def print_header():
    """Tampilkan header aplikasi."""
    print("=" * 60)
    print("           BOT PENCARI LOKASI DALAM RADIUS 250M")
    print("=" * 60)
    print("Bot ini membantu menemukan lokasi dari spreadsheet")
    print("yang berada dalam radius tertentu dari titik yang ditentukan.")
    print("=" * 60)
    print()

def get_credentials():
    """Dapatkan atau buat file kredensial Google API."""
    if os.path.exists('credentials.json'):
        print("File kredensial ditemukan.")
        return True
    
    print("File kredensial tidak ditemukan.")
    print("Anda perlu membuat Service Account di Google Cloud Console.")
    
    choice = input("Apakah Anda memiliki kredensial JSON untuk dimasukkan? (y/n): ")
    
    if choice.lower() == 'y':
        print("Silakan tempelkan (paste) konten file kredensial JSON Anda:")
        print("(Tekan Enter, lalu Ctrl+D (Unix) atau Ctrl+Z, lalu Enter (Windows) setelah selesai)")
        
        lines = []
        while True:
            try:
                line = input()
                lines.append(line)
            except EOFError:
                break
        
        credentials_json = '\n'.join(lines)
        
        try:
            # Validasi JSON
            json.loads(credentials_json)
            
            # Tulis ke file
            with open('credentials.json', 'w') as f:
                f.write(credentials_json)
            
            print("File kredensial berhasil dibuat.")
            return True
        except json.JSONDecodeError:
            print("Error: Format JSON tidak valid.")
            return False
    else:
        print("\nUntuk membuat kredensial baru:")
        print("1. Buka https://console.cloud.google.com/")
        print("2. Buat proyek baru (atau gunakan yang sudah ada)")
        print("3. Aktifkan Google Sheets API dan Google Drive API")
        print("4. Buat Service Account dan unduh file JSON kredensial")
        print("5. Rename file tersebut menjadi 'credentials.json' dan upload ke Replit")
        return False

def load_sample_data():
    """Muat atau buat data sampel."""
    if not os.path.exists('sample_locations.csv'):
        print("Membuat data sampel...")
        from sample_data_generator import generate_sample_locations, save_to_csv
        locations = generate_sample_locations()
        save_to_csv(locations)
    
    print("Data sampel tersedia di 'sample_locations.csv'")
    print("Anda dapat mengimpor file ini ke Google Sheets untuk pengujian.")
    print()
    print("Petunjuk impor ke Google Sheets:")
    print("1. Buka spreadsheet baru di Google Sheets")
    print("2. Pilih File > Import > Upload > Pilih file sample_locations.csv")
    print("3. Pilih 'Replace current sheet' dan 'Detect automatically'")
    print("4. Klik Import data")
    print("5. Bagikan spreadsheet ini dengan Service Account di file credentials.json")
    print()

def get_coordinates_from_address(address):
    """Konversi alamat menjadi koordinat menggunakan geocoding."""
    try:
        geolocator = Nominatim(user_agent="location-bot")
        location = geolocator.geocode(address)
        
        if location:
            return location.latitude, location.longitude
        else:
            return None
    except Exception as e:
        print(f"Error saat geocoding: {e}")
        return None

def main_menu():
    """Tampilkan menu utama aplikasi."""
    while True:
        clear_screen()
        print_header()
        
        print("MENU UTAMA:")
        print("1. Cari lokasi dari spreadsheet")
        print("2. Hasilkan data sampel")
        print("3. Bantuan dan Petunjuk")
        print("0. Keluar")
        print()
        
        choice = input("Pilih menu (0-3): ")
        
        if choice == '1':
            search_locations()
        elif choice == '2':
            load_sample_data()
            input("\nTekan Enter untuk kembali ke menu utama...")
        elif choice == '3':
            show_help()
        elif choice == '0':
            print("\nTerima kasih telah menggunakan Bot Pencari Lokasi!")
            break
        else:
            print("\nPilihan tidak valid. Silakan coba lagi.")
            input("Tekan Enter untuk melanjutkan...")

def search_locations():
    """Proses utama pencarian lokasi."""
    clear_screen()
    print_header()
    
    # Cek kredensial
    if not get_credentials():
        input("\nTekan Enter untuk kembali ke menu utama...")
        return
    
    # Buat instance bot
    bot = LocationBot()
    
    # Input spreadsheet
    print("DETAIL SPREADSHEET:")
    spreadsheet_name = input("Masukkan nama spreadsheet: ")
    worksheet_name = input("Masukkan nama worksheet (kosongkan untuk worksheet pertama): ")
    
    if not worksheet_name:
        worksheet_name = 0
    
    # Muat data
    print("\nMemuat data spreadsheet...")
    data = bot.load_spreadsheet(spreadsheet_name, worksheet_name)
    
    if data is None:
        print("Gagal memuat data spreadsheet.")
        input("\nTekan Enter untuk kembali ke menu utama...")
        return
    
    # Tampilkan kolom
    print("\nKolom-kolom yang tersedia:")
    for col in data.columns:
        print(f"- {col}")
    
    # Input kolom koordinat
    print("\nDETAIL KOLOM KOORDINAT:")
    lat_col = input("Masukkan nama kolom latitude: ")
    lng_col = input("Masukkan nama kolom longitude: ")
    
    # Validasi kolom
    if lat_col not in data.columns or lng_col not in data.columns:
        print(f"Error: Kolom {lat_col} atau {lng_col} tidak ditemukan di spreadsheet.")
        input("\nTekan Enter untuk kembali ke menu utama...")
        return
    
    # Input lokasi referensi
    print("\nDETAIL LOKASI REFERENSI:")
    print("Anda dapat memasukkan koordinat langsung atau menggunakan alamat")
    coord_choice = input("Gunakan alamat untuk referensi? (y/n): ")
    
    if coord_choice.lower() == 'y':
        address = input("Masukkan alamat referensi: ")
        coords = get_coordinates_from_address(address)
        
        if coords:
            ref_lat, ref_lng = coords
            print(f"Alamat dikonversi menjadi koordinat: {ref_lat}, {ref_lng}")
        else:
            print("Gagal mengonversi alamat menjadi koordinat. Silakan masukkan koordinat manual.")
            ref_lat = float(input("Masukkan latitude titik referensi: "))
            ref_lng = float(input("Masukkan longitude titik referensi: "))
    else:
        ref_lat = float(input("Masukkan latitude titik referensi: "))
        ref_lng = float(input("Masukkan longitude titik referensi: "))
    
    # Input radius
    radius = float(input("\nMasukkan radius pencarian dalam meter [default 250]: ") or "250")
    
    # Cari lokasi terdekat
    print(f"\nMencari lokasi dalam radius {radius}m dari titik ({ref_lat}, {ref_lng})...")
    nearby = bot.find_nearby_locations(data, lat_col, lng_col, ref_lat, ref_lng, radius)
    
    if nearby is None or nearby.empty:
        print("Tidak ditemukan lokasi dalam radius yang ditentukan.")
        input("\nTekan Enter untuk kembali ke menu utama...")
        return
    
    # Tampilkan hasil
    print(f"\nDitemukan {len(nearby)} lokasi dalam radius {radius}m:")
    
    # Pilih kolom untuk ditampilkan (jika terlalu banyak)
    if len(nearby.columns) > 7:
        display_cols = [lat_col, lng_col, 'distance_meters']
        
        # Tambahkan kolom penting lainnya
        important_cols = ['name', 'nama', 'title', 'address', 'alamat']
        for col in important_cols:
            for data_col in nearby.columns:
                if col in data_col.lower() and data_col not in display_cols:
                    display_cols.append(data_col)
        
        if len(display_cols) < 5:  # Jika masih sedikit, tambahkan beberapa kolom lagi
            for col in nearby.columns:
                if col not in display_cols and len(display_cols) < 7:
                    display_cols.append(col)
        
        display_df = nearby[display_cols].copy()
    else:
        display_df = nearby.copy()
    
    # Format jarak
    if 'distance_meters' in display_df.columns:
        display_df['distance_meters'] = display_df['distance_meters'].round(2)
        display_df = display_df.rename(columns={'distance_meters': 'Jarak (m)'})
    
    # Tampilkan hasil
    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', 1000)
    print(display_df)
    
    # Tampilkan statistik
    print("\nStatistik jarak:")
    print(f"Jarak terdekat: {nearby['distance_meters'].min():.2f} meter")
    print(f"Jarak terjauh: {nearby['distance_meters'].max():.2f} meter")
    print(f"Jarak rata-rata: {nearby['distance_meters'].mean():.2f} meter")
    
    # Simpan hasil jika diinginkan
    save_choice = input("\nApakah Anda ingin menyimpan hasil ke file CSV? (y/n): ")
    if save_choice.lower() == 'y':
        filename = input("Masukkan nama file [default: nearby_locations.csv]: ") or "nearby_locations.csv"
        nearby.to_csv(filename, index=False)
        print(f"Hasil berhasil disimpan ke {filename}")
    
    input("\nTekan Enter untuk kembali ke menu utama...")

def show_help():
    """Tampilkan bantuan dan petunjuk."""
    clear_screen()
    print_header()
    
    print("BANTUAN DAN PETUNJUK")
    print("\n1. Pengaturan Google Sheets API")
    print("   - Anda memerlukan file credentials.json untuk mengakses Google Sheets")
    print("   - File ini dibuat di Google Cloud Console dengan mengaktifkan Sheets API")
    print("   - Pastikan untuk membagikan spreadsheet Anda dengan service account")
    
    print("\n2. Format Data Spreadsheet")
    print("   - Spreadsheet Anda harus memiliki minimal dua kolom untuk lat/lng")
    print("   - Contoh nama kolom: 'Latitude'/'Longitude' atau 'Lat'/'Lng'")
    print("   - Nilai koordinat harus dalam format desimal (misal: -6.2088)")
    
    print("\n3. Tentang Radius Pencarian")
    print("   - Default radius pencarian adalah 250 meter")
    print("   - Anda dapat menentukan radius lain saat menjalankan pencarian")
    print("   - Perhitungan jarak menggunakan formula Haversine (jarak garis lurus)")
    
    print("\n4. Data Sampel")
    print("   - Bot ini menyediakan generator data sampel untuk pengujian")
    print("   - Data sampel berisi 50 lokasi acak di sekitar Jakarta Pusat")
    print("   - Gunakan data ini untuk menguji fungsi pencarian")
    
    print("\n5. Geocoding")
    print("   - Bot ini dapat mengkonversi alamat menjadi koordinat")
    print("   - Gunakan fitur ini jika Anda tidak mengetahui koordinat suatu lokasi")
    print("   - Hasil geocoding bisa bervariasi tergantung alamat yang diberikan")
    
    print("\n6. Troubleshooting")
    print("   - Pastikan file credentials.json sudah benar")
    print("   - Verifikasi bahwa spreadsheet dan worksheet yang ditentukan sudah benar")
    print("   - Periksa format data kolom latitude dan longitude")
    
    input("\nTekan Enter untuk kembali ke menu utama...")

if __name__ == "__main__":
    main_menu()