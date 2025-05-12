import pandas as pd
import logging

# Konfigurasi logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# URL spreadsheet Google
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1kGSZYcPYvs9vfL3-egGZfMkJpfqSh2vDVLRSCJgCf5c/edit?usp=sharing"

def load_from_url(url, sheet_name=0):
    """
    Muat data dari URL spreadsheet publik Google Sheets.
    
    Args:
        url: URL spreadsheet Google Sheets yang dibagikan secara publik
        sheet_name: Nama atau indeks worksheet (default: 0)
        
    Returns:
        DataFrame dengan data dari spreadsheet
    """
    try:
        # Ekstrak ID spreadsheet dari URL
        if "spreadsheets/d/" in url:
            parts = url.split("spreadsheets/d/")[1]
            spreadsheet_id = parts.split("/")[0]
        else:
            spreadsheet_id = url  # Asumsi user memasukkan ID langsung
        
        # Buat URL untuk ekspor CSV
        csv_export_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/export?format=csv"
        if isinstance(sheet_name, int):
            csv_export_url += f"&gid={sheet_name}"
        
        print(f"Mencoba akses: {csv_export_url}")
        
        # Muat data ke pandas DataFrame
        data = pd.read_csv(csv_export_url)
        print(f"Berhasil memuat {len(data)} baris data dari spreadsheet")
        
        # Tampilkan informasi kolom
        print("\nKolom-kolom yang tersedia:")
        for col in data.columns:
            print(f"- {col}")
        
        # Tampilkan beberapa baris pertama
        print("\nBeberapa baris data pertama:")
        print(data.head())
        
        return data
    except Exception as e:
        print(f"Error saat memuat spreadsheet: {e}")
        return None

def main():
    print("Mencoba akses data spreadsheet...")
    data = load_from_url(SPREADSHEET_URL)
    
    if data is not None:
        print("\nStatus: BERHASIL mengakses spreadsheet")
        
        # Cek apakah ada kolom latitude dan longitude
        lat_cols = [col for col in data.columns if 'lat' in col.lower()]
        lng_cols = [col for col in data.columns if 'lon' in col.lower() or 'lng' in col.lower()]
        
        if lat_cols and lng_cols:
            print(f"\nDitemukan kolom koordinat: {lat_cols[0]} dan {lng_cols[0]}")
        else:
            print("\nPeringatan: Tidak ditemukan kolom latitude/longitude")
            print("Pastikan spreadsheet memiliki kolom koordinat")
    else:
        print("\nStatus: GAGAL mengakses spreadsheet")
        print("Periksa URL spreadsheet dan pastikan akses publik diaktifkan")
        print("Petunjuk: Buka spreadsheet > Klik Share > Change to 'Anyone with the link can view'")

if __name__ == "__main__":
    main()