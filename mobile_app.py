import streamlit as st
import pandas as pd
from supabase import create_client, Client
import json
import os
from datetime import datetime
import io
import requests
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from PIL import Image as PILImage

# Register fonts that support Turkish characters
REG_FONT = "TurkishFont.ttf"
BOLD_FONT_FILE = "TurkishFont-Bold.ttf"
MAIN_FONT = "Helvetica"
BOLD_FONT = "Helvetica-Bold"

if os.path.exists(REG_FONT):
    try:
        pdfmetrics.registerFont(TTFont('TurkishFont', REG_FONT))
        MAIN_FONT = "TurkishFont"
    except Exception as e:
        st.error(f"Regular font hatası: {e}")

if os.path.exists(BOLD_FONT_FILE):
    try:
        pdfmetrics.registerFont(TTFont('TurkishFont-Bold', BOLD_FONT_FILE))
        BOLD_FONT = "TurkishFont-Bold"
    except Exception as e:
        st.error(f"Bold font hatası: {e}")

# --- SAYFA YAPILANDIRMASI (EN BAŞTA OLMALI) ---
st.set_page_config(page_title="Mobil CRM Portal", page_icon="🏠", layout="wide")

# Ayarları yükle
def load_settings():
    if "supabase_url" in st.secrets:
        return {
            "company_name": st.secrets.get("company_name", "Emlak Ofisim"),
            "company_phone": st.secrets.get("company_phone", "90..."),
            "company_email": st.secrets.get("company_email", "info@emlakofisi.com"),
            "company_logo_url": st.secrets.get("company_logo_url", ""),
            "supabase_url": st.secrets["supabase_url"],
            "supabase_key": st.secrets["supabase_key"]
        }
    if os.path.exists("settings.json"):
        with open("settings.json", "r", encoding="utf-8") as f:
            return json.load(f)
    return {"company_name": "Emlak Ofisim", "supabase_url": "", "supabase_key": ""}

config = load_settings()

# --- SUPABASE BAĞLANTISI (GÜVENLİ ÇALIŞTIRMA) ---
if not config.get("supabase_url") or not config.get("supabase_key"):
    st.error("⚠️ Supabase Ayarları Eksik!")
    st.info("Lütfen Streamlit Cloud üzerinden 'Settings -> Secrets' kısmına gidin ve Supabase URL ve Key bilgilerinizi girin.")
    st.stop()

try:
    supabase: Client = create_client(config["supabase_url"], config["supabase_key"])
except Exception as e:
    st.error(f"Supabase Bağlantı Hatası: {e}")
    st.stop()

st.title(f"🏠 {config['company_name']}")
st.subheader("Mobil Yönetim Paneli")

menu = ["Yeni Müşteri", "Müşteri Listesi", "Yeni Satılık Konut", "Yeni Kiralık Konut", "Yeni Satılık Arsa", "Portföy Listesi", "Akıllı Eşleştirme"]
choice = st.sidebar.selectbox("Menü", menu)

# --- PDF OLUŞTURMA FONKSİYONU ---
def generate_pdf_bytes(row):
    try:
        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4
        
        # --- Header ---
        c.setFillColorRGB(0.1, 0.2, 0.4)
        c.rect(0, height-1.8*inch, width, 1.8*inch, fill=1)
        
        # Logo Check
        logo_added = False
        if config.get("company_logo_url"):
            try:
                resp = requests.get(config["company_logo_url"], timeout=10)
                logo_data = io.BytesIO(resp.content)
                logo = PILImage.open(logo_data)
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
        
        if logo_added:
            c.drawString(title_x, height-0.8*inch, config['company_name'].upper())
            c.setFont(MAIN_FONT, 16)
            c.drawString(title_x, height-1.1*inch, "GAYRİMENKUL KATALOĞU")
        else:
            c.drawCentredString(width/2, height-0.8*inch, config['company_name'].upper())
            c.setFont(MAIN_FONT, 16)
            c.drawCentredString(width/2, height-1.1*inch, "GAYRİMENKUL KATALOĞU")
        
        y = height - 2.2*inch
        
        # --- Images Section ---
        img_urls = []
        if row.get('image_urls'):
            try:
                urls = row['image_urls'] if isinstance(row['image_urls'], list) else json.loads(row['image_urls'])
                img_urls = [f"{config['supabase_url']}/storage/v1/object/public/portfolio_images/{u}" for u in urls]
            except: pass
        elif row.get('resim_url'):
            img_urls = [f"{config['supabase_url']}/storage/v1/object/public/portfolio_images/{row['resim_url']}"]
            
        if img_urls:
            try:
                resp = requests.get(img_urls[0], timeout=10)
                img_data = io.BytesIO(resp.content)
                img = PILImage.open(img_data)
                iw, ih = img.size
                aspect = ih / float(iw)
                display_w = 6*inch
                display_h = display_w * aspect
                if display_h > 4.5*inch:
                    display_h = 4.5*inch
                    display_w = display_h / aspect
                
                c.setStrokeColorRGB(0.8, 0.8, 0.8)
                c.rect((width-display_w)/2 - 2, y-display_h - 2, display_w + 4, display_h + 4, stroke=1)
                c.drawInlineImage(img, (width-display_w)/2, y-display_h, width=display_w, height=display_h)
                y -= (display_h + 0.6*inch)
            except Exception as e:
                y -= 0.5*inch
        
        # --- Details ---
        c.setFillColorRGB(0, 0, 0)
        c.setFont(BOLD_FONT, 18)
        c.drawString(0.8*inch, y, "GAYRİMENKUL BİLGİLERİ")
        y -= 0.2*inch
        c.setStrokeColorRGB(0.1, 0.2, 0.4)
        c.setLineWidth(2)
        c.line(0.8*inch, y, width-0.8*inch, y)
        y -= 0.4*inch
        
        excluded = ['id', 'tarih', 'resim_klasoru', 'image_urls', 'resim_url', 'sahibi', 'sahibi_tel']
        for k, v in row.items():
            if v and k not in excluded:
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
        footer_text = f"İletişim: {config.get('company_phone', '')}  |  {config.get('company_email', '')}"
        c.drawCentredString(width/2, 0.6*inch, footer_text)
        c.setFont(MAIN_FONT, 8)
        c.drawCentredString(width/2, 0.4*inch, "Bu belge otomatik olarak Artu Gayrimenkul CRM tarafından oluşturulmuştur.")
        
        c.save()
        buffer.seek(0)
        return buffer
    except Exception as e:
        st.error(f"PDF Hatası: {e}")
        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=A4)
        c.drawString(1*inch, 10*inch, f"Hata: {e}")
        c.save()
        buf.seek(0)
        return buf

# --- YARDIMCI FONKSİYONLAR ---
def upload_images(files, ilan_no):
    urls = []
    for i, file in enumerate(files):
        try:
            file_ext = file.name.split(".")[-1]
            file_name = f"{ilan_no}_{int(datetime.now().timestamp())}_{i}.{file_ext}"
            supabase.storage.from_("portfolio_images").upload(file_name, file.getvalue(), {"content-type": f"image/{file_ext}", "upsert": "true"})
            urls.append(file_name)
        except Exception as e:
            st.error(f"Resim yükleme hatası: {e}")
    return urls

def get_image_urls(image_urls_data):
    if not image_urls_data: return []
    if isinstance(image_urls_data, list): return image_urls_data
    try: return json.loads(image_urls_data)
    except: return []

def get_full_image_url(file_name):
    if file_name:
        return f"{config['supabase_url']}/storage/v1/object/public/portfolio_images/{file_name}"
    return None

def write_to_cloud(table_name, data, image_files=None):
    try:
        clean_data = {k.lower().replace(" ", "_").replace("/", "_").replace("(", "").replace(")", ""): v for k, v in data.items()}
        
        # Resim yükleme
        if image_files:
            new_urls = upload_images(image_files, clean_data.get('ilan_no', 'new'))
            existing_urls = get_image_urls(clean_data.get('image_urls', []))
            clean_data['image_urls'] = existing_urls + new_urls
            
        if 'id' in clean_data: 
            record_id = clean_data['id']
            del clean_data['id']
            supabase.table(table_name).update(clean_data).eq("id", record_id).execute()
            st.success("Güncellendi!")
        else:
            supabase.table(table_name).insert(clean_data).execute()
            st.success("Kaydedildi!")
        return True
    except Exception as e:
        st.error(f"Hata: {e}")
        return False

# --- MENÜ İÇERİKLERİ ---

if choice == "Yeni Müşteri":
    st.header("👤 Yeni Müşteri Talebi")
    with st.form("customer_form"):
        name = st.text_input("Ad Soyad")
        phone = st.text_input("Telefon (90...)")
        email = st.text_input("E-posta")
        demand = st.selectbox("Talep Türü", ["Satılık Konut", "Kiralık Konut", "Satılık Arsa"])
        budget = st.text_input("Bütçe")
        region1 = st.text_input("Bölge 1"); region2 = st.text_input("Bölge 2"); region3 = st.text_input("Bölge 3")
        urgency = st.selectbox("Aciliyet", ["Acil", "Normal", "Belirtmedi"])
        notes = st.text_area("Notlar")
        if st.form_submit_button("Müşteriyi Kaydet"):
            data = {"tarih": datetime.now().strftime("%d.%m.%Y"), "ad_soyad": name, "telefon": phone, "e_posta": email, "talep_türü": demand, "bütçe": budget, "bölge_1": region1, "bölge_2": region2, "bölge_3": region3, "aciliyet": urgency, "notlar": notes}
            write_to_cloud("customers", data)

elif choice == "Müşteri Listesi":
    st.header("👥 Müşteri Listesi")
    res = supabase.table("customers").select("*").execute()
    if res.data:
        df = pd.DataFrame(res.data)
        for _, row in df.iterrows():
            with st.expander(f"{row['ad_soyad']} - {row['talep_türü']}"):
                if st.session_state.get(f"edit_cust_{row['id']}"):
                    with st.form(f"edit_form_{row['id']}"):
                        name = st.text_input("Ad Soyad", row['ad_soyad'])
                        phone = st.text_input("Telefon", row['telefon'])
                        email = st.text_input("E-posta", row['e_posta'])
                        demand = st.selectbox("Talep Türü", ["Satılık Konut", "Kiralık Konut", "Satılık Arsa"], index=["Satılık Konut", "Kiralık Konut", "Satılık Arsa"].index(row['talep_türü']))
                        budget = st.text_input("Bütçe", row['bütçe'])
                        r1 = st.text_input("Bölge 1", row['bölge_1'])
                        r2 = st.text_input("Bölge 2", row['bölge_2'])
                        r3 = st.text_input("Bölge 3", row['bölge_3'])
                        note = st.text_area("Notlar", row['notlar'])
                        if st.form_submit_button("Güncelle"):
                            data = {"id": row['id'], "ad_soyad": name, "telefon": phone, "e_posta": email, "talep_türü": demand, "bütçe": budget, "bölge_1": r1, "bölge_2": r2, "bölge_3": r3, "notlar": note}
                            if write_to_cloud("customers", data):
                                st.session_state[f"edit_cust_{row['id']}"] = False
                                st.rerun()
                    if st.button("İptal", key=f"cancel_{row['id']}"):
                        st.session_state[f"edit_cust_{row['id']}"] = False
                        st.rerun()
                else:
                    st.write(f"📞 {row['telefon']}")
                    st.write(f"💰 Bütçe: {row['bütçe']}")
                    st.write(f"📍 Bölgeler: {row['bölge_1']}, {row['bölge_2']}, {row['bölge_3']}")
                    st.write(f"📝 Notlar: {row['notlar']}")
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.link_button("WhatsApp", f"https://wa.me/{row['telefon']}", use_container_width=True)
                    with col2:
                        if st.button("Düzenle", key=f"edit_btn_{row['id']}", use_container_width=True):
                            st.session_state[f"edit_cust_{row['id']}"] = True
                            st.rerun()
                    with col3:
                        if st.button("Sil", key=f"del_btn_{row['id']}", type="primary", use_container_width=True):
                            supabase.table("customers").delete().eq("id", row['id']).execute()
                            st.rerun()
    else: st.info("Müşteri kaydı bulunamadı.")

elif choice == "Yeni Satılık Konut":
    st.header("� Yeni Satılık Konut")
    with st.form("sk_form"):
        ilan_no = st.text_input("İlan No")
        tip = st.selectbox("Konut Tipi", ["Daire", "Villa", "Rezidans"])
        fiyat = st.text_input("Fiyat")
        bolge = st.text_input("Bölge/Mahalle")
        oda = st.selectbox("Oda Sayısı", ["1+1", "2+1", "3+1", "4+1", "5+1"])
        kat = st.text_input("Kat")
        sahibi = st.text_input("Mülk Sahibi"); sahibi_tel = st.text_input("Sahibi Tel")
        notlar = st.text_area("Notlar")
        img = st.file_uploader("Resim Seç (Kamera/Galeri)", type=["jpg", "png", "jpeg"])
        if st.form_submit_button("İlanı Kaydet"):
            data = {"tarih": datetime.now().strftime("%d.%m.%Y"), "ilan_no": ilan_no, "konut_tipi": tip, "fiyat": fiyat, "bölge_mahalle": bolge, "oda_sayısı": oda, "kat": kat, "sahibi": sahibi, "sahibi_tel": sahibi_tel, "notlar": notlar}
            write_to_cloud("satilik_konut", data, img)

elif choice == "Portföy Listesi":
    st.header("📋 Güncel Portföyler")
    t1, t2, t3 = st.tabs(["Satılık Konut", "Kiralık Konut", "Satılık Arsa"])
    
    def show_portfolio(table):
        res = supabase.table(table).select("*").execute()
        if res.data:
            for row in res.data:
                with st.container(border=True):
                    # --- EDIT MODE ---
                    if st.session_state.get(f"edit_port_{table}_{row['id']}"):
                        with st.form(f"form_edit_{table}_{row['id']}"):
                            ilan_no = st.text_input("İlan No", row['ilan_no'])
                            fiyat = st.text_input("Fiyat", row.get('fiyat', row.get('kira_bedeli', '')))
                            bolge = st.text_input("Bölge", row['bölge_mahalle'])
                            notlar = st.text_area("Notlar", row['notlar'])
                            new_imgs = st.file_uploader("Yeni Resim Ekle", type=["jpg", "png", "jpeg"], accept_multiple_files=True)
                            
                            # Existing Images
                            urls = get_image_urls(row.get('image_urls', []))
                            if urls:
                                st.write("Mevcut Resimler:")
                                for u in urls:
                                    c1, c2 = st.columns([4, 1])
                                    c1.image(get_full_image_url(u), width=100)
                                    if c2.checkbox("Sil", key=f"del_img_{u}"):
                                        urls.remove(u)
                            
                            if st.form_submit_button("Güncelle"):
                                data = {"id": row['id'], "ilan_no": ilan_no, "bölge_mahalle": bolge, "notlar": notlar, "image_urls": urls}
                                if "fiyat" in row: data["fiyat"] = fiyat
                                else: data["kira_bedeli"] = fiyat
                                if write_to_cloud(table, data, new_imgs):
                                    st.session_state[f"edit_port_{table}_{row['id']}"] = False
                                    st.rerun()
                        if st.button("İptal", key=f"cancel_port_{table}_{row['id']}"):
                            st.session_state[f"edit_port_{table}_{row['id']}"] = False
                            st.rerun()
                    
                    # --- DISPLAY MODE ---
                    else:
                        col1, col2 = st.columns([1, 2])
                        with col1:
                            urls = get_image_urls(row.get('image_urls'))
                            if urls: st.image(get_full_image_url(urls[0]), use_container_width=True)
                            elif row.get('resim_url'): st.image(get_full_image_url(row['resim_url']), use_container_width=True)
                            else: st.info("Resim yok")
                        with col2:
                            st.write(f"**İlan No: {row['ilan_no']}**")
                            st.write(f"📍 {row['bölge_mahalle']}")
                            st.write(f"💰 {row.get('fiyat', row.get('kira_bedeli', ''))} TL")
                            
                            # Action Buttons
                            btn_col1, btn_col2, btn_col3 = st.columns(3)
                            with btn_col1:
                                pdf_bytes = generate_pdf_bytes(row)
                                st.download_button("📄 PDF", pdf_bytes, f"Sunum_{row['ilan_no']}.pdf", "application/pdf", key=f"pdf_{table}_{row['id']}", use_container_width=True)
                            with btn_col2:
                                if st.button("📝 Düzenle", key=f"edit_port_btn_{table}_{row['id']}", use_container_width=True):
                                    st.session_state[f"edit_port_{table}_{row['id']}"] = True
                                    st.rerun()
                            with btn_col3:
                                if st.button("🗑️ Sil", key=f"del_port_btn_{table}_{row['id']}", type="primary", use_container_width=True):
                                    supabase.table(table).delete().eq("id", row['id']).execute()
                                    st.rerun()
                            
                            st.link_button("🔗 WhatsApp'ta Paylaş", f"https://wa.me/?text=İlan No: {row['ilan_no']}\nBölge: {row['bölge_mahalle']}\nFiyat: {row.get('fiyat')} TL", use_container_width=True)
        else: st.info("Kayıt bulunamadı.")

    with t1: show_portfolio("satilik_konut")
    with t2: show_portfolio("kiralik_konut")
    with t3: show_portfolio("satilik_arsa")

elif choice == "Akıllı Eşleştirme":
    st.header("🎯 Akıllı Eşleştirme")
    cust_res = supabase.table("customers").select("*").execute()
    if cust_res.data:
        df_cust = pd.DataFrame(cust_res.data)
        selected = st.selectbox("Müşteri Seçin", df_cust["ad_soyad"].tolist())
        if selected:
            cust = df_cust[df_cust["ad_soyad"] == selected].iloc[0]
            table = {"Satılık Konut": "satilik_konut", "Kiralık Konut": "kiralik_konut", "Satılık Arsa": "satilik_arsa"}.get(cust["talep_türü"])
            if table:
                port_res = supabase.table(table).select("*").execute()
                if port_res.data:
                    regions = [str(cust[r]).lower().strip() for r in ["bölge_1", "bölge_2", "bölge_3"] if cust[r] and str(cust[r]).strip() != "-"]
                    matches = [p for p in port_res.data if any(r in str(p.get("bölge_mahalle", "")).lower() for r in regions)]
                    for p in matches:
                        with st.container(border=True):
                            c1, c2 = st.columns([1, 3])
                            with c1:
                                url = get_image_url(p.get('resim_url'))
                                if url: st.image(url, width=100)
                            with c2:
                                st.write(f"**İlan: {p['ilan_no']}** | {p['bölge_mahalle']} | {p.get('fiyat')} TL")
                                st.link_button("Müşteriye Gönder", f"https://wa.me/{cust['telefon']}?text=Sizin için uygun ilan: {p['ilan_no']}\nBölge: {p['bölge_mahalle']}\nFiyat: {p.get('fiyat')} TL")
    else: st.warning("Müşteri bulunamadı.")
