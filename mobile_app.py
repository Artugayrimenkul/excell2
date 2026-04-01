import streamlit as st
import pandas as pd
from supabase import create_client, Client
import json
import os
from datetime import datetime
import io
import requests
import urllib.parse
import time
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, Frame
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.utils import simpleSplit
from PIL import Image as PILImage, ImageOps

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

def fetch_table_cached(table_name: str, limit: int, order_col: str = "id", desc: bool = True, ttl_seconds: int = 20):
    cache_key = f"_cache_{table_name}_{limit}_{order_col}_{desc}"
    now = time.time()
    cached = st.session_state.get(cache_key)
    if cached and isinstance(cached, dict) and (now - cached.get("ts", 0)) < ttl_seconds:
        return cached.get("data", [])
    try:
        q = supabase.table(table_name).select("*")
        if order_col:
            q = q.order(order_col, desc=desc)
        if limit:
            q = q.limit(int(limit))
        data = q.execute().data or []
    except Exception:
        data = []
    st.session_state[cache_key] = {"ts": now, "data": data}
    return data

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

    storage_path = "assets/pdf_settings.json"

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
            return settings
    except:
        try:
            raw = supabase.storage.from_("portfolio_images").download(storage_path)
            if raw:
                if isinstance(raw, bytes):
                    value = json.loads(raw.decode("utf-8"))
                else:
                    value = json.loads(raw)
                if isinstance(value, dict):
                    settings.update(value)
        except:
            pass

    return settings

def save_pdf_settings(settings: dict):
    storage_path = "assets/pdf_settings.json"
    try:
        supabase.table("app_settings").upsert({"key": "pdf", "value": settings}).execute()
        return True
    except:
        try:
            payload = json.dumps(settings, ensure_ascii=False).encode("utf-8")
            supabase.storage.from_("portfolio_images").upload(
                storage_path,
                payload,
                {"content-type": "application/json", "upsert": "true"}
            )
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

def upload_pdf_bytes_to_storage(pdf_bytes: io.BytesIO, ilan_no: str):
    try:
        safe_ilan = str(ilan_no or "ilan").strip().replace("/", "_").replace("\\", "_").replace(" ", "_")
        file_name = f"assets/pdfs/{safe_ilan}_{int(datetime.now().timestamp())}.pdf"
        supabase.storage.from_("portfolio_images").upload(
            file_name,
            pdf_bytes.getvalue(),
            {"content-type": "application/pdf", "upsert": "true"}
        )
        return get_full_image_url(file_name)
    except Exception as e:
        st.error(f"PDF yükleme hatası: {e}")
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
                logo = ImageOps.exif_transpose(PILImage.open(logo_data))
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
                img = PILImage.open(io.BytesIO(resp.content))
                img = ImageOps.exif_transpose(img)
                return img
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

        styles = getSampleStyleSheet()
        base_style = styles["Normal"]
        base_style.fontName = MAIN_FONT
        base_style.fontSize = 10.5
        base_style.leading = 13

        label_style = ParagraphStyle(
            "LabelStyle",
            parent=base_style,
            fontName=BOLD_FONT,
            fontSize=10.5,
            leading=13,
            alignment=TA_LEFT,
        )

        value_style = ParagraphStyle(
            "ValueStyle",
            parent=base_style,
            fontName=MAIN_FONT,
            fontSize=10.5,
            leading=13,
            alignment=TA_LEFT,
        )

        left_x = 0.9 * inch
        label_w = 2.0 * inch
        gap_w = 0.2 * inch
        value_x = left_x + label_w + gap_w
        value_w = width - value_x - 0.9 * inch
        line_bottom_margin = 1.5 * inch

        def ensure_space(needed_h):
            nonlocal y
            if y - needed_h < line_bottom_margin:
                c.showPage()
                # Simple page header for continued details
                c.setFillColorRGB(*primary_rgb)
                c.rect(0, height-1.0*inch, width, 1.0*inch, fill=1)
                c.setFillColorRGB(1, 1, 1)
                c.setFont(BOLD_FONT, 14)
                c.drawString(0.8*inch, height-0.65*inch, f"{title_1} - DETAYLAR")
                y = height - 1.3 * inch

        for k, v in row.items():
            if not v or k in excluded:
                continue

            label = k.replace("_", " ").title()
            value = str(v)

            label_lines = simpleSplit(f"{label}:", BOLD_FONT, 10.5, label_w)
            value_lines = simpleSplit(value, MAIN_FONT, 10.5, value_w)
            row_lines = max(len(label_lines), len(value_lines), 1)
            row_h = row_lines * 13

            ensure_space(row_h + 6)

            label_p = Paragraph(f"{label}:", label_style)
            value_p = Paragraph(value.replace("\n", "<br/>"), value_style)

            label_f = Frame(left_x, y - row_h, label_w, row_h, leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0, showBoundary=0)
            value_f = Frame(value_x, y - row_h, value_w, row_h, leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0, showBoundary=0)

            label_f.addFromList([label_p], c)
            value_f.addFromList([value_p], c)

            y -= (row_h + 6)

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
            def optimize_image_bytes(raw: bytes):
                try:
                    img = PILImage.open(io.BytesIO(raw))
                    img = ImageOps.exif_transpose(img)
                    if img.mode not in ("RGB", "L"):
                        img = img.convert("RGB")
                    max_side = 1920
                    w, h = img.size
                    if max(w, h) > max_side:
                        if w >= h:
                            new_w = max_side
                            new_h = int(h * (max_side / float(w)))
                        else:
                            new_h = max_side
                            new_w = int(w * (max_side / float(h)))
                        img = img.resize((max(1, new_w), max(1, new_h)), PILImage.LANCZOS)

                    out = io.BytesIO()
                    img.save(out, format="JPEG", quality=88, optimize=True, progressive=True)
                    optimized = out.getvalue()
                    if len(optimized) >= len(raw) or len(raw) < 500_000:
                        return raw, None
                    return optimized, "jpg"
                except:
                    return raw, None

            raw = file.getvalue()
            optimized, forced_ext = optimize_image_bytes(raw)

            file_ext = forced_ext or file.name.split(".")[-1].lower()
            file_name = f"{ilan_no}_{int(datetime.now().timestamp())}_{i}.{file_ext}"
            content_type = "image/jpeg" if file_ext == "jpg" else f"image/{file_ext}"
            supabase.storage.from_("portfolio_images").upload(file_name, optimized, {"content-type": content_type, "upsert": "true"})
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
    q = st.text_input("Ara (Ad, Telefon, Bölge, Not)", key="cust_search").strip().lower()
    demand_filter = st.selectbox("Talep Türü Filtresi", ["Hepsi", "Satılık Konut", "Kiralık Konut", "Satılık Arsa"], key="cust_demand_filter")
    show_limit = st.slider("Gösterilecek maksimum kayıt", min_value=10, max_value=200, value=50, step=10, key="cust_limit")

    fetch_limit = max(200, int(show_limit) * 5)
    rows_data = fetch_table_cached("customers", limit=fetch_limit, order_col="id", desc=True)
    if rows_data:
        df = pd.DataFrame(rows_data)

        if demand_filter != "Hepsi" and "talep_türü" in df.columns:
            df = df[df["talep_türü"] == demand_filter]

        if q:
            def _safe(v):
                return "" if v is None else str(v).lower()

            cols = [c for c in ["ad_soyad", "telefon", "e_posta", "bölge_1", "bölge_2", "bölge_3", "notlar"] if c in df.columns]
            if cols:
                mask = df[cols].applymap(_safe).agg(" ".join, axis=1).str.contains(q, na=False)
                df = df[mask]

        if "ad_soyad" in df.columns:
            df = df.sort_values("ad_soyad")

        df = df.head(int(show_limit))

        st.caption(f"Toplam eşleşen: {len(df)}")

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
        c_top1, c_top2 = st.columns(2)
        with c_top1:
            fiyat = st.text_input("Fiyat (TL)")
        with c_top2:
            ilan_no = st.text_input("İlan No")

        c_loc1, c_loc2, c_loc3 = st.columns(3)
        with c_loc1:
            il = st.text_input("İl")
        with c_loc2:
            ilce = st.text_input("İlçe")
        with c_loc3:
            mahalle = st.text_input("Mahalle")

        ilan_tarihi = st.date_input("İlan Tarihi", value=datetime.now().date())

        emlak_tipi = st.selectbox("Emlak Tipi", ["Satılık Daire", "Satılık Villa", "Satılık Rezidans"])
        tip = st.selectbox("Konut Tipi", ["Daire", "Villa", "Rezidans"])

        c_m2_1, c_m2_2 = st.columns(2)
        with c_m2_1:
            m2_brut = st.text_input("m² (Brüt)")
        with c_m2_2:
            m2_net = st.text_input("m² (Net)")

        c_room1, c_room2 = st.columns(2)
        with c_room1:
            oda = st.selectbox("Oda Sayısı", ["1+1", "2+1", "3+1", "4+1", "5+1"])
        with c_room2:
            bina_yasi = st.text_input("Bina Yaşı")

        c_kat1, c_kat2 = st.columns(2)
        with c_kat1:
            bulundugu_kat = st.text_input("Bulunduğu Kat")
        with c_kat2:
            kat_sayisi = st.text_input("Kat Sayısı")

        c_opt1, c_opt2 = st.columns(2)
        with c_opt1:
            isitma = st.selectbox("Isıtma", ["Merkezi (Pay Ölçer)", "Kombi (Doğalgaz)", "Soba", "Yerden Isıtma", "Klima", "Belirtilmemiş"])
            banyo_sayisi = st.selectbox("Banyo Sayısı", ["1", "2", "3", "4+", "Belirtilmemiş"])
            mutfak = st.selectbox("Mutfak", ["Kapalı", "Açık", "Belirtilmemiş"])
            balkon = st.selectbox("Balkon", ["Var", "Yok", "Belirtilmemiş"])
        with c_opt2:
            otopark = st.selectbox("Otopark", ["Açık Otopark", "Kapalı Otopark", "Yok", "Belirtilmemiş"])
            kullanim_durumu = st.selectbox("Kullanım Durumu", ["Boş", "Kiracılı", "Mal Sahibi", "Belirtilmemiş"])
            site_icerisinde = st.selectbox("Site İçerisinde", ["Evet", "Hayır", "Belirtilmemiş"])
            krediye_uygun = st.selectbox("Krediye Uygun", ["Evet", "Hayır", "Belirtilmemiş"])

        sahibi = st.text_input("Mülk Sahibi")
        sahibi_tel = st.text_input("Sahibi Tel")
        notlar = st.text_area("Notlar / Açıklama")
        imgs = st.file_uploader("Resimler Seç (Kamera/Galeri)", type=["jpg", "png", "jpeg"], accept_multiple_files=True)
        if st.form_submit_button("İlanı Kaydet"):
            bolge_parts = [p.strip() for p in [il, ilce, mahalle] if p and str(p).strip()]
            bolge = " / ".join(bolge_parts)

            detaylar = []
            def add_detay(label, value):
                if value is None:
                    return
                s = str(value).strip()
                if not s or s == "Belirtilmemiş":
                    return
                detaylar.append(f"{label}: {s}")

            add_detay("İlan Tarihi", ilan_tarihi.strftime("%d.%m.%Y") if ilan_tarihi else "")
            add_detay("Emlak Tipi", emlak_tipi)
            add_detay("m² (Brüt)", m2_brut)
            add_detay("m² (Net)", m2_net)
            add_detay("Bina Yaşı", bina_yasi)
            add_detay("Bulunduğu Kat", bulundugu_kat)
            add_detay("Kat Sayısı", kat_sayisi)
            add_detay("Isıtma", isitma)
            add_detay("Banyo Sayısı", banyo_sayisi)
            add_detay("Mutfak", mutfak)
            add_detay("Balkon", balkon)
            add_detay("Otopark", otopark)
            add_detay("Kullanım Durumu", kullanim_durumu)
            add_detay("Site İçerisinde", site_icerisinde)
            add_detay("Krediye Uygun", krediye_uygun)

            notlar_full = (notlar or "").strip()
            if detaylar:
                if notlar_full:
                    notlar_full += "\n\n"
                notlar_full += "--- Detaylar ---\n" + "\n".join(detaylar)

            data = {
                "tarih": ilan_tarihi.strftime("%d.%m.%Y") if ilan_tarihi else datetime.now().strftime("%d.%m.%Y"),
                "ilan_no": ilan_no,
                "konut_tipi": tip,
                "fiyat": fiyat,
                "bölge_mahalle": bolge,
                "oda_sayısı": oda,
                "kat": bulundugu_kat,
                "sahibi": sahibi,
                "sahibi_tel": sahibi_tel,
                "notlar": notlar_full
            }
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
    
    def _parse_amount(v):
        if v is None:
            return None
        s = str(v).strip()
        if not s:
            return None
        s = s.replace(".", "").replace(",", "")
        s = "".join(ch for ch in s if ch.isdigit())
        if not s:
            return None
        try:
            return int(s)
        except:
            return None

    def show_portfolio(table, key_prefix, q, min_amount, max_amount, only_with_images, limit_count, show_thumbs):
        fetch_limit = max(200, int(limit_count) * 5)
        rows = fetch_table_cached(table, limit=fetch_limit, order_col="id", desc=True)
        if rows:

            if q:
                ql = q.strip().lower()
                def _row_text(r):
                    parts = [
                        r.get("ilan_no"),
                        r.get("bölge_mahalle"),
                        r.get("notlar"),
                        r.get("konut_tipi"),
                        r.get("arsa_tipi"),
                    ]
                    return " ".join([str(p).lower() for p in parts if p is not None])
                rows = [r for r in rows if ql in _row_text(r)]

            if only_with_images:
                rows = [r for r in rows if (get_image_urls(r.get("image_urls")) or r.get("resim_url"))]

            amount_field = "kira_bedeli" if table == "kiralik_konut" else "fiyat"
            if min_amount is not None or max_amount is not None:
                filtered = []
                for r in rows:
                    val = _parse_amount(r.get(amount_field))
                    if val is None:
                        continue
                    if min_amount is not None and val < min_amount:
                        continue
                    if max_amount is not None and val > max_amount:
                        continue
                    filtered.append(r)
                rows = filtered

            rows = rows[: int(limit_count)]

            st.caption(f"Toplam eşleşen: {len(rows)}")

            for row in rows:
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
                            if show_thumbs:
                                urls = get_image_urls(row.get('image_urls'))
                                if urls:
                                    st.image(get_full_image_url(urls[0]), use_container_width=True)
                                elif row.get('resim_url'):
                                    st.image(get_full_image_url(row['resim_url']), use_container_width=True)
                                else:
                                    st.info("Resim yok")
                            else:
                                st.write("📷")
                        with col2:
                            st.write(f"**İlan No: {row['ilan_no']}**")
                            st.write(f"📍 {row['bölge_mahalle']}")
                            st.write(f"💰 {row.get('fiyat', row.get('kira_bedeli', ''))} TL")
                            
                            # Action Buttons
                            btn_col1, btn_col2, btn_col3 = st.columns(3)
                            with btn_col1:
                                pdf_key = f"pf_pdf_bytes_{table}_{row['id']}"
                                if pdf_key not in st.session_state:
                                    st.session_state[pdf_key] = None
                                if st.session_state[pdf_key] is None:
                                    if st.button("📄 PDF Hazırla", key=f"prep_{pdf_key}", use_container_width=True):
                                        st.session_state[pdf_key] = generate_pdf_bytes(row).getvalue()
                                        st.rerun()
                                else:
                                    st.download_button(
                                        "📄 PDF İndir",
                                        st.session_state[pdf_key],
                                        f"Sunum_{row['ilan_no']}.pdf",
                                        "application/pdf",
                                        key=f"dl_{pdf_key}",
                                        use_container_width=True
                                    )
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

    with t1:
        st.subheader("Filtreler")
        q1 = st.text_input("Ara (İlan No / Bölge / Not)", key="pf_q_satilik")
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            min1 = st.number_input("Min Fiyat", min_value=0, value=0, step=100000, key="pf_min_satilik")
        with c2:
            max1 = st.number_input("Max Fiyat", min_value=0, value=0, step=100000, key="pf_max_satilik")
        with c3:
            only_img1 = st.checkbox("Sadece Resimli", value=False, key="pf_img_satilik")
        with c4:
            lim1 = st.slider("Limit", min_value=10, max_value=200, value=50, step=10, key="pf_lim_satilik")
        show_thumbs1 = st.checkbox("Önizleme Resimleri", value=False, key="pf_thumb_satilik")
        show_portfolio("satilik_konut", "satilik", q1, min1 if min1 > 0 else None, max1 if max1 > 0 else None, only_img1, lim1, show_thumbs1)

    with t2:
        st.subheader("Filtreler")
        q2 = st.text_input("Ara (İlan No / Bölge / Not)", key="pf_q_kiralik")
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            min2 = st.number_input("Min Kira", min_value=0, value=0, step=1000, key="pf_min_kiralik")
        with c2:
            max2 = st.number_input("Max Kira", min_value=0, value=0, step=1000, key="pf_max_kiralik")
        with c3:
            only_img2 = st.checkbox("Sadece Resimli", value=False, key="pf_img_kiralik")
        with c4:
            lim2 = st.slider("Limit", min_value=10, max_value=200, value=50, step=10, key="pf_lim_kiralik")
        show_thumbs2 = st.checkbox("Önizleme Resimleri", value=False, key="pf_thumb_kiralik")
        show_portfolio("kiralik_konut", "kiralik", q2, min2 if min2 > 0 else None, max2 if max2 > 0 else None, only_img2, lim2, show_thumbs2)

    with t3:
        st.subheader("Filtreler")
        q3 = st.text_input("Ara (İlan No / Bölge / Not)", key="pf_q_arsa")
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            min3 = st.number_input("Min Fiyat", min_value=0, value=0, step=100000, key="pf_min_arsa")
        with c2:
            max3 = st.number_input("Max Fiyat", min_value=0, value=0, step=100000, key="pf_max_arsa")
        with c3:
            only_img3 = st.checkbox("Sadece Resimli", value=False, key="pf_img_arsa")
        with c4:
            lim3 = st.slider("Limit", min_value=10, max_value=200, value=50, step=10, key="pf_lim_arsa")
        show_thumbs3 = st.checkbox("Önizleme Resimleri", value=False, key="pf_thumb_arsa")
        show_portfolio("satilik_arsa", "arsa", q3, min3 if min3 > 0 else None, max3 if max3 > 0 else None, only_img3, lim3, show_thumbs3)

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
                                match_key = f"match_pdf_url_{table}_{p.get('id', p.get('ilan_no', 'x'))}"
                                if match_key not in st.session_state:
                                    st.session_state[match_key] = ""

                                btn1, btn2 = st.columns(2)
                                with btn1:
                                    if st.button("📎 PDF Linki Oluştur", key=f"mk_{match_key}", use_container_width=True):
                                        pdf_bytes = generate_pdf_bytes(p)
                                        pdf_url = upload_pdf_bytes_to_storage(pdf_bytes, p.get("ilan_no"))
                                        if pdf_url:
                                            st.session_state[match_key] = pdf_url
                                            st.success("PDF linki hazır.")

                                with btn2:
                                    pdf_url = st.session_state.get(match_key, "")
                                    if pdf_url:
                                        msg = (
                                            f"Sizin için uygun ilan PDF\\n"
                                            f"İlan No: {p.get('ilan_no','')}\\n"
                                            f"Bölge: {p.get('bölge_mahalle','')}\\n"
                                            f"Fiyat: {p.get('fiyat', p.get('kira_bedeli',''))} TL\\n"
                                            f"PDF: {pdf_url}"
                                        )
                                        st.link_button(
                                            "📤 WhatsApp PDF Gönder",
                                            f"https://wa.me/{cust['telefon']}?text={urllib.parse.quote(msg)}",
                                            use_container_width=True
                                        )
                                    else:
                                        st.caption("Önce PDF linki oluşturun.")
    else: st.warning("Müşteri bulunamadı.")
