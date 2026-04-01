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

# --- SAYFA YAPILANDIRMASI (EN BAŞTA OLMALI) ---
st.set_page_config(page_title="Mobil CRM Portal", page_icon="🏠", layout="wide")

# Register fonts that support Turkish characters
REG_FONT = "TurkishFont.ttf"
BOLD_FONT_FILE = "TurkishFont-Bold.ttf"
MAIN_FONT = "Helvetica"
BOLD_FONT = "Helvetica-Bold"

def check_ttf(path):
    if not os.path.exists(path): return False
    with open(path, 'rb') as f:
        header = f.read(4)
        return header == b'\x00\x01\x00\x00' or header == b'OTTO'

if check_ttf(REG_FONT):
    try:
        pdfmetrics.registerFont(TTFont('TurkishFont', REG_FONT))
        MAIN_FONT = "TurkishFont"
    except: pass

if check_ttf(BOLD_FONT_FILE):
    try:
        pdfmetrics.registerFont(TTFont('TurkishFont-Bold', BOLD_FONT_FILE))
        BOLD_FONT = "TurkishFont-Bold"
    except: pass

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

menu = ["PDF Ayarları", "Yeni Müşteri", "Müşteri Listesi", "Yeni Satılık Konut", "Yeni Kiralık Konut", "Yeni Satılık Arsa", "Portföy Listesi", "Akıllı Eşleştirme"]
choice = st.sidebar.selectbox("Menü", menu)

# --- PDF AYARLARI ---
DEFAULT_PDF_SETTINGS = {
    "title_1": "",
    "title_2": "GAYRİMENKUL KATALOĞU",
    "section_title": "GAYRİMENKUL BİLGİLERİ",
    "footer_text": "",
    "note_text": "Bu belge otomatik olarak CRM tarafından oluşturulmuştur.",
    "primary_color": "#19325e",
    "show_all_images": True,
    "images_per_page": 4,
    "logo_file": ""
}

def _hex_to_rgb(hex_color: str):
    try:
        c = hex_color.strip().lstrip("#")
        if len(c) != 6:
            return (0.1, 0.2, 0.4)
        r = int(c[0:2], 16) / 255.0
        g = int(c[2:4], 16) / 255.0
        b = int(c[4:6], 16) / 255.0
        return (r, g, b)
    except:
        return (0.1, 0.2, 0.4)

def load_pdf_settings():
    settings = dict(DEFAULT_PDF_SETTINGS)
    settings["title_1"] = config.get("company_name", "")
    settings["footer_text"] = f"İletişim: {config.get('company_phone', '')}  |  {config.get('company_email', '')}"

    try:
        res = supabase.table("app_settings").select("value").eq("key", "pdf").execute()
        if res.data and isinstance(res.data, list) and len(res.data) > 0:
            value = res.data[0].get("value") or {}
            if isinstance(value, str):
                try:
                    value = json.loads(value)
                except:
                    value = {}
            if isinstance(value, dict):
                settings.update(value)
    except:
        pass

    return settings

def save_pdf_settings(settings: dict):
    try:
        supabase.table("app_settings").upsert({"key": "pdf", "value": settings}).execute()
        return True
    except:
        return False

def upload_pdf_logo(file):
    if not file:
        return ""
    try:
        ext = file.name.split(".")[-1].lower()
        if ext not in ["png", "jpg", "jpeg", "bmp"]:
            return ""
        path = "assets/company_logo." + ext
        supabase.storage.from_("portfolio_images").upload(
            path,
            file.getvalue(),
            {"content-type": f"image/{ext}", "upsert": "true"}
        )
        return path
    except:
        return ""

# --- PDF OLUŞTURMA FONKSİYONU ---
def generate_pdf_bytes(row):
    try:
        pdf_settings = load_pdf_settings()
        primary_rgb = _hex_to_rgb(pdf_settings.get("primary_color", "#19325e"))

        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4
        
        # --- Header ---
        c.setFillColorRGB(*primary_rgb)
        c.rect(0, height-1.8*inch, width, 1.8*inch, fill=1)
        
        # Logo Check
        logo_added = False
        logo_url = ""
        if pdf_settings.get("logo_file"):
            logo_url = get_full_image_url(pdf_settings["logo_file"])
        elif config.get("company_logo_url"):
            logo_url = config["company_logo_url"]

        if logo_url:
            try:
                resp = requests.get(logo_url, timeout=10)
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
        
        title_1 = (pdf_settings.get("title_1") or config.get("company_name") or "").upper()
        title_2 = (pdf_settings.get("title_2") or "").strip()

        if logo_added:
            c.drawString(title_x, height-0.8*inch, title_1)
            if title_2:
                c.setFont(MAIN_FONT, 16)
                c.drawString(title_x, height-1.1*inch, title_2)
        else:
            c.drawCentredString(width/2, height-0.8*inch, title_1)
            if title_2:
                c.setFont(MAIN_FONT, 16)
                c.drawCentredString(width/2, height-1.1*inch, title_2)
        
        y = height - 2.2*inch
        
        def draw_image_fit(img: PILImage.Image, x, y_bottom, w, h):
            img = img.convert("RGB")
            iw, ih = img.size
            if iw == 0 or ih == 0:
                return
            aspect = ih / float(iw)
            draw_w = w
            draw_h = draw_w * aspect
            if draw_h > h:
                draw_h = h
                draw_w = draw_h / aspect
            x0 = x + (w - draw_w) / 2
            y0 = y_bottom + (h - draw_h) / 2
            c.drawInlineImage(img, x0, y0, width=draw_w, height=draw_h)

        def fetch_image(url: str):
            try:
                resp = requests.get(url, timeout=15)
                if resp.status_code != 200:
                    return None
                return PILImage.open(io.BytesIO(resp.content))
            except:
                return None

        # --- Images Section ---
        img_urls = []
        raw_urls = get_image_urls(row.get("image_urls"))
        if raw_urls:
            img_urls = [get_full_image_url(u) for u in raw_urls if u]
        elif row.get("resim_url"):
            img_urls = [get_full_image_url(row["resim_url"])]
            
        if img_urls:
            try:
                img = fetch_image(img_urls[0])
                if img:
                    display_w = 6*inch
                    display_h = 4.5*inch
                    x_img = (width - display_w) / 2
                    y_img = y - display_h
                c.setStrokeColorRGB(0.8, 0.8, 0.8)
                    c.rect(x_img - 2, y_img - 2, display_w + 4, display_h + 4, stroke=1)
                    draw_image_fit(img, x_img, y_img, display_w, display_h)
                    y -= (display_h + 0.6*inch)
            except Exception as e:
                y -= 0.5*inch
        
        # --- Details ---
        c.setFillColorRGB(0, 0, 0)
        c.setFont(BOLD_FONT, 18)
        section_title = (pdf_settings.get("section_title") or "GAYRİMENKUL BİLGİLERİ").strip()
        c.drawString(0.8*inch, y, section_title)
        y -= 0.2*inch
        c.setStrokeColorRGB(*primary_rgb)
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

        if pdf_settings.get("show_all_images", True) and len(img_urls) > 1:
            remaining = img_urls[1:]
            images_per_page = int(pdf_settings.get("images_per_page", 4) or 4)
            if images_per_page not in [1, 4]:
                images_per_page = 4

            idx = 0
            while idx < len(remaining):
                c.showPage()
                c.setFillColorRGB(*primary_rgb)
                c.rect(0, height-1.2*inch, width, 1.2*inch, fill=1)
                c.setFillColorRGB(1, 1, 1)
                c.setFont(BOLD_FONT, 16)
                c.drawString(0.8*inch, height-0.8*inch, f"{title_1} - FOTOĞRAFLAR")

                if images_per_page == 1:
                    img = fetch_image(remaining[idx])
                    if img:
                        x0 = 0.8*inch
                        y0 = 1.5*inch
                        w0 = width - 1.6*inch
                        h0 = height - 2.9*inch
                        c.setStrokeColorRGB(0.8, 0.8, 0.8)
                        c.rect(x0 - 2, y0 - 2, w0 + 4, h0 + 4, stroke=1)
                        draw_image_fit(img, x0, y0, w0, h0)
                    idx += 1
                else:
                    margin_x = 0.8*inch
                    margin_y = 1.2*inch
                    gap = 0.3*inch
                    cell_w = (width - 2*margin_x - gap) / 2
                    cell_h = (height - 1.6*inch - margin_y - gap) / 2
                    positions = [
                        (margin_x, margin_y + cell_h + gap),
                        (margin_x + cell_w + gap, margin_y + cell_h + gap),
                        (margin_x, margin_y),
                        (margin_x + cell_w + gap, margin_y),
                    ]
                    for pos_i in range(4):
                        if idx >= len(remaining):
                            break
                        img = fetch_image(remaining[idx])
                        if img:
                            x0, y0 = positions[pos_i]
                            c.setStrokeColorRGB(0.8, 0.8, 0.8)
                            c.rect(x0 - 2, y0 - 2, cell_w + 4, cell_h + 4, stroke=1)
                            draw_image_fit(img, x0, y0, cell_w, cell_h)
                        idx += 1
                    
        # --- Footer ---
        c.setFillColorRGB(*primary_rgb)
        c.rect(0, 0, width, 1*inch, fill=1)
        c.setFillColorRGB(1, 1, 1)
        c.setFont(BOLD_FONT, 10)
        footer_text = (pdf_settings.get("footer_text") or "").strip()
        c.drawCentredString(width/2, 0.6*inch, footer_text)
        c.setFont(MAIN_FONT, 8)
        note_text = (pdf_settings.get("note_text") or "").strip()
        if note_text:
            c.drawCentredString(width/2, 0.4*inch, note_text)
        
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

if choice == "PDF Ayarları":
    st.header("🧾 PDF Ayarları")
    st.write("Bu sayfadan PDF başlığı, alt başlığı, iletişim bilgileri ve logo ayarlarını değiştirebilirsiniz.")

    current = load_pdf_settings()

    with st.form("pdf_settings_form"):
        title_1 = st.text_input("Başlık (Satır 1)", value=current.get("title_1", ""))
        title_2 = st.text_input("Başlık (Satır 2)", value=current.get("title_2", ""))
        section_title = st.text_input("Bölüm Başlığı", value=current.get("section_title", ""))
        footer_text = st.text_input("Alt Bilgi (İletişim)", value=current.get("footer_text", ""))
        note_text = st.text_input("Alt Not", value=current.get("note_text", ""))
        primary_color = st.text_input("Kurumsal Renk (HEX) örn: #19325e", value=current.get("primary_color", "#19325e"))
        show_all_images = st.checkbox("PDF'de tüm resimleri göster", value=bool(current.get("show_all_images", True)))
        images_per_page = st.selectbox("Galeri sayfası düzeni", options=[1, 4], index=1 if int(current.get("images_per_page", 4) or 4) == 4 else 0)
        logo_file = st.file_uploader("Logo Yükle (PNG/JPG)", type=["png", "jpg", "jpeg", "bmp"])
        clear_logo = st.checkbox("Logoyu kaldır")

        if st.form_submit_button("Kaydet"):
            new_settings = dict(current)
            new_settings["title_1"] = title_1
            new_settings["title_2"] = title_2
            new_settings["section_title"] = section_title
            new_settings["footer_text"] = footer_text
            new_settings["note_text"] = note_text
            new_settings["primary_color"] = primary_color
            new_settings["show_all_images"] = show_all_images
            new_settings["images_per_page"] = int(images_per_page)

            if clear_logo:
                new_settings["logo_file"] = ""
            else:
                uploaded_path = upload_pdf_logo(logo_file)
                if uploaded_path:
                    new_settings["logo_file"] = uploaded_path

            if save_pdf_settings(new_settings):
                st.success("PDF ayarları kaydedildi.")
                st.rerun()
            else:
                st.error("PDF ayarları kaydedilemedi. Supabase tarafında 'app_settings' tablosu eksik olabilir.")
                st.code(
                    "create table if not exists app_settings (\n"
                    "  key text primary key,\n"
                    "  value jsonb not null default '{}'::jsonb\n"
                    ");",
                    language="sql"
                )

    if current.get("logo_file"):
        st.caption("Mevcut Logo")
        st.image(get_full_image_url(current["logo_file"]), width=180)

elif choice == "Yeni Müşteri":
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
    st.header("🏠 Yeni Satılık Konut")
    with st.form("sk_form"):
        ilan_no = st.text_input("İlan No")
        tip = st.selectbox("Konut Tipi", ["Daire", "Villa", "Rezidans"])
        fiyat = st.text_input("Fiyat")
        bolge = st.text_input("Bölge/Mahalle")
        oda = st.selectbox("Oda Sayısı", ["1+1", "2+1", "3+1", "4+1", "5+1"])
        kat = st.text_input("Kat")
        sahibi = st.text_input("Mülk Sahibi"); sahibi_tel = st.text_input("Sahibi Tel")
        notlar = st.text_area("Notlar")
        imgs = st.file_uploader("Resimler Seç (Kamera/Galeri)", type=["jpg", "png", "jpeg"], accept_multiple_files=True)
        if st.form_submit_button("İlanı Kaydet"):
            data = {"tarih": datetime.now().strftime("%d.%m.%Y"), "ilan_no": ilan_no, "konut_tipi": tip, "fiyat": fiyat, "bölge_mahalle": bolge, "oda_sayısı": oda, "kat": kat, "sahibi": sahibi, "sahibi_tel": sahibi_tel, "notlar": notlar}
            write_to_cloud("satilik_konut", data, imgs)

elif choice == "Yeni Kiralık Konut":
    st.header("🏠 Yeni Kiralık Konut")
    with st.form("kk_form"):
        ilan_no = st.text_input("İlan No")
        tip = st.selectbox("Konut Tipi", ["Daire", "Villa", "Rezidans"])
        kira = st.text_input("Kira Bedeli")
        bolge = st.text_input("Bölge/Mahalle")
        oda = st.selectbox("Oda Sayısı", ["1+1", "2+1", "3+1", "4+1", "5+1"])
        kat = st.text_input("Kat")
        sahibi = st.text_input("Mülk Sahibi"); sahibi_tel = st.text_input("Sahibi Tel")
        notlar = st.text_area("Notlar")
        imgs = st.file_uploader("Resimler Seç", type=["jpg", "png", "jpeg"], accept_multiple_files=True)
        if st.form_submit_button("Kiralık İlanı Kaydet"):
            data = {"tarih": datetime.now().strftime("%d.%m.%Y"), "ilan_no": ilan_no, "konut_tipi": tip, "kira_bedeli": kira, "bölge_mahalle": bolge, "oda_sayısı": oda, "kat": kat, "sahibi": sahibi, "sahibi_tel": sahibi_tel, "notlar": notlar}
            write_to_cloud("kiralik_konut", data, imgs)

elif choice == "Yeni Satılık Arsa":
    st.header("🌳 Yeni Satılık Arsa")
    with st.form("sa_form"):
        ilan_no = st.text_input("İlan No")
        tip = st.selectbox("Arsa Tipi", ["İmarlı", "Tarla", "Zeytinlik"])
        ada = st.text_input("Ada"); parsel = st.text_input("Parsel")
        fiyat = st.text_input("Fiyat")
        bolge = st.text_input("Bölge/Mahalle")
        sahibi = st.text_input("Mülk Sahibi"); sahibi_tel = st.text_input("Sahibi Tel")
        notlar = st.text_area("Notlar")
        imgs = st.file_uploader("Resimler Seç", type=["jpg", "png", "jpeg"], accept_multiple_files=True)
        if st.form_submit_button("Arsa İlanını Kaydet"):
            data = {"tarih": datetime.now().strftime("%d.%m.%Y"), "ilan_no": ilan_no, "arsa_tipi": tip, "ada": ada, "parsel": parsel, "fiyat": fiyat, "bölge_mahalle": bolge, "sahibi": sahibi, "sahibi_tel": sahibi_tel, "notlar": notlar}
            write_to_cloud("satilik_arsa", data, imgs)

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
                            
                            st.link_button("🔗 WhatsApp'ta Paylaş", f"https://wa.me/?text=İlan No: {row['ilan_no']}\nBölge: {row['bölge_mahalle']}\nFiyat: {row.get('fiyat', row.get('kira_bedeli', ''))} TL", use_container_width=True)
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
                                urls = get_image_urls(p.get('image_urls'))
                                if urls: st.image(get_full_image_url(urls[0]), width=100)
                                elif p.get('resim_url'): st.image(get_full_image_url(p['resim_url']), width=100)
                            with c2:
                                st.write(f"**İlan: {p['ilan_no']}** | {p['bölge_mahalle']} | {p.get('fiyat', p.get('kira_bedeli', ''))} TL")
                                st.link_button("Müşteriye Gönder", f"https://wa.me/{cust['telefon']}?text=Sizin için uygun ilan: {p['ilan_no']}\nBölge: {p['bölge_mahalle']}\nFiyat: {p.get('fiyat', p.get('kira_bedeli', ''))} TL")
    else: st.warning("Müşteri bulunamadı.")
