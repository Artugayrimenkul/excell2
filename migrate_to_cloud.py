import pandas as pd
from supabase import create_client, Client
import json
import os

# Ayarları yükle
with open("settings.json", "r", encoding="utf-8") as f:
    config = json.load(f)

url = config.get("supabase_url")
# Öncelikli olarak Secret Key (Service Role) kullanıyoruz, yoksa Anon Key (Publishable)
key = config.get("supabase_secret_key") 
if not key or "BURAYA" in key:
    key = config.get("supabase_key")

supabase: Client = create_client(url, key)

def migrate_excel_to_supabase():
    excel_file = config.get("excel_path", "Gayrimenkul_CRM_V3.xlsx")
    
    if not os.path.exists(excel_file):
        print(f"HATA: {excel_file} bulunamadı!")
        return

    sheets_to_tables = {
        "MÜŞTERİ_LİSTESİ": "customers",
        "SATILIK_KONUT": "satilik_konut",
        "KİRALIK_KONUT": "kiralik_konut",
        "SATILIK_ARSA": "satilik_arsa",
        "HATIRLATICILAR": "reminders"
    }

    for sheet, table in sheets_to_tables.items():
        try:
            print(f"'{sheet}' aktarılıyor...")
            df = pd.read_excel(excel_file, sheet_name=sheet)
            
            # Veriyi temizle (NaN değerleri None yap)
            df = df.where(pd.notnull(df), None)
            
            # Sütun isimlerini Supabase uyumlu hale getir
            df.columns = [c.lower().replace(" ", "_").replace("/", "_").replace("(", "").replace(")", "") for c in df.columns]
            
            # 'not' ismini 'notlar' olarak değiştir (SQL rezerve kelime hatasını önlemek için)
            df.columns = ["notlar" if c == "not" else c for c in df.columns]
            
            # Verileri listeye dönüştür
            records = df.to_dict(orient="records")
            
            if records:
                # Verileri Supabase'e gönder
                # Not: Tabloların Supabase panelinde önceden oluşturulmuş olması gerekebilir 
                # veya SQL Editor üzerinden oluşturulmalıdır.
                data, count = supabase.table(table).insert(records).execute()
                print(f"BAŞARILI: {sheet} -> {table} ({len(records)} kayıt aktarıldı)")
            else:
                print(f"BİLGİ: {sheet} boş, aktarılacak veri yok.")
                
        except Exception as e:
            print(f"HATA ('{sheet}'): {str(e)}")

if __name__ == "__main__":
    print("Bulut Aktarım Sistemi Başlatılıyor...")
    migrate_excel_to_supabase()
    print("\nAktarım tamamlandı!")
