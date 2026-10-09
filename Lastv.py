# ===================================================================
# Lastv.py — نظام إدارة الجراج المتكامل
# النسخة النهائية: Multi-Garage + Railway Volume + Session Security
# المطور: مهندس أحمد شعبان — 01095387792
# ===================================================================
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import sqlite3
from datetime import datetime, timedelta
import plotly.express as px
import hashlib
import time
import os
import logging
import math
import json
import copy
import uuid
from contextlib import contextmanager
import qrcode
from io import BytesIO
import base64
from PIL import Image

# ⭐ تحميل .env
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    import barcode
    from barcode.writer import ImageWriter
    BARCODE_AVAILABLE = True
except ImportError:
    BARCODE_AVAILABLE = False

# ⭐ استيراد بوابة المشترك ⭐
try:
    from subscriber_portal import subscriber_portal_page, show_app_payments
except Exception:
    subscriber_portal_page = None
    show_app_payments = None
# ===================== تقارير Excel / PDF =====================
try:
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter
    EXCEL_AVAILABLE = True
except ImportError:
    EXCEL_AVAILABLE = False

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import (SimpleDocTemplate, Table, TableStyle,
                                     Paragraph, Spacer, Image as RLImage)
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    import arabic_reshaper
    from bidi.algorithm import get_display
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False
# ===================== بيانات المطور =====================
DEVELOPER_NAME = "مهندس أحمد شعبان"
DEVELOPER_PHONE = "01095387792"
INSTAPAY_NUMBER = "ahmedibrahimshaban92@instapay"
APP_FEE_DEFAULT = 10.0
SESSION_VALIDITY_MINUTES = 30


# ===================================================================
# ⭐⭐⭐ Railway Volume Support ⭐⭐⭐
# ===================================================================
def _get_base_data_dir():
    """يرجع مسار التخزين الأساسي — Volume على Railway أو المجلد الحالي"""
    # ⭐ جديد: مجلد بيانات مخصص (نسخة الويندوز)
    custom = os.environ.get('PARKING_DATA_DIR')
    if custom:
        try:
            os.makedirs(custom, exist_ok=True)
            return custom
        except Exception:
            pass
    if os.path.exists('/data') and os.path.isdir('/data'):
        try:
            test_file = os.path.join('/data', '.write_test')
            with open(test_file, 'w') as f:
                f.write('test')
            os.remove(test_file)
            return '/data'
        except Exception:
            pass
    return '.'


def _get_db_path(filename):
    """يبني مسار قاعدة بيانات صحيح"""
    base = _get_base_data_dir()
    if base == '/data':
        return os.path.join('/data', filename)
    return filename


def _get_garages_dir():
    """يرجع مسار مجلد الجراجات"""
    base = _get_base_data_dir()
    if base == '/data':
        return os.path.join('/data', 'garages')
    return 'garages'


def _get_logs_dir():
    """يرجع مسار مجلد اللوجات"""
    base = _get_base_data_dir()
    if base == '/data':
        return os.path.join('/data', 'logs')
    return 'logs'


# ===================== الإعدادات الافتراضية للجراج =====================
DEFAULT_GARAGE_NAME = "نظام إدارة الجراج المتكامل"
DEFAULT_FLOOR_NAMES = {
    0: "الدور الأرضي", 1: "الدور الأول", 2: "الدور الثاني",
    3: "الدور الثالث", 4: "الدور الرابع", 5: "الدور الخامس",
    6: "الدور السادس", 7: "الدور السابع", 8: "الدور الثامن",
    9: "الدور التاسع", 10: "🅿️ دور الانتظار"
}
DEFAULT_STRUCTURE = {
    0: {0: {'spots': 4, 'name': 'مستوى أ', 'start': 1},
        1: {'spots': 28, 'name': 'مستوى ب', 'start': 5}},
    1: {0: {'spots': 27, 'name': 'مستوى أ', 'start': 33},
        1: {'spots': 28, 'name': 'مستوى ب', 'start': 60}},
    2: {0: {'spots': 51, 'name': 'مستوى أ', 'start': 88},
        1: {'spots': 52, 'name': 'مستوى ب', 'start': 139}},
    3: {0: {'spots': 52, 'name': 'مستوى أ', 'start': 191},
        1: {'spots': 52, 'name': 'مستوى ب', 'start': 243}},
    4: {0: {'spots': 52, 'name': 'مستوى أ', 'start': 295},
        1: {'spots': 54, 'name': 'مستوى ب', 'start': 347}},
    5: {0: {'spots': 55, 'name': 'مستوى أ', 'start': 401},
        1: {'spots': 55, 'name': 'مستوى ب', 'start': 456}},
    6: {0: {'spots': 50, 'name': 'مستوى أ', 'start': 511},
        1: {'spots': 52, 'name': 'مستوى ب', 'start': 563}},
    7: {0: {'spots': 53, 'name': 'مستوى أ', 'start': 615},
        1: {'spots': 54, 'name': 'مستوى ب', 'start': 668}},
    8: {0: {'spots': 81, 'name': 'المستوى الوحيد', 'start': 722}},
    9: {0: {'spots': 90, 'name': 'المستوى الوحيد', 'start': 803}},
    10: {0: {'spots': 150, 'name': 'منطقة الانتظار', 'start': 900}},
}

_FLOOR_NAMES_CACHE = dict(DEFAULT_FLOOR_NAMES)
_GARAGE_NAME_CACHE = DEFAULT_GARAGE_NAME


def get_floor_name(floor):
    return _FLOOR_NAMES_CACHE.get(floor, f"الدور {floor}")


def update_floor_names_cache(names):
    global _FLOOR_NAMES_CACHE
    _FLOOR_NAMES_CACHE = dict(names)


def get_garage_name_cached():
    return _GARAGE_NAME_CACHE


def update_garage_name_cache(name):
    global _GARAGE_NAME_CACHE
    _GARAGE_NAME_CACHE = name or DEFAULT_GARAGE_NAME


# ===================== Logging =====================
def setup_logging(log_level=logging.WARNING):
    log_dir = _get_logs_dir()
    if not os.path.exists(log_dir):
        try:
            os.makedirs(log_dir, exist_ok=True)
        except Exception:
            log_dir = "."
    log_file = os.path.join(log_dir, f"garage_{datetime.now().strftime('%Y%m%d')}.log")
    logger = logging.getLogger("garage_system")
    logger.setLevel(log_level)
    if logger.handlers:
        logger.handlers.clear()
    try:
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setLevel(log_level)
        fh.setFormatter(logging.Formatter("%(asctime)s | %(levelname)-8s | %(message)s",
                                          datefmt="%Y-%m-%d %H:%M:%S"))
        logger.addHandler(fh)
    except Exception:
        pass
    return logger


logger = setup_logging()


def app_log(level, message):
    try:
        getattr(logger, level.lower(), logger.info)(message)
    except Exception:
        pass


st.set_page_config(
    page_title="نظام إدارة الجراج المتكامل",
    page_icon="🚗",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ===================== CSS =====================
st.markdown("""
<style>
    .stApp { direction: rtl; text-align: right; background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%); font-size: 16px; font-weight: bold; }
    .main-header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 20px; border-radius: 15px; color: white; margin-bottom: 20px; box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4); display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; gap: 10px; }
    .main-header h1 { font-size: clamp(18px, 3vw, 28px); font-weight: bold; margin: 0; }
    .main-header p { font-size: clamp(14px, 2vw, 18px); font-weight: bold; margin: 5px 0 0 0; }
    .metric-card { background: white; border-radius: 15px; padding: 15px; text-align: center; box-shadow: 0 2px 10px rgba(0,0,0,0.1); border-right: 5px solid #667eea; margin: 5px 0; min-height: 100px; display: flex; flex-direction: column; justify-content: center; }
    .metric-value { font-size: clamp(20px, 3vw, 32px); font-weight: bold; color: #667eea; }
    .metric-label { font-size: clamp(12px, 1.5vw, 16px); font-weight: bold; color: #666; margin-top: 5px; }
    .badge { display: inline-block; padding: 5px 15px; border-radius: 20px; font-size: clamp(12px, 1.5vw, 16px); font-weight: bold; color: white; white-space: nowrap; }
    .badge-admin { background: #f44336; }
    .badge-manager { background: #ff9800; }
    .badge-entry { background: #4CAF50; }
    .badge-exit { background: #2196F3; }
    .badge-subscriber { background: #9C27B0; }
    .badge-super { background: linear-gradient(135deg, #FFD700 0%, #FF8C00 100%); color: #000; }
    .stButton > button { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border: none; border-radius: 10px; padding: 10px 15px; font-weight: bold; transition: all 0.3s; width: 100%; font-size: clamp(12px, 1.4vw, 15px); min-height: 42px; }
    .stButton > button:hover { transform: scale(1.03); box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4); }
    .stTabs [data-baseweb="tab-list"] { gap: 5px; flex-wrap: wrap; }
    .stTabs [data-baseweb="tab"] { background: white; border-radius: 10px; padding: 10px 16px; color: #333; font-weight: bold; }
    .stTabs [aria-selected="true"] { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white !important; }
    .stMarkdown, label, p, span, div { font-size: clamp(13px, 1.4vw, 16px); }
    label { font-weight: bold !important; }
    input, select, textarea { font-size: clamp(14px, 1.5vw, 16px) !important; font-weight: bold !important; }
    [data-testid="column"] { padding: 2px !important; }
    [data-testid="stSidebar"] { min-width: 260px !important; }
    [data-testid="stSidebar"] * { font-size: clamp(13px, 1.4vw, 16px); }
    .inside-card { background: white; border-radius: 10px; padding: 10px; margin: 5px 0; border-right: 4px solid #4CAF50; box-shadow: 0 1px 4px rgba(0,0,0,0.08); }
    .developer-footer { text-align: center; padding: 12px 5px; margin-top: 15px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 10px; color: white; box-shadow: 0 2px 8px rgba(102,126,234,0.3); }
    .developer-footer .dev-name { font-size: 13px; font-weight: bold; display: block; }
    .developer-footer .dev-phone { font-size: 12px; display: block; margin-top: 3px; direction: ltr; }
    .lock-screen { background: linear-gradient(135deg, #ff416c 0%, #ff4b2b 100%); color: white; padding: 40px 20px; border-radius: 20px; text-align: center; box-shadow: 0 10px 40px rgba(255,65,108,0.4); margin: 20px 0; }
    .lock-screen h1 { font-size: clamp(22px, 4vw, 40px); margin: 10px 0; }
    .lock-screen .contact-box { background: rgba(255,255,255,0.15); border-radius: 15px; padding: 20px; margin: 20px auto; max-width: 500px; border: 2px solid rgba(255,255,255,0.3); }
    .lock-screen .contact-box .name { font-size: clamp(18px, 3vw, 26px); font-weight: bold; }
    .lock-screen .contact-box .phone { font-size: clamp(20px, 3.5vw, 30px); font-weight: bold; direction: ltr; letter-spacing: 2px; margin-top: 10px; }
    .floor-card { background: white; border-radius: 12px; padding: 12px; margin: 8px 0; box-shadow: 0 2px 8px rgba(0,0,0,0.08); border-right: 5px solid #667eea; }
</style>
""", unsafe_allow_html=True)


# ===================== دوال مساعدة =====================
def parse_spot_id(spot_id):
    try:
        parts = spot_id.split('_')
        if len(parts) == 3:
            return int(parts[0]), int(parts[1]), int(parts[2])
    except Exception:
        pass
    return None, None, None


def get_spot_location(spot_id):
    floor, level, number = parse_spot_id(spot_id)
    if floor is not None:
        return f"{get_floor_name(floor)} - مكان {number}"
    return "غير محدد"


def get_next_movement_number(db):
    try:
        result = db.execute_query("SELECT value FROM parking_settings WHERE key='last_movement_number'", fetch=True)
        new = int(result[0]['value']) + 1 if result else 1
        db.execute_query("UPDATE parking_settings SET value=? WHERE key='last_movement_number'", (str(new),), commit=True)
        return new
    except Exception:
        db.execute_query("INSERT OR IGNORE INTO parking_settings (key, value) VALUES ('last_movement_number', '1')", commit=True)
        return 1


def generate_qr_base64(data, color="#000000", box_size=6):
    try:
        qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=box_size, border=2)
        qr.add_data(str(data))
        qr.make(fit=True)
        img = qr.make_image(fill_color=color, back_color="white").convert('RGB')
        img = img.resize((220, 220), Image.Resampling.LANCZOS)
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        buffered.seek(0)
        return base64.b64encode(buffered.getvalue()).decode('utf-8')
    except Exception:
        return ""


def generate_barcode_base64(data, color="#000000"):
    if not BARCODE_AVAILABLE:
        return ""
    try:
        from barcode import get_barcode_class
        data_str = str(data)[:25]
        code_class = get_barcode_class('code128')
        rv = BytesIO()
        code = code_class(data_str, writer=ImageWriter())
        code.write(rv, options={'write_text': True, 'text_distance': 3.0, 'font_size': 14,
                                'module_width': 1.2, 'module_height': 40.0, 'quiet_zone': 4,
                                'foreground': color, 'background': 'white'})
        rv.seek(0)
        barcode_img = Image.open(BytesIO(rv.getvalue()))
        new_width = 400
        ratio = new_width / barcode_img.width
        barcode_img = barcode_img.resize((new_width, int(barcode_img.height * ratio)), Image.Resampling.LANCZOS)
        buffered = BytesIO()
        barcode_img.save(buffered, format="PNG")
        buffered.seek(0)
        return base64.b64encode(buffered.getvalue()).decode('utf-8')
    except Exception:
        return ""


def generate_qr_content_from_fields(fields):
    return "\n".join([f"{f['label']}: {f['value']}" for f in fields])


def _ar(text):
    """يعالج النص العربي لـ PDF"""
    if not PDF_AVAILABLE:
        return str(text)
    try:
        reshaped = arabic_reshaper.reshape(str(text))
        return get_display(reshaped)
    except Exception:
        return str(text)


def _setup_arabic_font():
    """يسجل خط عربي في reportlab"""
    if not PDF_AVAILABLE:
        return None
    try:
        # هنستخدم خط Cairo من النظام أو الافتراضي
        font_paths = [
            'Cairo-Regular.ttf',
            '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
            'C:\\Windows\\Fonts\\arial.ttf',
            'C:\\Windows\\Fonts\\tahoma.ttf',
        ]
        for fp in font_paths:
            if os.path.exists(fp):
                pdfmetrics.registerFont(TTFont('ArabicFont', fp))
                return 'ArabicFont'
    except Exception:
        pass
    return 'Helvetica'


def export_to_excel(manager, data_type='subscribers', filters=None):
    """
    يصدّر البيانات لملف Excel
    data_type: 'subscribers' | 'visitors' | 'financial' | 'inside'
    """
    if not EXCEL_AVAILABLE:
        return None

    try:
        df = pd.DataFrame()

        if data_type == 'subscribers':
            subs = manager.get_all_subscribers()
            if subs:
                data = []
                for r in subs:
                    end_dt = datetime.fromisoformat(r[9]) if r[9] else None
                    days_left = (end_dt - datetime.now()).days if end_dt else None
                    data.append({
                        'المعرف': r[0],
                        'الاسم': r[1] or '',
                        'جهة العمل': r[2] or '',
                        'رقم الكارت': r[3] or '',
                        'نوع السيارة': r[4] or '',
                        'رقم السيارة': r[5] or '',
                        'الهاتف': r[6] or '',
                        'نوع الاشتراك': r[7] or '',
                        'بداية': r[8][:10] if r[8] else '',
                        'نهاية': r[9][:10] if r[9] else '',
                        'أيام متبقية': days_left if days_left is not None else '',
                        'المكان': get_spot_location(r[13]) if r[13] else 'غير مخصص',
                    })
                df = pd.DataFrame(data)

        elif data_type == 'financial':
            rec = manager.get_all_financial_records()
            if rec:
                data = [{
                    'المعرف': r[0],
                    'المشترك': r[1] or '-',
                    'النوع': r[2],
                    'المبلغ': r[3],
                    'الحالة': r[4],
                    'الوصف': r[5],
                    'التاريخ': r[6][:16] if r[6] else '',
                } for r in rec]
                df = pd.DataFrame(data)

        elif data_type == 'visitors':
            vis = manager.visitor_manager.get_visitors_financial_report() if hasattr(manager, 'visitor_manager') else []
            if not vis:
                # من manager.db مباشرة
                rows = manager.db.execute_query(
                    "SELECT ticket_number, entry_time, exit_time, vehicle_number, "
                    "duration_minutes, amount, payment_status, phone "
                    "FROM visitors ORDER BY entry_time DESC LIMIT 5000",
                    fetch=True
                ) or []
                data = [{
                    'التذكرة': r['ticket_number'],
                    'السيارة': r['vehicle_number'],
                    'الهاتف': r['phone'] or '-',
                    'الدخول': r['entry_time'][:16] if r['entry_time'] else '',
                    'الخروج': r['exit_time'][:16] if r['exit_time'] else '',
                    'المدة (دقيقة)': r['duration_minutes'],
                    'المبلغ': r['amount'],
                    'الحالة': r['payment_status'],
                } for r in rows]
                df = pd.DataFrame(data)

        elif data_type == 'inside':
            inside = get_cached_active_visitors(manager.db.db_path)
            if inside:
                data = [{
                    'التذكرة': v['ticket_number'],
                    'السيارة': v.get('vehicle_number', ''),
                    'الهاتف': v.get('phone', '') or '-',
                    'الدخول': v['entry_time'][:16] if v.get('entry_time') else '',
                    'المكان': get_spot_location(v['spot_id']) if v.get('spot_id') else 'غير مخصص',
                } for v in inside]
                df = pd.DataFrame(data)

        if df.empty:
            return None

        # هنكتب لـ BytesIO
        buf = BytesIO()
        with pd.ExcelWriter(buf, engine='xlsxwriter') as writer:
            df.to_excel(writer, sheet_name='Data', index=False)

            workbook = writer.book
            worksheet = writer.sheets['Data']

            # تنسيق الهيدر
            header_fmt = workbook.add_format({
                'bold': True,
                'bg_color': '#667eea',
                'font_color': 'white',
                'align': 'center',
                'valign': 'vcenter',
                'border': 1,
            })

            # ضبط عرض الأعمدة
            for idx, col in enumerate(df.columns):
                col_width = max(len(str(col)) + 2, df[col].astype(str).str.len().max() + 2) if len(df) > 0 else 15
                col_width = min(col_width, 40)
                worksheet.set_column(idx, idx, col_width)
                worksheet.write(0, idx, col, header_fmt)

            # تجميد الصف الأول
            worksheet.freeze_panes(1, 0)

        buf.seek(0)
        return buf.getvalue()

    except Exception as e:
        print(f"Excel export error: {e}")
        return None


def export_to_pdf(manager, data_type='subscribers'):
    """
    يصدّر البيانات لملف PDF مع دعم العربي
    """
    if not PDF_AVAILABLE:
        return None

    try:
        font_name = _setup_arabic_font()
        garage_name = get_garage_name_cached()

        # نجمع البيانات
        rows = []
        title = ''

        if data_type == 'subscribers':
            title = 'قائمة المشتركين'
            subs = manager.get_all_subscribers()
            for r in subs:
                end_dt = datetime.fromisoformat(r[9]) if r[9] else None
                days_left = (end_dt - datetime.now()).days if end_dt else '-'
                rows.append([
                    _ar(r[1] or ''),
                    _ar(r[3] or ''),
                    _ar(r[6] or ''),
                    _ar(r[7] or ''),
                    _ar(r[9][:10] if r[9] else ''),
                    _ar(str(days_left)),
                ])
            headers = [_ar(h) for h in ['الاسم', 'رقم الكارت', 'الهاتف', 'الاشتراك', 'النهاية', 'متبقي']]

        elif data_type == 'financial':
            title = 'المعاملات المالية'
            rec = manager.get_all_financial_records()
            for r in rec[:500]:  # حد أقصى 500
                rows.append([
                    _ar(r[2] or ''),
                    _ar(str(r[3]) if r[3] else ''),
                    _ar(r[4] or ''),
                    _ar((r[5] or '')[:50]),
                    _ar(r[6][:16] if r[6] else ''),
                ])
            headers = [_ar(h) for h in ['النوع', 'المبلغ', 'الحالة', 'الوصف', 'التاريخ']]

        elif data_type == 'inside':
            title = 'الزوار داخل الجراج'
            inside = get_cached_active_visitors(manager.db.db_path)
            for v in inside:
                rows.append([
                    _ar(v['ticket_number']),
                    _ar(v.get('vehicle_number', '')),
                    _ar(v.get('phone', '') or '-'),
                    _ar(v['entry_time'][:16] if v.get('entry_time') else ''),
                    _ar(get_spot_location(v['spot_id']) if v.get('spot_id') else '-'),
                ])
            headers = [_ar(h) for h in ['التذكرة', 'السيارة', 'الهاتف', 'الدخول', 'المكان']]

        if not rows:
            return None

        # نبني PDF
        buf = BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=A4,
                                rightMargin=1 * cm, leftMargin=1 * cm,
                                topMargin=1.5 * cm, bottomMargin=1.5 * cm)

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Title'],
            fontName=font_name,
            fontSize=18,
            alignment=1,  # center
            spaceAfter=6,
        )
        sub_style = ParagraphStyle(
            'CustomSub',
            parent=styles['Normal'],
            fontName=font_name,
            fontSize=10,
            alignment=1,
            textColor=colors.grey,
        )

        story = []

        # العنوان
        story.append(Paragraph(_ar(garage_name), title_style))
        story.append(Paragraph(_ar(title), title_style))
        story.append(Paragraph(_ar(f'التاريخ: {datetime.now().strftime("%Y-%m-%d %H:%M")}'), sub_style))
        story.append(Spacer(1, 0.5 * cm))

        # الجدول
        data = [headers] + rows
        table = Table(data, repeatRows=1)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#667eea')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTNAME', (0, 0), (-1, -1), font_name),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f5f7fa')]),
        ]))
        story.append(table)

        story.append(Spacer(1, 0.5 * cm))
        story.append(Paragraph(
            _ar(f'تم التطوير بواسطة: {DEVELOPER_NAME} | {DEVELOPER_PHONE}'),
            sub_style
        ))

        doc.build(story)
        buf.seek(0)
        return buf.getvalue()

    except Exception as e:
        print(f"PDF export error: {e}")
        return None
def get_paper_width_from_settings(db):
    try:
        result = db.execute_query("SELECT value FROM parking_settings WHERE key='paper_width'", fetch=True)
        if result:
            return int(result[0]['value'])
    except Exception:
        pass
    return 80


def render_developer_footer():
    st.markdown(f"""
    <div class="developer-footer">
        <span class="dev-name">🚗 تم التطوير بواسطة: {DEVELOPER_NAME}</span>
        <span class="dev-phone">📱 للتواصل: {DEVELOPER_PHONE}</span>
    </div>
    """, unsafe_allow_html=True)


def generate_receipt_html(title, fields, qr_data=None, barcode_data=None, footer_text=None, paper_width=80, movement_number=None):
    if qr_data is None and fields:
        qr_data = generate_qr_content_from_fields(fields)
    if movement_number is not None:
        fields = [{'label': 'رقم الحركة', 'value': str(movement_number)}] + fields

    fields_html = ""
    for field in fields:
        fields_html += f'<div style="display:flex; flex-wrap:wrap; justify-content:space-between; padding:2px 0; border-bottom:1px dashed #ccc; font-size:11px; gap:4px;"><span style="font-weight:bold; color:#333;">{field["label"]}:</span><span style="color:#000;">{field["value"]}</span></div>'
    footer = footer_text or datetime.now().strftime('%Y-%m-%d %H:%M')

    qr_html = ""
    if qr_data:
        qr_b64 = generate_qr_base64(qr_data, box_size=6)
        if qr_b64:
            qr_html = f'<div style="text-align:center; margin:4px 0;"><img src="data:image/png;base64,{qr_b64}" style="width:100px; height:100px; border:1px solid #ddd; padding:1px;"></div>'

    barcode_html = ""
    if barcode_data:
        b64 = generate_barcode_base64(barcode_data)
        if b64:
            barcode_html = f'<div style="text-align:center; margin:4px 0;"><img src="data:image/png;base64,{b64}" style="width:100%; max-width:300px;"></div>'

    return f"""
    <div style="background: white; direction: rtl; font-family: 'Arial', sans-serif; max-width: {paper_width}mm; margin: 0 auto; padding: 2mm; font-size: 11px;">
        <div style="text-align:center; border-bottom:2px solid #000; padding-bottom:3px; margin-bottom:3px;">
            <div style="font-size:16px; font-weight:bold;">{title}</div>
            <div style="font-size:10px; color:#666;">{get_garage_name_cached()}</div>
        </div>
        {qr_html}
        <div style="width:100%;">{fields_html}</div>
        {barcode_html}
        <div style="text-align:center; border-top:2px solid #000; padding-top:3px; margin-top:3px; font-size:10px; color:#666;">
            {footer}
        </div>
        <div style="text-align:center; margin-top:3px; font-size:9px; color:#999;">
            تم التطوير بواسطة: {DEVELOPER_NAME} | {DEVELOPER_PHONE}
        </div>
    </div>
    <div class="no-print" style="text-align:center; margin-top:10px;">
        <button onclick="window.print()" style="padding:10px 30px; background:#667eea; color:white; border:none; border-radius:6px; font-weight:bold; cursor:pointer; font-size:16px;">🖨️ طباعة</button>
    </div>
    """


def display_receipt_with_buttons(title, fields, qr_data=None, barcode_data=None, footer_text=None, db=None, movement_number=None):
    paper_width = get_paper_width_from_settings(db) if db else 80
    html = generate_receipt_html(title, fields, qr_data, barcode_data, footer_text, paper_width=paper_width, movement_number=movement_number)
    components.html(html, height=550, scrolling=False)
    st.markdown("---")
    if st.button("✖ إغلاق الإيصال", use_container_width=True, key="close_receipt_btn"):
        st.session_state.pop('receipt_data', None)
        st.rerun()


# ===================================================================
# ⭐⭐⭐ نظام صلاحية النظام (License) ⭐⭐⭐
# ===================================================================
def is_system_expired(db):
    try:
        result = db.execute_query("SELECT value FROM parking_settings WHERE key='system_expiry_date'", fetch=True)
        if result and result[0]['value']:
            try:
                expiry_dt = datetime.fromisoformat(result[0]['value'])
                return datetime.now() > expiry_dt, expiry_dt
            except Exception:
                pass
        return False, None
    except Exception:
        return False, None


def set_system_expiry(db, expiry_date):
    try:
        if expiry_date is None:
            db.execute_query("INSERT OR REPLACE INTO parking_settings (key, value) VALUES ('system_expiry_date', '')", commit=True)
        else:
            db.execute_query("INSERT OR REPLACE INTO parking_settings (key, value) VALUES ('system_expiry_date', ?)",
                             (expiry_date.isoformat(),), commit=True)
        return True
    except Exception as e:
        app_log("error", f"فشل ضبط تاريخ الانتهاء: {e}")
        return False


# ===================================================================
# ⭐⭐⭐ فحص اشتراك التطبيق + إدارة الجلسات ⭐⭐⭐
# ===================================================================
def get_subscriber_app_status(db, sub):
    """
    يرجع (status, days_remaining, msg)
    status: 'active' | 'trial' | 'expired' | 'disabled' | 'garage_free'
    """
    if not sub:
        return 'expired', 0, 'غير مسجل'

    # ⭐ 1) الإدارة أوقفت الخدمة يدوياً؟
    if sub.get('app_service_disabled'):
        return 'disabled', 0, '⛔ الخدمة موقوفة من الإدارة'

    # ⭐ 2) الجراج معفى نهائياً؟
    try:
        r = db.execute_query("SELECT value FROM parking_settings WHERE key='garage_free_forever'", fetch=True)
        if r and r[0]['value'] == '1':
            return 'garage_free', 999, '🎉 الخدمة مجانية لهذا الجراج'
    except Exception:
        pass

    # ⭐ 3) الجراج معفى لفترة محددة؟
    try:
        r = db.execute_query("SELECT value FROM parking_settings WHERE key='garage_free_until'", fetch=True)
        if r and r[0]['value']:
            free_until = datetime.fromisoformat(str(r[0]['value']).replace('Z', '').split('.')[0])
            if free_until >= datetime.now():
                days = max(0, (free_until - datetime.now()).days)
                return 'garage_free', days, f'🎉 مجاني للجراج — يتبقى {days} يوم'
    except Exception:
        pass

    # 4) اشتراك مدفوع نشط؟
    if sub.get('app_subscription_active'):
        end = sub.get('app_subscription_end')
        if end:
            try:
                end_dt = datetime.fromisoformat(str(end).replace('Z', '').split('.')[0])
                if end_dt >= datetime.now():
                    days = max(0, (end_dt - datetime.now()).days)
                    return 'active', days, f'✅ اشتراك نشط — يتبقى {days} يوم'
            except Exception:
                pass

    # 5) فترة تجريبية (لو مفعّلة)؟
    try:
        r = db.execute_query("SELECT value FROM parking_settings WHERE key='trial_enabled'", fetch=True)
        trial_enabled = (r and r[0]['value'] == '1') if r else True
    except Exception:
        trial_enabled = True

    if trial_enabled:
        reg = sub.get('registration_date')
        if reg:
            try:
                reg_dt = datetime.fromisoformat(str(reg).replace('Z', '').split('.')[0])
                trial_days = 3
                try:
                    r = db.execute_query(
                        "SELECT value FROM parking_settings WHERE key='app_trial_days'",
                        fetch=True
                    )
                    if r and r[0]['value']:
                        trial_days = int(r[0]['value'])
                except Exception:
                    pass

                trial_end = reg_dt + timedelta(days=trial_days)
                if trial_end >= datetime.now():
                    days = max(0, (trial_end - datetime.now()).days)
                    return 'trial', days, f'🎁 فترة تجريبية — يتبقى {days} يوم'
            except Exception:
                pass

    return 'expired', 0, '❌ انتهى الاشتراك'
def is_subscriber_app_active(sub):
    """يبقى للتوافق مع الكود القديم — لكن الأفضل استخدام get_subscriber_app_status"""
    if not sub:
        return False
    if not sub.get('app_subscription_active'):
        return False
    end = sub.get('app_subscription_end')
    if not end:
        return False
    try:
        end_str = str(end).replace('Z', '').split('.')[0]
        end_dt = datetime.fromisoformat(end_str)
        return end_dt >= datetime.now()
    except Exception:
        return False

def validate_subscriber_session(db, subscriber_id, session_token):
    """يتحقق من صلاحية الجلسة"""
    if not session_token:
        return False, "no_token"
    try:
        rows = db.execute_query(
            """SELECT id, expires_at FROM subscriber_sessions 
               WHERE subscriber_id=? AND session_token=? AND is_active=1""",
            (subscriber_id, session_token), fetch=True
        )
        if not rows:
            return False, "invalid"
        expires = rows[0]['expires_at']
        try:
            exp_dt = datetime.fromisoformat(str(expires).replace('Z', '').split('.')[0])
            if exp_dt < datetime.now():
                return False, "expired"
        except Exception:
            pass
        return True, "ok"
    except Exception:
        return False, "error"


def revoke_subscriber_sessions(db, subscriber_id, reason="manual"):
    """إلغاء كل جلسات المشترك"""
    try:
        db.execute_query(
            """UPDATE subscriber_sessions 
               SET is_active=0, revoked_at=?, revoked_reason=?
               WHERE subscriber_id=? AND is_active=1""",
            (datetime.now().isoformat(), reason, subscriber_id),
            commit=True
        )
    except Exception:
        pass


# ===================================================================
# ⭐⭐⭐ الكاش ⭐⭐⭐
# ===================================================================
@st.cache_data(ttl=3, show_spinner=False)
def get_all_spots_map(db_path):
    conn = sqlite3.connect(db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.cursor()
        cur.execute('SELECT id, floor, level, number, is_occupied, subscriber_id, status FROM spots')
        spots = {}
        for row in cur.fetchall():
            spots[row['id']] = {
                'id': row['id'], 'floor': row['floor'], 'level': row['level'],
                'number': row['number'], 'is_occupied': row['is_occupied'],
                'subscriber_id': row['subscriber_id'], 'status': row['status']
            }
        return spots
    finally:
        conn.close()


@st.cache_data(ttl=3, show_spinner=False)
def get_cached_inside_subscribers(db_path):
    conn = sqlite3.connect(db_path, timeout=30)
    try:
        cur = conn.cursor()
        cur.execute("SELECT DISTINCT subscriber_id FROM subscriber_attendance WHERE status='inside'")
        return {row[0] for row in cur.fetchall()}
    finally:
        conn.close()


@st.cache_data(ttl=3, show_spinner=False)
def get_cached_floor_summary(db_path):
    conn = sqlite3.connect(db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.cursor()
        cur.execute('SELECT floor, level, COUNT(*) as total, COALESCE(SUM(is_occupied),0) as occ FROM spots GROUP BY floor, level')
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


@st.cache_data(ttl=3, show_spinner=False)
def get_cached_dashboard_stats(db_path):
    conn = sqlite3.connect(db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.cursor()
        cur.execute('''SELECT
            (SELECT COUNT(*) FROM spots) as total_spots,
            (SELECT COUNT(*) FROM spots WHERE is_occupied=1) as occupied_spots,
            (SELECT COUNT(*) FROM subscribers) as total_subscribers''')
        row = cur.fetchone()
        return {'total': row['total_spots'], 'occupied': row['occupied_spots'], 'subs': row['total_subscribers']}
    finally:
        conn.close()


@st.cache_data(ttl=5, show_spinner=False)
def get_cached_active_visitors(db_path):
    conn = sqlite3.connect(db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM visitors WHERE status='inside' ORDER BY entry_time DESC")
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


@st.cache_data(ttl=5, show_spinner=False)
def get_cached_inside_subscribers_data(db_path):
    conn = sqlite3.connect(db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.cursor()
        cur.execute("""SELECT s.id, s.name, s.car_number, s.phone, s.car_type, s.spot_id,
                              s.subscription_type, s.subscription_end, sa.entry_time
                       FROM subscriber_attendance sa
                       JOIN subscribers s ON s.id = sa.subscriber_id
                       WHERE sa.status='inside'
                       ORDER BY sa.entry_time DESC""")
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


@st.cache_data(ttl=5, show_spinner=False)
def get_cached_users_count(db_path):
    conn = sqlite3.connect(db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.cursor()
        cur.execute("SELECT role, COUNT(*) as cnt FROM users GROUP BY role")
        result = {'entry': 0, 'exit': 0, 'admin': 0, 'manager': 0, 'subscriber': 0, 'super_admin': 0}
        for row in cur.fetchall():
            result[row['role']] = row['cnt']
        return result
    finally:
        conn.close()


@st.cache_data(ttl=15, show_spinner=False)
def get_cached_expiring_subscribers(db_path, days=7):
    conn = sqlite3.connect(db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        now = datetime.now().isoformat()
        end = (datetime.now() + timedelta(days=days)).isoformat()
        cur = conn.cursor()
        cur.execute("SELECT id, name, car_number, phone, subscription_type, subscription_end FROM subscribers WHERE subscription_end >= ? AND subscription_end <= ? AND status='active'", (now, end))
        result = []
        for row in cur.fetchall():
            end_dt = datetime.fromisoformat(row['subscription_end'])
            result.append({'subscriber_id': row['id'], 'name': row['name'], 'car_number': row['car_number'],
                           'phone': row['phone'], 'subscription_type': row['subscription_type'],
                           'days_left': (end_dt - datetime.now()).days, 'end_date': end_dt})
        return sorted(result, key=lambda x: x['days_left'])
    finally:
        conn.close()


@st.cache_data(ttl=15, show_spinner=False)
def get_cached_expired_subscribers(db_path):
    conn = sqlite3.connect(db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        now = datetime.now().isoformat()
        cur = conn.cursor()
        cur.execute("SELECT id, name, car_number, phone, subscription_type, subscription_end FROM subscribers WHERE subscription_end < ? AND status='active'", (now,))
        result = []
        for row in cur.fetchall():
            end_dt = datetime.fromisoformat(row['subscription_end'])
            result.append({'subscriber_id': row['id'], 'name': row['name'], 'car_number': row['car_number'],
                           'phone': row['phone'], 'subscription_type': row['subscription_type'],
                           'days_overdue': (datetime.now() - end_dt).days, 'end_date': end_dt})
        return sorted(result, key=lambda x: x['days_overdue'], reverse=True)
    finally:
        conn.close()


def clear_all_caches():
    get_all_spots_map.clear()
    get_cached_inside_subscribers.clear()
    get_cached_floor_summary.clear()
    get_cached_dashboard_stats.clear()
    get_cached_active_visitors.clear()
    get_cached_inside_subscribers_data.clear()
    get_cached_users_count.clear()
    get_cached_expiring_subscribers.clear()
    get_cached_expired_subscribers.clear()


# ===================================================================
# ⭐⭐⭐ سجل الجراجات (Railway Volume Support) ⭐⭐⭐
# ===================================================================
class GarageRegistry:
    """إدارة الجراجات المتعددة — كل جراج له قاعدة بيانات مستقلة"""
    def __init__(self, registry_path=None):
        if registry_path is None:
            registry_path = _get_db_path('garages_registry.db')
        self.path = registry_path
        self._init_db()

    def _init_db(self):
        try:
            garages_dir = _get_garages_dir()
            os.makedirs(garages_dir, exist_ok=True)

            with sqlite3.connect(self.path) as conn:
                conn.execute('''CREATE TABLE IF NOT EXISTS garages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    db_path TEXT NOT NULL,
                    address TEXT,
                    phone TEXT,
                    is_active INTEGER DEFAULT 1,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )''')
                cur = conn.execute('SELECT COUNT(*) FROM garages')
                if cur.fetchone()[0] == 0:
                    initial_db_path = os.path.join(garages_dir, 'جراج_الجمهورية.db')
                    conn.execute(
                        "INSERT INTO garages (name, db_path, phone) VALUES (?, ?, ?)",
                        ('جراج الجمهورية', initial_db_path, '01095387792')
                    )
                conn.commit()
        except Exception as e:
            app_log("error", f"فشل تهيئة سجل الجراجات: {e}")

    def list_garages(self, active_only=False):
        try:
            with sqlite3.connect(self.path) as conn:
                conn.row_factory = sqlite3.Row
                q = 'SELECT * FROM garages'
                if active_only:
                    q += ' WHERE is_active=1'
                q += ' ORDER BY id'
                return [dict(r) for r in conn.execute(q).fetchall()]
        except Exception:
            return []

    def get_garage(self, garage_id):
        try:
            with sqlite3.connect(self.path) as conn:
                conn.row_factory = sqlite3.Row
                r = conn.execute('SELECT * FROM garages WHERE id=?', (garage_id,)).fetchone()
                return dict(r) if r else None
        except Exception:
            return None

    def create_garage(self, name, address='', phone=''):
        try:
            safe = ''.join(c for c in name if c.isalnum() or c in '_- ')
            safe = safe.replace(' ', '_').strip('_')
            if not safe:
                safe = f"garage_{int(time.time())}"

            garages_dir = _get_garages_dir()
            os.makedirs(garages_dir, exist_ok=True)
            db_path = os.path.join(garages_dir, f"{safe}.db")

            base = db_path
            n = 1
            while os.path.exists(db_path):
                db_path = base.replace('.db', f'_{n}.db')
                n += 1

            _ = Database(db_path)

            with sqlite3.connect(self.path) as conn:
                conn.execute(
                    "INSERT INTO garages (name, db_path, address, phone) VALUES (?, ?, ?, ?)",
                    (name.strip(), db_path, address.strip(), phone.strip())
                )
                conn.commit()
            return True, db_path
        except sqlite3.IntegrityError:
            return False, "يوجد جراج بنفس الاسم بالفعل"
        except Exception as e:
            return False, str(e)

    def toggle_active(self, garage_id):
        try:
            with sqlite3.connect(self.path) as conn:
                conn.execute("UPDATE garages SET is_active = 1 - is_active WHERE id=?", (garage_id,))
                conn.commit()
            return True
        except Exception:
            return False

    def delete_garage(self, garage_id):
        try:
            garage = self.get_garage(garage_id)
            if not garage:
                return False, "الجراج غير موجود"
            actives = [g for g in self.list_garages() if g['is_active']]
            if len(actives) <= 1 and garage['is_active']:
                return False, "لا يمكن حذف آخر جراج نشط"
            with sqlite3.connect(self.path) as conn:
                conn.execute("DELETE FROM garages WHERE id=?", (garage_id,))
                conn.commit()
            return True, "تم الحذف"
        except Exception as e:
            return False, str(e)

    def update_garage_info(self, garage_id, name, address, phone):
        try:
            with sqlite3.connect(self.path) as conn:
                conn.execute(
                    "UPDATE garages SET name=?, address=?, phone=? WHERE id=?",
                    (name.strip(), address.strip(), phone.strip(), garage_id)
                )
                conn.commit()
            return True
        except Exception:
            return False


# ===================================================================
# ⭐⭐⭐ قاعدة البيانات (Railway Volume Support) ⭐⭐⭐
# ===================================================================
class Database:
    def __init__(self, db_path='garage.db'):
        # ⭐ Railway Volume Support
        base = _get_base_data_dir()
        if base == '/data':
            if not db_path.startswith('/data'):
                if db_path.startswith('garages/'):
                    db_path = os.path.join('/data', db_path)
                else:
                    db_path = os.path.join('/data', db_path)

        self.db_path = db_path
        d = os.path.dirname(db_path)
        if d:
            os.makedirs(d, exist_ok=True)
        self.init_db()

    @contextmanager
    def get_connection(self):
        conn = None
        try:
            conn = sqlite3.connect(self.db_path, timeout=30, check_same_thread=False, isolation_level=None)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            yield conn
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass

    def execute_query(self, query, params=None, commit=False, fetch=False):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            if fetch:
                return cursor.fetchall()
            return None

    def init_db(self):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''CREATE TABLE IF NOT EXISTS users
                                  (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL,
                                   password TEXT NOT NULL, role TEXT NOT NULL, full_name TEXT,
                                   created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
                cursor.execute('''CREATE TABLE IF NOT EXISTS subscribers
                                  (id TEXT PRIMARY KEY, name TEXT NOT NULL, workplace TEXT,
                                   car_number TEXT, car_type TEXT, car_color TEXT, phone TEXT,
                                   subscription_type TEXT, subscription_start TEXT, subscription_end TEXT,
                                   payment_amount REAL, payment_status TEXT, status TEXT,
                                   spot_id TEXT, registration_date TEXT, assigned_date TEXT)''')
                cursor.execute('''CREATE TABLE IF NOT EXISTS spots
                                  (id TEXT PRIMARY KEY, floor INTEGER, level INTEGER, number INTEGER,
                                   is_occupied INTEGER DEFAULT 0, subscriber_id TEXT, status TEXT)''')
                cursor.execute('''CREATE TABLE IF NOT EXISTS visitors
                                  (id INTEGER PRIMARY KEY AUTOINCREMENT, ticket_number TEXT UNIQUE NOT NULL,
                                   entry_time TEXT NOT NULL, exit_time TEXT, vehicle_number TEXT,
                                   vehicle_type TEXT, status TEXT DEFAULT 'inside', amount REAL DEFAULT 0,
                                   payment_status TEXT DEFAULT 'pending', duration_minutes INTEGER DEFAULT 0,
                                   created_at TEXT DEFAULT CURRENT_TIMESTAMP, spot_id TEXT,
                                   movement_number INTEGER, phone TEXT)''')
                cursor.execute('''CREATE TABLE IF NOT EXISTS parking_settings (key TEXT PRIMARY KEY, value TEXT)''')
                cursor.execute('''CREATE TABLE IF NOT EXISTS financial_records
                                  (id TEXT PRIMARY KEY, subscriber_id TEXT, type TEXT, amount REAL,
                                   status TEXT, description TEXT, date TEXT, shift_id INTEGER)''')
                cursor.execute('''CREATE TABLE IF NOT EXISTS history
                                  (id INTEGER PRIMARY KEY AUTOINCREMENT, type TEXT, subscriber_id TEXT,
                                   spot_id TEXT, details TEXT, date TEXT, movement_number INTEGER)''')
                cursor.execute('''CREATE TABLE IF NOT EXISTS subscriber_attendance
                                  (id INTEGER PRIMARY KEY AUTOINCREMENT, subscriber_id TEXT NOT NULL,
                                   entry_time TEXT, exit_time TEXT, status TEXT DEFAULT 'outside',
                                   created_at TEXT DEFAULT CURRENT_TIMESTAMP, movement_number INTEGER)''')
                cursor.execute('''CREATE TABLE IF NOT EXISTS shifts
                                  (id INTEGER PRIMARY KEY AUTOINCREMENT, opened_by TEXT, opened_at TEXT,
                                   closed_by TEXT, closed_at TEXT, status TEXT DEFAULT 'open',
                                   total_revenue REAL DEFAULT 0, total_entries INTEGER DEFAULT 0,
                                   total_exits INTEGER DEFAULT 0, visitor_revenue REAL DEFAULT 0,
                                   subscriber_revenue REAL DEFAULT 0, details TEXT)''')
                # ⭐ جدول الجلسات
                cursor.execute('''CREATE TABLE IF NOT EXISTS subscriber_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    subscriber_id TEXT NOT NULL,
                    garage_id INTEGER NOT NULL,
                    device_id TEXT NOT NULL,
                    device_info TEXT,
                    session_token TEXT UNIQUE NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    expires_at TEXT NOT NULL,
                    last_seen_at TEXT,
                    is_active INTEGER DEFAULT 1,
                    revoked_at TEXT,
                    revoked_reason TEXT
                )''')
                # ⭐ جدول دفعات التطبيق
                cursor.execute('''CREATE TABLE IF NOT EXISTS app_payments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    subscriber_id TEXT NOT NULL,
                    garage_id INTEGER,
                    amount REAL DEFAULT 10,
                    method TEXT,
                    reference_number TEXT,
                    status TEXT DEFAULT 'pending',
                    notes TEXT,
                    confirmed_at TEXT,
                    rejected_at TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )''')

                # Indexes
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_visitors_ticket ON visitors(ticket_number)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_visitors_status ON visitors(status)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_subscribers_car ON subscribers(car_number)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_subscribers_phone ON subscribers(phone)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_subscribers_status ON subscribers(status)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_history_date ON history(date)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_attendance_status ON subscriber_attendance(status)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_sessions_token ON subscriber_sessions(session_token)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_sessions_subscriber ON subscriber_sessions(subscriber_id, is_active)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_sessions_device ON subscriber_sessions(device_id)')

                defaults = {'first_hour_price': '20', 'second_hour_price': '10', 'free_minutes': '10',
                            'printer_type': 'epson_tm', 'printer_port': 'USB001', 'paper_width': '80',
                            'last_movement_number': '0', 'last_visitor_ticket_number': '0',
                            'daily_max_charge': '250', 'auto_refresh_sec': '0',
                            'hour_grace_minutes': '10', 'system_expiry_date': '',
                            'garage_name': DEFAULT_GARAGE_NAME,
                            'app_fee': '10',
                            'app_trial_days': '3',
                            'instapay_number': INSTAPAY_NUMBER,
                            'vodafone_cash_number': '',
                            'trial_enabled': '1',              # ⭐ جديد — تشغيل/إيقاف التجربة
                            'garage_free_forever': '0',        # ⭐ جديد — الجراج معفى نهائياً
                            'garage_free_until': ''}           # ⭐ جديد — معفى حتى تاريخ
                for k, v in defaults.items():
                    cursor.execute('INSERT OR IGNORE INTO parking_settings (key, value) VALUES (?, ?)', (k, v))

                # Default users
                for uname, pw, role, name in [('superadmin', 'super123', 'super_admin', 'Super Admin - المطور'),
                                              ('admin', 'admin123', 'admin', 'مدير النظام'),
                                              ('manager', 'manager123', 'manager', 'مدير الجراج'),
                                              ('entry', 'entry123', 'entry', 'موظف دخول'),
                                              ('exit', 'exit123', 'exit', 'موظف خروج'),
                                              ('subscriber', 'sub123', 'subscriber', 'موظف المشتركين')]:
                    hashed = hashlib.sha256(pw.encode()).hexdigest()
                    cursor.execute('INSERT OR IGNORE INTO users (username, password, role, full_name) VALUES (?, ?, ?, ?)',
                                   (uname, hashed, role, name))

                # ⭐ Migration: Sync Support
                for table, col, typ in [
                    ('visitors', 'spot_id', 'TEXT'), ('visitors', 'movement_number', 'INTEGER'),
                    ('visitors', 'phone', 'TEXT'), ('history', 'movement_number', 'INTEGER'),
                    ('subscriber_attendance', 'movement_number', 'INTEGER'),
                    ('financial_records', 'shift_id', 'INTEGER'),
                    ('shifts', 'visitor_revenue', 'REAL DEFAULT 0'),
                    ('shifts', 'subscriber_revenue', 'REAL DEFAULT 0'),
                    ('subscribers', 'app_subscription_active', 'INTEGER DEFAULT 0'),
                    ('subscribers', 'app_subscription_end', 'TEXT'),
                    ('subscribers', 'garage_id', 'INTEGER DEFAULT 1'),
                    ('subscribers', 'app_service_disabled', 'INTEGER DEFAULT 0'),
                    ('subscribers', 'updated_at', 'TEXT'),      # ⭐ Sync
                    ('visitors', 'updated_at', 'TEXT'),          # ⭐ Sync
                    ('spots', 'updated_at', 'TEXT'),             # ⭐ Sync
                ]:
                    cursor.execute(f"PRAGMA table_info({table})")
                    cols = [c[1] for c in cursor.fetchall()]
                    if col not in cols:
                        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {col} {typ}")

                # ⭐ جدول سجل المزامنة
                cursor.execute('''CREATE TABLE IF NOT EXISTS sync_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    table_name TEXT NOT NULL,
                    record_id TEXT NOT NULL,
                    operation TEXT NOT NULL,
                    data TEXT,
                    timestamp TEXT NOT NULL,
                    device_id TEXT,
                    synced INTEGER DEFAULT 0
                )''')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_sync_synced ON sync_log(synced)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_sync_time ON sync_log(timestamp)')
                existing = self.execute_query("SELECT value FROM parking_settings WHERE key='garage_structure'", fetch=True)
                if not existing:
                    structure_serializable = {str(f): {str(l): v for l, v in levels.items()}
                                              for f, levels in DEFAULT_STRUCTURE.items()}
                    cursor.execute('INSERT OR IGNORE INTO parking_settings (key, value) VALUES (?, ?)',
                                   ('garage_structure', json.dumps(structure_serializable, ensure_ascii=False)))

                existing_fn = self.execute_query("SELECT value FROM parking_settings WHERE key='garage_floor_names'", fetch=True)
                if not existing_fn:
                    fn_serializable = {str(f): name for f, name in DEFAULT_FLOOR_NAMES.items()}
                    cursor.execute('INSERT OR IGNORE INTO parking_settings (key, value) VALUES (?, ?)',
                                   ('garage_floor_names', json.dumps(fn_serializable, ensure_ascii=False)))
        except Exception as e:
            app_log("error", f"فشل تهيئة قاعدة البيانات: {e}")

    # ============ إعدادات الجراج ============
    def get_garage_name(self):
        try:
            result = self.execute_query("SELECT value FROM parking_settings WHERE key='garage_name'", fetch=True)
            if result and result[0]['value']:
                return result[0]['value']
        except Exception:
            pass
        return DEFAULT_GARAGE_NAME

    def set_garage_name(self, name):
        try:
            self.execute_query("INSERT OR REPLACE INTO parking_settings (key, value) VALUES ('garage_name', ?)",
                               (name or DEFAULT_GARAGE_NAME,), commit=True)
            return True
        except Exception:
            return False

    def get_garage_structure(self):
        try:
            result = self.execute_query("SELECT value FROM parking_settings WHERE key='garage_structure'", fetch=True)
            if result and result[0]['value']:
                raw = json.loads(result[0]['value'])
                structure = {}
                for f_str, levels in raw.items():
                    f = int(f_str)
                    structure[f] = {}
                    for l_str, data in levels.items():
                        l = int(l_str)
                        structure[f][l] = {
                            'spots': int(data.get('spots', 0)),
                            'name': data.get('name', f'مستوى {l}'),
                            'start': int(data.get('start', 1))
                        }
                return structure
        except Exception as e:
            app_log("error", f"فشل تحميل هيكل الجراج: {e}")
        return None

    def set_garage_structure(self, structure):
        try:
            serializable = {str(f): {str(l): v for l, v in levels.items()}
                            for f, levels in structure.items()}
            self.execute_query("INSERT OR REPLACE INTO parking_settings (key, value) VALUES ('garage_structure', ?)",
                               (json.dumps(serializable, ensure_ascii=False),), commit=True)
            return True
        except Exception as e:
            app_log("error", f"فشل حفظ هيكل الجراج: {e}")
            return False

    def get_floor_names(self):
        try:
            result = self.execute_query("SELECT value FROM parking_settings WHERE key='garage_floor_names'", fetch=True)
            if result and result[0]['value']:
                raw = json.loads(result[0]['value'])
                return {int(k): v for k, v in raw.items()}
        except Exception:
            pass
        return dict(DEFAULT_FLOOR_NAMES)

    def set_floor_names(self, names):
        try:
            serializable = {str(k): v for k, v in names.items()}
            self.execute_query("INSERT OR REPLACE INTO parking_settings (key, value) VALUES ('garage_floor_names', ?)",
                               (json.dumps(serializable, ensure_ascii=False),), commit=True)
            return True
        except Exception:
            return False

    # ============ المستخدمين ============
    def get_user(self, username, password):
        try:
            hashed = hashlib.sha256(password.encode()).hexdigest()
            result = self.execute_query('SELECT id, username, password, role, full_name FROM users WHERE username=? AND password=?',
                                        (username, hashed), fetch=True)
            if result and len(result) > 0:
                return dict(result[0])
            return None
        except Exception as e:
            app_log("error", f"خطأ في get_user: {e}")
            return None

    def get_all_users(self):
        try:
            return self.execute_query('SELECT id, username, role, full_name, created_at FROM users', fetch=True) or []
        except Exception:
            return []

    def add_user(self, username, password, role, full_name):
        try:
            hashed = hashlib.sha256(password.encode()).hexdigest()
            self.execute_query('INSERT INTO users (username, password, role, full_name) VALUES (?, ?, ?, ?)',
                               (username, hashed, role, full_name), commit=True)
            return True
        except Exception:
            return False

    def delete_user(self, user_id):
        try:
            self.execute_query('DELETE FROM users WHERE id=?', (user_id,), commit=True)
            return True
        except Exception:
            return False

    def update_user(self, user_id, **kwargs):
        try:
            updates, params = [], []
            if kwargs.get('username'):
                updates.append("username=?")
                params.append(kwargs['username'])
            if kwargs.get('full_name') is not None:
                updates.append("full_name=?")
                params.append(kwargs['full_name'])
            if kwargs.get('password'):
                updates.append("password=?")
                params.append(hashlib.sha256(kwargs['password'].encode()).hexdigest())
            if kwargs.get('role'):
                updates.append("role=?")
                params.append(kwargs['role'])
            if not updates:
                return False
            params.append(user_id)
            self.execute_query(f"UPDATE users SET {', '.join(updates)} WHERE id=?", params, commit=True)
            return True
        except Exception:
            return False

    def reset_all_passwords(self):
        try:
            users = [
                ('superadmin', 'super123', 'super_admin', 'Super Admin - المطور'),
                ('admin', 'admin123', 'admin', 'مدير النظام'),
                ('manager', 'manager123', 'manager', 'مدير الجراج'),
                ('entry', 'entry123', 'entry', 'موظف دخول'),
                ('exit', 'exit123', 'exit', 'موظف خروج'),
                ('subscriber', 'sub123', 'subscriber', 'موظف المشتركين'),
            ]
            results = []
            for uname, pw, role, name in users:
                hashed = hashlib.sha256(pw.encode()).hexdigest()
                existing = self.execute_query('SELECT id FROM users WHERE username=?', (uname,), fetch=True)
                if existing:
                    self.execute_query('UPDATE users SET password=?, role=?, full_name=? WHERE username=?',
                                       (hashed, role, name, uname), commit=True)
                    results.append(f"✅ تم تحديث: {uname} | كلمة المرور: {pw}")
                else:
                    self.execute_query('INSERT INTO users (username, password, role, full_name) VALUES (?, ?, ?, ?)',
                                       (uname, hashed, role, name), commit=True)
                    results.append(f"➕ تم إضافة: {uname} | كلمة المرور: {pw}")
            return results
        except Exception as e:
            return [f"❌ خطأ: {e}"]

    def open_shift(self, username):
        try:
            if self.get_current_shift():
                return False
            self.execute_query('INSERT INTO shifts (opened_by, opened_at, status) VALUES (?, ?, ?)',
                               (username, datetime.now().isoformat(), 'open'), commit=True)
            return True
        except Exception:
            return False

    def close_shift(self, username, total_revenue, total_entries, total_exits, visitor_revenue, subscriber_revenue, details):
        try:
            result = self.execute_query("SELECT id FROM shifts WHERE status='open' ORDER BY id DESC LIMIT 1", fetch=True)
            if not result:
                return False
            shift_id = result[0]['id']
            self.execute_query(
                "UPDATE shifts SET closed_by=?, closed_at=?, status='closed', total_revenue=?, total_entries=?, total_exits=?, visitor_revenue=?, subscriber_revenue=?, details=? WHERE id=?",
                (username, datetime.now().isoformat(), total_revenue, total_entries, total_exits,
                 visitor_revenue, subscriber_revenue, details, shift_id), commit=True)
            return True
        except Exception:
            return False

    def get_current_shift(self):
        try:
            result = self.execute_query("SELECT * FROM shifts WHERE status='open' ORDER BY id DESC LIMIT 1", fetch=True)
            return dict(result[0]) if result else None
        except Exception:
            return None

    def get_shift_history(self):
        try:
            result = self.execute_query('SELECT * FROM shifts ORDER BY id DESC', fetch=True)
            return [dict(r) for r in result] if result else []
        except Exception:
            return []

    def clear_data_range(self, date_from, date_to, clear_visitors=True, clear_financial=True,
                         clear_history=True, clear_shifts=False, clear_attendance=True):
        try:
            results = {'visitors': 0, 'financial': 0, 'history': 0, 'shifts': 0, 'attendance': 0}
            with self.get_connection() as conn:
                cursor = conn.cursor()
                if clear_visitors:
                    cursor.execute('DELETE FROM visitors WHERE date(entry_time) >= ? AND date(entry_time) <= ?', (date_from, date_to))
                    results['visitors'] = cursor.rowcount
                if clear_financial:
                    cursor.execute('DELETE FROM financial_records WHERE date(date) >= ? AND date(date) <= ?', (date_from, date_to))
                    results['financial'] = cursor.rowcount
                if clear_history:
                    cursor.execute('DELETE FROM history WHERE date(date) >= ? AND date(date) <= ?', (date_from, date_to))
                    results['history'] = cursor.rowcount
                if clear_shifts:
                    cursor.execute("DELETE FROM shifts WHERE date(opened_at) >= ? AND date(opened_at) <= ? AND status='closed'", (date_from, date_to))
                    results['shifts'] = cursor.rowcount
                if clear_attendance:
                    cursor.execute('DELETE FROM subscriber_attendance WHERE date(entry_time) >= ? AND date(entry_time) <= ?', (date_from, date_to))
                    results['attendance'] = cursor.rowcount
            clear_all_caches()
            return results
        except Exception as e:
            app_log("error", f"خطأ في مسح البيانات: {e}")
            return None


def get_parking_settings(db):
    settings = {}
    result = db.execute_query('SELECT key, value FROM parking_settings', fetch=True)
    if result:
        for row in result:
            settings[row['key']] = row['value']
    return settings


def update_parking_settings(db, settings):
    try:
        for k, v in settings.items():
            db.execute_query('UPDATE parking_settings SET value=? WHERE key=?', (v, k), commit=True)
        return True
    except Exception:
        return False
# ===================================================================
# ⭐⭐⭐ Sync Support ⭐⭐⭐
# ===================================================================
SYNC_MODE = os.environ.get('SYNC_MODE', 'local')
DEVICE_ID = os.environ.get('DEVICE_ID', 'garage-pc-1')


def log_change(db, table, record_id, operation, data=None):
    """يسجل تغيير في sync_log للمزامنة"""
    try:
        db.execute_query(
            "INSERT INTO sync_log (table_name, record_id, operation, data, timestamp, device_id) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (table, str(record_id), operation,
             json.dumps(data, ensure_ascii=False, default=str) if data else None,
             datetime.now().isoformat(), DEVICE_ID),
            commit=True
        )
    except Exception as e:
        app_log("error", f"log_change: {e}")
# ===================================================================
# ⭐⭐⭐ Sync Support ⭐⭐⭐
# ===================================================================
SYNC_MODE = os.environ.get('SYNC_MODE', 'local')  # 'local' أو 'cloud'
DEVICE_ID = os.environ.get('DEVICE_ID', 'garage-pc-1')


def log_change(db, table, record_id, operation, data=None):
    """يسجل تغيير في sync_log للمزامنة"""
    try:
        db.execute_query(
            "INSERT INTO sync_log (table_name, record_id, operation, data, timestamp, device_id) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (table, str(record_id), operation,
             json.dumps(data, ensure_ascii=False, default=str) if data else None,
             datetime.now().isoformat(), DEVICE_ID),
            commit=True
        )
    except Exception as e:
        app_log("error", f"log_change: {e}")
# ===================================================================
# ⭐⭐⭐ VisitorManager ⭐⭐⭐
# ===================================================================
class VisitorManager:
    def __init__(self, db):
        self.db = db

    def generate_ticket(self):
        for attempt in range(5):
            try:
                with self.db.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("BEGIN IMMEDIATE")
                    cursor.execute("SELECT value FROM parking_settings WHERE key='last_visitor_ticket_number'")
                    row = cursor.fetchone()
                    new = int(row[0]) + 1 if row else 1
                    cursor.execute("UPDATE parking_settings SET value=? WHERE key='last_visitor_ticket_number'", (str(new),))
                    conn.commit()
                    return f"VIS-{new:06d}"
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e) and attempt < 4:
                    time.sleep(0.2)
                    continue
                raise
        return None

    def entry_visitor(self, vehicle_number, vehicle_type='سيارة', spot_id=None, phone=None):
        try:
            for attempt in range(3):
                ticket = self.generate_ticket()
                if not ticket:
                    return None, None
                now = datetime.now().isoformat()
                mv = get_next_movement_number(self.db)
                try:
                    self.db.execute_query(
                        'INSERT INTO visitors (ticket_number, entry_time, vehicle_number, vehicle_type, status, created_at, spot_id, movement_number, phone) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
                        (ticket, now, vehicle_number, vehicle_type, 'inside', now, spot_id, mv, phone), commit=True)
                    break
                except sqlite3.IntegrityError:
                    if attempt < 2:
                        continue
                    raise
            if spot_id:
                self.db.execute_query("UPDATE spots SET is_occupied=1, status='occupied' WHERE id=?", (spot_id,), commit=True)
            self.db.execute_query(
                'INSERT INTO history (type, subscriber_id, spot_id, details, date, movement_number) VALUES (?, ?, ?, ?, ?, ?)',
                ('visitor_entry', None, spot_id, f"دخول زائر - {ticket} - {phone or 'بدون'}", now, mv), commit=True)
            clear_all_caches()
            log_change(self.db, 'visitors', ticket, 'insert', {
                'ticket_number': ticket,
                'entry_time': now,
                'vehicle_number': vehicle_number,
                'vehicle_type': vehicle_type,
                'status': 'inside',
                'spot_id': spot_id,
                'movement_number': mv,
                'phone': phone,
                'updated_at': now,
            })
            if spot_id:
                log_change(self.db, 'spots', spot_id, 'update', {
                    'id': spot_id, 'is_occupied': 1,
                    'status': 'occupied', 'updated_at': now
                })
            return ticket, mv
        except Exception as e:
            app_log("error", f"فشل تسجيل دخول زائر: {e}")
            return None, None
    def calculate_amount(self, duration, settings):
        first = float(settings.get('first_hour_price', 20))
        second = float(settings.get('second_hour_price', 10))
        free = int(settings.get('free_minutes', 10))
        grace = int(settings.get('hour_grace_minutes', 10))
        daily_max = float(settings.get('daily_max_charge', 250))

        if duration <= 0:
            duration = 1

        if duration >= 1440:
            days = math.ceil(duration / 1440)
            return round(days * daily_max, 2)

        if duration <= free:
            return 0.0

        effective = duration - free
        full_hours = effective // 60
        remainder = effective - (full_hours * 60)
        if remainder <= grace:
            hours = max(1, full_hours)
        else:
            hours = full_hours + 1
        if hours < 1:
            hours = 1

        if hours == 1:
            amount = first
        else:
            amount = first + (hours - 1) * second

        if amount > daily_max:
            amount = daily_max

        return round(amount, 2)

    def exit_visitor(self, ticket):
        try:
            result = self.db.execute_query("SELECT * FROM visitors WHERE ticket_number=? AND status='inside'", (ticket,), fetch=True)
            if not result:
                return None
            row = dict(result[0])
            entry_time = datetime.fromisoformat(row['entry_time'])
            exit_time = datetime.now()
            duration = max(1, int((exit_time - entry_time).total_seconds() / 60))
            settings = {}
            for s in self.db.execute_query('SELECT key, value FROM parking_settings', fetch=True):
                settings[s['key']] = s['value']
            amount = self.calculate_amount(duration, settings)
            free_min = int(settings.get('free_minutes', 10))
            is_free = duration <= free_min
            now = exit_time.isoformat()
            mv = get_next_movement_number(self.db)

            if is_free:
                self.db.execute_query(
                    "UPDATE visitors SET exit_time=?, status='cancelled', amount=0, payment_status='free', duration_minutes=? WHERE ticket_number=?",
                    (now, duration, ticket), commit=True)
            else:
                self.db.execute_query(
                    "UPDATE visitors SET exit_time=?, status='outside', amount=?, payment_status='paid', duration_minutes=? WHERE ticket_number=?",
                    (now, amount, duration, ticket), commit=True)

            if row['spot_id']:
                spot_info = self.db.execute_query('SELECT subscriber_id FROM spots WHERE id=?', (row['spot_id'],), fetch=True)
                owner_sub = spot_info[0]['subscriber_id'] if spot_info else None
                if owner_sub:
                    self.db.execute_query("UPDATE spots SET is_occupied=0, status='subscriber_out' WHERE id=?", (row['spot_id'],), commit=True)
                else:
                    self.db.execute_query("UPDATE spots SET is_occupied=0, subscriber_id=NULL, status='available' WHERE id=?", (row['spot_id'],), commit=True)

            details = f"خروج {'مجاني' if is_free else 'زائر'} - {ticket} - {amount} جنيه"
            self.db.execute_query(
                'INSERT INTO history (type, subscriber_id, spot_id, details, date, movement_number) VALUES (?, ?, ?, ?, ?, ?)',
                ('visitor_exit', None, row['spot_id'], details, now, mv), commit=True)
            if amount > 0:
                shift = self.db.execute_query("SELECT id FROM shifts WHERE status='open' ORDER BY id DESC LIMIT 1", fetch=True)
                shift_id = shift[0]['id'] if shift else None
                self.db.execute_query(
                    'INSERT INTO financial_records (id, subscriber_id, type, amount, status, description, date, shift_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                    (f"FIN_{datetime.now().strftime('%Y%m%d%H%M%S%f')}", None, 'زائر', amount, 'مدفوع',
                     f"رسوم زائر - {ticket}", now, shift_id), commit=True)
            clear_all_caches()
            log_change(self.db, 'visitors', ticket, 'update', {
                'ticket_number': ticket,
                'exit_time': now,
                'status': 'cancelled' if is_free else 'outside',
                'amount': amount,
                'payment_status': 'free' if is_free else 'paid',
                'duration_minutes': duration,
                'updated_at': now,
            })
            if row['spot_id']:
                spot_info = self.db.execute_query('SELECT subscriber_id FROM spots WHERE id=?', (row['spot_id'],), fetch=True)
                owner_sub = spot_info[0]['subscriber_id'] if spot_info else None
                log_change(self.db, 'spots', row['spot_id'], 'update', {
                    'id': row['spot_id'],
                    'is_occupied': 0,
                    'subscriber_id': owner_sub if owner_sub else None,
                    'status': 'subscriber_out' if owner_sub else 'available',
                    'updated_at': now,
                })
            return {'ticket_number': ticket, 'entry_time': entry_time, 'exit_time': exit_time,
                    'duration': duration, 'amount': amount, 'vehicle_number': row['vehicle_number'],
                    'spot_id': row['spot_id'], 'movement_number': mv, 'phone': row.get('phone', ''),
                    'is_free_exit': is_free, 'free_minutes': free_min}
        except Exception as e:
            app_log("error", f"فشل خروج زائر: {e}")
            return None
    def get_visitor_by_ticket(self, ticket):
        result = self.db.execute_query('SELECT * FROM visitors WHERE ticket_number=?', (ticket,), fetch=True)
        return dict(result[0]) if result else None

    def get_visitor_by_spot(self, spot_id):
        result = self.db.execute_query("SELECT * FROM visitors WHERE spot_id=? AND status='inside'", (spot_id,), fetch=True)
        return dict(result[0]) if result else None

    def get_active_visitors(self):
        return get_cached_active_visitors(self.db.db_path)

    def search_visitors(self, query):
        q = f'%{query}%'
        result = self.db.execute_query(
            "SELECT * FROM visitors WHERE status='inside' AND (ticket_number LIKE ? OR vehicle_number LIKE ? OR phone LIKE ?)",
            (q, q, q), fetch=True)
        return [dict(r) for r in result] if result else []

    def get_visitors_summary(self):
        try:
            with self.db.get_connection() as conn:
                cur = conn.cursor()
                cur.execute('''SELECT
                    (SELECT COUNT(*) FROM visitors WHERE status='inside') as active,
                    (SELECT COALESCE(SUM(amount),0) FROM visitors WHERE status='outside') as revenue,
                    (SELECT COUNT(*) FROM visitors WHERE date(entry_time)=date('now','localtime')) as today''')
                row = cur.fetchone()
                return {'active': row['active'], 'total_revenue': row['revenue'], 'today_visitors': row['today']}
        except Exception:
            return {'active': 0, 'total_revenue': 0, 'today_visitors': 0}

    def get_visitors_financial_report(self):
        try:
            result = self.db.execute_query('''SELECT ticket_number, entry_time, exit_time, vehicle_number,
                                                     duration_minutes, amount, payment_status, phone,
                                                     strftime('%Y-%m', entry_time) as month
                                              FROM visitors WHERE status='outside' AND amount > 0
                                              ORDER BY exit_time DESC''', fetch=True)
            return [dict(row) for row in result] if result else []
        except Exception:
            return []


# ===================================================================
# ⭐⭐⭐ GarageManager ⭐⭐⭐
# ===================================================================
class GarageManager:
    def __init__(self, db):
        self.db = db
        self.garage_name = db.get_garage_name()
        self.floor_names = db.get_floor_names()
        structure = db.get_garage_structure()
        if not structure:
            structure = copy.deepcopy(DEFAULT_STRUCTURE)
            db.set_garage_structure(structure)
        self.structure = structure
        self.subscription_plans = {'شهري': 30, 'ربع سنوي': 90, 'نصف سنوي': 180, 'سنوي': 365}
        update_floor_names_cache(self.floor_names)
        update_garage_name_cache(self.garage_name)
        self.init_spots()

    def reload_config(self):
        self.garage_name = self.db.get_garage_name()
        self.floor_names = self.db.get_floor_names()
        structure = self.db.get_garage_structure()
        if structure:
            self.structure = structure
        update_floor_names_cache(self.floor_names)
        update_garage_name_cache(self.garage_name)

    def get_total_spots_count(self):
        total = 0
        for f in self.structure:
            for l in self.structure[f]:
                total += self.structure[f][l]['spots']
        return total

    def init_spots(self):
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                for floor in self.structure:
                    for level in self.structure[floor]:
                        data = self.structure[floor][level]
                        for i in range(data['spots']):
                            num = data['start'] + i
                            cursor.execute('INSERT OR IGNORE INTO spots (id, floor, level, number, status) VALUES (?, ?, ?, ?, ?)',
                                           (f"{floor}_{level}_{num}", floor, level, num, 'available'))
        except Exception as e:
            app_log("error", f"خطأ في init_spots: {e}")

    def save_and_apply_structure(self, new_structure, new_floor_names):
        counter = 1
        for floor in sorted(new_structure.keys()):
            for level in sorted(new_structure[floor].keys()):
                new_structure[floor][level]['start'] = counter
                counter += new_structure[floor][level]['spots']

        new_spot_ids = set()
        for floor in new_structure:
            for level in new_structure[floor]:
                data = new_structure[floor][level]
                for i in range(data['spots']):
                    num = data['start'] + i
                    new_spot_ids.add(f"{floor}_{level}_{num}")

        added = 0
        deleted = 0
        preserved = 0

        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute("SELECT id, is_occupied FROM spots")
                existing = {row['id']: row['is_occupied'] for row in cursor.fetchall()}

                for sid, occupied in existing.items():
                    if sid not in new_spot_ids:
                        if occupied:
                            preserved += 1
                        else:
                            cursor.execute("DELETE FROM spots WHERE id=?", (sid,))
                            deleted += 1

                for floor in new_structure:
                    for level in new_structure[floor]:
                        data = new_structure[floor][level]
                        for i in range(data['spots']):
                            num = data['start'] + i
                            sid = f"{floor}_{level}_{num}"
                            if sid not in existing:
                                cursor.execute('INSERT INTO spots (id, floor, level, number, status) VALUES (?, ?, ?, ?, ?)',
                                               (sid, floor, level, num, 'available'))
                                added += 1

            self.db.set_garage_structure(new_structure)
            self.db.set_floor_names(new_floor_names)

            self.structure = new_structure
            self.floor_names = new_floor_names
            update_floor_names_cache(new_floor_names)

            clear_all_caches()
            return True, added, deleted, preserved
        except Exception as e:
            app_log("error", f"فشل حفظ الهيكل: {e}")
            return False, 0, 0, 0

    def ensure_correct_spot_count(self):
        try:
            result = self.db.execute_query('SELECT COUNT(*) FROM spots', fetch=True)
            expected = self.get_total_spots_count()
            if (result[0][0] if result else 0) != expected:
                self.init_spots()
        except Exception:
            pass

    def get_spot_info(self, spot_id):
        spots_map = get_all_spots_map(self.db.db_path)
        return spots_map.get(spot_id)

    def get_spot_id(self, floor, level, number):
        return f"{floor}_{level}_{number}"

    def is_spot_available_for_visitor(self, info, inside_subs):
        if not info:
            return False
        if info['status'] == 'available':
            return True
        if info['status'] == 'subscriber_out':
            return True
        sub_id = info.get('subscriber_id')
        if sub_id and sub_id not in inside_subs:
            return True
        return False

    def get_subscriber(self, sid):
        result = self.db.execute_query('SELECT * FROM subscribers WHERE id=?', (sid,), fetch=True)
        if result:
            row = result[0]
            return {'id': row[0], 'name': row[1], 'workplace': row[2], 'car_number': row[3],
                    'car_type': row[4], 'car_color': row[5], 'phone': row[6],
                    'subscription_type': row[7], 'subscription_start': row[8], 'subscription_end': row[9],
                    'payment_amount': row[10], 'payment_status': row[11], 'status': row[12],
                    'spot_id': row[13], 'registration_date': row[14], 'assigned_date': row[15]}
        return None

    def get_subscriber_by_car_number(self, car):
        result = self.db.execute_query('SELECT * FROM subscribers WHERE car_number=?', (car,), fetch=True)
        return dict(result[0]) if result else None

    def get_subscriber_by_id_or_car(self, identifier):
        if identifier.startswith('SUB_') or identifier.startswith('sub_'):
            return self.get_subscriber(identifier)
        return self.get_subscriber_by_car_number(identifier)

    def search_subscribers(self, query):
        q = f'%{query}%'
        result = self.db.execute_query(
            'SELECT * FROM subscribers WHERE name LIKE ? OR car_number LIKE ? OR phone LIKE ? OR id LIKE ? OR car_type LIKE ?',
            (q, q, q, q, q), fetch=True)
        if result:
            return [{'id': r[0], 'name': r[1], 'workplace': r[2], 'car_number': r[3],
                     'car_type': r[4], 'car_color': r[5], 'phone': r[6],
                     'subscription_type': r[7], 'subscription_start': r[8], 'subscription_end': r[9],
                     'payment_amount': r[10], 'payment_status': r[11], 'status': r[12],
                     'spot_id': r[13], 'registration_date': r[14], 'assigned_date': r[15]} for r in result]
        return []

    def get_floor_summary(self, floor=None):
        rows = get_cached_floor_summary(self.db.db_path)
        summary = {}
        for row in rows:
            f = row['floor']
            level = row['level']
            if floor is not None and f != floor:
                continue
            if f in self.structure and level in self.structure[f]:
                name = self.structure[f][level]['name']
                if f not in summary:
                    summary[f] = {}
                total = row['total']
                occ = row['occ']
                summary[f][name] = {'total': total, 'occupied': occ, 'available': total - occ,
                                    'occupancy_rate': (occ / total * 100) if total > 0 else 0}
        return summary

    def get_all_subscribers(self):
        try:
            return self.db.execute_query('SELECT * FROM subscribers', fetch=True) or []
        except Exception:
            return []

    def add_subscriber(self, data):
        try:
            if self.db.execute_query('SELECT id FROM subscribers WHERE car_number=?', (data['car_number'],), fetch=True):
                return None
            sid = f"SUB_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
            now = datetime.now().isoformat()
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''INSERT INTO subscribers (id, name, workplace, car_number, car_type, car_color, phone,
                                                           subscription_type, subscription_start, subscription_end,
                                                           payment_amount, payment_status, status, registration_date)
                                  VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                               (sid, data['name'], data.get('workplace', ''), data['car_number'],
                                data.get('car_type', ''), data.get('car_color', ''), data['phone'],
                                data['subscription_type'], data.get('subscription_start', now),
                                data.get('subscription_end', (datetime.now() + timedelta(days=30)).isoformat()),
                                data.get('payment_amount', 0), 'paid', 'active', now))
                shift = self.db.execute_query("SELECT id FROM shifts WHERE status='open' ORDER BY id DESC LIMIT 1", fetch=True)
                shift_id = shift[0]['id'] if shift else None
                if data.get('payment_amount', 0) > 0:
                    cursor.execute('INSERT INTO financial_records (id, subscriber_id, type, amount, status, description, date, shift_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                                   (f"FIN_{datetime.now().strftime('%Y%m%d%H%M%S%f')}", sid, 'اشتراك جديد',
                                    data['payment_amount'], 'مدفوع', f"اشتراك {data['name']}", now, shift_id))
                cursor.execute('INSERT INTO history (type, subscriber_id, spot_id, details, date) VALUES (?, ?, ?, ?, ?)',
                               ('add_subscriber', sid, None, f"إضافة مشترك: {data['name']}", now))
            clear_all_caches()
            log_change(self.db, 'subscribers', sid, 'insert', {
                'id': sid, 'name': data['name'], 'workplace': data.get('workplace', ''),
                'car_number': data['car_number'], 'car_type': data.get('car_type', ''),
                'car_color': data.get('car_color', ''), 'phone': data['phone'],
                'subscription_type': data['subscription_type'],
                'subscription_start': data.get('subscription_start', now),
                'subscription_end': data.get('subscription_end'),
                'status': 'active', 'registration_date': now,
                'updated_at': now,
            })
            return sid
        except Exception as e:
            app_log("error", f"فشل إضافة مشترك: {e}")
            return None

    def assign_spot(self, spot_id, sid):
        try:
            spot = self.get_spot_info(spot_id)
            if spot and spot['status'] in ('occupied', 'subscriber_out'):
                return False
            sub = self.get_subscriber(sid)
            if sub and sub.get('spot_id'):
                return False
            now_ts = datetime.now().isoformat()
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE spots SET is_occupied=1, subscriber_id=?, status='occupied' WHERE id=?",
                               (sid, spot_id))
                cursor.execute('UPDATE subscribers SET spot_id=?, assigned_date=? WHERE id=?',
                               (spot_id, now_ts, sid))
                cursor.execute(
                    'INSERT INTO history (type, subscriber_id, spot_id, details, date) VALUES (?, ?, ?, ?, ?)',
                    ('assign_spot', sid, spot_id, f"تخصيص مكان - {get_spot_location(spot_id)}", now_ts))
            clear_all_caches()
            log_change(self.db, 'subscribers', sid, 'update', {
                'id': sid, 'spot_id': spot_id, 'assigned_date': now_ts, 'updated_at': now_ts
            })
            log_change(self.db, 'spots', spot_id, 'update', {
                'id': spot_id, 'subscriber_id': sid, 'is_occupied': 1,
                'status': 'occupied', 'updated_at': now_ts
            })
            return True
        except Exception:
            return False

    def unassign_spot(self, sid):
        try:
            sub = self.get_subscriber(sid)
            if not sub or not sub.get('spot_id'):
                return False
            spot_id = sub['spot_id']
            now_ts = datetime.now().isoformat()
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE spots SET is_occupied=0, subscriber_id=NULL, status='available' WHERE id=?",
                               (spot_id,))
                cursor.execute('UPDATE subscribers SET spot_id=NULL, assigned_date=NULL WHERE id=?', (sid,))
                cursor.execute(
                    'INSERT INTO history (type, subscriber_id, spot_id, details, date) VALUES (?, ?, ?, ?, ?)',
                    ('unassign_spot', sid, spot_id, f"إلغاء تخصيص مكان {get_spot_location(spot_id)}", now_ts))
            clear_all_caches()
            log_change(self.db, 'subscribers', sid, 'update', {
                'id': sid, 'spot_id': None, 'assigned_date': None, 'updated_at': now_ts
            })
            log_change(self.db, 'spots', spot_id, 'update', {
                'id': spot_id, 'subscriber_id': None, 'is_occupied': 0,
                'status': 'available', 'updated_at': now_ts
            })
            return True
        except Exception:
            return False
    def change_spot(self, sid, new_spot_id):
        try:
            sub = self.get_subscriber(sid)
            if not sub:
                return False
            new_spot = self.get_spot_info(new_spot_id)
            if not new_spot or new_spot['status'] not in ('available',):
                return False
            old_spot_id = sub.get('spot_id')
            now_ts = datetime.now().isoformat()
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                if old_spot_id:
                    cursor.execute("UPDATE spots SET is_occupied=0, subscriber_id=NULL, status='available' WHERE id=?", (old_spot_id,))
                cursor.execute("UPDATE spots SET is_occupied=1, subscriber_id=?, status='occupied' WHERE id=?", (sid, new_spot_id))
                cursor.execute('UPDATE subscribers SET spot_id=?, assigned_date=? WHERE id=?',
                               (new_spot_id, now_ts, sid))
                cursor.execute('INSERT INTO history (type, subscriber_id, spot_id, details, date) VALUES (?, ?, ?, ?, ?)',
                               ('change_spot', sid, new_spot_id,
                                f"تغيير المكان إلى {get_spot_location(new_spot_id)}", now_ts))
            clear_all_caches()
            log_change(self.db, 'subscribers', sid, 'update', {
                'id': sid, 'spot_id': new_spot_id, 'assigned_date': now_ts, 'updated_at': now_ts
            })
            if old_spot_id:
                log_change(self.db, 'spots', old_spot_id, 'update', {
                    'id': old_spot_id, 'subscriber_id': None, 'is_occupied': 0,
                    'status': 'available', 'updated_at': now_ts
                })
            log_change(self.db, 'spots', new_spot_id, 'update', {
                'id': new_spot_id, 'subscriber_id': sid, 'is_occupied': 1,
                'status': 'occupied', 'updated_at': now_ts
            })
            return True
        except Exception:
            return False
    def renew_subscription(self, sid, stype, fee, start=None, end=None):
        try:
            sub = self.get_subscriber(sid)
            if not sub:
                return False
            if not start:
                start = datetime.now().isoformat()
            if not end:
                days = self.subscription_plans.get(stype, 30)
                end = (datetime.now() + timedelta(days=days)).isoformat()
            now_ts = datetime.now().isoformat()
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE subscribers SET subscription_type=?, subscription_start=?, subscription_end=?, payment_amount=?, status='active' WHERE id=?",
                               (stype, start, end, fee, sid))
                shift = self.db.execute_query("SELECT id FROM shifts WHERE status='open' ORDER BY id DESC LIMIT 1", fetch=True)
                shift_id = shift[0]['id'] if shift else None
                if fee and fee > 0:
                    cursor.execute('INSERT INTO financial_records (id, subscriber_id, type, amount, status, description, date, shift_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                                   (f"FIN_{datetime.now().strftime('%Y%m%d%H%M%S%f')}", sid, f'تجديد {stype}',
                                    fee, 'مدفوع', f'تجديد اشتراك {sub.get("name")}', now_ts, shift_id))
                cursor.execute('INSERT INTO history (type, subscriber_id, spot_id, details, date) VALUES (?, ?, ?, ?, ?)',
                               ('renew_subscription', sid, None, f"تجديد: {sub.get('name')}", now_ts))
            clear_all_caches()
            log_change(self.db, 'subscribers', sid, 'update', {
                'id': sid, 'subscription_type': stype, 'subscription_start': start,
                'subscription_end': end, 'payment_amount': fee, 'status': 'active',
                'updated_at': now_ts
            })
            return True
        except Exception:
            return False
    def update_subscriber(self, sid, data):
        try:
            if self.db.execute_query('SELECT id FROM subscribers WHERE car_number=? AND id!=?',
                                     (data['car_number'], sid), fetch=True):
                return False
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''UPDATE subscribers
                                  SET name=?, workplace=?, car_number=?, car_type=?, car_color=?, phone=?,
                                      subscription_type=?, subscription_start=?, subscription_end=?,
                                      payment_amount=?, status=?
                                  WHERE id = ?''',
                               (data['name'], data.get('workplace', ''), data['car_number'], data.get('car_type', ''),
                                data.get('car_color', ''), data['phone'], data['subscription_type'],
                                data['subscription_start'], data['subscription_end'], data['payment_amount'],
                                data.get('status', 'active'), sid))
                cursor.execute(
                    'INSERT INTO history (type, subscriber_id, spot_id, details, date) VALUES (?, ?, ?, ?, ?)',
                    ('update_subscriber', sid, None, f"تحديث: {data['name']}", datetime.now().isoformat()))
            clear_all_caches()
            log_change(self.db, 'subscribers', sid, 'update', {
                'id': sid,
                'name': data['name'],
                'workplace': data.get('workplace', ''),
                'car_number': data['car_number'],
                'car_type': data.get('car_type', ''),
                'car_color': data.get('car_color', ''),
                'phone': data['phone'],
                'subscription_type': data['subscription_type'],
                'subscription_start': data['subscription_start'],
                'subscription_end': data['subscription_end'],
                'payment_amount': data['payment_amount'],
                'status': data.get('status', 'active'),
                'updated_at': datetime.now().isoformat(),
            })
            return True
        except Exception:
            return False

    def delete_subscriber(self, sid):
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT name, spot_id FROM subscribers WHERE id=?', (sid,))
                r = cursor.fetchone()
                if r:
                    name, spot_id = r[0], r[1]
                    if spot_id:
                        cursor.execute(
                            "UPDATE spots SET is_occupied=0, subscriber_id=NULL, status='available' WHERE id=?",
                            (spot_id,))
                    cursor.execute('DELETE FROM subscribers WHERE id=?', (sid,))
                    cursor.execute(
                        'INSERT INTO history (type, subscriber_id, spot_id, details, date) VALUES (?, ?, ?, ?, ?)',
                        ('delete_subscriber', sid, None, f"حذف: {name}", datetime.now().isoformat()))
            clear_all_caches()
            log_change(self.db, 'subscribers', sid, 'delete', None)
            return True
        except Exception:
            return False
    def get_expiring_subscribers(self, days=7):
        return get_cached_expiring_subscribers(self.db.db_path, days)

    def get_expired_subscribers(self):
        return get_cached_expired_subscribers(self.db.db_path)

    def get_financial_summary(self):
        try:
            with self.db.get_connection() as conn:
                cur = conn.cursor()
                cur.execute("""SELECT
                    COALESCE((SELECT SUM(amount) FROM financial_records WHERE status='مدفوع'),0) as total,
                    COALESCE((SELECT SUM(amount) FROM financial_records WHERE status!='مدفوع'),0) as pending,
                    (SELECT COUNT(*) FROM financial_records) as cnt""")
                row = cur.fetchone()
                cur.execute("SELECT strftime('%Y-%m', date) as month, COALESCE(SUM(amount), 0) FROM financial_records WHERE status='مدفوع' GROUP BY month ORDER BY month")
                monthly = {r[0]: r[1] for r in cur.fetchall()}
                return {'total_income': row['total'], 'total_pending': row['pending'],
                        'monthly_income': monthly, 'total_records': row['cnt']}
        except Exception:
            return {'total_income': 0, 'total_pending': 0, 'monthly_income': {}, 'total_records': 0}

    def get_history(self, limit=100, offset=0, filters=None):
        query = "SELECT date, type, details, movement_number FROM history WHERE 1=1"
        params = []
        if filters:
            for k, v in filters.items():
                if v:
                    query += f" AND {k} LIKE ?"
                    params.append(f'%{v}%')
        query += " ORDER BY date DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        try:
            return self.db.execute_query(query, params, fetch=True) or []
        except Exception:
            return []

    def count_history(self, filters=None):
        query = "SELECT COUNT(*) FROM history WHERE 1=1"
        params = []
        if filters:
            for k, v in filters.items():
                if v:
                    query += f" AND {k} LIKE ?"
                    params.append(f'%{v}%')
        try:
            result = self.db.execute_query(query, params, fetch=True)
            return result[0][0] if result else 0
        except Exception:
            return 0

    def get_subscribers_paginated(self, limit=20, offset=0, search=None, filters=None):
        query = "SELECT * FROM subscribers WHERE 1=1"
        params = []
        if search:
            query += " AND (name LIKE ? OR car_number LIKE ? OR phone LIKE ?)"
            params.extend([f'%{search}%'] * 3)
        if filters:
            for k, v in filters.items():
                if v:
                    query += f" AND {k} LIKE ?"
                    params.append(f'%{v}%')
        query += " ORDER BY registration_date DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        return self.db.execute_query(query, params, fetch=True) or []

    def count_subscribers(self, search=None, filters=None):
        query = "SELECT COUNT(*) FROM subscribers WHERE 1=1"
        params = []
        if search:
            query += " AND (name LIKE ? OR car_number LIKE ? OR phone LIKE ?)"
            params.extend([f'%{search}%'] * 3)
        if filters:
            for k, v in filters.items():
                if v:
                    query += f" AND {k} LIKE ?"
                    params.append(f'%{v}%')
        result = self.db.execute_query(query, params, fetch=True)
        return result[0][0] if result else 0

    def get_all_financial_records(self, filters=None):
        query = "SELECT id, subscriber_id, type, amount, status, description, date FROM financial_records WHERE 1=1"
        params = []
        if filters:
            for k, v in filters.items():
                if v:
                    query += f" AND {k} LIKE ?"
                    params.append(f'%{v}%')
        query += " ORDER BY date DESC"
        try:
            return self.db.execute_query(query, params, fetch=True) or []
        except Exception as e:
            app_log("error", f"get_all_financial_records: {e}")
            return []

    def get_shift_financial_data(self, opened_at, closed_at):
        try:
            with self.db.get_connection() as conn:
                cur = conn.cursor()
                cur.execute("""SELECT
                    COALESCE((SELECT SUM(amount) FROM financial_records WHERE date >= ? AND date <= ? AND status='مدفوع'),0) as total,
                    COALESCE((SELECT SUM(amount) FROM financial_records WHERE date >= ? AND date <= ? AND status='مدفوع' AND type='زائر'),0) as vis_rev,
                    COALESCE((SELECT SUM(amount) FROM financial_records WHERE date >= ? AND date <= ? AND status='مدفوع' AND (type LIKE 'اشتراك%' OR type LIKE 'تجديد%')),0) as sub_rev,
                    (SELECT COUNT(*) FROM history WHERE type IN ('visitor_entry', 'subscriber_entry') AND date >= ? AND date <= ?) as entries,
                    (SELECT COUNT(*) FROM history WHERE type IN ('visitor_exit', 'subscriber_exit') AND date >= ? AND date <= ?) as exits""",
                    (opened_at, closed_at, opened_at, closed_at, opened_at, closed_at, opened_at, closed_at, opened_at, closed_at))
                row = cur.fetchone()
                return row['total'], row['entries'], row['exits'], row['vis_rev'], row['sub_rev']
        except Exception as e:
            app_log("error", f"get_shift_financial_data: {e}")
            return 0, 0, 0, 0, 0


# ===================================================================
# ⭐⭐⭐ SubscriberAttendanceManager (مع حماية اشتراك التطبيق) ⭐⭐⭐
# ===================================================================
class SubscriberAttendanceManager:
    def __init__(self, db):
        self.db = db

    def record_entry(self, sid):
        try:
            sub_row = self.db.execute_query(
                "SELECT * FROM subscribers WHERE id=?",
                (sid,), fetch=True
            )
            if not sub_row:
                return False

            sub_dict = dict(sub_row[0])
            status, days, msg = get_subscriber_app_status(self.db, sub_dict)

            if status in ('expired', 'disabled'):
                app_log("warning", f"محاولة دخول مرفوضة: {sid} — {msg}")
                return False

            if self.db.execute_query(
                "SELECT id FROM subscriber_attendance WHERE subscriber_id=? AND status='inside'",
                (sid,), fetch=True
            ):
                return False

            now = datetime.now().isoformat()
            mv = get_next_movement_number(self.db)

            self.db.execute_query(
                'INSERT INTO subscriber_attendance (subscriber_id, entry_time, status, movement_number) VALUES (?, ?, ?, ?)',
                (sid, now, 'inside', mv), commit=True
            )
            self.db.execute_query(
                "UPDATE spots SET is_occupied=1, status='occupied' WHERE subscriber_id=?",
                (sid,), commit=True
            )

            details = f'دخول مشترك ({status})'
            self.db.execute_query(
                'INSERT INTO history (type, subscriber_id, spot_id, details, date, movement_number) VALUES (?, ?, ?, ?, ?, ?)',
                ('subscriber_entry', sid, None, details, now, mv), commit=True
            )
            clear_all_caches()
            log_change(self.db, 'subscriber_attendance', sid, 'insert', {
                'subscriber_id': sid,
                'entry_time': now,
                'status': 'inside',
                'movement_number': mv,
                'updated_at': now,
            })
            log_change(self.db, 'subscribers', sid, 'update', {
                'id': sid, 'updated_at': now
            })
            return True
        except Exception as e:
            app_log("error", f"record_entry: {e}")
            return False
    def record_exit(self, sid):
        try:
            active = self.db.execute_query("SELECT id FROM subscriber_attendance WHERE subscriber_id=? AND status='inside'", (sid,), fetch=True)
            if not active:
                return False
            now = datetime.now().isoformat()
            mv = get_next_movement_number(self.db)
            self.db.execute_query('UPDATE subscriber_attendance SET exit_time=?, status="outside", movement_number=? WHERE id=?',
                                  (now, mv, active[0][0]), commit=True)
            self.db.execute_query("UPDATE spots SET is_occupied=0, status='subscriber_out' WHERE subscriber_id=?", (sid,), commit=True)
            self.db.execute_query('INSERT INTO history (type, subscriber_id, spot_id, details, date, movement_number) VALUES (?, ?, ?, ?, ?, ?)',
                                  ('subscriber_exit', sid, None, 'خروج مشترك', now, mv), commit=True)
            clear_all_caches()
            log_change(self.db, 'subscriber_attendance', sid, 'update', {
                'subscriber_id': sid,
                'exit_time': now,
                'status': 'outside',
                'movement_number': mv,
                'updated_at': now,
            })
            log_change(self.db, 'subscribers', sid, 'update', {
                'id': sid, 'updated_at': now
            })
            return True
        except Exception as e:
            app_log("error", f"record_exit: {e}")
            return False
    def get_current_status(self, sid):
        result = self.db.execute_query("SELECT * FROM subscriber_attendance WHERE subscriber_id=? AND status='inside'", (sid,), fetch=True)
        return result[0] if result else None

    def get_all_inside_ids(self):
        try:
            result = self.db.execute_query("SELECT DISTINCT subscriber_id FROM subscriber_attendance WHERE status='inside'", fetch=True)
            return {r[0] for r in result} if result else set()
        except Exception:
            return set()


# ===================================================================
# ⭐⭐⭐ نافذة إغلاق الوردية ⭐⭐⭐
# ===================================================================
def _render_close_shift_confirmation(db, manager):
    st.markdown("## ⚠️ تأكيد إغلاق الوردية")
    shift_data = st.session_state.get('shift_close_data', {})
    tr = shift_data.get('total_revenue', 0)
    te = shift_data.get('total_entries', 0)
    tex = shift_data.get('total_exits', 0)
    vr = shift_data.get('visitor_revenue', 0)
    sr = shift_data.get('subscriber_revenue', 0)

    st.warning("هل أنت متأكد من إغلاق الوردية؟")

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(f"""<div class="metric-card" style="border-right-color: #4CAF50;"><div class="metric-value" style="color: #4CAF50; font-size: 24px;">{tr:,.0f}</div><div class="metric-label">💰 الإيرادات</div></div>""", unsafe_allow_html=True)
    with c2:
        st.markdown(f"""<div class="metric-card" style="border-right-color: #2196F3;"><div class="metric-value" style="color: #2196F3; font-size: 24px;">{vr:,.0f}</div><div class="metric-label">🚗 الزوار</div></div>""", unsafe_allow_html=True)
    with c3:
        st.markdown(f"""<div class="metric-card" style="border-right-color: #9C27B0;"><div class="metric-value" style="color: #9C27B0; font-size: 24px;">{sr:,.0f}</div><div class="metric-label">👤 المشتركين</div></div>""", unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        if st.button("✅ نعم، أغلق الوردية", use_container_width=True, type="primary", key="confirm_close_yes_v6"):
            username = st.session_state.get('username', '')
            if db.close_shift(username, tr, te, tex, vr, sr, f"إغلاق بواسطة {username}"):
                with db.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute('SELECT * FROM shifts ORDER BY id DESC LIMIT 1')
                    last_shift = cursor.fetchone()
                if last_shift:
                    fields = [
                        {'label': 'الوردية', 'value': str(last_shift['id'])},
                        {'label': 'افتتحت بواسطة', 'value': last_shift['opened_by'] or ''},
                        {'label': 'وقت الفتح', 'value': last_shift['opened_at'][:16] if last_shift['opened_at'] else ''},
                        {'label': 'أغلقت بواسطة', 'value': last_shift['closed_by'] or ''},
                        {'label': 'وقت الإغلاق', 'value': last_shift['closed_at'][:16] if last_shift['closed_at'] else ''},
                        {'label': 'إيرادات الزوار', 'value': f"{last_shift['visitor_revenue']:.2f}"},
                        {'label': 'إيرادات المشتركين', 'value': f"{last_shift['subscriber_revenue']:.2f}"},
                        {'label': 'الإيرادات الكلية', 'value': f"{last_shift['total_revenue']:.2f}"},
                        {'label': 'دخول', 'value': str(last_shift['total_entries'])},
                        {'label': 'خروج', 'value': str(last_shift['total_exits'])},
                    ]
                    st.session_state['receipt_data'] = {
                        'title': "📊 إغلاق الوردية", 'fields': fields,
                        'barcode_data': None, 'qr_data': None,
                        'footer_text': datetime.now().strftime('%Y-%m-%d %H:%M')
                    }
                st.session_state['confirm_close_shift'] = False
                st.session_state.pop('shift_close_data', None)
                st.rerun()
            else:
                st.error("❌ خطأ")
    with col2:
        if st.button("❌ إلغاء", use_container_width=True, key="cancel_close_v6"):
            st.session_state['confirm_close_shift'] = False
            st.session_state.pop('shift_close_data', None)
            st.rerun()


# ===================================================================
# ⭐⭐⭐ شاشة النظام المنتهي ⭐⭐⭐
# ===================================================================
def locked_page(db):
    expired, expiry_dt = is_system_expired(db)
    expiry_str = expiry_dt.strftime('%Y-%m-%d') if expiry_dt else ''
    gname = get_garage_name_cached()

    st.markdown(f"""
    <div class="lock-screen">
        <div style="font-size: 60px;">🔒</div>
        <h1>⚠️ انتهت صلاحية النظام</h1>
        <p style="font-size: clamp(14px, 2vw, 18px); opacity: 0.95;">
            تم إيقاف {gname} مؤقتاً. يرجى التواصل مع مسؤول النظام للتجديد.
        </p>
        <div class="contact-box">
            <div style="font-size: 13px; opacity: 0.85; margin-bottom: 8px;">📞 للتواصل والتجديد:</div>
            <div class="name">👨‍💻 {DEVELOPER_NAME}</div>
            <div class="phone">📱 {DEVELOPER_PHONE}</div>
        </div>
        {f'<div style="margin-top: 15px; font-size: 13px; opacity: 0.85;">📅 تاريخ الانتهاء: {expiry_str}</div>' if expiry_str else ''}
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("### 🔐 دخول Super Admin للتجديد")
    with st.expander("اضغط هنا للدخول كـ Super Admin", expanded=False):
        with st.form("super_admin_login_lock"):
            c1, c2 = st.columns(2)
            with c1:
                u = st.text_input("اسم المستخدم", key="lock_su_user")
            with c2:
                p = st.text_input("كلمة المرور", type="password", key="lock_su_pass")
            if st.form_submit_button("🔓 دخول Super Admin", use_container_width=True):
                if not u or not p:
                    st.warning("⚠️ أدخل البيانات")
                else:
                    user = db.get_user(u.strip(), p.strip())
                    if user and user['role'] == 'super_admin':
                        st.session_state.update({
                            'logged_in': True, 'username': u.strip(),
                            'user_role': 'super_admin', 'user_id': user['id'],
                            'user_name': user['full_name']
                        })
                        st.success("✅ تم الدخول")
                        time.sleep(0.3)
                        st.rerun()
                    else:
                        st.error("❌ بيانات خاطئة أو ليست صلاحية Super Admin")

    render_developer_footer()


# ===================================================================
# ⭐⭐⭐ لوحة Super Admin ⭐⭐⭐
# ===================================================================
def super_admin_page(db, manager):
    st.markdown("## 🔐 لوحة Super Admin")
    t1, t2, t3, t4, t5 = st.tabs([
        "🏢 اسم الجراج والهيكل",
        "📅 صلاحية النظام",
        "💰 سعر الخدمة والتجربة",
        "👨‍💻 معلومات المطور",
        "📁 استعادة DB"          # ⭐ جديد
    ])
    with t1:
        _render_garage_config(db, manager)
    with t2:
        _render_license_config(db)
    with t3:
        _render_app_fee_config(db)
    with t4:
        _render_dev_info()
    with t5:
        _render_restore_db(db, manager)
def _render_garage_config(db, manager):
    st.markdown("### 🏷️ اسم الجراج")
    current_name = db.get_garage_name()
    st.markdown(f"""<div class="floor-card">
        <div style="font-size: 15px; color: #333;"><b>الاسم الحالي:</b> {current_name}</div>
    </div>""", unsafe_allow_html=True)

    c1, c2 = st.columns([3, 1])
    with c1:
        new_name = st.text_input("✏️ اسم الجراج الجديد:", value=current_name, key="sa_garage_name")
    with c2:
        st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
        if st.button("💾 حفظ الاسم", key="sa_save_garage_name", use_container_width=True):
            if new_name and new_name.strip():
                if db.set_garage_name(new_name.strip()):
                    update_garage_name_cache(new_name.strip())
                    manager.garage_name = new_name.strip()
                    st.success(f"✅ تم حفظ الاسم: {new_name.strip()}")
                    time.sleep(0.5)
                    st.rerun()
                else:
                    st.error("❌ فشل")
            else:
                st.error("❌ اكتب الاسم أولاً")

    st.markdown("---")
    st.markdown("### 🏗️ الهيكل التنظيمي (الأدوار والمستويات والأماكن)")

    if 'sa_structure_working' not in st.session_state:
        st.session_state.sa_structure_working = copy.deepcopy(manager.structure)
    if 'sa_floor_names_working' not in st.session_state:
        st.session_state.sa_floor_names_working = dict(manager.floor_names)

    ws = st.session_state.sa_structure_working
    wfn = st.session_state.sa_floor_names_working

    total_floors = len(ws)
    total_levels = sum(len(ws[f]) for f in ws)
    total_spots_calc = sum(ws[f][l]['spots'] for f in ws for l in ws[f])
    st.info(f"📊 **{total_floors}** دور | **{total_levels}** مستوى | **{total_spots_calc}** مكان")

    for floor in sorted(list(ws.keys())):
        with st.expander(f"🏢 {wfn.get(floor, f'الدور {floor}')}", expanded=False):
            c1, c2 = st.columns([4, 1])
            with c1:
                fname = st.text_input(f"اسم الدور:", value=wfn.get(floor, ''), key=f"sa_fn_{floor}")
                wfn[floor] = fname
            with c2:
                st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
                if st.button("🗑️ حذف الدور", key=f"sa_del_floor_{floor}"):
                    del ws[floor]
                    if floor in wfn:
                        del wfn[floor]
                    st.success(f"✅ تم حذف الدور {fname}")
                    time.sleep(0.3)
                    st.rerun()

            for level in sorted(list(ws[floor].keys())):
                st.markdown(f"<div style='background:#f8f9fa; border-radius:8px; padding:8px; margin:5px 0; border-right:3px solid #667eea;'>", unsafe_allow_html=True)
                lc1, lc2, lc3 = st.columns([3, 2, 1])
                with lc1:
                    lname = st.text_input(f"اسم المستوى:", value=ws[floor][level].get('name', ''), key=f"sa_ln_{floor}_{level}")
                    ws[floor][level]['name'] = lname
                with lc2:
                    spots = st.number_input(f"عدد الأماكن:", min_value=1, max_value=1000,
                                            value=int(ws[floor][level].get('spots', 1)),
                                            step=1, key=f"sa_sp_{floor}_{level}")
                    ws[floor][level]['spots'] = spots
                with lc3:
                    st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
                    if st.button("🗑️", key=f"sa_del_level_{floor}_{level}", help="حذف المستوى"):
                        if len(ws[floor]) <= 1:
                            st.warning("⚠️ يجب أن يبقى مستوى واحد على الأقل")
                        else:
                            del ws[floor][level]
                            st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)

            if st.button(f"➕ إضافة مستوى جديد للدور {wfn.get(floor, floor)}", key=f"sa_add_level_{floor}"):
                new_level_id = max(ws[floor].keys()) + 1 if ws[floor] else 0
                ws[floor][new_level_id] = {'spots': 10, 'name': f'مستوى {new_level_id + 1}', 'start': 0}
                st.rerun()

    st.markdown("---")
    c_add1, c_add2 = st.columns(2)
    with c_add1:
        if st.button("➕ إضافة دور جديد", key="sa_add_floor", use_container_width=True):
            new_floor_id = max(ws.keys()) + 1 if ws else 0
            ws[new_floor_id] = {0: {'spots': 10, 'name': 'مستوى أ', 'start': 0}}
            wfn[new_floor_id] = f"الدور {new_floor_id}"
            st.success(f"✅ تم إضافة دور جديد - قم بتعديل بياناته")
            time.sleep(0.3)
            st.rerun()

    with c_add2:
        if st.button("🔄 إعادة تعيين المسودات", key="sa_reset_working", use_container_width=True):
            st.session_state.sa_structure_working = copy.deepcopy(manager.structure)
            st.session_state.sa_floor_names_working = dict(manager.floor_names)
            st.success("✅ تمت إعادة التعيين")
            time.sleep(0.3)
            st.rerun()

    st.markdown("---")
    st.warning("⚠️ **تنبيه:** عند الحفظ، سيتم حذف الأماكن غير المشغولة التي تم إزالتها، والإبقاء على الأماكن المشغولة.")

    if st.button("💾 حفظ وتطبيق الهيكل الجديد", key="sa_save_structure", type="primary", use_container_width=True):
        if not ws:
            st.error("❌ لا يمكن حفظ هيكل فارغ")
        else:
            success, added, deleted, preserved = manager.save_and_apply_structure(
                copy.deepcopy(ws), dict(wfn)
            )
            if success:
                st.success(f"✅ تم الحفظ | ➕ {added} مكان جديد | 🗑️ {deleted} مكان محذوف | 🔒 {preserved} مكان مشغول تم الاحتفاظ به")
                st.session_state.pop('sa_structure_working', None)
                st.session_state.pop('sa_floor_names_working', None)
                clear_all_caches()
                time.sleep(1.5)
                st.rerun()
            else:
                st.error("❌ فشل الحفظ")
def _render_restore_db(db, manager):
    st.markdown("### 📁 استعادة قاعدة بيانات من ملف")
    st.warning("⚠️ **تحذير:** هذا سيستبدل كل البيانات الحالية!")

    uploaded = st.file_uploader("اختر ملف قاعدة البيانات (.db)", type=['db'])

    if uploaded:
        st.info(f"📦 حجم الملف: {uploaded.size / 1024:.1f} KB")

        if st.button("🔥 استبدال قاعدة البيانات", type="primary"):
            import shutil
            db_path = db.db_path  # المسار الحالي

            # نسخة احتياطية
            backup_path = db_path + ".backup"
            try:
                shutil.copy2(db_path, backup_path)
                st.info(f"✅ تم إنشاء نسخة احتياطية: {backup_path}")
            except Exception as e:
                st.warning(f"⚠️ فشل النسخ الاحتياطي: {e}")

            # اكتب الملف الجديد
            try:
                with open(db_path, 'wb') as f:
                    f.write(uploaded.getbuffer())

                # امسح الـ wal / shm
                for ext in ['-wal', '-shm']:
                    p = db_path + ext
                    if os.path.exists(p):
                        os.remove(p)

                st.success("✅ تم استبدال قاعدة البيانات!")
                st.info("🔄 أعد تشغيل التطبيق على Railway لتطبيق التغييرات")
                time.sleep(2)
            except Exception as e:
                st.error(f"❌ فشل: {e}")

def _render_app_fee_config(db):
    st.markdown("### 💰 سعر خدمة التطبيق لهذا الجراج")

    def _get_setting(key, default=''):
        r = db.execute_query(
            "SELECT value FROM parking_settings WHERE key=?",
            (key,), fetch=True
        )
        return r[0]['value'] if r and r[0]['value'] else default

    current_fee = _get_setting('app_fee', '10')
    current_trial = _get_setting('app_trial_days', '3')
    current_instapay = _get_setting('instapay_number', '')
    current_vodafone = _get_setting('vodafone_cash_number', '')
    trial_enabled = _get_setting('trial_enabled', '1') == '1'
    free_forever = _get_setting('garage_free_forever', '0') == '1'
    free_until_str = _get_setting('garage_free_until', '')

    st.info(f"""
    ⚙️ **الإعدادات الحالية:**
    - 💵 السعر: **{current_fee} ج/شهر**
    - 🎁 تجربة: **{current_trial} يوم** ({'✅' if trial_enabled else '⛔'})
    - 🎉 إعفاء الجراج: {'✅ معفى نهائياً' if free_forever else (f'✅ حتى {free_until_str[:10]}' if free_until_str else '❌ لا يوجد')}
    """)

    with st.form("app_fee_form"):
        c1, c2 = st.columns(2)
        with c1:
            new_fee = st.number_input("💵 السعر الشهري", min_value=0.0,
                                      value=float(current_fee), step=5.0, key="fee_input")
        with c2:
            new_trial = st.number_input("🎁 أيام تجريبية", min_value=0, max_value=90,
                                        value=int(current_trial), step=1, key="trial_input")

        st.markdown("---")
        new_trial_enabled = st.checkbox("✅ تفعيل الفترة التجريبية",
                                        value=trial_enabled, key="trial_enabled_input")

        c1, c2 = st.columns(2)
        with c1:
            new_free_forever = st.checkbox("🎉 الجراج معفى نهائياً",
                                           value=free_forever, key="free_forever_input")
        with c2:
            try:
                _def_date = datetime.fromisoformat(free_until_str).date() if free_until_str else datetime.now().date()
            except Exception:
                _def_date = datetime.now().date()
            free_until_date = st.date_input("📅 أو معفى حتى:", value=_def_date, key="free_until_input")
            use_free_until = st.checkbox("استخدام التاريخ",
                                         value=bool(free_until_str and not free_forever),
                                         key="use_free_until")

        st.markdown("---")
        c1, c2 = st.columns(2)
        with c1:
            instapay = st.text_input("💳 InstaPay", value=current_instapay, key="instapay_input")
        with c2:
            vodafone = st.text_input("📱 Vodafone Cash", value=current_vodafone, key="vodafone_input")

        if st.form_submit_button("💾 حفظ", use_container_width=True, type="primary"):
            updates = {
                'app_fee': str(new_fee),
                'app_trial_days': str(new_trial),
                'instapay_number': instapay.strip(),
                'vodafone_cash_number': vodafone.strip(),
                'trial_enabled': '1' if new_trial_enabled else '0',
                'garage_free_forever': '1' if new_free_forever else '0',
                'garage_free_until': free_until_date.isoformat() if (use_free_until and not new_free_forever) else '',
            }
            for k, v in updates.items():
                db.execute_query(
                    "INSERT OR REPLACE INTO parking_settings (key, value) VALUES (?, ?)",
                    (k, v), commit=True
                )
            st.success("✅ تم الحفظ")
            time.sleep(0.5)
            st.rerun()
def _render_license_config(db):
    st.markdown("### 📅 إدارة صلاحية النظام")

    expired, expiry_dt = is_system_expired(db)

    if expiry_dt:
        if expired:
            st.error(f"🔴 **النظام منتهي الصلاحية!** — تاريخ الانتهاء: **{expiry_dt.strftime('%Y-%m-%d')}**")
        else:
            days_left = (expiry_dt - datetime.now()).days
            hours_left = int((expiry_dt - datetime.now()).total_seconds() // 3600)
            if days_left >= 1:
                st.success(f"🟢 **النظام نشط** — متبقي: **{days_left} يوم** — ينتهي: **{expiry_dt.strftime('%Y-%m-%d')}**")
            else:
                st.warning(f"🟡 **النظام ينتهي قريباً** — متبقي: **{hours_left} ساعة** — ينتهي: **{expiry_dt.strftime('%Y-%m-%d %H:%M')}**")
    else:
        st.info("ℹ️ **لا يوجد تاريخ انتهاء محدد** — النظام يعمل بدون قيود زمنية.")

    st.markdown("---")
    st.markdown("### ⚙️ ضبط تاريخ انتهاء جديد")

    with st.form("set_expiry_form"):
        c1, c2 = st.columns(2)
        with c1:
            preset = st.selectbox("⏱️ صلاحية سريعة:", [
                "اختر...",
                "شهر واحد (30 يوم)",
                "3 شهور (90 يوم)",
                "6 شهور (180 يوم)",
                "سنة كاملة (365 يوم)",
                "سنتان (730 يوم)"
            ])
        with c2:
            custom_date = st.date_input("📅 أو اختر تاريخ محدد:", value=datetime.now() + timedelta(days=365))

        st.markdown("**ملاحظة:** اختيار صلاحية سريعة سيتجاهل التاريخ المخصص.")

        preset_days = {
            "شهر واحد (30 يوم)": 30,
            "3 شهور (90 يوم)": 90,
            "6 شهور (180 يوم)": 180,
            "سنة كاملة (365 يوم)": 365,
            "سنتان (730 يوم)": 730,
        }

        c1, c2, c3 = st.columns(3)
        with c1:
            if st.form_submit_button("✅ حفظ التاريخ", use_container_width=True, type="primary"):
                if preset != "اختر..." and preset in preset_days:
                    new_expiry = datetime.now() + timedelta(days=preset_days[preset])
                else:
                    new_expiry = datetime.combine(custom_date, datetime.max.time()).replace(microsecond=0)
                if set_system_expiry(db, new_expiry):
                    st.success(f"✅ تم ضبط تاريخ الانتهاء: **{new_expiry.strftime('%Y-%m-%d')}**")
                    time.sleep(0.5)
                    st.rerun()
                else:
                    st.error("❌ فشل الحفظ")
        with c2:
            if st.form_submit_button("🗑️ إزالة القيد", use_container_width=True):
                if set_system_expiry(db, None):
                    st.success("✅ تم إزالة تاريخ الانتهاء — النظام يعمل بدون قيود")
                    time.sleep(0.5)
                    st.rerun()
                else:
                    st.error("❌ فشل")
        with c3:
            if st.form_submit_button("➕ تمديد سنة إضافية", use_container_width=True):
                if expiry_dt and not expired:
                    new_expiry = expiry_dt + timedelta(days=365)
                else:
                    new_expiry = datetime.now() + timedelta(days=365)
                if set_system_expiry(db, new_expiry):
                    st.success(f"✅ تم التمديد حتى: **{new_expiry.strftime('%Y-%m-%d')}**")
                    time.sleep(0.5)
                    st.rerun()
                else:
                    st.error("❌ فشل")


def _render_dev_info():
    st.markdown("### 👨‍💻 معلومات المطور")
    st.markdown(f"""
    <div style="background: white; border-radius: 15px; padding: 20px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
        <div style="font-size: 18px; font-weight: bold; color: #667eea; margin-bottom: 10px;">
            🚗 {DEVELOPER_NAME}
        </div>
        <div style="font-size: 16px; color: #333; direction: ltr; text-align: right;">
            📱 <b>للتواصل والدعم الفني:</b> <span style="color: #4CAF50; font-size: 20px; font-weight: bold;">{DEVELOPER_PHONE}</span>
        </div>
        <div style="margin-top: 15px; padding-top: 15px; border-top: 1px dashed #ddd; color: #666; font-size: 13px;">
            ℹ️ هذا النظام مرخص لاستخدامك الشخصي. يُرجى عدم مشاركة الملفات مع أي طرف آخر.
        </div>
    </div>
    """, unsafe_allow_html=True)


# ===================================================================
# ⭐⭐⭐ إدارة الجراجات (Super Admin) ⭐⭐⭐
# ===================================================================
def show_garages_management(registry, current_active_id):
    st.markdown("## 🏢 إدارة الجراجات")
    st.info("💡 كل جراج له قاعدة بيانات مستقلة تماماً: مشتركينه، هيكله، إعداداته، وردياته.")

    garages = registry.list_garages()
    st.write(f"**إجمالي الجراجات:** {len(garages)}")

    with st.expander("➕ إنشاء جراج جديد", expanded=False):
        with st.form("create_garage_form"):
            c1, c2 = st.columns(2)
            with c1:
                new_name = st.text_input("🏢 اسم الجراج *", placeholder="مثال: جراج المعادي")
                new_address = st.text_input("📍 العنوان")
            with c2:
                new_phone = st.text_input("📞 الهاتف")
            if st.form_submit_button("✅ إنشاء الجراج", use_container_width=True, type="primary"):
                if not new_name.strip():
                    st.error("❌ اكتب اسم الجراج")
                else:
                    ok, msg = registry.create_garage(new_name, new_address, new_phone)
                    if ok:
                        st.success(f"✅ تم إنشاء الجراج | قاعدة البيانات: {msg}")
                        time.sleep(0.8)
                        st.rerun()
                    else:
                        st.error(f"❌ {msg}")

    st.markdown("---")

    for g in garages:
        is_current = (g['id'] == current_active_id)
        status_icon = "✅" if g['is_active'] else "⛔"
        current_badge = " 🟢 [الحالي]" if is_current else ""
        with st.expander(f"{status_icon} {g['name']}{current_badge} — DB: `{g['db_path']}`"):
            c1, c2 = st.columns(2)
            with c1:
                st.write(f"**🏢 الاسم:** {g['name']}")
                st.write(f"**📍 العنوان:** {g.get('address') or '-'}")
                st.write(f"**📞 الهاتف:** {g.get('phone') or '-'}")
            with c2:
                st.write(f"**📁 ملف DB:** `{g['db_path']}`")
                st.write(f"**📅 تاريخ الإنشاء:** {g.get('created_at', '')[:19]}")
                st.write(f"**📌 الحالة:** {'✅ نشط' if g['is_active'] else '⛔ موقوف'}")

            try:
                temp_db = Database(g['db_path'])
                spots_count = temp_db.execute_query('SELECT COUNT(*) FROM spots', fetch=True)
                subs_count = temp_db.execute_query('SELECT COUNT(*) FROM subscribers', fetch=True)
                vis_count = temp_db.execute_query("SELECT COUNT(*) FROM visitors WHERE status='inside'", fetch=True)
                m1, m2, m3 = st.columns(3)
                m1.metric("🅿️ أماكن", spots_count[0][0] if spots_count else 0)
                m2.metric("👤 مشتركين", subs_count[0][0] if subs_count else 0)
                m3.metric("🚗 زوار حالياً", vis_count[0][0] if vis_count else 0)
            except Exception as e:
                st.warning(f"⚠️ تعذر قراءة إحصائيات الجراج: {e}")

            st.markdown("---")
            c1, c2, c3 = st.columns(3)
            with c1:
                if not is_current:
                    if st.button("🔄 التبديل إلى هذا الجراج", key=f"switch_{g['id']}",
                                 use_container_width=True, type="primary"):
                        # ⭐ تحديث كل بيانات الجراج النشط
                        st.session_state['active_garage_id'] = g['id']
                        st.session_state['active_garage_name'] = g['name']
                        st.session_state['active_garage_db_path'] = g['db_path']
                        st.session_state['db'] = Database(g['db_path'])
                        for k in ['garage_manager', 'visitor_manager', 'attendance_manager']:
                            st.session_state.pop(k, None)
                        clear_all_caches()
                        st.success(f"✅ تم التبديل إلى {g['name']}")
                        time.sleep(0.5)
                        st.rerun()
                else:
                    st.button("✅ الجراج الحالي", key=f"current_{g['id']}",
                              use_container_width=True, disabled=True)
            with c2:
                if st.button(f"{'⛔ إيقاف' if g['is_active'] else '✅ تفعيل'}",
                             key=f"toggle_{g['id']}", use_container_width=True):
                    if registry.toggle_active(g['id']):
                        st.rerun()
            with c3:
                if not is_current:
                    if st.button("🗑️ حذف", key=f"del_{g['id']}", use_container_width=True):
                        st.session_state[f'confirm_del_garage_{g["id"]}'] = True
                        st.rerun()
                else:
                    st.button("🗑️ حذف", key=f"del_dis_{g['id']}",
                              use_container_width=True, disabled=True)

            if st.session_state.get(f'confirm_del_garage_{g["id"]}'):
                st.error(f"⚠️ هل أنت متأكد من حذف **{g['name']}**؟ (لن تُحذف قاعدة البيانات من القرص)")
                cc1, cc2 = st.columns(2)
                with cc1:
                    if st.button("✅ نعم، احذف من القائمة", key=f"yes_del_{g['id']}",
                                 use_container_width=True, type="primary"):
                        ok, msg = registry.delete_garage(g['id'])
                        if ok:
                            st.success(f"✅ {msg}")
                            st.session_state.pop(f'confirm_del_garage_{g["id"]}', None)
                            time.sleep(0.5)
                            st.rerun()
                        else:
                            st.error(f"❌ {msg}")
                with cc2:
                    if st.button("❌ إلغاء", key=f"no_del_{g['id']}", use_container_width=True):
                        st.session_state.pop(f'confirm_del_garage_{g["id"]}', None)
                        st.rerun()


# ===================================================================
# ⭐⭐⭐ شاشة اختيار الجراج قبل الدخول ⭐⭐⭐
# ===================================================================
def garage_selection_login_screen(registry):
    st.markdown(f"""
    <div style="text-align:center; margin: 30px 0;">
        <h1 style="color:#667eea; font-size:clamp(24px,4vw,38px);">🚗 نظام إدارة الجراج المتكامل</h1>
        <p style="color:#666; font-size:clamp(14px,2vw,20px); margin-top:10px;">اختر الجراج للبدء</p>
    </div>
    """, unsafe_allow_html=True)

    garages = registry.list_garages(active_only=True)
    if not garages:
        st.error("❌ لا توجد جراجات نشطة. تواصل مع Super Admin.")
        render_developer_footer()
        return

    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        st.markdown("### 🏢 الجراجات المتاحة")
        for g in garages:
            label = f"🏢  {g['name']}\n\n📍 {g.get('address') or 'بدون عنوان'}\n\n📞 {g.get('phone') or '-'}"
            if st.button(label, key=f"pick_login_garage_{g['id']}", use_container_width=True):
                st.session_state.selected_login_garage = g
                st.rerun()

    st.markdown("---")
    render_developer_footer()


# ===================================================================
# ⭐⭐⭐ صفحة الدخول ⭐⭐⭐
# ===================================================================
def login_page(db):
    # ⭐ عرض صفحة التطبيقات لو مطلوب
    if st.session_state.get('show_download_apps'):
        show_download_apps_page()
        return

    selected = st.session_state.get('selected_login_garage')
    selected_name = selected.get('name') if selected else db.get_garage_name()

    gname = db.get_garage_name()
    update_garage_name_cache(gname)

    st.markdown(f"""
    <div style="text-align:center;margin-bottom:30px;">
        <h1 style="color:#667eea; font-size:clamp(22px,4vw,36px);">🚗 تسجيل الدخول</h1>
        <p style="color:#666; font-size:clamp(14px,2vw,20px); margin-top:10px;">
            🏢 <b>{selected_name}</b>
        </p>
    </div>
    """, unsafe_allow_html=True)

    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        if st.button("← تغيير الجراج", key="change_login_garage_btn", use_container_width=True):
            st.session_state.pop('selected_login_garage', None)
            st.rerun()

        st.markdown("<br>", unsafe_allow_html=True)

        with st.form("login_form"):
            u = st.text_input("👤 اسم المستخدم", placeholder="أدخل اسم المستخدم")
            p = st.text_input("🔑 كلمة المرور", type="password", placeholder="أدخل كلمة المرور")
            if st.form_submit_button("🚀 تسجيل الدخول", use_container_width=True):
                if not u or not p:
                    st.warning("⚠️ أدخل البيانات")
                else:
                    try:
                        user = db.get_user(u.strip(), p.strip())
                        if user:
                            st.session_state.update({
                                'logged_in': True,
                                'username': u.strip(),
                                'user_role': user['role'],
                                'user_id': user['id'],
                                'user_name': user['full_name'],
                            })
                            if selected:
                                st.session_state['active_garage_id'] = selected['id']
                                st.session_state['active_garage_name'] = selected['name']
                                st.session_state['active_garage_db_path'] = selected['db_path']
                            st.success("✅")
                            time.sleep(0.2)
                            st.rerun()
                        else:
                            st.error("❌ بيانات خاطئة")
                    except Exception as e:
                        st.error(f"❌ خطأ: {e}")

        # ⭐ زر تحميل التطبيقات (جديد)
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("📲 تحميل التطبيقات", use_container_width=True, key="download_apps_login_btn"):
            st.session_state['show_download_apps'] = True
            st.rerun()

    st.markdown("---")
    render_developer_footer()
# ===================================================================
# ⭐⭐⭐ إدارة المستخدمين ⭐⭐⭐
# ===================================================================
def manage_users(db):
    st.markdown("## 👥 إدارة المستخدمين")

    # ⭐ قراءة اسم الجراج الحالي من الـ Registry مباشرة (مصدر الحقيقة)
    cur_garage = 'الجراج الحالي'
    try:
        active_id = st.session_state.get('active_garage_id')
        registry = st.session_state.get('garage_registry')
        if registry and active_id:
            g = registry.get_garage(active_id)
            if g:
                cur_garage = g['name']
        else:
            cur_garage = st.session_state.get('active_garage_name', 'الجراج الحالي')
    except Exception:
        cur_garage = st.session_state.get('active_garage_name', 'الجراج الحالي')

    st.info(f"🏢 **المستخدمون هنا يخصون: {cur_garage}** — كل جراج له مستخدموه المستقلون")
    users = db.get_all_users()
    if users:
        df = pd.DataFrame([{'ID': u['id'], 'اسم المستخدم': u['username'], 'الدور': u['role'],
                            'الاسم الكامل': u['full_name'], 'تاريخ الإنشاء': u['created_at']} for u in users])
        df['الدور'] = df['الدور'].map({'super_admin': 'Super Admin', 'admin': 'مدير', 'manager': 'مدير الجراج',
                                       'entry': 'دخول', 'exit': 'خروج', 'subscriber': 'مشتركين'}).fillna(df['الدور'])
        st.dataframe(df, use_container_width=True)
    with st.expander("➕ إضافة مستخدم"):
        with st.form("add_user"):
            c1, c2 = st.columns(2)
            with c1:
                u = st.text_input("اسم المستخدم")
                fn = st.text_input("الاسم الكامل")
            with c2:
                p = st.text_input("كلمة المرور", type="password")
                r = st.selectbox("الدور", ['admin', 'manager', 'entry', 'exit', 'subscriber'])
            if st.form_submit_button("إضافة"):
                if u and p and db.add_user(u, p, r, fn):
                    st.success("✅")
                    st.rerun()
    st.markdown("### ✏️ تعديل / حذف")
    ul = db.get_all_users()
    if ul:
        opts = {str(u['id']): f"{u['full_name']} ({u['username']})" for u in ul}
        sel = st.selectbox("اختر", list(opts.keys()), format_func=lambda x: opts[x])
        if sel:
            su = [u for u in ul if str(u['id']) == sel][0]
            if su['username'] == 'superadmin':
                st.warning("⚠️ حساب Super Admin محمي - لا يمكن تعديله من هنا")
                return
            with st.form("edit_user"):
                c1, c2 = st.columns(2)
                with c1:
                    eu = st.text_input("اسم المستخدم", value=su['username'])
                    ef = st.text_input("الاسم الكامل", value=su['full_name'] or '')
                with c2:
                    ep = st.text_input("كلمة مرور جديدة", type="password")
                    er = st.selectbox("الدور", ['admin', 'manager', 'entry', 'exit', 'subscriber'],
                                      index=['admin', 'manager', 'entry', 'exit', 'subscriber'].index(su['role']) if su['role'] in ['admin', 'manager', 'entry', 'exit', 'subscriber'] else 0)
                c1, c2 = st.columns(2)
                with c1:
                    if st.form_submit_button("💾 حفظ"):
                        ups = {}
                        if eu != su['username']: ups['username'] = eu
                        if ef != su['full_name']: ups['full_name'] = ef
                        if ep: ups['password'] = ep
                        if er != su['role']: ups['role'] = er
                        if ups and db.update_user(int(sel), **ups):
                            st.success("✅")
                            st.rerun()
                with c2:
                    if st.form_submit_button("🗑️ حذف"):
                        if su['username'] == 'admin':
                            st.error("❌ لا يمكن حذف المدير")
                        elif db.delete_user(int(sel)):
                            st.success("✅")
                            st.rerun()


# ===================================================================
# ⭐⭐⭐ لوحة التحكم ⭐⭐⭐
# ===================================================================
def show_dashboard(manager, visitor_manager):
    st.markdown("## 🏠 لوحة التحكم")
    db_path = manager.db.db_path
    stats = get_cached_dashboard_stats(db_path)
    total = stats['total']; occ = stats['occupied']; subs = stats['subs']
    avail = total - occ

    active_visitors = get_cached_active_visitors(db_path)
    inside_subs_data = get_cached_inside_subscribers_data(db_path)
    users_count = get_cached_users_count(db_path)

    active_visitors_count = len(active_visitors)
    inside_subs_count = len(inside_subs_data)

    cols = st.columns(4)
    with cols[0]:
        st.markdown(f"""<div class="metric-card"><div class="metric-value">{total}</div><div class="metric-label">🏢 إجمالي الأماكن</div></div>""", unsafe_allow_html=True)
    with cols[1]:
        st.markdown(f"""<div class="metric-card" style="border-right-color: #f44336;"><div class="metric-value" style="color: #f44336;">{occ}</div><div class="metric-label">🔴 مشغول</div></div>""", unsafe_allow_html=True)
    with cols[2]:
        st.markdown(f"""<div class="metric-card" style="border-right-color: #4CAF50;"><div class="metric-value" style="color: #4CAF50;">{avail}</div><div class="metric-label">🟢 متاح</div></div>""", unsafe_allow_html=True)
    with cols[3]:
        st.markdown(f"""<div class="metric-card" style="border-right-color: #ff9800;"><div class="metric-value" style="color: #ff9800;">{subs}</div><div class="metric-label">👤 إجمالي المشتركين</div></div>""", unsafe_allow_html=True)

    st.markdown("### 📊 إحصائيات الحركة الحالية")
    cols2 = st.columns(4)
    with cols2[0]:
        st.markdown(f"""<div class="metric-card" style="border-right-color: #2196F3;"><div class="metric-value" style="color: #2196F3;">{active_visitors_count}</div><div class="metric-label">🚗 زوار داخل الجراج</div></div>""", unsafe_allow_html=True)
    with cols2[1]:
        st.markdown(f"""<div class="metric-card" style="border-right-color: #4CAF50;"><div class="metric-value" style="color: #4CAF50;">{inside_subs_count}</div><div class="metric-label">👤 مشتركين داخل الجراج</div></div>""", unsafe_allow_html=True)
    with cols2[2]:
        st.markdown(f"""<div class="metric-card" style="border-right-color: #673AB7;"><div class="metric-value" style="color: #673AB7;">{users_count.get('entry', 0)}</div><div class="metric-label">📥 مستخدمو الدخول</div></div>""", unsafe_allow_html=True)
    with cols2[3]:
        st.markdown(f"""<div class="metric-card" style="border-right-color: #009688;"><div class="metric-value" style="color: #009688;">{users_count.get('exit', 0)}</div><div class="metric-label">📤 مستخدمو الخروج</div></div>""", unsafe_allow_html=True)

    expiring = manager.get_expiring_subscribers()
    expired = manager.get_expired_subscribers()
    if expiring or expired:
        st.markdown("### ⚠️ التنبيهات")
        if expired:
            st.error(f"🔴 **{len(expired)} مشترك منتهي!**")
        if expiring:
            st.warning(f"🟡 **{len(expiring)} يقترب من الانتهاء**")

    st.markdown("---")
    st.markdown(f"### 👥 المشتركون داخل الجراج حالياً ({inside_subs_count})")
    if inside_subs_data:
        for s in inside_subs_data:
            spot_loc = get_spot_location(s['spot_id']) if s.get('spot_id') else 'غير مخصص'
            entry_time = s['entry_time'][:16] if s.get('entry_time') else ''
            st.markdown(f"""<div class="inside-card">
                <b>👤 {s['name']}</b> | 🚗 {s.get('car_number', '-')} | 📱 {s.get('phone', '-')}<br>
                <small>🅿️ {spot_loc} | 🕐 دخل في: {entry_time} | 📅 الاشتراك: {s.get('subscription_type', '')}</small>
            </div>""", unsafe_allow_html=True)
    else:
        st.info("لا يوجد مشتركون داخل الجراج حالياً")

    st.markdown(f"### 🚗 الزوار داخل الجراج حالياً ({active_visitors_count})")
    if active_visitors:
        for v in active_visitors[:20]:
            spot_loc = get_spot_location(v['spot_id']) if v.get('spot_id') else 'غير مخصص'
            entry_time = v['entry_time'][:16] if v.get('entry_time') else ''
            st.markdown(f"""<div class="inside-card" style="border-right-color: #2196F3;">
                <b>🎫 {v['ticket_number']}</b> | 🚗 {v.get('vehicle_number', '-')} | 📱 {v.get('phone', '-') or '-'}<br>
                <small>🅿️ {spot_loc} | 🕐 دخل في: {entry_time}</small>
            </div>""", unsafe_allow_html=True)
        if len(active_visitors) > 20:
            st.caption(f"... و {len(active_visitors) - 20} زائر آخر")
    else:
        st.info("لا يوجد زوار داخل الجراج حالياً")

    st.markdown("### 📈 تحليلات")
    c1, c2 = st.columns(2)
    with c1:
        summary = manager.get_floor_summary()
        fd = []
        for f in sorted(summary.keys()):
            fo, ft = 0, 0
            for s in summary[f].values():
                fo += s['occupied']
                ft += s['total']
            if ft > 0:
                fd.append({'الدور': get_floor_name(f), 'المشغول': fo, 'المتاح': ft - fo})
        if fd:
            df = pd.DataFrame(fd)
            fig = px.bar(df, x='الدور', y=['المشغول', 'المتاح'], title='الإشغال حسب الدور',
                         color_discrete_map={'المشغول': '#f44336', 'المتاح': '#4CAF50'}, barmode='stack')
            st.plotly_chart(fig, use_container_width=True)
    with c2:
        fin = manager.get_financial_summary()
        if fin['monthly_income']:
            df = pd.DataFrame([{'الشهر': m, 'الإيرادات': a} for m, a in sorted(fin['monthly_income'].items())])
            fig = px.line(df, x='الشهر', y='الإيرادات', title='الإيرادات الشهرية', markers=True)
            st.plotly_chart(fig, use_container_width=True)


# ===================================================================
# ⭐⭐⭐ البحث الموحد ⭐⭐⭐
# ===================================================================
def render_unified_search(manager, visitor_manager, key_prefix="unified"):
    st.markdown("### 🔍 بحث متكامل")
    st.caption("ابحث برقم السيارة / رقم الكارت / الهاتف / الاسم / المعرف")
    q = st.text_input("🔎 اكتب كلمة البحث", key=f"{key_prefix}_search_input")
    if not q:
        return
    subs = manager.search_subscribers(q)
    vis = visitor_manager.search_visitors(q)
    if not subs and not vis:
        st.warning("لا توجد نتائج")
        return

    if vis:
        st.markdown(f"#### 🚗 زوار داخل الجراج ({len(vis)})")
        for v in vis:
            with st.expander(f"🅿️ {v['ticket_number']} - {v['vehicle_number']}"):
                c1, c2 = st.columns(2)
                with c1:
                    st.write(f"**التذكرة:** {v['ticket_number']}")
                    st.write(f"**السيارة:** {v['vehicle_number']}")
                    st.write(f"**النوع:** {v.get('vehicle_type', '')}")
                with c2:
                    st.write(f"**الهاتف:** {v.get('phone', '-')}")
                    st.write(f"**الدخول:** {v['entry_time'][:16]}")
                    st.write(f"**المكان:** {get_spot_location(v['spot_id']) if v.get('spot_id') else '-'}")

    if subs:
        st.markdown(f"#### 👤 مشتركين ({len(subs)})")
        for s in subs:
            ed = datetime.fromisoformat(s['subscription_end']) if s.get('subscription_end') else None
            dl = (ed - datetime.now()).days if ed else None
            status = "❌ منتهي" if (dl is not None and dl < 0) else (f"🟡 {dl} يوم" if (dl is not None and dl <= 7) else "✅ نشط")
            with st.expander(f"👤 {s['name']} - {s['car_number']} ({status})"):
                c1, c2 = st.columns(2)
                with c1:
                    st.write(f"**الاسم:** {s['name']}")
                    st.write(f"**الهاتف:** {s['phone']}")
                with c2:
                    st.write(f"**رقم السيارة:** {s['car_number']}")
                    st.write(f"**المكان:** {get_spot_location(s['spot_id']) if s.get('spot_id') else 'غير مخصص'}")
                cols = st.columns(3)
                with cols[0]:
                    if st.button("🔄 تجديد", key=f"{key_prefix}_renew_{s['id']}"):
                        st.session_state['renew_subscriber_id'] = s['id']
                        st.session_state['_goto_page'] = "👤 إدارة المشتركين"
                        st.rerun()
                with cols[1]:
                    if st.button("🎫 كارت", key=f"{key_prefix}_card_{s['id']}"):
                        st.session_state['show_subscriber_card'] = s['id']
                        st.session_state['_goto_page'] = "👤 إدارة المشتركين"
                        st.rerun()


# ===================================================================
# ⭐⭐⭐ عرض الجراج ⭐⭐⭐
# ===================================================================
def show_garage_view(manager, visitor_manager):
    st.markdown("## 🗺️ عرض الجراج")
    manager.ensure_correct_spot_count()

    goto_floor = st.session_state.pop('_goto_floor', None)
    goto_spot = st.session_state.pop('_goto_spot', None)

    show_search = st.toggle("🔍 البحث المتكامل (زوار ومشتركين)", key="garage_show_search")
    if show_search:
        render_unified_search(manager, visitor_manager, key_prefix="garage")
    st.markdown("---")
    floors = sorted(manager.structure.keys())
    if not floors:
        st.warning("⚠️ لا يوجد أدوار. تواصل مع Super Admin.")
        return

    if goto_floor is not None and goto_floor in floors:
        target_floor = goto_floor
    else:
        target_floor = st.session_state.get('garage_floor_view_sel', floors[0])
        if target_floor not in floors:
            target_floor = floors[0]

    try:
        default_idx = floors.index(target_floor)
    except Exception:
        default_idx = 0

    selected_floor = st.selectbox("اختر الدور:", floors, index=default_idx,
                                   format_func=get_floor_name, key="garage_floor_view_sel")

    if goto_spot:
        st.session_state['selected_garage_spot'] = goto_spot

    if selected_floor is None:
        return

    spots_map = get_all_spots_map(manager.db.db_path)
    inside_subs = get_cached_inside_subscribers(manager.db.db_path)

    c1, c2 = st.columns([1, 3])
    with c1:
        st.markdown(f"### 📊 {get_floor_name(selected_floor)}")
        summary = manager.get_floor_summary(selected_floor)
        if selected_floor in summary:
            for ln, stt in summary[selected_floor].items():
                st.markdown(f"""<div style="background:white; border-radius:10px; padding:10px; margin:5px 0;">
                    <b>{ln}</b><br>🟢 {stt['available']} | 🔴 {stt['occupied']}<br>
                    <small>{stt['occupancy_rate']:.1f}%</small></div>""", unsafe_allow_html=True)

    with c2:
        levels = sorted(manager.structure[selected_floor].keys())
        selected_spot_id = st.session_state.get('selected_garage_spot')
        for level in levels:
            ln = manager.structure[selected_floor][level]['name']
            st.markdown(f"### 📍 {ln}")
            count = manager.structure[selected_floor][level]['spots']
            start = manager.structure[selected_floor][level]['start']
            cpr = 10
            rows = (count + cpr - 1) // cpr
            for r in range(rows):
                cols = st.columns(cpr)
                for ci in range(cpr):
                    idx = r * cpr + ci
                    if idx < count:
                        num = start + idx
                        sid = manager.get_spot_id(selected_floor, level, num)
                        info = spots_map.get(sid)
                        if info:
                            is_sel = (selected_spot_id == sid)
                            if info['status'] == 'available':
                                label = f"🟢{num}"
                            elif info['status'] == 'subscriber_out':
                                label = f"🟡{num}"
                            elif info['status'] == 'occupied':
                                sub_id = info.get('subscriber_id')
                                if sub_id and sub_id not in inside_subs:
                                    label = f"🟡{num}"
                                else:
                                    label = f"🔴{num}"
                            else:
                                label = f"⚪{num}"
                            if is_sel:
                                label = f"🔵{num}"
                            with cols[ci]:
                                if st.button(label, key=f"view_spot_{sid}"):
                                    if selected_spot_id == sid:
                                        st.session_state.pop('selected_garage_spot', None)
                                    else:
                                        st.session_state['selected_garage_spot'] = sid
                                    st.rerun()

    selected_spot_id = st.session_state.get('selected_garage_spot')
    if selected_spot_id:
        info = spots_map.get(selected_spot_id)
        if info:
            st.markdown("---")
            st.markdown(f"### 📍 تفاصيل: {get_spot_location(selected_spot_id)}")
            status_map = {'available': '🟢 متاح', 'occupied': '🔴 مشغول',
                          'subscriber_out': '🟡 محفوظ لمشترك (خارج حالياً)'}
            st.write(f"**الحالة:** {status_map.get(info['status'], info['status'])}")
            if info['status'] in ('occupied', 'subscriber_out'):
                sub_id = info.get('subscriber_id')
                if sub_id:
                    sub = manager.get_subscriber(sub_id)
                    if sub:
                        is_inside = sub_id in inside_subs
                        st.write(f"**👤 الاسم:** {sub['name']}")
                        st.write(f"**🚗 السيارة:** {sub['car_number']}")
                        st.write(f"**📱 الهاتف:** {sub['phone']}")
                        st.write(f"**📅 نهاية الاشتراك:** {sub['subscription_end'][:10] if sub['subscription_end'] else ''}")
                        st.write(f"**الحضور:** {'🟢 داخل الجراج' if is_inside else '🔴 خارج الجراج (المكان متاح مؤقتاً)'}")
                        c1, c2, c3 = st.columns(3)
                        with c1:
                            if st.button("🔄 تجديد", key=f"gr_{sub_id}"):
                                st.session_state['renew_subscriber_id'] = sub_id
                                st.session_state['_goto_page'] = "👤 إدارة المشتركين"
                                st.rerun()
                        with c2:
                            if st.button("🎫 كارت", key=f"gc_{sub_id}"):
                                st.session_state['show_subscriber_card'] = sub_id
                                st.session_state['_goto_page'] = "👤 إدارة المشتركين"
                                st.rerun()
                        with c3:
                            if st.button("✖ إلغاء", key=f"gd_{selected_spot_id}"):
                                st.session_state.pop('selected_garage_spot', None)
                                st.rerun()
                        c4, c5 = st.columns(2)
                        with c4:
                            if is_inside:
                                if st.button("📤 تسجيل خروج المشترك", key=f"exit_sub_{sub_id}", use_container_width=True):
                                    if st.session_state.attendance_manager.record_exit(sub_id):
                                        st.success("✅ تم - المكان أصبح متاحاً للزوار")
                                        time.sleep(0.4)
                                        st.rerun()
                        with c5:
                            if not is_inside:
                                if st.button("📥 تسجيل دخول المشترك", key=f"enter_sub_{sub_id}", use_container_width=True):
                                    if st.session_state.attendance_manager.record_entry(sub_id):
                                        st.success("✅ تم")
                                        time.sleep(0.4)
                                        st.rerun()
                else:
                    visitor = visitor_manager.get_visitor_by_spot(selected_spot_id)
                    if visitor:
                        st.write(f"**🚗 زائر:** {visitor['vehicle_number']}")
                        st.write(f"**📱 الهاتف:** {visitor.get('phone', '') or '-'}")
                        st.write(f"**🎫 التذكرة:** {visitor['ticket_number']}")
                        st.write(f"**⏱ الدخول:** {visitor['entry_time'][:16]}")
                        try:
                            et = datetime.fromisoformat(visitor['entry_time'])
                            dur = int((datetime.now() - et).total_seconds() / 60)
                            st.write(f"**⏳ المدة:** {dur} دقيقة")
                        except Exception:
                            pass
                        cc1, cc2 = st.columns(2)
                        with cc1:
                            if st.button("🖨️ إعادة طباعة الإيصال", key=f"reprint_{selected_spot_id}", use_container_width=True, type="primary"):
                                fields = [
                                    {'label': 'التذكرة', 'value': visitor['ticket_number']},
                                    {'label': 'التاريخ', 'value': visitor['entry_time'][:16]},
                                    {'label': 'رقم السيارة', 'value': visitor['vehicle_number']},
                                    {'label': 'النوع', 'value': visitor.get('vehicle_type', 'سيارة')},
                                ]
                                if visitor.get('phone'):
                                    fields.append({'label': 'الهاتف', 'value': visitor['phone']})
                                if visitor.get('spot_id'):
                                    fields.append({'label': 'المكان', 'value': get_spot_location(visitor['spot_id'])})
                                st.session_state['receipt_data'] = {
                                    'title': "🅿️ إيصال دخول (إعادة طباعة)",
                                    'fields': fields,
                                    'qr_data': None,
                                    'barcode_data': visitor['ticket_number'],
                                    'footer_text': "إعادة طباعة - احتفظ بالإيصال",
                                    'movement_number': visitor.get('movement_number')
                                }
                                st.rerun()
                        with cc2:
                            if st.button("✖ إلغاء", key=f"gdv_{selected_spot_id}", use_container_width=True):
                                st.session_state.pop('selected_garage_spot', None)
                                st.rerun()
            else:
                if st.button("✖ إلغاء", key=f"gda_{selected_spot_id}"):
                    st.session_state.pop('selected_garage_spot', None)
                    st.rerun()


# ===================================================================
# ⭐⭐⭐ إدارة المشتركين ⭐⭐⭐
# ===================================================================
def show_renew_subscription(manager, sid):
    st.markdown("## 🔄 تجديد")
    sub = manager.get_subscriber(sid)
    if not sub:
        st.error("غير موجود")
        if st.button("↩️"):
            st.session_state.pop('renew_subscriber_id', None)
            st.rerun()
        return
    if st.button("↩️ العودة"):
        st.session_state.pop('renew_subscriber_id', None)
        st.rerun()
    st.markdown(f"""<div style="background:white; border-radius:10px; padding:20px; margin:10px 0;">
        <h3>👤 {sub.get('name', '')}</h3>
        <p><strong>السيارة:</strong> {sub.get('car_number', '')}</p>
        <p><strong>الحالي:</strong> {sub.get('subscription_type', '')}</p>
        <p><strong>ينتهي:</strong> {sub.get('subscription_end', '')[:10] if sub.get('subscription_end') else ''}</p>
    </div>""", unsafe_allow_html=True)
    with st.form("renew_form"):
        nt = st.selectbox("📅 النوع", list(manager.subscription_plans.keys()))
        c1, c2 = st.columns(2)
        with c1:
            ns = st.date_input("📅 البداية", datetime.now())
        with c2:
            days = manager.subscription_plans.get(nt, 30)
            ne = st.date_input("📅 النهاية", datetime.now() + timedelta(days=days))
        c1, c2 = st.columns(2)
        with c1:
            if st.form_submit_button("🔄 تجديد", use_container_width=True):
                if manager.renew_subscription(sid, nt, 0, ns.isoformat(), ne.isoformat()):
                    st.success("✅ تم التجديد بنجاح")
                    st.session_state.pop('renew_subscriber_id', None)
                    time.sleep(0.2)
                    st.rerun()
        with c2:
            if st.form_submit_button("↩️ إلغاء", use_container_width=True):
                st.session_state.pop('renew_subscriber_id', None)
                st.rerun()


def show_edit_subscriber(manager, sid):
    st.markdown("## ✏️ تعديل")
    sub = manager.get_subscriber(sid)
    if not sub:
        st.error("غير موجود")
        return
    if st.button("↩️ العودة"):
        st.session_state.pop('edit_subscriber', None)
        st.rerun()
    with st.form("edit_sub"):
        c1, c2 = st.columns(2)
        with c1:
            n = st.text_input("👤 الاسم *", sub.get('name', ''))
            w = st.text_input("🏢 جهة العمل", sub.get('workplace', ''))
            cn = st.text_input("🚗 رقم الكارت *", sub.get('car_number', ''))
        with c2:
            ct = st.text_input("🚙 النوع", sub.get('car_type', ''))
            cc = st.text_input("🎨 رقم السيارة", sub.get('car_color', ''))
            ph = st.text_input("📱 الهاتف *", sub.get('phone', ''))
        stype = st.selectbox("📅 الاشتراك", list(manager.subscription_plans.keys()),
                             index=list(manager.subscription_plans.keys()).index(sub.get('subscription_type', 'شهري')) if sub.get('subscription_type') in manager.subscription_plans else 0)
        c3, c4 = st.columns(2)
        with c3:
            sd = st.date_input("📅 البداية", datetime.fromisoformat(sub['subscription_start']) if sub.get('subscription_start') else datetime.now())
        with c4:
            ed = st.date_input("📅 النهاية", datetime.fromisoformat(sub['subscription_end']) if sub.get('subscription_end') else datetime.now() + timedelta(days=30))
        stt = st.selectbox("📌 الحالة", ['active', 'inactive'], index=0 if sub.get('status') == 'active' else 1)
        c1, c2 = st.columns(2)
        with c1:
            if st.form_submit_button("💾 حفظ", use_container_width=True):
                if n and cn and ph:
                    d = {'name': n, 'workplace': w, 'car_number': cn, 'car_type': ct, 'car_color': cc, 'phone': ph,
                         'subscription_type': stype, 'subscription_start': sd.isoformat(),
                         'subscription_end': ed.isoformat(), 'payment_amount': sub.get('payment_amount', 0), 'status': stt}
                    if manager.update_subscriber(sid, d):
                        st.success("✅")
                        st.session_state.pop('edit_subscriber', None)
                        st.rerun()
                else:
                    st.error("❌ املأ الحقول *")
        with c2:
            if st.form_submit_button("↩️ إلغاء", use_container_width=True):
                st.session_state.pop('edit_subscriber', None)
                st.rerun()


def _show_change_spot(manager, sid):
    st.markdown("## 🔀 تغيير مكان المشترك")
    sub = manager.get_subscriber(sid)
    if not sub:
        st.error("غير موجود")
        return
    if st.button("↩️ العودة"):
        st.session_state.pop('change_spot_sid', None)
        st.session_state.pop('change_spot_new', None)
        st.rerun()
    st.info(f"**الاسم:** {sub['name']} | **المكان الحالي:** {get_spot_location(sub['spot_id']) if sub.get('spot_id') else 'غير مخصص'}")

    c1, c2 = st.columns(2)
    with c1:
        floors = sorted(manager.structure.keys())
        f = st.selectbox("اختر الدور:", floors, format_func=get_floor_name, key="chg_floor")
    with c2:
        levels = sorted(manager.structure[f].keys())
        l = st.selectbox("اختر المستوى:", levels, format_func=lambda x: manager.structure[f][x]['name'], key="chg_level")

    spots_map = get_all_spots_map(manager.db.db_path)
    count = manager.structure[f][l]['spots']
    start = manager.structure[f][l]['start']
    cpr = 10
    rows = (count + cpr - 1) // cpr
    selected_new = st.session_state.get('change_spot_new')
    for r in range(rows):
        cols = st.columns(cpr)
        for ci in range(cpr):
            ix = r * cpr + ci
            if ix < count:
                num = start + ix
                sid_ = manager.get_spot_id(f, l, num)
                info = spots_map.get(sid_)
                if info and info['status'] == 'available':
                    is_sel = (selected_new == sid_)
                    label = f"🔵{num}" if is_sel else f"🟢{num}"
                    with cols[ci]:
                        if st.button(label, key=f"chg_{sid_}"):
                            st.session_state['change_spot_new'] = sid_
                            st.rerun()
    if selected_new:
        st.success(f"المكان المختار: {get_spot_location(selected_new)}")
        if st.button("✅ تأكيد التغيير", type="primary", use_container_width=True):
            if manager.change_spot(sid, selected_new):
                st.success("✅ تم التغيير")
                st.session_state.pop('change_spot_sid', None)
                st.session_state.pop('change_spot_new', None)
                time.sleep(0.3)
                st.rerun()
            else:
                st.error("❌ فشل")


def _gen_sub_card(sub):
    fields = [
        {'label': 'المعرف', 'value': sub.get('id', '')},
        {'label': 'الاسم', 'value': sub.get('name', '')},
        {'label': 'جهة العمل', 'value': sub.get('workplace', '')},
        {'label': 'رقم الكارت', 'value': sub.get('car_number', '')},
        {'label': 'نوع السيارة', 'value': sub.get('car_type', '')},
        {'label': 'رقم السيارة', 'value': sub.get('car_color', '')},
        {'label': 'الهاتف', 'value': sub.get('phone', '')},
        {'label': 'نوع الاشتراك', 'value': sub.get('subscription_type', '')},
        {'label': 'بداية', 'value': sub.get('subscription_start', '')[:10] if sub.get('subscription_start') else ''},
        {'label': 'نهاية', 'value': sub.get('subscription_end', '')[:10] if sub.get('subscription_end') else ''},
        {'label': 'المكان', 'value': get_spot_location(sub.get('spot_id', '')) if sub.get('spot_id') else 'غير مخصص'}
    ]
    qr_data = sub['car_number']
    qr_b64 = generate_qr_base64(qr_data)
    fields_html = "".join([f'<div style="display:flex; justify-content:space-between; padding:2px 0; border-bottom:1px dashed #ccc; font-size:11px;"><span style="font-weight:bold;">{f["label"]}:</span><span>{f["value"]}</span></div>' for f in fields])
    return f"""<div style="background:white; direction:rtl; font-family:Arial; max-width:80mm; margin:0 auto; padding:5px; font-size:11px;">
        <div style="text-align:center; border-bottom:2px solid #000; padding-bottom:3px; margin-bottom:3px;">
            <div style="font-size:16px; font-weight:bold;">🚗 كارت المشترك</div>
        </div>
        {'<div style="text-align:center;"><img src="data:image/png;base64,' + qr_b64 + '" style="width:100px;height:100px;"></div>' if qr_b64 else ''}
        <div>{fields_html}</div>
        <div style="text-align:center; border-top:2px solid #000; padding-top:3px; margin-top:3px; font-size:10px; color:#666;">
            {datetime.now().strftime('%Y-%m-%d %H:%M')}
        </div>
        <div style="text-align:center; margin-top:3px; font-size:9px; color:#999;">
            تم التطوير بواسطة: {DEVELOPER_NAME} | {DEVELOPER_PHONE}
        </div>
    </div>
    <div class="no-print" style="text-align:center; margin-top:10px;">
        <button onclick="window.print()" style="padding:10px 30px; background:#667eea; color:white; border:none; border-radius:6px; font-weight:bold; cursor:pointer; font-size:16px;">🖨️ طباعة</button>
    </div>"""

def _gen_barcode_html(sub):
    b64 = generate_barcode_base64(sub.get('car_number', ''))   # ⭐ car_number بدل id
    return f"""<div style="background:white; direction:rtl; text-align:center; padding:10px;">
        <div style="font-size:14px; font-weight:bold;">{sub.get('name','')}</div>
        <div style="font-size:12px; color:#555;">رقم السيارة: {sub.get('car_number','')}</div>
        {'<img src="data:image/png;base64,' + b64 + '" style="width:100%;max-width:280px;">' if b64 else ''}
        <div style="font-size:12px; margin-top:3px; color:#888;">رقم الكارت: {sub.get('car_number','')}</div>
    </div>
    <div class="no-print" style="text-align:center; margin-top:10px;">
        <button onclick="window.print()" style="padding:10px 30px; background:#667eea; color:white; border:none; border-radius:6px; font-weight:bold; cursor:pointer; font-size:16px;">🖨️ طباعة</button>
    </div>"""

def manage_subscribers(manager):
    st.markdown("## 👤 إدارة المشتركين")
    ur = st.session_state.get('user_role', 'user')
    is_admin = ur in ['admin', 'manager', 'subscriber', 'super_admin']

    if st.session_state.get('show_subscriber_card'):
        sub = manager.get_subscriber(st.session_state['show_subscriber_card'])
        if sub:
            components.html(_gen_sub_card(sub), height=550, scrolling=False)
            if st.button("✖ إغلاق"):
                st.session_state.pop('show_subscriber_card', None)
                st.rerun()
        else:
            st.session_state.pop('show_subscriber_card', None)
            st.rerun()
        return

    if st.session_state.get('renew_subscriber_id'):
        show_renew_subscription(manager, st.session_state['renew_subscriber_id'])
        return
    if st.session_state.get('edit_subscriber'):
        show_edit_subscriber(manager, st.session_state['edit_subscriber'])
        return
    if st.session_state.get('change_spot_sid'):
        _show_change_spot(manager, st.session_state['change_spot_sid'])
        return

    tabs = st.tabs(["➕ إضافة مشترك", "📋 قائمة المشتركين", "🔄 تجديد"])

    with tabs[0]:
        with st.form("add_sub_form_stable", clear_on_submit=True):
            c1, c2 = st.columns(2)
            with c1:
                n = st.text_input("👤 الاسم *", key="add_n")
                w = st.text_input("🏢 جهة العمل", key="add_w")
                cn = st.text_input("🚗 رقم الكارت *", key="add_cn")
            with c2:
                ct = st.text_input("🚙 النوع", key="add_ct")
                cc = st.text_input("🎨 رقم السيارة", key="add_cc")
                ph = st.text_input("📱 الهاتف *", key="add_ph")

            stype = st.selectbox("📅 الاشتراك", list(manager.subscription_plans.keys()), key="add_stype")
            sd = st.date_input("📅 البداية", datetime.now(), key="add_sd")
            days = manager.subscription_plans.get(stype, 30)
            ed = st.date_input("📅 النهاية", sd + timedelta(days=days), key="add_ed")

            _submitted = st.form_submit_button("✅ إضافة", use_container_width=True)

            if _submitted:
                if n and cn and ph:
                    d = {
                        'name': n, 'workplace': w, 'car_number': cn,
                        'car_type': ct, 'car_color': cc, 'phone': ph,
                        'subscription_type': stype, 'payment_amount': 0,
                        'subscription_start': sd.isoformat(),
                        'subscription_end': ed.isoformat()
                    }
                    sid = manager.add_subscriber(d)
                    if sid:
                        st.success(f"✅ تمت الإضافة: {sid}")
                        clear_all_caches()
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("❌ رقم الكارت مستخدم بالفعل")
                else:
                    st.error("❌ املأ الحقول المطلوبة (*)")
    with tabs[1]:
        page_size = 10
        c1, c2, c3 = st.columns(3)
        with c1:
            nf = st.text_input("الاسم", key="sub_name_f")
        with c2:
            cf = st.text_input("رقم السيارة", key="sub_car_f")
        with c3:
            pf = st.text_input("الهاتف", key="sub_phone_f")
        filters = {}
        if nf: filters['name'] = nf
        if cf: filters['car_number'] = cf
        if pf: filters['phone'] = pf

        total = manager.count_subscribers(filters=filters)
        tp = max(1, (total + page_size - 1) // page_size)
        page = st.number_input("الصفحة", min_value=1, max_value=tp, value=1, step=1, key="sub_page")
        offset = (page - 1) * page_size
        subs = manager.get_subscribers_paginated(page_size, offset, filters=filters)
        inside_subs = get_cached_inside_subscribers(manager.db.db_path)

        if subs:
            st.write(f"إجمالي: {total} (صفحة {page}/{tp})")
            for i, row in enumerate(subs, 1):
                ed = datetime.fromisoformat(row[9]) if row[9] else None
                dl = (ed - datetime.now()).days if ed else None
                if dl is not None:
                    status = "❌ منتهي" if dl < 0 else (f"🟡 {dl} يوم" if dl <= 7 else "✅ نشط")
                else:
                    status = "?"
                inside_marker = " 🟢" if row[0] in inside_subs else " 🔴"
                with st.expander(f"#{i} {row[1]} - {status}{inside_marker}"):
                    c1, c2 = st.columns(2)
                    with c1:
                        st.write(f"**المعرف:** {row[0]}")
                        st.write(f"**الاسم:** {row[1]}")
                        st.write(f"**جهة العمل:** {row[2] or ''}")
                        st.write(f"**رقم الكارت:** {row[3] or ''}")
                        st.write(f"**النوع:** {row[4] or ''}")
                    with c2:
                        st.write(f"**رقم السيارة:** {row[5] or ''}")
                        st.write(f"**الهاتف:** {row[6] or ''}")
                        st.write(f"**الاشتراك:** {row[7] or ''}")
                        st.write(f"**بداية:** {row[8][:10] if row[8] else ''}")
                        st.write(f"**نهاية:** {row[9][:10] if row[9] else ''}")
                        if row[13]:
                            st.write(f"**📍 المكان:** {get_spot_location(row[13])}")
                    # ⭐ أزرار التحكم في المشترك
                    nb = 8 if ur == 'super_admin' else (7 if is_admin else 3)
                    bcols = st.columns(nb)

                    with bcols[0]:
                        if st.button("🔄 تجديد", key=f"rn_{row[0]}"):
                            st.session_state['renew_subscriber_id'] = row[0]
                            st.rerun()

                    if is_admin:
                        with bcols[1]:
                            if st.button("✏️ تعديل", key=f"ed_{row[0]}"):
                                st.session_state['edit_subscriber'] = row[0]
                                st.rerun()

                        with bcols[2]:
                            if st.button("🗑️ حذف", key=f"dl_{row[0]}"):
                                if manager.delete_subscriber(row[0]):
                                    st.success("✅")
                                    st.rerun()

                        with bcols[3]:
                            if st.button("🎫 كارت", key=f"cd_{row[0]}"):
                                st.session_state['show_subscriber_card'] = row[0]
                                st.rerun()

                        with bcols[4]:
                            if st.button("❌ إلغاء مكان", key=f"un_{row[0]}"):
                                if manager.unassign_spot(row[0]):
                                    st.success("✅ تم إلغاء التخصيص")
                                    st.rerun()
                                else:
                                    st.warning("لا يوجد مكان")

                        with bcols[5]:
                            if st.button("🔀 تغيير مكان", key=f"ch_{row[0]}"):
                                st.session_state['change_spot_sid'] = row[0]
                                st.rerun()

                        with bcols[6]:
                            if st.button("🏷️ باركود", key=f"bc_{row[0]}"):
                                s = manager.get_subscriber(row[0])
                                if s:
                                    components.html(_gen_barcode_html(s), height=400, scrolling=False)

                        # ⭐ زر إيقاف/تشغيل الخدمة (سوبر أدمن فقط)
                        if ur == 'super_admin':
                            with bcols[7]:
                                sub_data = manager.get_subscriber(row[0])
                                is_disabled = sub_data.get('app_service_disabled', 0) if sub_data else 0
                                btn_label = "▶️ تشغيل" if is_disabled else "⛔ إيقاف"
                                if st.button(btn_label, key=f"disable_{row[0]}"):
                                    new_val = 0 if is_disabled else 1
                                    manager.db.execute_query(
                                        "UPDATE subscribers SET app_service_disabled=? WHERE id=?",
                                        (new_val, row[0]), commit=True
                                    )
                                    clear_all_caches()
                                    st.success("✅ تم التحديث")
                                    time.sleep(0.3)
                                    st.rerun()
    with tabs[2]:
        subs = manager.get_all_subscribers()
        if subs:
            opts = {r[0]: f"{r[1]} - {r[3]}" for r in subs}
            sel = st.selectbox("اختر مشترك:", list(opts.keys()), format_func=lambda x: opts[x])
            if sel and st.button("🔄 تجديد", use_container_width=True):
                st.session_state['renew_subscriber_id'] = sel
                st.rerun()
        else:
            st.warning("لا يوجد مشتركين")


# ===================================================================
# ⭐⭐⭐ تخصيص مكان ⭐⭐⭐
# ===================================================================
def assign_spot_page(manager):
    st.markdown("## 📝 تخصيص مكان")
    floors = sorted(manager.structure.keys())
    if not floors:
        st.warning("⚠️ لا يوجد أدوار.")
        return
    c1, c2 = st.columns(2)
    with c1:
        f = st.selectbox("اختر الدور:", floors, format_func=get_floor_name, key="assign_floor")
    with c2:
        levels = sorted(manager.structure[f].keys())
        l = st.selectbox("اختر المستوى:", levels, format_func=lambda x: manager.structure[f][x]['name'], key="assign_level")

    st.markdown("### الأماكن المتاحة")
    spots_map = get_all_spots_map(manager.db.db_path)
    count = manager.structure[f][l]['spots']
    start = manager.structure[f][l]['start']
    avail_count = 0
    cpr = 10
    rows = (count + cpr - 1) // cpr
    selected = st.session_state.get('assign_spot_id')
    for r in range(rows):
        cols = st.columns(cpr)
        for ci in range(cpr):
            ix = r * cpr + ci
            if ix < count:
                num = start + ix
                sid = manager.get_spot_id(f, l, num)
                info = spots_map.get(sid)
                if info and info['status'] == 'available':
                    avail_count += 1
                    is_sel = (selected == sid)
                    label = f"🔵{num}" if is_sel else f"🟢{num}"
                    with cols[ci]:
                        if st.button(label, key=f"av_{sid}"):
                            st.session_state['assign_spot_id'] = sid
                            st.rerun()

    if avail_count > 0:
        st.info(f"✅ {avail_count} مكان متاح")
        if selected:
            st.success(f"المكان المختار: {get_spot_location(selected)}")
            subs = manager.get_all_subscribers()
            if subs:
                opts = {r[0]: f"{r[1]} - {r[3]}" for r in subs}
                sel = st.selectbox("اختر مشترك:", list(opts.keys()), format_func=lambda x: opts[x])
                if st.button("✅ تخصيص", use_container_width=True):
                    if manager.assign_spot(selected, sel):
                        st.success("✅")
                        st.session_state.pop('assign_spot_id', None)
                        st.rerun()
                    else:
                        st.error("❌ فشل")
    else:
        st.warning("⚠️ جميع الأماكن مشغولة")


# ===================================================================
# ⭐⭐⭐ صفحة الدخول (مع Session Token) ⭐⭐⭐
# ===================================================================
def db_has_open_shift(db):
    try:
        return db.get_current_shift() is not None
    except Exception:
        return False


def entry_page(manager, visitor_manager, attendance_manager):
    st.markdown("## 📥 الدخول")

    if not db_has_open_shift(manager.db):
        st.error("⚠️ **يجب فتح وردية أولاً!**")
        st.info("👉 اذهب إلى القائمة الجانبية واضغط '🟢 فتح وردية'.")
        return

    if st.toggle("🔍 بحث متكامل قبل الدخول", key="entry_show_search"):
        render_unified_search(manager, visitor_manager, key_prefix="entry")
    st.markdown("---")
    tab1, tab2 = st.tabs(["🚗 دخول زائر", "👤 دخول مشترك"])

    with tab1:
        st.markdown("**📌 اختر مكاناً متاحاً (يشمل أماكن المشتركين الخارجين) ثم أدخل البيانات**")
        floors = sorted(manager.structure.keys())
        sf = st.selectbox("اختر الدور:", floors, format_func=get_floor_name, key="entry_floor")
        levels = sorted(manager.structure[sf].keys())
        sl = st.selectbox("اختر المستوى:", levels, format_func=lambda x: manager.structure[sf][x]['name'], key="entry_level")

        spots_map = get_all_spots_map(manager.db.db_path)
        inside_subs = get_cached_inside_subscribers(manager.db.db_path)
        count = manager.structure[sf][sl]['spots']
        start = manager.structure[sf][sl]['start']
        cpr = 10
        rows = (count + cpr - 1) // cpr

        available_count = 0
        for r in range(rows):
            cols = st.columns(cpr)
            for ci in range(cpr):
                ix = r * cpr + ci
                if ix < count:
                    num = start + ix
                    sid = manager.get_spot_id(sf, sl, num)
                    info = spots_map.get(sid)
                    if info and manager.is_spot_available_for_visitor(info, inside_subs):
                        available_count += 1
                        is_sel = st.session_state.get('selected_entry_spot') == sid
                        if info['status'] == 'available' or not info.get('subscriber_id'):
                            icon = "🟢"
                        else:
                            icon = "🟡"
                        label = f"🔵{num}" if is_sel else f"{icon}{num}"
                        with cols[ci]:
                            if st.button(label, key=f"entry_spot_{sid}"):
                                st.session_state['selected_entry_spot'] = sid
                                st.rerun()

        if available_count == 0:
            st.warning("⚠️ لا توجد أماكن متاحة في هذا المستوى")
        else:
            st.caption(f"🟢 متاح | 🟡 محفوظ لمشترك (خارج حالياً) - الإجمالي: {available_count}")

        if 'selected_entry_spot' in st.session_state:
            st.info(f"**المكان المختار:** {get_spot_location(st.session_state['selected_entry_spot'])}")
            if st.button("إلغاء المكان", key="clr_entry_spot"):
                st.session_state.pop('selected_entry_spot', None)
                st.rerun()

        with st.form("visitor_form"):
            c1, c2 = st.columns(2)
            with c1:
                vn = st.text_input("🚗 رقم السيارة *")
            with c2:
                vt = st.selectbox("🚙 النوع", ['سيارة', 'شاحنة', 'دراجة نارية', 'حافلة'])
            vp = st.text_input("📱 الهاتف (اختياري)")
            if st.form_submit_button("✅ تسجيل الدخول", use_container_width=True):
                if not vn:
                    st.error("❌ أدخل رقم السيارة")
                elif vn.strip().upper().startswith('SUB_') or vn.strip().upper().startswith('SUB-'):
                    st.error("❌ هذا رقم كارت مشترك! استخدم تبويب '👤 دخول مشترك' من فضلك")
                else:
                    existing_sub = manager.get_subscriber_by_car_number(vn.strip())
                    if existing_sub:
                        st.error(f"❌ **هذا الرقم مسجل كمشترك بالفعل!**")
                        st.warning(f"👤 **الاسم:** {existing_sub.get('name', '')} | 🚗 **الكارت:** {existing_sub.get('car_number', '')}")
                        st.info("👉 استخدم تبويب **'👤 دخول مشترك'** لتسجيل دخوله")
                    elif not st.session_state.get('selected_entry_spot'):
                        st.error("❌ اختر مكاناً")
                    else:
                        sid = st.session_state['selected_entry_spot']
                        ticket, mv = visitor_manager.entry_visitor(vn, vt, sid, vp)
                        if ticket:
                            fields = [
                                {'label': 'التذكرة', 'value': ticket},
                                {'label': 'التاريخ', 'value': datetime.now().strftime('%Y-%m-%d %H:%M')},
                                {'label': 'رقم السيارة', 'value': vn},
                                {'label': 'النوع', 'value': vt},
                            ]
                            if vp: fields.append({'label': 'الهاتف', 'value': vp})
                            if sid:
                                fields.append({'label': 'المكان', 'value': get_spot_location(sid)})
                                st.session_state.pop('selected_entry_spot', None)
                            st.session_state['receipt_data'] = {
                                'title': "🅿️ إيصال دخول", 'fields': fields,
                                'qr_data': None, 'barcode_data': ticket,
                                'footer_text': "احتفظ بالإيصال", 'movement_number': mv
                            }
                            st.rerun()

    with tab2:
        st.markdown("**📌 أدخل رقم الكارت أو امسح QR**")
        ident = st.text_input("🔍 رقم الكارت / المعرف / QR", key="entry_sub_id",
                               placeholder="امسح الـ QR أو اكتب رقم الكارت")

        if ident:
            sub = manager.get_subscriber_by_id_or_car(ident.strip())
            if not sub:
                st.error("❌ غير موجود")
            else:
                st.write(f"**الاسم:** {sub['name']}")
                st.write(f"**الاشتراك:** {sub['subscription_type']}")
                st.write(f"**ينتهي:** {sub['subscription_end'][:10] if sub.get('subscription_end') else ''}")
                if sub.get('spot_id'):
                    st.info(f"🅿️ **رقم مكان الركنة:** {get_spot_location(sub['spot_id'])}")
                else:
                    st.warning("⚠️ لا يوجد مكان ركنة مخصص لهذا المشترك")

                # ⭐ فحص اشتراك التطبيق
                if not is_subscriber_app_active(sub):
                    st.error("❌ **اشتراكك في التطبيق منتهي أو غير مفعّل**")
                    st.warning("💡 يجب دفع اشتراك استخدام التطبيق أولاً")
                    st.info(f"👉 **حوّل {APP_FEE_DEFAULT:.0f} جنيه عبر InstaPay إلى:** `{INSTAPAY_NUMBER}`")
                else:
                    current_att = attendance_manager.get_current_status(sub['id'])
                    if current_att:
                        st.success(f"🕐 **وقت الدخول الحالي:** {current_att['entry_time'][:16]}")
                        st.info("🟢 داخل بالفعل")
                    else:
                        if sub.get('subscription_end') and datetime.fromisoformat(sub['subscription_end']) < datetime.now():
                            st.error("⚠️ اشتراك الجراج منتهي!")
                        else:
                            if st.button("📥 تسجيل دخول", key="entry_sub_btn", use_container_width=True):
                                if attendance_manager.record_entry(sub['id']):
                                    st.success("✅ تم")
                                    time.sleep(0.3)
                                    st.rerun()
                                else:
                                    st.error("❌ فشل - تحقق من اشتراك التطبيق")

# ===================================================================
# ⭐⭐⭐ صفحة الخروج ⭐⭐⭐
# ===================================================================
def exit_page(manager, visitor_manager, attendance_manager):
    st.markdown("## 📤 الخروج")

    if not db_has_open_shift(manager.db):
        st.error("⚠️ **يجب فتح وردية أولاً!**")
        return

    if st.toggle("🔍 بحث متكامل قبل الخروج", key="exit_show_search"):
        render_unified_search(manager, visitor_manager, key_prefix="exit")
    st.markdown("---")
    tab1, tab2 = st.tabs(["🚗 خروج زائر", "👤 خروج مشترك"])

    with tab1:
        st.markdown("**📌 أدخل رقم التذكرة أو السيارة**")
        ti = st.text_input("🔍 رقم التذكرة/السيارة", key="exit_ticket")
        if ti:
            vis = visitor_manager.get_visitor_by_ticket(ti)
            if not vis:
                for v in visitor_manager.get_active_visitors():
                    if v['vehicle_number'] == ti:
                        vis = v
                        break
            if vis:
                if vis['status'] == 'inside':
                    et = datetime.fromisoformat(vis['entry_time'])
                    dur = int((datetime.now() - et).total_seconds() / 60)
                    settings = {}
                    for s in manager.db.execute_query('SELECT key, value FROM parking_settings', fetch=True):
                        settings[s['key']] = s['value']
                    fm = int(settings.get('free_minutes', 10))
                    amt = visitor_manager.calculate_amount(dur, settings)
                    is_free = dur <= fm
                    st.info(f"""**بيانات:**
- التذكرة: {vis['ticket_number']}
- الدخول: {et.strftime('%Y-%m-%d %H:%M')}
- المدة: {dur} دقيقة
- {'🟢 خروج مجاني' if is_free else f'💰 المبلغ: {amt:.2f} جنيه'}
- السيارة: {vis['vehicle_number']}""")
                    if st.button("💰 حساب وخروج", use_container_width=True):
                        r = visitor_manager.exit_visitor(vis['ticket_number'])
                        if r:
                            if r.get('is_free_exit'):
                                fields = [
                                    {'label': 'التذكرة', 'value': r['ticket_number']},
                                    {'label': 'الدخول', 'value': r['entry_time'].strftime('%Y-%m-%d %H:%M')},
                                    {'label': 'الخروج', 'value': datetime.now().strftime('%Y-%m-%d %H:%M')},
                                    {'label': 'المدة', 'value': f"{r['duration']} دقيقة"},
                                    {'label': 'المبلغ', 'value': "0 جنيه (مجاني)"},
                                ]
                                title = "🅿️ إيصال خروج مجاني"
                                footer = "خروج مجاني"
                            else:
                                fields = [
                                    {'label': 'التذكرة', 'value': r['ticket_number']},
                                    {'label': 'الدخول', 'value': r['entry_time'].strftime('%Y-%m-%d %H:%M')},
                                    {'label': 'الخروج', 'value': datetime.now().strftime('%Y-%m-%d %H:%M')},
                                    {'label': 'المدة', 'value': f"{r['duration']} دقيقة"},
                                    {'label': 'المبلغ', 'value': f"{r['amount']:.2f} جنيه"},
                                ]
                                if r.get('phone'):
                                    fields.append({'label': 'الهاتف', 'value': r.get('phone', '')})
                                if r.get('spot_id'):
                                    fields.append({'label': 'المكان', 'value': get_spot_location(r['spot_id'])})
                                title = "🅿️ إيصال خروج"
                                footer = "تم الدفع"
                            st.session_state['receipt_data'] = {
                                'title': title, 'fields': fields,
                                'qr_data': None, 'barcode_data': r['ticket_number'],
                                'footer_text': footer,
                                'movement_number': r.get('movement_number')
                            }
                            st.rerun()
                else:
                    st.warning("⚠️ خارج بالفعل")
            else:
                st.error("❌ غير موجود")

    with tab2:
        ident = st.text_input("🔍 المعرف/رقم السيارة", key="exit_sub_id")
        if ident:
            sub = manager.get_subscriber_by_id_or_car(ident)
            if not sub:
                st.error("❌ غير موجود")
            else:
                st.write(f"**الاسم:** {sub['name']}")
                if sub.get('spot_id'):
                    st.info(f"🅿️ **رقم مكان الركنة:** {get_spot_location(sub['spot_id'])}")
                cur = attendance_manager.get_current_status(sub['id'])
                if not cur:
                    st.info("🔴 خارج الجراج")
                else:
                    st.success(f"🕐 **وقت الدخول:** {cur['entry_time'][:16]}")
                    if st.button("📤 خروج", key="exit_sub_btn", use_container_width=True):
                        if attendance_manager.record_exit(sub['id']):
                            st.success("✅ تم - المكان أصبح متاحاً للزوار")
                            time.sleep(0.3)
                            st.rerun()


# ===================================================================
# ⭐⭐⭐ التقارير ⭐⭐⭐
# ===================================================================
def show_visitors_financial_report(visitor_manager):
    st.markdown("### 📊 ملخص الزوار")
    s = visitor_manager.get_visitors_summary()
    c1, c2, c3 = st.columns(3)
    with c1: st.metric("🚗 نشطين", s['active'])
    with c2: st.metric("💰 الإيرادات", f"{s['total_revenue']:,.0f}")
    with c3: st.metric("📅 اليوم", s['today_visitors'])

    vs = visitor_manager.get_visitors_financial_report()
    if vs:
        df = pd.DataFrame(vs)
        df = df.rename(columns={'ticket_number': 'التذكرة', 'entry_time': 'الدخول', 'exit_time': 'الخروج',
                                'vehicle_number': 'السيارة', 'duration_minutes': 'المدة', 'amount': 'المبلغ',
                                'payment_status': 'الحالة', 'phone': 'الهاتف', 'month': 'الشهر'})
        df['المبلغ'] = pd.to_numeric(df['المبلغ'], errors='coerce')
        mr = df.groupby('الشهر')['المبلغ'].sum().reset_index()
        mr.columns = ['الشهر', 'الإيرادات']
        fig = px.bar(mr, x='الشهر', y='الإيرادات', title='الإيرادات الشهرية')
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(df, use_container_width=True)
    else:
        st.info("لا توجد بيانات زوار بعد")


def show_financial_reports(manager, visitor_manager):
    st.markdown("## 💰 التقارير المالية")
    t1, t2, t3, t4 = st.tabs(["📊 الملخص", "💰 الزوار", "📈 الإيرادات", "📋 المعاملات"])

    with t1:
        fin = manager.get_financial_summary()
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown(f"""<div class="metric-card" style="border-right-color: #4CAF50;"><div class="metric-value" style="color: #4CAF50;">{fin['total_income']:,.0f}</div><div class="metric-label">💰 الإيرادات</div></div>""", unsafe_allow_html=True)
        with c2:
            st.markdown(f"""<div class="metric-card" style="border-right-color: #ff9800;"><div class="metric-value" style="color: #ff9800;">{fin['total_pending']:,.0f}</div><div class="metric-label">⏳ معلقة</div></div>""", unsafe_allow_html=True)
        with c3:
            st.markdown(f"""<div class="metric-card"><div class="metric-value">{fin['total_records']}</div><div class="metric-label">📝 المعاملات</div></div>""", unsafe_allow_html=True)
        if fin['monthly_income']:
            df = pd.DataFrame([{'الشهر': m, 'الإيرادات': a} for m, a in sorted(fin['monthly_income'].items())])
            fig = px.bar(df, x='الشهر', y='الإيرادات', title='الإيرادات الشهرية')
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("لا توجد إيرادات شهرية بعد")

    with t2:
        show_visitors_financial_report(visitor_manager)

    with t3:
        try:
            with manager.db.get_connection() as conn:
                c = conn.cursor()
                yr = datetime.now().year
                c.execute("SELECT strftime('%m', date), COALESCE(SUM(amount), 0) FROM financial_records WHERE status='مدفوع' AND strftime('%Y', date)=? GROUP BY 1 ORDER BY 1", (str(yr),))
                yearly = c.fetchall()
            if yearly:
                mn = ['يناير', 'فبراير', 'مارس', 'أبريل', 'مايو', 'يونيو', 'يوليو', 'أغسطس', 'سبتمبر', 'أكتوبر', 'نوفمبر', 'ديسمبر']
                data = [{'الشهر': mn[int(r[0]) - 1], 'الإيرادات': r[1]} for r in yearly]
                df = pd.DataFrame(data)
                fig = px.line(df, x='الشهر', y='الإيرادات', title=f'الإيرادات {yr}', markers=True)
                st.plotly_chart(fig, use_container_width=True)
                st.metric(f"إجمالي {yr}", f"{sum(r[1] for r in yearly):,.0f} جنيه")
            else:
                st.info(f"لا توجد إيرادات لسنة {yr} بعد")
        except Exception as e:
            st.error(f"خطأ: {e}")

    with t4:
        rec = manager.get_all_financial_records()
        if rec:
            df = pd.DataFrame([{'المعرف': r[0], 'المشترك': r[1] or '-', 'النوع': r[2], 'المبلغ': r[3],
                                'الحالة': r[4], 'الوصف': r[5], 'التاريخ': r[6]} for r in rec])
            st.dataframe(df, use_container_width=True, height=400)
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button("📥 CSV", csv, f"fin_{datetime.now().strftime('%Y%m%d')}.csv", "text/csv", use_container_width=True)
        else:
            st.info("لا توجد معاملات مالية بعد")


def show_reports(manager):
    st.markdown("## 📊 التقارير")
    t1, t2, t3, t4, t5 = st.tabs(["📈 عامة", "📋 الإشغال", "👤 المشتركين", "🚗 الزوار النشطين", "📥 تصدير"])
    with t1:
        stats = get_cached_dashboard_stats(manager.db.db_path)
        tot = stats['total']; oc = stats['occupied']; sb = stats['subs']
        av = tot - oc
        c1, c2, c3, c4 = st.columns(4)
        with c1: st.metric("🏢 إجمالي", tot)
        with c2: st.metric("🔴 مشغول", oc)
        with c3: st.metric("🟢 متاح", av)
        with c4: st.metric("👤 المشتركين", sb)

    with t2:
        data = []
        summary = manager.get_floor_summary()
        for f in sorted(summary.keys()):
            for ln, stt in summary[f].items():
                data.append({'الدور': get_floor_name(f), 'المستوى': ln, 'إجمالي': stt['total'],
                             'مشغول': stt['occupied'], 'متاح': stt['available'],
                             'نسبة': f"{stt['occupancy_rate']:.1f}%"})
        if data:
            st.dataframe(pd.DataFrame(data), use_container_width=True)

    with t3:
        sn = st.text_input("اسم", key="rep_n")
        sc = st.text_input("سيارة", key="rep_c")
        subs = manager.get_all_subscribers()
        if subs:
            filtered = [r for r in subs if (not sn or sn.lower() in (r[1] or '').lower()) and (not sc or sc in (r[3] or ''))]
            st.write(f"**إجمالي:** {len(filtered)}")
            data = [{'الاسم': r[1], 'رقم الكارت': r[3] or '', 'الهاتف': r[6] or '',
                     'الاشتراك': r[7] or '', 'النهاية': r[9][:10] if r[9] else '',
                     'المكان': get_spot_location(r[13]) if r[13] else 'غير مخصص'} for r in filtered]
            st.dataframe(pd.DataFrame(data), use_container_width=True)

    with t4:
        st.markdown("### 🚗 الزوار الموجودون داخل الجراج حالياً")
        active_visitors = get_cached_active_visitors(manager.db.db_path)
        active_count = len(active_visitors)

        if active_count > 0:
            st.metric("🚗 إجمالي الزوار النشطين", active_count)
            total_minutes = 0
            data = []
            settings = {}
            for s in manager.db.execute_query('SELECT key, value FROM parking_settings', fetch=True):
                settings[s['key']] = s['value']

            for v in active_visitors:
                try:
                    et = datetime.fromisoformat(v['entry_time'])
                    dur = int((datetime.now() - et).total_seconds() / 60)
                    total_minutes += dur
                    amt = 0
                    try:
                        first = float(settings.get('first_hour_price', 20))
                        second = float(settings.get('second_hour_price', 10))
                        free = int(settings.get('free_minutes', 10))
                        grace = int(settings.get('hour_grace_minutes', 10))
                        daily_max = float(settings.get('daily_max_charge', 250))
                        if dur >= 1440:
                            amt = math.ceil(dur / 1440) * daily_max
                        elif dur <= free:
                            amt = 0
                        else:
                            effective = dur - free
                            full_hours = effective // 60
                            remainder = effective - (full_hours * 60)
                            if remainder <= grace:
                                hours = max(1, full_hours)
                            else:
                                hours = full_hours + 1
                            if hours < 1:
                                hours = 1
                            if hours == 1:
                                amt = first
                            else:
                                amt = first + (hours - 1) * second
                            if amt > daily_max:
                                amt = daily_max
                    except Exception:
                        amt = 0

                    data.append({
                        'التذكرة': v['ticket_number'],
                        'السيارة': v.get('vehicle_number', ''),
                        'النوع': v.get('vehicle_type', ''),
                        'الهاتف': v.get('phone', '') or '-',
                        'وقت الدخول': v['entry_time'][:16] if v.get('entry_time') else '',
                        'المدة (دقيقة)': dur,
                        'المكان': get_spot_location(v['spot_id']) if v.get('spot_id') else 'غير مخصص',
                        'المبلغ المتوقع': f"{amt:.2f}"
                    })
                except Exception:
                    pass

            if data:
                df = pd.DataFrame(data)
                st.dataframe(df, use_container_width=True, height=400)

                c1, c2, c3 = st.columns(3)
                with c1: st.metric("⏱️ إجمالي الدقائق", total_minutes)
                with c2: st.metric("⏱️ متوسط المدة", f"{total_minutes // active_count} دقيقة" if active_count > 0 else "0")
                with c3: st.metric("💰 إجمالي المتوقع", f"{sum(float(d['المبلغ المتوقع']) for d in data):,.2f}")

                csv = df.to_csv(index=False).encode('utf-8')
                st.download_button("📥 تصدير CSV", csv, f"active_visitors_{datetime.now().strftime('%Y%m%d_%H%M')}.csv", "text/csv", use_container_width=True)
        else:
            st.info("✅ لا يوجد زوار داخل الجراج حالياً")

    with t5:
        st.markdown("### 📥 تصدير التقارير")

        c1, c2 = st.columns(2)

        with c1:
            st.markdown("#### 📊 Excel")
            if not EXCEL_AVAILABLE:
                st.error("❌ مكتبة openpyxl مش مثبتة")
            else:
                if st.button("📥 تصدير المشتركين (Excel)", use_container_width=True, key="xl_subs"):
                    data = export_to_excel(manager, 'subscribers')
                    if data:
                        st.download_button(
                            "💾 تنزيل الملف",
                            data,
                            f"subscribers_{datetime.now().strftime('%Y%m%d')}.xlsx",
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            key="dl_subs"
                        )

                if st.button("📥 تصدير المعاملات المالية (Excel)", use_container_width=True, key="xl_fin"):
                    data = export_to_excel(manager, 'financial')
                    if data:
                        st.download_button(
                            "💾 تنزيل الملف",
                            data,
                            f"financial_{datetime.now().strftime('%Y%m%d')}.xlsx",
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            key="dl_fin"
                        )

                if st.button("📥 تصدير الزوار (Excel)", use_container_width=True, key="xl_vis"):
                    data = export_to_excel(manager, 'visitors')
                    if data:
                        st.download_button(
                            "💾 تنزيل الملف",
                            data,
                            f"visitors_{datetime.now().strftime('%Y%m%d')}.xlsx",
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            key="dl_vis"
                        )

        with c2:
            st.markdown("#### 📄 PDF")
            if not PDF_AVAILABLE:
                st.error("❌ مكتبات PDF مش مثبتة")
            else:
                if st.button("📄 تصدير المشتركين (PDF)", use_container_width=True, key="pdf_subs"):
                    data = export_to_pdf(manager, 'subscribers')
                    if data:
                        st.download_button(
                            "💾 تنزيل الملف",
                            data,
                            f"subscribers_{datetime.now().strftime('%Y%m%d')}.pdf",
                            "application/pdf",
                            key="dl_pdf_subs"
                        )
                    else:
                        st.warning("لا توجد بيانات")

                if st.button("📄 تصدير المعاملات المالية (PDF)", use_container_width=True, key="pdf_fin"):
                    data = export_to_pdf(manager, 'financial')
                    if data:
                        st.download_button(
                            "💾 تنزيل الملف",
                            data,
                            f"financial_{datetime.now().strftime('%Y%m%d')}.pdf",
                            "application/pdf",
                            key="dl_pdf_fin"
                        )

                if st.button("📄 تصدير الزوار الحاليين (PDF)", use_container_width=True, key="pdf_inside"):
                    data = export_to_pdf(manager, 'inside')
                    if data:
                        st.download_button(
                            "💾 تنزيل الملف",
                            data,
                            f"inside_{datetime.now().strftime('%Y%m%d')}.pdf",
                            "application/pdf",
                            key="dl_pdf_inside"
                        )


def show_alerts(manager):
    st.markdown("## ⚠️ التنبيهات")
    t1, t2 = st.tabs(["🟡 قاربت", "🔴 منتهية"])
    with t1:
        exp = manager.get_expiring_subscribers()
        if exp:
            for i in exp:
                with st.expander(f"⚠️ {i['name']} - {i['days_left']} يوم"):
                    st.write(f"**السيارة:** {i['car_number']}")
                    st.write(f"**الهاتف:** {i['phone']}")
                    if st.button(f"🔄 تجديد", key=f"ra_{i['subscriber_id']}"):
                        st.session_state['renew_subscriber_id'] = i['subscriber_id']
                        st.session_state['_goto_page'] = "👤 إدارة المشتركين"
                        st.rerun()
        else:
            st.success("✅ لا يوجد")
    with t2:
        exp = manager.get_expired_subscribers()
        if exp:
            for i in exp:
                with st.expander(f"❌ {i['name']} - {i['days_overdue']} يوم"):
                    st.write(f"**السيارة:** {i['car_number']}")
                    st.write(f"**الهاتف:** {i['phone']}")
                    if st.button(f"🔄 تجديد", key=f"re_{i['subscriber_id']}"):
                        st.session_state['renew_subscriber_id'] = i['subscriber_id']
                        st.session_state['_goto_page'] = "👤 إدارة المشتركين"
                        st.rerun()
        else:
            st.success("✅ لا يوجد")


def show_history(manager):
    st.markdown("## 📜 سجل العمليات")
    c1, c2 = st.columns(2)
    with c1: ft = st.text_input("النوع", key="h_t")
    with c2: fd = st.text_input("التفاصيل", key="h_d")
    f = {}
    if ft: f['type'] = ft
    if fd: f['details'] = fd
    ps = 20
    tc = manager.count_history(filters=f)
    tp = max(1, (tc + ps - 1) // ps)
    p = st.number_input("الصفحة", min_value=1, max_value=tp, value=1, step=1)
    h = manager.get_history(ps, (p - 1) * ps, filters=f)
    if h:
        st.write(f"إجمالي: {tc} (صفحة {p}/{tp})")
        data = [{'التاريخ': r[0], 'النوع': r[1], 'التفاصيل': r[2], 'رقم الحركة': r[3] if len(r) > 3 else '-'} for r in h]
        st.dataframe(pd.DataFrame(data), use_container_width=True, height=500)
    else:
        st.info("لا يوجد سجل")


def show_system_settings(manager):
    st.markdown("## ⚙️ الإعدادات")
    db = manager.db
    s = get_parking_settings(db)
    t1, t2, t3, t4 = st.tabs(["💰 الأسعار", "⏱️ الوقت", "🖨️ الطابعة", "🔐 كلمات المرور"])

    with t1:
        st.info(f"""**طريقة الحساب:**
- أول {s.get('free_minutes', 10)} دقيقة: **مجانية**
- أول ساعة: {s.get('first_hour_price', 20)} جنيه
- كل ساعة إضافية: {s.get('second_hour_price', 10)} جنيه
- **الحد الأقصى اليومي:** {s.get('daily_max_charge', 250)} جنيه لكل 24 ساعة""")
        with st.form("price_form"):
            c1, c2 = st.columns(2)
            with c1:
                fh = st.number_input("أول ساعة", min_value=0.0, value=float(s.get('first_hour_price', 20)), step=5.0)
                fm = st.number_input("دقائق مجانية", min_value=0, value=int(s.get('free_minutes', 10)), step=1)
            with c2:
                sh = st.number_input("الساعة التالية", min_value=0.0, value=float(s.get('second_hour_price', 10)), step=5.0)
                dm = st.number_input("الحد الأقصى اليومي", min_value=0.0, value=float(s.get('daily_max_charge', 250)), step=10.0)
            if st.form_submit_button("💾 حفظ", use_container_width=True):
                if update_parking_settings(db, {'first_hour_price': str(fh), 'second_hour_price': str(sh),
                                                'free_minutes': str(fm), 'daily_max_charge': str(dm)}):
                    st.success("✅")
                    st.rerun()

    with t2:
        st.markdown("### ⏱️ إعدادات الوقت")
        st.info("**سماحية الساعة:** كل ساعة تُحسب بعد مرور X دقيقة من حدودها.")
        with st.form("time_form"):
            hg = st.number_input("سماحية الساعة (دقائق)", min_value=0, value=int(s.get('hour_grace_minutes', 10)), step=1)
            if st.form_submit_button("💾 حفظ", use_container_width=True):
                if update_parking_settings(db, {'hour_grace_minutes': str(hg)}):
                    st.success("✅")
                    st.rerun()

    with t3:
        st.info("الإيصالات تظهر مباشرة مع زر طباعة")
        if st.button("🖨️ اختبار طباعة", use_container_width=True):
            st.session_state['receipt_data'] = {'title': "🖨️ اختبار",
                                                'fields': [{'label': 'اختبار', 'value': 'نجاح'}],
                                                'barcode_data': 'TEST-001', 'footer_text': 'تم'}
            st.rerun()

    with t4:
        st.markdown("### 🔐 إعادة تعيين كلمات المرور")
        st.warning("⚠️ **تحذير:** سيعيد كلمات المرور الافتراضية.")
        confirm_reset = st.checkbox("✅ أؤكد")
        if st.button("🔄 إعادة تعيين", use_container_width=True, disabled=not confirm_reset):
            results = db.reset_all_passwords()
            st.success("✅ تم!")
            for line in results:
                st.write(line)


def show_shift_management(db, manager):
    st.markdown("## 🕒 إدارة الورديات")

    if st.session_state.get('confirm_close_shift', False):
        _render_close_shift_confirmation(db, manager)
        return

    current_shift = db.get_current_shift()
    ur = st.session_state.get('user_role', 'user')
    username = st.session_state.get('username', '')

    if current_shift:
        st.success(f"🟢 وردية مفتوحة - {current_shift['opened_by']} في {current_shift['opened_at'][:16]}")
        opened_at = current_shift['opened_at']
        now = datetime.now().isoformat()
        tr, te, tex, vr, sr = manager.get_shift_financial_data(opened_at, now)
        st.info(f"**إجمالي:** {tr:.2f} | **زوار:** {vr:.2f} | **مشتركين:** {sr:.2f} | **دخول:** {te} | **خروج:** {tex}")

        c1, c2 = st.columns(2)
        with c1:
            if st.button("🖨️ طباعة الإجماليات", use_container_width=True, key="print_cur_totals"):
                fields = [
                    {'label': 'الوردية', 'value': 'الحالية'},
                    {'label': 'افتتحت بواسطة', 'value': current_shift['opened_by']},
                    {'label': 'وقت الفتح', 'value': current_shift['opened_at'][:16]},
                    {'label': 'إيرادات الزوار', 'value': f"{vr:.2f}"},
                    {'label': 'إيرادات المشتركين', 'value': f"{sr:.2f}"},
                    {'label': 'الإجمالي', 'value': f"{tr:.2f}"},
                    {'label': 'دخول', 'value': str(te)},
                    {'label': 'خروج', 'value': str(tex)},
                ]
                st.session_state['receipt_data'] = {
                    'title': "📊 إجماليات الوردية", 'fields': fields,
                    'barcode_data': None, 'qr_data': None,
                    'footer_text': datetime.now().strftime('%Y-%m-%d %H:%M')
                }
                st.rerun()
        with c2:
            if ur in ['exit', 'admin', 'manager', 'super_admin']:
                if st.button("🔒 إغلاق الوردية", use_container_width=True, key="close_shift_btn"):
                    st.session_state['confirm_close_shift'] = True
                    st.session_state['shift_close_data'] = {
                        'total_revenue': tr, 'total_entries': te, 'total_exits': tex,
                        'visitor_revenue': vr, 'subscriber_revenue': sr, 'opened_at': opened_at
                    }
                    st.rerun()
            else:
                st.button("🔒 إغلاق", use_container_width=True, disabled=True, key="close_dis")
    else:
        st.warning("🔴 لا توجد وردية مفتوحة")
        if ur in ['entry', 'admin', 'manager', 'super_admin']:
            if st.button("🟢 فتح وردية جديدة", use_container_width=True, key="open_shift_btn"):
                if db.open_shift(username):
                    st.success("✅")
                    st.rerun()

    st.markdown("---")
    st.markdown("### 📋 تاريخ الورديات")
    shifts = db.get_shift_history()
    if shifts:
        for row in shifts:
            status_icon = "🟢" if row['status'] == 'open' else "🔴"
            with st.expander(f"{status_icon} وردية #{row['id']} - {row['opened_by']} - {row['opened_at'][:16] if row['opened_at'] else ''}"):
                c1, c2 = st.columns(2)
                with c1:
                    st.write(f"**افتتحت:** {row['opened_by']} - {row['opened_at'][:16] if row['opened_at'] else ''}")
                    st.write(f"**أغلقت:** {row['closed_by'] or '-'} - {row['closed_at'][:16] if row['closed_at'] else '-'}")
                with c2:
                    st.write(f"**زوار:** {row['visitor_revenue']:.2f}")
                    st.write(f"**مشتركين:** {row['subscriber_revenue']:.2f}")
                    st.write(f"**إجمالي:** {row['total_revenue']:.2f}")


def show_data_cleanup(db):
    st.markdown("## 🗑️ مسح البيانات")
    st.error("⚠️ لا يمكن التراجع!")
    with st.form("cleanup_form"):
        c1, c2 = st.columns(2)
        with c1:
            df_ = st.date_input("من", value=datetime.now() - timedelta(days=30))
        with c2:
            dt_ = st.date_input("إلى", value=datetime.now())
        ca, cb = st.columns(2)
        with ca:
            cv = st.checkbox("🚗 الزوار", value=True)
            cf = st.checkbox("💰 المالية", value=True)
            ch = st.checkbox("📜 السجل", value=True)
        with cb:
            cs = st.checkbox("🕒 الورديات", value=False)
            catt = st.checkbox("👤 الحضور", value=True)
        c1 = st.checkbox("✅ أؤكد")
        c2 = st.text_input("اكتب **تأكيد المسح**")
        if st.form_submit_button("🗑️ مسح", use_container_width=True):
            if not c1 or c2.strip() != "تأكيد المسح":
                st.error("❌ تأكيد خاطئ")
            elif df_ > dt_:
                st.error("❌ التاريخ")
            else:
                res = db.clear_data_range(df_.strftime('%Y-%m-%d'), dt_.strftime('%Y-%m-%d'),
                                          clear_visitors=cv, clear_financial=cf,
                                          clear_history=ch, clear_shifts=cs, clear_attendance=catt)
                if res:
                    st.success("✅ تم المسح")
                    for k, v in res.items():
                        st.write(f"- {k}: {v}")


# ===================================================================
# ⭐⭐⭐ الدالة الرئيسية ⭐⭐⭐
# ===================================================================
# ⭐⭐⭐ صفحة تحميل التطبيقات ⭐⭐⭐
# ===================================================================
def show_download_apps_page():
    st.markdown("## 📲 تحميل التطبيقات")

    st.markdown("""
    <div style="text-align:center; padding:20px; background:white;
                border-radius:15px; margin-bottom:20px;
                box-shadow:0 2px 10px rgba(0,0,0,0.1);">
        <h2 style="color:#667eea; margin:0;">🚗 تطبيق Parking</h2>
        <p style="color:#666; margin-top:8px;">
            امسح كود الـ QR لتحميل التطبيق على هاتفك
        </p>
    </div>
    """, unsafe_allow_html=True)

    # الصورة الموحدة (iPhone + Android)
    st.markdown("### 📱 امسح للتحميل")
    try:
        st.image("static/both_qr.png", use_container_width=True)
    except Exception:
        st.warning("⚠️ الصورة غير موجودة: static/both_qr.png")

    st.markdown("---")

    # صورتين منفصلتين
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### 🍎 iPhone")
        try:
            st.image("static/iphone_qr.png", use_container_width=True)
        except Exception:
            st.warning("⚠️ static/iphone_qr.png")
    with col2:
        st.markdown("### 🤖 Android")
        try:
            st.image("static/android_qr.png", use_container_width=True)
        except Exception:
            st.warning("⚠️ static/android_qr.png")

    st.markdown("---")
    st.info("""
    💡 **ملاحظات:**
    - **iPhone:** الكود يفتح Safari — اضغط زر المشاركة 📤 ثم **"إضافة إلى الشاشة الرئيسية"**.
    - **Android:** الكود يحمّل ملف APK مباشرة — اسمح بالتحميل من مصادر غير معروفة.
    """)

    if st.button("← العودة", use_container_width=True, key="back_from_download"):
        st.session_state.pop('show_download_apps', None)
        st.rerun()

    render_developer_footer()
# ===================================================================
def main():
    # ⭐⭐⭐ كود مؤقت لتنزيل DB من Railway ⭐⭐⭐
    try:
        if st.query_params.get("download_db") == "yes":
            import glob
            st.title("📥 تنزيل قاعدة بيانات الجراج")

            # ابحث عن كل ملفات .db
            base_dir = "/data/garages" if os.path.exists("/data/garages") else "garages"
            st.write(f"🔍 أبحث في: `{base_dir}`")

            db_files = []
            if os.path.exists(base_dir):
                for f in os.listdir(base_dir):
                    if f.endswith('.db'):
                        fp = os.path.join(base_dir, f)
                        size_kb = os.path.getsize(fp) / 1024
                        db_files.append((f, fp, size_kb))

            if not db_files:
                st.error(f"❌ مفيش ملفات .db في {base_dir}")
                st.write("**الملفات الموجودة:**")
                try:
                    for f in os.listdir(base_dir):
                        st.write(f"- {f}")
                except Exception as e:
                    st.write(f"خطأ: {e}")
                st.stop()

            st.success(f"✅ لقيت {len(db_files)} ملف")

            for fname, fpath, size_kb in db_files:
                st.markdown(f"### 📄 {fname}")
                st.write(f"**الحجم:** {size_kb:.1f} KB")

                try:
                    with open(fpath, "rb") as f:
                        data = f.read()

                    st.download_button(
                        label=f"⬇️ نزّل {fname}",
                        data=data,
                        file_name=fname,
                        mime="application/octet-stream",
                        key=f"dl_{fname}"
                    )
                except Exception as e:
                    st.error(f"❌ فشل قراءة {fname}: {e}")

            st.markdown("---")
            st.warning("⚠️ **مهم:** بعد ما تنزّل الملف، امسح الكود ده من `Lastv.py` وأعد الرفع على Railway")

            if st.button("🚪 إغلاق الصفحة"):
                st.query_params.clear()
                st.rerun()

            st.stop()
    except Exception as _e:
        st.error(f"❌ خطأ: {_e}")


    # ⭐ بوابة المشترك للموبايل ⭐
    try:
        if st.query_params.get("view") == "subscriber":
            if 'db' not in st.session_state:
                st.session_state['db'] = Database()
            if subscriber_portal_page:
                subscriber_portal_page(st.session_state['db'])
            else:
                st.error("❌ بوابة المشترك غير متوفرة — تأكد من وجود subscriber_portal.py")
            return
    except Exception as _e:
        st.error(f"❌ خطأ في بوابة المشترك: {_e}")
        return

    # ⭐ تهيئة سجل الجراجات (Multi-Garage) ⭐
    if 'garage_registry' not in st.session_state:
        st.session_state.garage_registry = GarageRegistry()
    registry = st.session_state.garage_registry

    # ========================================================
    # ⭐⭐⭐ تسجيل الدخول: اختيار الجراج ثم تسجيل الدخول ⭐⭐⭐
    # ========================================================
    if not st.session_state.get('logged_in'):
        selected = st.session_state.get('selected_login_garage')
        if not selected:
            garage_selection_login_screen(registry)
            return

        g = registry.get_garage(selected['id'])
        if not g or not g.get('is_active'):
            st.session_state.pop('selected_login_garage', None)
            st.error("❌ الجراج لم يعد متاحاً")
            if st.button("← العودة"):
                st.rerun()
            return

        db_path = g['db_path']
        if not os.path.exists(db_path):
            try:
                _ = Database(db_path)
            except Exception as e:
                st.error(f"❌ فشل إنشاء قاعدة البيانات: {e}")
                if st.button("← تغيير الجراج"):
                    st.session_state.pop('selected_login_garage', None)
                    st.rerun()
                return

        st.session_state.selected_login_garage = g
        login_db = Database(db_path)
        login_page(login_db)
        return

    # ========================================================
    # ⭐ المستخدم مسجل دخول بالفعل ⭐
    # ========================================================
    ur = st.session_state.get('user_role', 'user')
    active_garage_id = st.session_state.get('active_garage_id')

    if 'db' not in st.session_state:
        if active_garage_id:
            g = registry.get_garage(active_garage_id)
            db_path = g['db_path'] if g else _get_db_path('garage.db')
        else:
            db_path = _get_db_path('garage.db')
        st.session_state['db'] = Database(db_path)

    db = st.session_state['db']

    # ⭐ فحص الترخيص ⭐
    expired, expiry_dt = is_system_expired(db)
    if expired and ur != 'super_admin':
        for k in list(st.session_state.keys()):
            if k not in ['db', 'garage_manager', 'visitor_manager', 'attendance_manager',
                         'garage_registry', 'active_garage_id', 'selected_login_garage']:
                try:
                    st.session_state.pop(k, None)
                except Exception:
                    pass
        locked_page(db)
        return

    # ⭐ managers ⭐
    if 'garage_manager' not in st.session_state:
        st.session_state.garage_manager = GarageManager(db)
    if 'visitor_manager' not in st.session_state:
        st.session_state.visitor_manager = VisitorManager(db)
    if 'attendance_manager' not in st.session_state:
        st.session_state.attendance_manager = SubscriberAttendanceManager(db)

    manager = st.session_state.garage_manager
    visitor_manager = st.session_state.visitor_manager
    attendance_manager = st.session_state.attendance_manager
    garage_name = manager.garage_name

    role_badge = {'admin': 'badge-admin', 'manager': 'badge-manager', 'entry': 'badge-entry',
                  'exit': 'badge-exit', 'subscriber': 'badge-subscriber',
                  'super_admin': 'badge-super'}.get(ur, 'badge-admin')
    role_name = {'admin': 'مدير', 'manager': 'مدير الجراج', 'entry': 'دخول', 'exit': 'خروج',
                 'subscriber': 'مشتركين', 'super_admin': 'Super Admin ⭐'}.get(ur, ur)

    st.markdown(
        f"""<div class="main-header"><div><h1>🚗 {garage_name}</h1><p>مرحباً {st.session_state.get('user_name', '')}</p></div><span class="badge {role_badge}">{role_name}</span></div>""",
        unsafe_allow_html=True
    )

    if not expired and expiry_dt and ur in ['admin', 'manager', 'super_admin']:
        days_left = (expiry_dt - datetime.now()).days
        if 0 <= days_left <= 14:
            st.warning(
                f"⚠️ **تنبيه:** سينتهي ترخيص النظام خلال **{days_left} يوم** "
                f"(بتاريخ {expiry_dt.strftime('%Y-%m-%d')}). "
                f"للتواصل: {DEVELOPER_NAME} — {DEVELOPER_PHONE}"
            )

    # ========================================================
    # ⭐⭐⭐ Sidebar ⭐⭐⭐
    # ========================================================
    with st.sidebar:
        _curr_g = None
        try:
            if active_garage_id:
                _curr_g = registry.get_garage(active_garage_id)
        except Exception:
            pass
        _curr_name = _curr_g['name'] if _curr_g else garage_name

        st.markdown(
            f"""
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white; padding: 12px; border-radius: 10px;
                    text-align: center; font-weight: bold; margin-bottom: 10px;">
            🏢 الجراج الحالي<br>
            <span style="font-size: 15px;">{_curr_name}</span>
        </div>
        """,
            unsafe_allow_html=True
        )

        if ur == 'super_admin':
            if st.button("🔄 تبديل الجراج", use_container_width=True, key="switch_garage_sidebar"):
                st.session_state['main_menu'] = "🏢 إدارة الجراجات"
                st.session_state['_goto_page'] = "🏢 إدارة الجراجات"
                st.rerun()

        st.markdown("---")

        # ========================================================
        # ⭐ الورديات ⭐
        # ========================================================
        current_shift = db.get_current_shift()
        if current_shift:
            st.success(f"🟢 مفتوحة - {current_shift['opened_by']}")
            if ur in ['exit', 'admin', 'manager', 'super_admin']:
                if st.button("🔒 إغلاق الوردية", use_container_width=True, key="sb_close_shift"):
                    opened_at = current_shift['opened_at']
                    now = datetime.now().isoformat()
                    tr, te, tex, vr, sr = manager.get_shift_financial_data(opened_at, now)
                    st.session_state['confirm_close_shift'] = True
                    st.session_state['shift_close_data'] = {
                        'total_revenue': tr, 'total_entries': te, 'total_exits': tex,
                        'visitor_revenue': vr, 'subscriber_revenue': sr, 'opened_at': opened_at
                    }
                    st.rerun()
        else:
            st.warning("🔴 لا توجد وردية")
            if ur in ['entry', 'admin', 'manager', 'super_admin']:
                if st.button("🟢 فتح وردية", use_container_width=True, key="sb_open_shift"):
                    if db.open_shift(st.session_state['username']):
                        st.success("✅")
                        st.rerun()

        st.markdown("---")

        # ========================================================
        # ⭐ قسم المزامنة ⭐
        # ========================================================
        st.markdown("### 🔄 المزامنة الكاملة")
        try:
            from sync_engine import (
                sync_both_ways as _sync_both,
                push_full_sync as _push_full,
                pull_full_sync as _pull_full,
                get_status as _get_status,
            )

            # ⭐ نحدد الجراج الحالي
            _current_db_path = db.db_path
            _current_garage_id = st.session_state.get('active_garage_id', 1)
            _current_garage_name = st.session_state.get('active_garage_name', '?')
            _garage_key = f"g{_current_garage_id}"    # مثال: g1, g2

            st.caption(f"🏢 الجراج: **{_current_garage_name}**")
            st.caption(f"🔑 المفتاح: `{_garage_key}`")

            _st = _get_status(garage_key=_garage_key)

            if _st.get('gist_configured'):
                st.caption(f"🆔 هذا الجهاز: `{_st['device_id']}`")

                if _st.get('remote_device'):
                    st.caption(f"☁️ آخر رفع من: `{_st['remote_device']}`")
                    ts = _st.get('remote_timestamp', '') or ''
                    st.caption(f"🕐 {ts[:19]}")
                else:
                    st.caption(f"☁️ مفيش snapshot للجراج {_garage_key} على Gist")

                if st.button("🔄 مزامنة كاملة",
                             use_container_width=True,
                             key="sync_both_btn",
                             type="primary"):
                    with st.spinner("جاري المزامنة..."):
                        _r = _sync_both(db_path=_current_db_path, garage_key=_garage_key)

                    p = _r.get('pulled', {})
                    msg = f"⬇️ سُحب {p.get('applied', 0)} | تخطي {p.get('skipped', 0)}"

                    if _r.get('pushed_ok'):
                        st.success(f"✅ {msg} | ⬆️ تم الرفع")
                        clear_all_caches()
                        time.sleep(2)
                        st.rerun()
                    elif _r.get('pushed_error'):
                        st.warning(f"⚠️ {msg} | ⚠️ {_r['pushed_error']}")
                        if p.get('applied', 0) > 0:
                            clear_all_caches()
                            time.sleep(2)
                            st.rerun()
                    else:
                        st.info(f"ℹ️ {msg}")

                c1, c2 = st.columns(2)
                with c1:
                    if st.button("⬆️ رفع", use_container_width=True, key="push_full_btn"):
                        with st.spinner("..."):
                            _r = _push_full(db_path=_current_db_path, garage_key=_garage_key)
                        if _r.get('ok'):
                            st.success("✅ رُفع")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error(f"❌ {_r.get('error', '')}")
                with c2:
                    if st.button("⬇️ سحب", use_container_width=True, key="pull_full_btn"):
                        with st.spinner("..."):
                            _r = _pull_full(db_path=_current_db_path, garage_key=_garage_key)
                        if _r.get('ok'):
                            st.success(
                                f"✅ سُحب {_r.get('applied', 0)} | "
                                f"تخطي {_r.get('skipped', 0)}"
                            )
                            clear_all_caches()
                            time.sleep(2)
                            st.rerun()
                        else:
                            st.error(f"❌ {_r.get('error', '')}")
            else:
                st.caption("⚠️ Gist غير مُعدّ")

        except ImportError as _e:
            st.error(f"❌ sync_engine.py مش موجود: {_e}")
        except Exception as _e:
            st.error(f"❌ {str(_e)[:150]}")
        # ─── 2) مزامنة السيرفر لأول مرة فقط ───
        st.markdown("---")
        with st.expander("⬇️ مزامنة السيرفر (أول مرة فقط)", expanded=False):
            st.caption(
                "اسحب كل الداتا من الـ Gist (السيرفر) وطبقها محليًا. "
                "يُستخدم مرة واحدة عند بدء جهاز جديد."
            )

            try:
                from first_sync import get_gist_info, force_pull_all

                _info = get_gist_info()

                if not _info.get('ok'):
                    st.error(f"❌ {_info.get('error', 'خطأ غير معروف')}")
                else:
                    st.info(
                        f"📊 الـ Gist فيه **{_info['total']}** تغيير | "
                        f"آخر تحديث: {_info['last_update']}"
                    )

                    if _info['total'] > 0:
                        with st.expander("📋 تفاصيل الـ Gist", expanded=False):
                            st.write("**الأجهزة اللي رفعت الداتا:**")
                            for dev, cnt in _info['devices'].items():
                                marker = " ← أنت" if dev == _info.get('my_device') else ""
                                st.write(f"- `{dev}`: {cnt} تغيير{marker}")
                            st.write("**الجداول:**")
                            for tbl, cnt in _info['tables'].items():
                                st.write(f"- {tbl}: {cnt}")

                        st.warning(
                            "⚠️ **تحذير:** لو الداتا المحلية فيها تغييرات، "
                            "هيتم استبدالها بالداتا اللي جاية من السيرفر."
                        )

                        if st.button(
                            "⬇️ اسحب الداتا الآن",
                            key="force_pull_btn",
                            use_container_width=True,
                            type="primary"
                        ):
                            with st.spinner("جاري سحب الداتا من السيرفر..."):
                                _r = force_pull_all(db.db_path)

                            if _r.get('ok'):
                                st.success(f"✅ تم تطبيق **{_r['applied']}** سجل")
                                st.write(f"👤 مشتركين: **{_r['subs_count']}**")
                                st.write(f"🅿️ أماكن: **{_r['spots_count']}**")
                                st.write(f"🚗 زوار نشطين: **{_r['vis_count']}**")

                                if _r.get('skipped'):
                                    st.caption(f"⏭️ تم تخطي: {_r['skipped']}")
                                if _r.get('errors'):
                                    st.caption(f"⚠️ أخطاء: {_r['errors']}")

                                st.info("🔄 أعد تشغيل التطبيق لرؤية التغييرات")
                                time.sleep(2)
                                st.rerun()
                            else:
                                st.error(f"❌ {_r.get('error', 'فشل')}")
                    else:
                        st.warning("⚠️ الـ Gist فاضي — مفيش داتا لسحبها")

            except ImportError as _e:
                st.error(f"❌ first_sync.py مش موجود: {_e}")
            except Exception as _e:
                st.error(f"❌ {str(_e)[:120]}")

        st.markdown("---")

        # ========================================================
        # ⭐ القائمة الرئيسية ⭐
        # ========================================================
        menu_items = []

        if ur == 'super_admin':
            menu_items.extend([
                "🔐 لوحة Super Admin", "🏢 إدارة الجراجات",
                "🏠 لوحة التحكم", "🗺️ عرض الجراج",
                "👤 إدارة المشتركين", "📝 تخصيص مكان", "📥 دخول", "📤 خروج",
                "💰 التقارير المالية", "📊 التقارير", "⚠️ التنبيهات",
                "📜 سجل العمليات", "🕒 إدارة الورديات",
                "📱 دفعات التطبيق",
                "👥 إدارة المستخدمين", "⚙️ إعدادات النظام", "🗑️ مسح البيانات"
            ])
        elif ur == 'entry':
            menu_items.extend(["🏠 لوحة التحكم", "🗺️ عرض الجراج", "📥 دخول", "📜 سجل العمليات"])
        elif ur == 'exit':
            menu_items.extend(["🏠 لوحة التحكم", "📤 خروج", "📜 سجل العمليات"])
        elif ur == 'subscriber':
            menu_items.extend([
                "🏠 لوحة التحكم", "🗺️ عرض الجراج", "👤 إدارة المشتركين",
                "📝 تخصيص مكان", "💰 التقارير المالية", "📊 التقارير",
                "⚠️ التنبيهات", "📜 سجل العمليات"
            ])
        elif ur == 'manager':
            menu_items.extend([
                "🏠 لوحة التحكم", "🗺️ عرض الجراج", "👤 إدارة المشتركين",
                "📝 تخصيص مكان", "📥 دخول", "📤 خروج",
                "💰 التقارير المالية", "📊 التقارير", "⚠️ التنبيهات",
                "📜 سجل العمليات", "🕒 إدارة الورديات"
            ])
        elif ur == 'admin':
            menu_items.extend([
                "🏠 لوحة التحكم", "🗺️ عرض الجراج", "👤 إدارة المشتركين",
                "📝 تخصيص مكان", "📥 دخول", "📤 خروج",
                "💰 التقارير المالية", "📊 التقارير", "⚠️ التنبيهات",
                "📜 سجل العمليات", "🕒 إدارة الورديات",
                "👥 إدارة المستخدمين", "⚙️ إعدادات النظام", "🗑️ مسح البيانات"
            ])

        goto_page = st.session_state.pop('_goto_page', None)

        if menu_items:
            if goto_page and goto_page in menu_items:
                if 'main_menu' in st.session_state:
                    st.session_state['main_menu'] = goto_page
                default_idx = menu_items.index(goto_page)
            elif 'main_menu' in st.session_state and st.session_state['main_menu'] in menu_items:
                default_idx = menu_items.index(st.session_state['main_menu'])
            else:
                default_idx = 0

            page = st.radio("اختر:", menu_items, index=default_idx, key="main_menu")
        else:
            page = None

        st.markdown("---")

        # ========================================================
        # ⭐ إحصائيات سريعة ⭐
        # ========================================================
        stats = get_cached_dashboard_stats(db.db_path)
        c1, c2 = st.columns(2)
        with c1:
            st.metric("🚗 مشغول", stats['occupied'])
        with c2:
            st.metric("🟢 متاح", stats['total'] - stats['occupied'])
        st.metric("👤 المشتركين", stats['subs'])

        exp = manager.get_expiring_subscribers()
        expd = manager.get_expired_subscribers()
        if exp or expd:
            st.markdown("---")
            if exp:
                st.warning(f"🟡 {len(exp)} قارب")
            if expd:
                st.error(f"🔴 {len(expd)} منتهي")

        if expiry_dt:
            st.markdown("---")
            if expired:
                st.error(f"🔒 الترخيص منتهي\n{expiry_dt.strftime('%Y-%m-%d')}")
            else:
                days_left = (expiry_dt - datetime.now()).days
                if days_left <= 14:
                    st.warning(f"⏰ الترخيص: {days_left} يوم")
                else:
                    st.info(f"✅ الترخيص ساري\n{expiry_dt.strftime('%Y-%m-%d')}")

        st.markdown("---")

        if st.button("🚪 تسجيل الخروج", use_container_width=True, key="logout"):
            for k in list(st.session_state.keys()):
                if k not in ['db', 'garage_manager', 'visitor_manager', 'attendance_manager',
                             'garage_registry', 'active_garage_id', 'selected_login_garage']:
                    try:
                        st.session_state.pop(k, None)
                    except Exception:
                        pass
            clear_all_caches()
            st.rerun()

        st.markdown("---")
        render_developer_footer()

        if st.button("📲 تحميل التطبيقات", use_container_width=True, key="download_apps_sidebar_btn"):
            st.session_state['show_download_apps'] = True
            st.rerun()

    # ========================================================
    # ⭐⭐⭐ عرض الصفحات ⭐⭐⭐
    # ========================================================

    # ⭐ صفحة تحميل التطبيقات
    if st.session_state.get('show_download_apps'):
        show_download_apps_page()
        return

    if page is None:
        return

    # ⭐ تأكيد إغلاق الوردية
    if st.session_state.get('confirm_close_shift', False):
        _render_close_shift_confirmation(db, manager)
        return

    # ⭐ الإيصال
    if st.session_state.get('receipt_data'):
        d = st.session_state['receipt_data']
        display_receipt_with_buttons(
            d['title'], d['fields'],
            d.get('qr_data'), d.get('barcode_data'),
            d.get('footer_text'),
            db=db, movement_number=d.get('movement_number')
        )
        return

    # ⭐ التوجيه للصفحات
    if page == "🔐 لوحة Super Admin" and ur == 'super_admin':
        super_admin_page(db, manager)
    elif page == "🏢 إدارة الجراجات" and ur == 'super_admin':
        show_garages_management(registry, st.session_state.get('active_garage_id', 1))
    elif page == "📱 دفعات التطبيق" and ur == 'super_admin':
        if show_app_payments:
            show_app_payments(db)
        else:
            st.error("❌ لم يتم تحميل صفحة الدفعات")
    elif page == "🏠 لوحة التحكم":
        show_dashboard(manager, visitor_manager)
    elif page == "🗺️ عرض الجراج":
        show_garage_view(manager, visitor_manager)
    elif page == "👤 إدارة المشتركين":
        manage_subscribers(manager)
    elif page == "📝 تخصيص مكان":
        assign_spot_page(manager)
    elif page == "📥 دخول":
        entry_page(manager, visitor_manager, attendance_manager)
    elif page == "📤 خروج":
        exit_page(manager, visitor_manager, attendance_manager)
    elif page == "💰 التقارير المالية":
        show_financial_reports(manager, visitor_manager)
    elif page == "📊 التقارير":
        show_reports(manager)
    elif page == "⚠️ التنبيهات":
        show_alerts(manager)
    elif page == "📜 سجل العمليات":
        show_history(manager)
    elif page == "👥 إدارة المستخدمين" and ur in ['admin', 'super_admin']:
        manage_users(db)
    elif page == "⚙️ إعدادات النظام" and ur in ['admin', 'super_admin']:
        show_system_settings(manager)
    elif page == "🕒 إدارة الورديات" and ur in ['admin', 'manager', 'entry', 'exit', 'super_admin']:
        show_shift_management(db, manager)
    elif page == "🗑️ مسح البيانات" and ur in ['admin', 'super_admin']:
        show_data_cleanup(db)

if __name__ == "__main__":
    main()