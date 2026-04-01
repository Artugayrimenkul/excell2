import customtkinter as ctk
import pandas as pd
from datetime import datetime
import os
import webbrowser
import json
from tkinter import filedialog
from supabase import create_client, Client
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from PIL import Image

# Register a font that supports Turkish characters
FONT_PATH = "TurkishFont.ttf"
try:
    if os.path.exists(FONT_PATH):
        pdfmetrics.registerFont(TTFont('TurkishFont', FONT_PATH))
        pdfmetrics.registerFont(TTFont('TurkishFont-Bold', FONT_PATH)) # Use same for bold if needed or separate
        MAIN_FONT = "TurkishFont"
        BOLD_FONT = "TurkishFont" # In a real case we'd use a bold .ttf
    else:
        MAIN_FONT = "Helvetica"
        BOLD_FONT = "Helvetica-Bold"
except Exception as e:
    print(f"Font registration error: {e}")
    MAIN_FONT = "Helvetica"
    BOLD_FONT = "Helvetica-Bold"

# Set appearance mode and color theme
ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")

class EmlakCRMApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Gayrimenkul CRM PRO - Bulut Yönetim Paneli")
        self.geometry("1100x950")

        # Config paths
        self.settings_file = "settings.json"
        self.load_settings()
        
        # Supabase Client
        self.supabase: Client = create_client(self.config["supabase_url"], self.config["supabase_key"])

        # Tabview
        self.tabview = ctk.CTkTabview(self, width=1050, height=900)
        self.tabview.pack(padx=10, pady=10, fill="both", expand=True)

        self.tab_customer = self.tabview.add("Müşteri Kaydı")
        self.tab_entry = self.tabview.add("Yeni Portföy")
        self.tab_management = self.tabview.add("Portföy Yönetimi")
        self.tab_reminders = self.tabview.add("Hatırlatıcılar")
        self.tab_matching = self.tabview.add("Akıllı Eşleştirme")
        self.tab_settings = self.tabview.add("Ayarlar")

        self.setup_customer_tab()
        self.setup_entry_tab()
        self.setup_management_tab()
        self.setup_reminders_tab()
        self.setup_matching_tab()
        self.setup_settings_tab()

        # Check for reminders on startup
        self.after(1000, self.check_today_reminders)

    def load_settings(self):
        default_settings = {
            "company_name": "Emlak Ofisim",
            "company_phone": "90...",
            "company_email": "info@emlakofisi.com",
            "logo_path": "",
            "supabase_url": "",
            "supabase_key": ""
        }
        if os.path.exists(self.settings_file):
            with open(self.settings_file, "r", encoding="utf-8") as f:
                self.config = json.load(f)
        else:
            self.config = default_settings

    def save_config(self):
        with open(self.settings_file, "w", encoding="utf-8") as f:
            json.dump(self.config, f, ensure_ascii=False, indent=4)

    # --- BULUT KAYIT FONKSİYONU ---
    def write_to_cloud(self, table_name, data):
        try:
            # Clean keys for Supabase (lowercase and underscores)
            clean_data = {k.lower().replace(" ", "_").replace("/", "_").replace("(", "").replace(")", ""): v for k, v in data.items()}
            
            # Remove 'id' if exists to let Supabase generate it
            if 'id' in clean_data: del clean_data['id']
            
            res = self.supabase.table(table_name).insert(clean_data).execute()
            self.show_message("BAŞARILI", f"Veri bulut veritabanına kaydedildi.")
            return True
        except Exception as e:
            self.show_message("HATA", f"Bulut kaydı başarısız: {e}")
            return False

    def fetch_from_cloud(self, table_name):
        try:
            res = self.supabase.table(table_name).select("*").execute()
            return pd.DataFrame(res.data)
        except Exception as e:
            self.show_message("HATA", f"Veri çekilemedi: {e}")
            return pd.DataFrame()

    def get_image_urls(self, image_urls_json):
        if not image_urls_json:
            return []
        try:
            # If it's already a list (from Supabase SDK)
            if isinstance(image_urls_json, list):
                urls = image_urls_json
            else:
                # If it's a JSON string
                urls = json.loads(image_urls_json)
            
            base_url = f"{self.config['supabase_url']}/storage/v1/object/public/portfolio_images/"
            return [f"{base_url}{url}" for url in urls]
        except Exception as e:
            print(f"URL parsing error: {e}")
            return []

    # --- MÜŞTERİ KAYDI ---
    def setup_customer_tab(self):
        scroll = ctk.CTkScrollableFrame(self.tab_customer)
        scroll.pack(padx=5, pady=5, fill="both", expand=True)
        ctk.CTkLabel(scroll, text="YENİ MÜŞTERİ TALEBİ (BULUT)", font=ctk.CTkFont(size=18, weight="bold")).pack(pady=10)
        
        self.c_name = self.create_input(scroll, "Müşteri Ad Soyad:")
        self.c_phone = self.create_input(scroll, "Telefon No (WhatsApp için 90...):")
        self.c_email = self.create_input(scroll, "E-posta Adresi:")
        self.c_budget = self.create_input(scroll, "Bütçe:")
        self.c_demand = self.create_combo(scroll, "Ne İstiyor?", ["Satılık Konut", "Kiralık Konut", "Satılık Arsa"])
        self.c_region1 = self.create_input(scroll, "Bölge 1:")
        self.c_region2 = self.create_input(scroll, "Bölge 2:")
        self.c_region3 = self.create_input(scroll, "Bölge 3:")
        self.c_urgency = self.create_combo(scroll, "Aciliyet:", ["Acil", "Normal", "Belirtmedi"])
        self.c_notes = self.create_input(scroll, "Notlar:")
        
        btn_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        btn_frame.pack(pady=20)
        ctk.CTkButton(btn_frame, text="BULUTA KAYDET", command=self.save_customer, fg_color="green", width=200).pack(side="left", padx=10)
        ctk.CTkButton(btn_frame, text="WHATSAPP", command=lambda: self.open_whatsapp(self.c_phone.get()), fg_color="#25D366", width=200).pack(side="left", padx=10)

    # --- PORTFÖY GİRİŞİ ---
    def setup_entry_tab(self):
        sub_tabview = ctk.CTkTabview(self.tab_entry)
        sub_tabview.pack(fill="both", expand=True)
        t_sk = sub_tabview.add("Satılık Konut")
        t_kk = sub_tabview.add("Kiralık Konut")
        t_sa = sub_tabview.add("Satılık Arsa")
        
        # Setup sections... (same structure as before but saving to cloud)
        s_sk = ctk.CTkScrollableFrame(t_sk); s_sk.pack(fill="both", expand=True)
        self.sk_fields = self.create_portfolio_fields(s_sk)
        ctk.CTkButton(s_sk, text="SATILIK KONUTU BULUTA EKLE", command=self.save_sk).pack(pady=20)
        
        s_kk = ctk.CTkScrollableFrame(t_kk); s_kk.pack(fill="both", expand=True)
        self.kk_fields = self.create_portfolio_fields(s_kk)
        ctk.CTkButton(s_kk, text="KİRALIK KONUTU BULUTA EKLE", command=self.save_kk).pack(pady=20)
        
        s_sa = ctk.CTkScrollableFrame(t_sa); s_sa.pack(fill="both", expand=True)
        self.sa_fields = self.create_arsa_fields(s_sa)
        ctk.CTkButton(s_sa, text="ARSAYI BULUTA EKLE", command=self.save_sa).pack(pady=20)

    # --- PORTFÖY YÖNETİMİ ---
    def setup_management_tab(self):
        self.manage_top = ctk.CTkFrame(self.tab_management)
        self.manage_top.pack(fill="x", padx=10, pady=10)
        self.combo_manage_type = ctk.CTkComboBox(self.manage_top, values=["customers", "satilik_konut", "kiralik_konut", "satilik_arsa"])
        self.combo_manage_type.pack(side="left", padx=10)
        ctk.CTkButton(self.manage_top, text="BULUTTAN YÜKLE", command=self.load_management_list).pack(side="left", padx=10)
        self.manage_scroll = ctk.CTkScrollableFrame(self.tab_management)
        self.manage_scroll.pack(fill="both", expand=True, padx=10, pady=10)

    def load_management_list(self):
        for widget in self.manage_scroll.winfo_children(): widget.destroy()
        table_name = self.combo_manage_type.get()
        df = self.fetch_from_cloud(table_name)
        if df.empty: return
        
        for _, row in df.iterrows():
            f = ctk.CTkFrame(self.manage_scroll)
            f.pack(fill="x", pady=5, padx=5)
            
            # Dynamic info display
            disp_name = row.get('ad_soyad', row.get('ilan_no', 'Kayıt'))
            info = f"{disp_name} | {row.get('bölge_mahalle', row.get('bölge_1', ''))} | {row.get('fiyat', row.get('kira_bedeli', ''))} TL"
            
            # Show image thumbnail if exists
            img_urls = self.get_image_urls(row.get('image_urls'))
            if img_urls:
                info = "📸 " + info
            elif row.get('resim_url'): # Legacy support
                info = "📸 " + info

            ctk.CTkLabel(f, text=info, anchor="w").pack(side="left", padx=10, fill="x", expand=True)
            
            # Actions
            ctk.CTkButton(f, text="SİL", width=60, fg_color="red", command=lambda r=row, t=table_name: self.delete_record(t, r['id'])).pack(side="right", padx=5)
            ctk.CTkButton(f, text="KATALOG", width=80, fg_color="brown", command=lambda r=row: self.generate_pdf(r)).pack(side="right", padx=5)
            ctk.CTkButton(f, text="WHATSAPP", width=80, fg_color="#25D366", command=lambda r=row: self.share_on_whatsapp(r)).pack(side="right", padx=5)

    def delete_record(self, table, record_id):
        try:
            self.supabase.table(table).delete().eq("id", record_id).execute()
            self.show_message("BAŞARILI", "Kayıt buluttan silindi.")
            self.load_management_list()
        except Exception as e:
            self.show_message("HATA", f"Silinemedi: {e}")

    # --- KAYIT MANTIKLARI ---
    def save_customer(self):
        data = {"tarih": datetime.now().strftime("%d.%m.%Y"), "ad_soyad": self.c_name.get(), "telefon": self.c_phone.get(), "e_posta": self.c_email.get(), "bütçe": self.c_budget.get(), "talep_türü": self.c_demand.get(), "bölge_1": self.c_region1.get(), "bölge_2": self.c_region2.get(), "bölge_3": self.c_region3.get(), "aciliyet": self.c_urgency.get(), "notlar": self.c_notes.get()}
        self.write_to_cloud("customers", data)

    def save_sk(self):
        data = {k: v.get() for k, v in self.sk_fields.items()}
        data["tarih"] = datetime.now().strftime("%d.%m.%Y")
        self.write_to_cloud("satilik_konut", data)

    def save_kk(self):
        data = {k: v.get() for k, v in self.kk_fields.items()}
        data["tarih"] = datetime.now().strftime("%d.%m.%Y")
        self.write_to_cloud("kiralik_konut", data)

    def save_sa(self):
        data = {k: v.get() for k, v in self.sa_fields.items()}
        data["tarih"] = datetime.now().strftime("%d.%m.%Y")
        self.write_to_cloud("satilik_arsa", data)

    # --- HATIRLATICILAR ---
    def setup_reminders_tab(self):
        f = ctk.CTkFrame(self.tab_reminders); f.pack(fill="both", expand=True, padx=10, pady=10)
        ctk.CTkLabel(f, text="YENİ BULUT HATIRLATICI", font=ctk.CTkFont(weight="bold")).pack(pady=10)
        self.rem_name = self.create_input(f, "Müşteri Adı:")
        self.rem_tel = self.create_input(f, "Telefon:")
        self.rem_date = self.create_input(f, "Tarih (GG.AA.YYYY):")
        self.rem_note = self.create_input(f, "Not:")
        ctk.CTkButton(f, text="BULUTA KAYDET", command=self.save_reminder, fg_color="green").pack(pady=10)
        self.rem_list_box = ctk.CTkTextbox(f, height=300); self.rem_list_box.pack(fill="both", padx=20, pady=20)

    def save_reminder(self):
        data = {"tarih": datetime.now().strftime("%d.%m.%Y"), "müşteri_adı": self.rem_name.get(), "telefon": self.rem_tel.get(), "hatırlatma_tarihi": self.rem_date.get(), "notlar": self.rem_note.get()}
        if self.write_to_cloud("reminders", data): self.check_today_reminders()

    def check_today_reminders(self):
        df = self.fetch_from_cloud("reminders")
        if df.empty: return
        today = datetime.now().strftime("%d.%m.%Y")
        todays = df[df["hatırlatma_tarihi"] == today]
        self.rem_list_box.delete("1.0", "end")
        for _, r in todays.iterrows():
            self.rem_list_box.insert("end", f"🔔 {r['müşteri_adı']} - {r['notlar']} ({r['telefon']})\n")

    # --- AYARLAR ---
    def setup_settings_tab(self):
        scroll = ctk.CTkScrollableFrame(self.tab_settings); scroll.pack(fill="both", expand=True, padx=20, pady=20)
        self.create_section_label(scroll, "BULUT VE FİRMA AYARLARI")
        self.e_company = self.create_input(scroll, "Firma Adı:"); self.e_company.insert(0, self.config["company_name"])
        self.e_phone = self.create_input(scroll, "Firma Tel:"); self.e_phone.insert(0, self.config["company_phone"])
        self.e_email = self.create_input(scroll, "Firma E-posta:"); self.e_email.insert(0, self.config.get("company_email", ""))
        self.e_url = self.create_input(scroll, "Supabase URL:"); self.e_url.insert(0, self.config["supabase_url"])
        self.e_key = self.create_input(scroll, "Supabase Key:"); self.e_key.insert(0, self.config["supabase_key"])
        
        # Logo Selection
        self.create_section_label(scroll, "LOGO AYARI")
        self.logo_path_var = ctk.StringVar(value=self.config.get("logo_path", ""))
        self.logo_label = ctk.CTkLabel(scroll, text=f"Mevcut Logo: {os.path.basename(self.logo_path_var.get()) if self.logo_path_var.get() else 'Yok'}")
        self.logo_label.pack()
        ctk.CTkButton(scroll, text="LOGO SEÇ", command=self.select_logo).pack(pady=5)

        ctk.CTkButton(scroll, text="AYARLARI GÜNCELLE", command=self.update_settings, fg_color="green", height=40).pack(pady=20)

    def select_logo(self):
        path = filedialog.askopenfilename(filetypes=[("Image files", "*.png *.jpg *.jpeg *.bmp")])
        if path:
            self.logo_path_var.set(path)
            self.logo_label.configure(text=f"Mevcut Logo: {os.path.basename(path)}")

    def update_settings(self):
        self.config.update({
            "company_name": self.e_company.get(), 
            "company_phone": self.e_phone.get(), 
            "company_email": self.e_email.get(),
            "supabase_url": self.e_url.get(), 
            "supabase_key": self.e_key.get(),
            "logo_path": self.logo_path_var.get()
        })
        self.save_config(); self.show_message("BAŞARILI", "Ayarlar güncellendi.")

    # --- HELPERS ---
    def create_portfolio_fields(self, parent):
        f = {}; f['ilan_no'] = self.create_input(parent, "İlan No:")
        f['konut_tipi'] = self.create_combo(parent, "Tip:", ["Daire", "Villa", "Rezidans"])
        f['fiyat'] = self.create_input(parent, "Fiyat:")
        f['bölge_mahalle'] = self.create_input(parent, "Bölge:")
        f['oda_sayısı'] = self.create_combo(parent, "Oda:", ["1+1", "2+1", "3+1", "4+1"])
        f['kat'] = self.create_input(parent, "Kat:")
        f['sahibi'] = self.create_input(parent, "Sahibi:")
        f['sahibi_tel'] = self.create_input(parent, "Sahibi Tel:")
        f['notlar'] = self.create_input(parent, "Notlar:")
        return f

    def create_arsa_fields(self, parent):
        f = {}; f['ilan_no'] = self.create_input(parent, "İlan No:")
        f['arsa_tipi'] = self.create_combo(parent, "Tip:", ["İmarlı", "Tarla", "Zeytinlik"])
        f['ada'] = self.create_input(parent, "Ada:"); f['parsel'] = self.create_input(parent, "Parsel:")
        f['fiyat'] = self.create_input(parent, "Fiyat:")
        f['bölge_mahalle'] = self.create_input(parent, "Bölge:")
        f['sahibi'] = self.create_input(parent, "Sahibi:"); f['sahibi_tel'] = self.create_input(parent, "Sahibi Tel:")
        f['notlar'] = self.create_input(parent, "Notlar:")
        return f

    def create_input(self, parent, label):
        ctk.CTkLabel(parent, text=label).pack(pady=(5,0)); e = ctk.CTkEntry(parent, width=500); e.pack(pady=(0,10)); return e

    def create_combo(self, parent, label, vals):
        ctk.CTkLabel(parent, text=label).pack(pady=(5,0)); c = ctk.CTkComboBox(parent, values=vals, width=500); c.pack(pady=(0,10)); return c

    def create_section_label(self, parent, text):
        ctk.CTkLabel(parent, text=text, font=ctk.CTkFont(weight="bold"), text_color="#366092").pack(pady=15)

    def show_message(self, title, msg):
        m = ctk.CTkToplevel(self); m.title(title); m.geometry("400x200"); m.attributes("-topmost", True)
        ctk.CTkLabel(m, text=msg, wraplength=350).pack(pady=30); ctk.CTkButton(m, text="Tamam", command=m.destroy).pack()

    def open_whatsapp(self, phone):
        if phone: webbrowser.open(f"https://wa.me/{phone}")

    def share_on_whatsapp(self, row):
        msg = f"Portföy No: {row.get('ilan_no')}\nBölge: {row.get('bölge_mahalle')}\nFiyat: {row.get('fiyat')} TL"
        webbrowser.open(f"https://wa.me/?text={msg}")

    def setup_matching_tab(self):
        f = ctk.CTkFrame(self.tab_matching); f.pack(fill="both", expand=True, padx=10, pady=10)
        self.c_match = ctk.CTkComboBox(f, width=500, values=["Yükleniyor..."]); self.c_match.pack(pady=10)
        ctk.CTkButton(f, text="Müşterileri Yenile", command=self.refresh_match_list).pack()
        ctk.CTkButton(f, text="EŞLEŞTİR", command=self.run_match, fg_color="#366092").pack(pady=20)
        self.match_res = ctk.CTkTextbox(f, width=700, height=400); self.match_res.pack(pady=10)

    def refresh_match_list(self):
        df = self.fetch_from_cloud("customers")
        if not df.empty: self.c_match.configure(values=df["ad_soyad"].tolist())

    def run_match(self):
        name = self.c_match.get()
        df_cust = self.fetch_from_cloud("customers")
        cust = df_cust[df_cust["ad_soyad"] == name].iloc[0]
        table = {"Satılık Konut": "satilik_konut", "Kiralık Konut": "kiralik_konut", "Satılık Arsa": "satilik_arsa"}[cust["talep_türü"]]
        df_port = self.fetch_from_cloud(table)
        self.match_res.delete("1.0", "end")
        for _, p in df_port.iterrows():
            regions = [cust["bölge_1"], cust["bölge_2"], cust["bölge_3"]]
            if any(str(r).lower() in str(p["bölge_mahalle"]).lower() for r in regions if r != "-"):
                self.match_res.insert("end", f"İLAN: {p['ilan_no']} | {p['bölge_mahalle']} | {p.get('fiyat')} TL\n")

    def generate_pdf(self, row):
        import requests
        from io import BytesIO
        
        # Professional PDF logic using cloud data
        filename = f"Katalog_{row.get('ilan_no', 'Yeni')}.pdf"
        c = canvas.Canvas(filename, pagesize=A4)
        width, height = A4
        
        # --- Header ---
        c.setFillColorRGB(0.1, 0.2, 0.4) # Darker professional blue
        c.rect(0, height-1.8*inch, width, 1.8*inch, fill=1)
        
        # Logo Check
        logo_added = False
        if self.config.get("logo_path") and os.path.exists(self.config["logo_path"]):
            try:
                logo = Image.open(self.config["logo_path"])
                lw, lh = logo.size
                laspect = lh / float(lw)
                ldisplay_w = 1.4*inch
                ldisplay_h = ldisplay_w * laspect
                c.drawInlineImage(logo, 0.5*inch, height-1.5*inch, width=ldisplay_w, height=ldisplay_h)
                logo_added = True
            except: pass

        c.setFillColorRGB(1, 1, 1)
        c.setFont(BOLD_FONT, 22)
        title_x = 2.2*inch if logo_added else width/2
        title_text = f"{self.config['company_name']}\nPORTFÖY TANITIMI"
        
        if logo_added:
            c.drawString(title_x, height-0.8*inch, self.config['company_name'].upper())
            c.setFont(MAIN_FONT, 16)
            c.drawString(title_x, height-1.1*inch, "GAYRİMENKUL KATALOĞU")
        else:
            c.drawCentredString(width/2, height-0.8*inch, self.config['company_name'].upper())
            c.setFont(MAIN_FONT, 16)
            c.drawCentredString(width/2, height-1.1*inch, "GAYRİMENKUL KATALOĞU")
        
        y = height - 2.2*inch
        
        # --- Images Section ---
        img_urls = self.get_image_urls(row.get('image_urls'))
        if not img_urls and row.get('resim_url'):
            img_urls = [f"{self.config['supabase_url']}/storage/v1/object/public/portfolio_images/{row['resim_url']}"]
            
        if img_urls:
            try:
                response = requests.get(img_urls[0], timeout=10)
                img_data = BytesIO(response.content)
                img = Image.open(img_data)
                iw, ih = img.size
                aspect = ih / float(iw)
                display_w = 6*inch
                display_h = display_w * aspect
                if display_h > 4.5*inch:
                    display_h = 4.5*inch
                    display_w = display_h / aspect
                
                # Shadow/Border for image
                c.setStrokeColorRGB(0.8, 0.8, 0.8)
                c.rect((width-display_w)/2 - 2, y-display_h - 2, display_w + 4, display_h + 4, stroke=1)
                c.drawInlineImage(img, (width-display_w)/2, y-display_h, width=display_w, height=display_h)
                y -= (display_h + 0.6*inch)
            except Exception as e:
                y -= 0.5*inch
        
        # --- Details Section ---
        c.setFillColorRGB(0, 0, 0)
        c.setFont(BOLD_FONT, 18)
        c.drawString(0.8*inch, y, "GAYRİMENKUL BİLGİLERİ")
        y -= 0.2*inch
        c.setStrokeColorRGB(0.1, 0.2, 0.4)
        c.setLineWidth(2)
        c.line(0.8*inch, y, width-0.8*inch, y)
        y -= 0.4*inch
        
        excluded_keys = ['id', 'tarih', 'resim_klasoru', 'image_urls', 'resim_url', 'sahibi', 'sahibi_tel']
        
        # Two column details for better look
        c.setFont(MAIN_FONT, 12)
        for k, v in row.items():
            if v and k not in excluded_keys:
                label = k.replace("_", " ").title()
                c.setFont(BOLD_FONT, 11)
                c.setFillColorRGB(0.2, 0.2, 0.2)
                c.drawString(1*inch, y, f"{label}:")
                c.setFont(MAIN_FONT, 11)
                c.setFillColorRGB(0, 0, 0)
                c.drawString(3*inch, y, str(v))
                y -= 0.3*inch
                
                if y < 1.5*inch:
                    c.showPage()
                    y = height - 1*inch
        
        # --- Footer ---
        c.setFillColorRGB(0.1, 0.2, 0.4)
        c.rect(0, 0, width, 1*inch, fill=1)
        c.setFillColorRGB(1, 1, 1)
        c.setFont(BOLD_FONT, 10)
        footer_text = f"İletişim: {self.config['company_phone']}  |  {self.config['company_email']}"
        c.drawCentredString(width/2, 0.6*inch, footer_text)
        c.setFont(MAIN_FONT, 8)
        c.drawCentredString(width/2, 0.4*inch, "Bu belge otomatik olarak Artu Gayrimenkul CRM tarafından oluşturulmuştur.")
        
        c.save()
        try:
            os.startfile(filename)
        except:
            self.show_message("BAŞARILI", f"PDF Oluşturuldu: {filename}")

if __name__ == "__main__":
    app = EmlakCRMApp()
    app.mainloop()
