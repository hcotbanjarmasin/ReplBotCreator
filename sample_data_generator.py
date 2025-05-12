import pandas as pd
import random
import csv

def generate_sample_locations(num_points=50, center_lat=-6.2088, center_lng=106.8456):
    """
    Menghasilkan data lokasi acak di sekitar pusat yang ditentukan.
    
    Args:
        num_points: Jumlah titik untuk dihasilkan
        center_lat: Latitude pusat
        center_lng: Longitude pusat
    
    Returns:
        DataFrame dengan data lokasi
    """
    # Variasi random dalam derajat (sekitar 1-2 km radius)
    lat_variation = 0.02
    lng_variation = 0.02
    
    data = []
    
    # Nama jalan di Jakarta
    street_names = [
        "Jalan Sudirman", "Jalan Thamrin", "Jalan Gatot Subroto", "Jalan Rasuna Said",
        "Jalan Kebon Sirih", "Jalan Hayam Wuruk", "Jalan Gajah Mada", "Jalan Pintu Besar",
        "Jalan Asia Afrika", "Jalan Wahid Hasyim", "Jalan Imam Bonjol", "Jalan Diponegoro",
        "Jalan Fatmawati", "Jalan Senopati", "Jalan Kemang", "Jalan Tendean",
        "Jalan Wolter Monginsidi", "Jalan Sisingamangaraja", "Jalan Panglima Polim", "Jalan Melawai"
    ]
    
    # Jenis bisnis
    business_types = [
        "Restaurant", "Café", "Hotel", "Toko", "Kantor", "Sekolah", "Rumah Sakit", 
        "Apotek", "Bank", "ATM", "Mall", "Pasar", "Bengkel", "SPBU", "Salon"
    ]
    
    # Ratings
    ratings = [3.0, 3.5, 4.0, 4.5, 5.0]
    
    for i in range(num_points):
        # Generate random latitude and longitude around center
        lat = center_lat + (random.random() * 2 - 1) * lat_variation
        lng = center_lng + (random.random() * 2 - 1) * lng_variation
        
        # Generate other data
        name = f"{random.choice(business_types)} {random.randint(1, 99)}"
        address = f"{random.choice(street_names)} No. {random.randint(1, 200)}"
        rating = random.choice(ratings)
        
        # Add to data
        data.append({
            "Nama": name,
            "Alamat": address,
            "Jenis": random.choice(business_types),
            "Rating": rating,
            "Latitude": round(lat, 6),
            "Longitude": round(lng, 6),
            "Telepon": f"021-{random.randint(1000000, 9999999)}"
        })
    
    # Convert to DataFrame
    df = pd.DataFrame(data)
    return df

def save_to_csv(df, filename="sample_locations.csv"):
    """
    Simpan DataFrame ke file CSV.
    
    Args:
        df: DataFrame untuk disimpan
        filename: Nama file output
    """
    df.to_csv(filename, index=False)
    print(f"Data berhasil disimpan ke {filename}")

if __name__ == "__main__":
    # Generate sample data
    print("Generating sample location data...")
    locations = generate_sample_locations()
    
    # Save to CSV
    save_to_csv(locations)
    
    # Show sample
    print("\nContoh data yang dihasilkan:")
    print(locations.head())
    
    print("\nStatistik data:")
    print(f"Jumlah lokasi: {len(locations)}")
    print(f"Jenis lokasi unik: {locations['Jenis'].nunique()}")
    
    # Instruksi
    print("\nInstruksi Penggunaan:")
    print("1. File CSV ini dapat diimpor ke Google Sheets")
    print("2. Gunakan location_bot.py untuk menemukan lokasi di sekitar titik tertentu")
    print("3. Untuk pengujian, Anda dapat menggunakan koordinat sekitar:")
    print("   Latitude: -6.2088, Longitude: 106.8456 (sekitar Jakarta Pusat)")