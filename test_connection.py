from supabase import create_client, Client
import json

with open("settings.json", "r", encoding="utf-8") as f:
    config = json.load(f)

url = config.get("supabase_url")
key = config.get("supabase_key")

supabase: Client = create_client(url, key)

try:
    # Test if we can access the customers table
    res = supabase.table("customers").select("*").limit(1).execute()
    print("Bağlantı Başarılı: 'customers' tablosu mevcut.")
except Exception as e:
    print(f"Hata: {e}")
