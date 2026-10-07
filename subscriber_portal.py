# subscriber_portal.py — بوابة المشترك (Multi-Garage, no circular import)
import streamlit as st
from datetime import datetime, timedelta
import qrcode
from io import BytesIO
import base64
from PIL import Image
import time
import json
import os
import sqlite3

try:
    import barcode
    from barcode.writer import ImageWriter
    BARCODE_AVAILABLE = True
except ImportError:
    BARCODE_AVAILABLE = False

DEVELOPER_NAME = "مهندس أحمد شعبان"
DEVELOPER_PHONE = "01095387792"


# ============================================================
#  SQLite helpers مباشرة (بدون Database class)
# ============================================================
def _query_one(db_path, query, params=()):
    """يرجع صف واحد كـ dict"""
    try:
        with sqlite3.connect(db_path, timeout=30) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.execute(query, params)
            row = cur.fetchone()
            return dict(row) if row else None
    except Exception:
        return None


def _query_all(db_path, query, params=()):
    """يرجع كل الصفوف كـ list of dict"""
    try:
        with sqlite3.connect(db_path, timeout=30) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.execute(query, params)
            return [dict(r) for r in cur.fetchall()]
    except Exception:
        return []


def _execute(db_path, query, params=()):
    """تنفيذ أمر كتابة"""
    try:
        with sqlite3.connect(db_path, timeout=30) as conn:
            conn.execute(query, params)
            conn.commit()
        return True
    except Exception:
        return False


def _init_app_tables(db_path):
    """يضمن وجود جداول وأعمدة اشتراك التطبيق"""
    try:
        with sqlite3.connect(db_path, timeout=30) as conn:
            cur = conn.cursor()

            # subscribers
            cur.execute("PRAGMA table_info(subscribers)")
            cols = [c[1] for c in cur.fetchall()]
            if 'app_subscription_active' not in cols:
                cur.execute("ALTER TABLE subscribers ADD COLUMN app_subscription_active INTEGER DEFAULT 0")
            if 'app_subscription_end' not in cols:
                cur.execute("ALTER TABLE subscribers ADD COLUMN app_subscription_end TEXT")
            if 'garage_id' not in cols:
                cur.execute("ALTER TABLE subscribers ADD COLUMN garage_id INTEGER DEFAULT 1")

            # app_payments
            cur.execute('''CREATE TABLE IF NOT EXISTS app_payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subscriber_id TEXT NOT NULL,
                garage_id INTEGER,
                amount REAL DEFAULT 10,
                method TEXT,
                reference_number TEXT,
                status TEXT DEFAULT 'pending',
                notes TEXT,
                confirmed_at TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )''')

            cur.execute("PRAGMA table_info(app_payments)")
            ap_cols = [c[1] for c in cur.fetchall()]
            if 'garage_id' not in ap_cols:
                cur.execute("ALTER TABLE app_payments ADD COLUMN garage_id INTEGER")

            # settings
            cur.execute("INSERT OR IGNORE INTO parking_settings (key, value) VALUES ('app_fee', '10')")
            cur.execute("INSERT OR IGNORE INTO parking_settings (key, value) VALUES ('instapay_number', 'ahmed.shaban@instapay')")
            cur.execute("INSERT OR IGNORE INTO parking_settings (key, value) VALUES ('vodafone_cash_number', '01095387792')")
            conn.commit()
    except Exception:
        pass


# ============================================================
#  قراءة الجراجات من garages_registry.db
# ============================================================
def get_all_garages_from_registry():
    try:
        registry_path = 'garages_registry.db'
        if not os.path.exists(registry_path):
            return []
        return _query_all(
            registry_path,
            "SELECT id, name, address, phone, db_path FROM garages WHERE is_active=1 ORDER BY id"
        )
    except Exception:
        return []


# ============================================================
#  QR & Barcode
# ============================================================
def generate_qr_base64(data, box_size=8):
    try:
        qr = qrcode.QRCode(
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=box_size,
            border=2
        )
        qr.add_data(str(data))
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white").convert('RGB')
        img = img.resize((300, 300), Image.Resampling.LANCZOS)
        buf = BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return base64.b64encode(buf.getvalue()).decode()
    except Exception as e:
        print(f"❌ QR Error: {e}")
        return ""


def generate_barcode_base64(data):
    if not BARCODE_AVAILABLE:
        return ""
    try:
        from barcode import get_barcode_class
        code = get_barcode_class('code128')(str(data)[:25], writer=ImageWriter())
        rv = BytesIO()
        code.write(rv, options={'write_text': True, 'font_size': 18,
                                'module_width': 1.8, 'module_height': 50})
        rv.seek(0)
        img = Image.open(BytesIO(rv.getvalue()))
        new_w = 600
        ratio = new_w / img.width
        img = img.resize((new_w, int(img.height * ratio)), Image.Resampling.LANCZOS)
        out = BytesIO()
        img.save(out, format="PNG")
        out.seek(0)
        return base64.b64encode(out.getvalue()).decode()
    except Exception:
        return ""


# ============================================================
#  CSS للموبايل
# ============================================================
def inject_mobile_css():
    st.markdown("""
    <style>
        .main .block-container {
            max-width: 520px !important;
            padding-left: 1rem !important;
            padding-right: 1rem !important;
            padding-top: 1rem !important;
        }
        .stApp {
            direction: rtl; text-align: right;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
        }
        .portal-header {
            background: white; padding: 22px; border-radius: 20px;
            text-align: center; margin-bottom: 18px;
            box-shadow: 0 8px 25px rgba(0,0,0,0.15);
        }
        .portal-header h1 { color: #667eea; font-size: 22px; margin: 0; }
        .portal-header p { color: #666; font-size: 13px; margin-top: 6px; margin-bottom: 0; }
        .sub-card {
            background: white; border-radius: 20px; padding: 22px;
            margin: 12px 0; box-shadow: 0 8px 25px rgba(0,0,0,0.15);
        }
        .sub-card .name { font-size: 22px; font-weight: bold; color: #333; }
        .sub-card .car { font-size: 18px; color: #667eea; margin: 8px 0; font-weight: bold; }
        .sub-card .row {
            font-size: 14px; color: #444; margin: 6px 0;
            padding: 8px 0; border-bottom: 1px dashed #eee;
        }
        .status-ok {
            background: #4CAF50; color: white; padding: 14px;
            border-radius: 14px; text-align: center; font-size: 15px;
            font-weight: bold; margin: 12px 0;
        }
        .status-expired {
            background: #f44336; color: white; padding: 14px;
            border-radius: 14px; text-align: center; font-size: 15px;
            font-weight: bold; margin: 12px 0;
        }
        .status-warning {
            background: #ff9800; color: white; padding: 14px;
            border-radius: 14px; text-align: center; font-size: 15px;
            font-weight: bold; margin: 12px 0;
        }
        .qr-box {
            background: white; border-radius: 20px; padding: 22px;
            text-align: center; margin: 12px 0;
            box-shadow: 0 8px 25px rgba(0,0,0,0.15);
        }
        .qr-label {
            font-size: 15px; font-weight: bold; color: #667eea;
            margin-bottom: 14px;
        }
        .qr-box img { border: 2px solid #eee; border-radius: 12px; padding: 6px; }
        .contact-box {
            background: linear-gradient(135deg, #FF6B6B 0%, #EE5A6F 100%);
            color: white; border-radius: 20px; padding: 26px 20px;
            text-align: center; margin: 14px 0;
        }
        .contact-box .title { font-size: 14px; opacity: 0.95; margin-bottom: 8px; }
        .contact-box .name { font-size: 20px; font-weight: bold; margin-bottom: 12px; }
        .contact-box .phone {
            font-size: 26px; font-weight: bold;
            direction: ltr; letter-spacing: 2px; margin-top: 10px;
        }
        .pay-box {
            background: white; border-radius: 20px; padding: 24px;
            text-align: center; margin: 12px 0;
            box-shadow: 0 8px 25px rgba(0,0,0,0.15);
        }
        .pay-box h2 { color: #667eea; font-size: 19px; margin: 0 0 12px 0; }
        .pay-box .amount { font-size: 46px; color: #4CAF50; font-weight: bold; margin: 16px 0; }
        .pay-method {
            background: #f8f9fa; border-radius: 12px; padding: 14px;
            margin: 10px 0; border-right: 4px solid #667eea; text-align: right;
        }
        .pay-method .label { font-size: 13px; color: #666; margin-bottom: 4px; }
        .pay-method .value { font-size: 16px; color: #333;
                              font-weight: bold; direction: ltr; word-break: break-all; }
        .stButton > button {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
            color: white !important; border: none !important;
            border-radius: 14px !important; padding: 14px 24px !important;
            font-weight: bold !important; font-size: 16px !important;
            width: 100% !important; min-height: 52px !important;
        }
        input, select, textarea {
            font-size: 17px !important; font-weight: bold !important;
            text-align: center !important; padding: 12px !important;
        }
        label { font-size: 15px !important; font-weight: bold !important; }
    </style>
    """, unsafe_allow_html=True)


def footer():
    st.markdown(f"""
    <div style="text-align:center; padding:15px; color:white;
                font-size:12px; opacity:0.9; margin-top:18px;">
        <div style="font-weight:bold;">🚗 تم التطوير بواسطة: {DEVELOPER_NAME}</div>
        <div style="direction:ltr; margin-top:5px;">📱 {DEVELOPER_PHONE}</div>
    </div>
    """, unsafe_allow_html=True)


# ============================================================
#  Helpers
# ============================================================
def get_subscriber_by_phone(db_path, phone):
    row = _query_one(db_path, "SELECT * FROM subscribers WHERE phone=?", (phone,))
    if not row:
        return None
    row.setdefault('app_subscription_active', 0)
    row.setdefault('app_subscription_end', None)
    return row


def get_setting(db_path, key, default=""):
    row = _query_one(db_path, "SELECT value FROM parking_settings WHERE key=?", (key,))
    if row and row.get('value'):
        return row['value']
    return default


def get_spot_location_text(db_path, spot_id):
    if not spot_id:
        return "غير محدد"
    try:
        parts = str(spot_id).split('_')
        if len(parts) == 3:
            floor = int(parts[0])
            number = int(parts[2])
            row = _query_one(db_path,
                             "SELECT value FROM parking_settings WHERE key='garage_floor_names'")
            if row and row.get('value'):
                names = json.loads(row['value'])
                fname = names.get(str(floor), f"الدور {floor}")
            else:
                fname = f"الدور {floor}"
            return f"{fname} - مكان {number}"
    except Exception:
        pass
    return "غير محدد"


# ============================================================
#  Screens
# ============================================================
def garage_selection_screen():
    st.markdown("""
    <div class="portal-header">
        <div style="font-size: 55px;">🏢</div>
        <h1>اختر الجراج</h1>
        <p>اختر الجراج التابع له</p>
    </div>
    """, unsafe_allow_html=True)

    garages = get_all_garages_from_registry()
    if not garages:
        st.error("❌ لا توجد جراجات. تواصل مع الإدارة")
        return

    for g in garages:
        if st.button(f"🏢  {g['name']}\n📍 {g.get('address') or 'بدون عنوان'}",
                     key=f"garage_btn_{g['id']}", use_container_width=True):
            st.session_state['sub_portal_garage_id'] = g['id']
            st.session_state['sub_portal_garage_name'] = g['name']
            st.session_state['sub_portal_garage_db_path'] = g['db_path']
            st.rerun()


def login_screen():
    garage_name = st.session_state.get('sub_portal_garage_name', '')

    st.markdown(f"""
    <div class="portal-header">
        <div style="font-size: 55px;">🚗</div>
        <h1>بوابة المشترك</h1>
        <p>🏢 {garage_name}</p>
    </div>
    """, unsafe_allow_html=True)

    if st.button("← تغيير الجراج", key="change_garage"):
        for k in ['sub_portal_garage_id', 'sub_portal_garage_name', 'sub_portal_garage_db_path']:
            st.session_state.pop(k, None)
        st.rerun()

    with st.form("sub_login"):
        phone = st.text_input("📱 رقم التلفون", placeholder="01xxxxxxxxx")
        submit = st.form_submit_button("🚀 دخول", use_container_width=True)
        if submit:
            if not phone.strip():
                st.warning("⚠️ أدخل رقم التلفون")
            else:
                db_path = st.session_state.get('sub_portal_garage_db_path')
                if not db_path or not os.path.exists(db_path):
                    st.error("❌ قاعدة بيانات الجراج غير موجودة")
                    return

                _init_app_tables(db_path)
                sub = get_subscriber_by_phone(db_path, phone.strip())
                if not sub:
                    st.error("❌ رقم التلفون غير مسجل في هذا الجراج")
                else:
                    st.session_state['sub_portal_logged_in'] = True
                    st.session_state['sub_portal_phone'] = phone.strip()
                    st.session_state['sub_portal_sub_id'] = sub['id']
                    st.rerun()


def expired_screen(sub):
    st.markdown("""
    <div class="portal-header">
        <div style="font-size: 55px;">⛔</div>
        <h1>اشتراكك منتهي</h1>
    </div>
    """, unsafe_allow_html=True)

    end_date = sub['subscription_end'][:10] if sub.get('subscription_end') else '—'

    st.markdown(f"""
    <div class="sub-card">
        <div class="name">👤 {sub.get('name', '')}</div>
        <div class="car">🚗 {sub.get('car_number', '')}</div>
        <div class="row"><b>📅 تاريخ الانتهاء:</b> {end_date}</div>
    </div>
    <div class="status-expired">
        ⛔ برجاء تجديد الاشتراك للاستمرار
    </div>
    <div class="contact-box">
        <div class="title">📞 للتواصل والتجديد</div>
        <div class="name">👨‍💻 {DEVELOPER_NAME}</div>
        <div class="phone">📱 {DEVELOPER_PHONE}</div>
    </div>
    """, unsafe_allow_html=True)

    if st.button("🚪 خروج", key="logout_expired"):
        for k in ['sub_portal_logged_in', 'sub_portal_phone', 'sub_portal_sub_id',
                  'sub_portal_garage_id', 'sub_portal_garage_name', 'sub_portal_garage_db_path']:
            st.session_state.pop(k, None)
        st.rerun()


def app_payment_screen(db_path, sub):
    garage_name = st.session_state.get('sub_portal_garage_name', '')
    garage_id = st.session_state.get('sub_portal_garage_id', 1)

    st.markdown(f"""
    <div class="portal-header">
        <div style="font-size: 48px;">📱</div>
        <h1>اشتراك استخدام التطبيق</h1>
        <p>🏢 {garage_name}</p>
    </div>
    <div class="sub-card">
        <div class="name">👤 {sub.get('name', '')}</div>
        <div class="car">🚗 {sub.get('car_number', '')}</div>
    </div>
    """, unsafe_allow_html=True)

    fee = float(get_setting(db_path, 'app_fee', '10'))
    instapay = get_setting(db_path, 'instapay_number', '')
    vodafone = get_setting(db_path, 'vodafone_cash_number', '')

    st.markdown(f"""
    <div class="pay-box">
        <h2>💰 المطلوب دفعه شهرياً</h2>
        <div class="amount">{fee:.0f} جنيه</div>
        <div style="text-align: right; font-weight: bold;
                    color: #667eea; margin: 12px 0;">
            📌 طرق التحويل المتاحة:
        </div>
    </div>
    """, unsafe_allow_html=True)

    if instapay:
        st.markdown(f"""
        <div class="pay-method">
            <div class="label">💳 InstaPay</div>
            <div class="value">{instapay}</div>
        </div>
        """, unsafe_allow_html=True)

    if vodafone:
        st.markdown(f"""
        <div class="pay-method">
            <div class="label">📱 Vodafone Cash</div>
            <div class="value">{vodafone}</div>
        </div>
        """, unsafe_allow_html=True)

    with st.form("app_pay_form"):
        st.markdown("### 📝 بيانات التحويل")
        method = st.selectbox("🔄 طريقة الدفع",
                              ["InstaPay", "Vodafone Cash", "أخرى"])
        ref = st.text_input("🔢 رقم المرجع / آخر 4 أرقام")
        notes = st.text_area("📝 ملاحظات (اختياري)", height=70)

        if st.form_submit_button("✅ إرسال للمراجعة", use_container_width=True):
            if not ref.strip():
                st.error("❌ أدخل رقم المرجع")
            else:
                ok = _execute(
                    db_path,
                    "INSERT INTO app_payments "
                    "(subscriber_id, garage_id, amount, method, reference_number, notes, status) "
                    "VALUES (?, ?, ?, ?, ?, ?, 'pending')",
                    (sub['id'], garage_id, fee, method, ref.strip(), notes.strip())
                )
                if ok:
                    st.success("✅ تم إرسال طلبك")
                    st.info("⏳ سيتم مراجعة التحويل خلال دقائق")
                else:
                    st.error("❌ فشل الإرسال")

    if st.button("🚪 خروج", key="logout_pay"):
        for k in ['sub_portal_logged_in', 'sub_portal_phone', 'sub_portal_sub_id',
                  'sub_portal_garage_id', 'sub_portal_garage_name', 'sub_portal_garage_db_path']:
            st.session_state.pop(k, None)
        st.rerun()


def main_screen(db_path, sub):
    garage_name = st.session_state.get('sub_portal_garage_name', '')

    st.markdown(f"""
    <div class="portal-header">
        <h1>🚗 أهلاً {sub.get('name', '')}</h1>
        <p>🏢 {garage_name}</p>
    </div>
    """, unsafe_allow_html=True)

    try:
        end_dt = datetime.fromisoformat(sub['subscription_end']) if sub.get('subscription_end') else None
        if end_dt:
            days_left = (end_dt - datetime.now()).days
            if days_left < 0:
                cls, txt = "status-expired", f"⛔ منتهي منذ {abs(days_left)} يوم"
            elif days_left <= 7:
                cls, txt = "status-warning", f"⚠️ يتبقى {days_left} يوم"
            else:
                cls, txt = "status-ok", f"✅ نشط — يتبقى {days_left} يوم"
        else:
            cls, txt = "status-warning", "⚠️ لا يوجد تاريخ انتهاء"
    except Exception:
        cls, txt = "status-warning", "⚠️ خطأ في التاريخ"

    st.markdown(f'<div class="{cls}">{txt}</div>', unsafe_allow_html=True)

    spot_txt = get_spot_location_text(db_path, sub.get('spot_id'))
    end_date = sub['subscription_end'][:10] if sub.get('subscription_end') else '—'

    st.markdown(f"""
    <div class="sub-card">
        <div class="name">👤 {sub.get('name', '')}</div>
        <div class="car">🚗 {sub.get('car_number', '')}</div>
        <div class="row"><b>🅿️ مكان الركنة:</b> {spot_txt}</div>
        <div class="row"><b>📅 انتهاء الاشتراك:</b> {end_date}</div>
        <div class="row"><b>📱 الهاتف:</b> {sub.get('phone', '—')}</div>
    </div>
    """, unsafe_allow_html=True)

    qr_data = sub['car_number']  # ⭐ QR = ID مشترك فقط
    qr_b64 = generate_qr_base64(qr_data)
    if qr_b64:
        st.markdown(f"""
        <div class="qr-box">
            <div class="qr-label">📱 امسح هذا الكود للدخول / الخروج</div>
            <img src="data:image/png;base64,{qr_b64}" style="width:260px;height:260px;">
        </div>
        """, unsafe_allow_html=True)

    bc_b64 = generate_barcode_base64(sub.get('car_number', ''))
    if bc_b64:
        st.markdown(f"""
        <div class="qr-box">
            <div class="qr-label">🏷️ باركود رقم الكارت</div>
            <img src="data:image/png;base64,{bc_b64}" style="width:100%; max-width:360px;">
        </div>
        """, unsafe_allow_html=True)

    app_end = sub.get('app_subscription_end')
    app_active = sub.get('app_subscription_active')
    if app_active and app_end:
        try:
            aed = datetime.fromisoformat(app_end)
            a_days = (aed - datetime.now()).days
            if a_days >= 0:
                st.info(f"📱 اشتراك التطبيق: نشط — يتبقى {a_days} يوم")
        except Exception:
            pass

    if st.button("🚪 تسجيل الخروج", key="logout_main"):
        for k in ['sub_portal_logged_in', 'sub_portal_phone', 'sub_portal_sub_id',
                  'sub_portal_garage_id', 'sub_portal_garage_name', 'sub_portal_garage_db_path']:
            st.session_state.pop(k, None)
        st.rerun()


# ============================================================
#  📱 صفحة دفعات التطبيق للسوبر أدمن
# ============================================================
def show_app_payments(db):
    st.markdown("## 📱 دفعات اشتراك التطبيق")

    garages = get_all_garages_from_registry()
    all_pending = []

    for g in garages:
        try:
            db_path = g['db_path']
            if not os.path.exists(db_path):
                continue
            _init_app_tables(db_path)

            rows = _query_all(
                db_path,
                '''SELECT ap.id, ap.subscriber_id, ap.amount,
                          ap.method, ap.reference_number, ap.status,
                          ap.created_at, ap.notes,
                          s.name, s.car_number, s.phone
                   FROM app_payments ap
                   LEFT JOIN subscribers s ON s.id = ap.subscriber_id
                   WHERE ap.status = 'pending'
                   ORDER BY ap.id DESC'''
            )
            for r in rows:
                r['garage_id'] = g['id']
                r['garage_name'] = g['name']
                r['db_path'] = db_path
                all_pending.append(r)
        except Exception:
            continue

    if not all_pending:
        st.success("✅ لا توجد دفعات معلقة")
        return

    st.warning(f"⚠️ يوجد **{len(all_pending)}** دفعة في انتظار التأكيد")
    st.markdown("---")

    for r in all_pending:
        garage_label = r.get('garage_name') or '—'
        unique_key = f"{r['garage_id']}_{r['id']}"
        with st.expander(f"💰 {r.get('name') or '—'} — {r.get('amount')} ج — 🏢 {garage_label}"):
            c1, c2 = st.columns(2)
            with c1:
                st.write(f"**🏢 الجراج:** {garage_label}")
                st.write(f"**👤 الاسم:** {r.get('name') or '—'}")
                st.write(f"**🚗 رقم الكارت:** {r.get('car_number') or '—'}")
                st.write(f"**📱 الهاتف:** {r.get('phone') or '—'}")
            with c2:
                st.write(f"**💰 المبلغ:** {r.get('amount')} ج")
                st.write(f"**🔄 الطريقة:** {r.get('method') or '—'}")
                st.write(f"**🔢 المرجع:** {r.get('reference_number') or '—'}")
                created = r.get('created_at') or ''
                st.write(f"**📅 التاريخ:** {created[:16] if created else '—'}")
            if r.get('notes'):
                st.info(f"📝 ملاحظات: {r['notes']}")

            c1, c2 = st.columns(2)
            with c1:
                if st.button("✅ تأكيد وتفعيل", key=f"confirm_app_pay_{unique_key}",
                             use_container_width=True, type="primary"):
                    now = datetime.now()
                    new_end = (now + timedelta(days=30)).isoformat()
                    ok1 = _execute(
                        r['db_path'],
                        "UPDATE subscribers SET app_subscription_active=1, "
                        "app_subscription_end=? WHERE id=?",
                        (new_end, r['subscriber_id'])
                    )
                    ok2 = _execute(
                        r['db_path'],
                        "UPDATE app_payments SET status='confirmed', confirmed_at=? WHERE id=?",
                        (now.isoformat(), r['id'])
                    )
                    if ok1 and ok2:
                        st.success(f"✅ تم التفعيل حتى {new_end[:10]}")
                        time.sleep(0.4)
                        st.rerun()
                    else:
                        st.error("❌ فشل التحديث")
            with c2:
                if st.button("❌ رفض", key=f"reject_app_pay_{unique_key}",
                             use_container_width=True):
                    ok = _execute(
                        r['db_path'],
                        "UPDATE app_payments SET status='rejected', confirmed_at=? WHERE id=?",
                        (datetime.now().isoformat(), r['id'])
                    )
                    if ok:
                        st.success("تم الرفض")
                        time.sleep(0.3)
                        st.rerun()
                    else:
                        st.error("❌ فشل")


# ============================================================
#  نقطة الدخول
# ============================================================
def subscriber_portal_page(db=None):
    """db parameter موجود للتوافق فقط — لا يُستخدم"""
    inject_mobile_css()

    # 1) اختيار الجراج
    if not st.session_state.get('sub_portal_garage_id'):
        garage_selection_screen()
        footer()
        return

    # 2) تسجيل الدخول
    if not st.session_state.get('sub_portal_logged_in'):
        login_screen()
        footer()
        return

    # 3) فتح قاعدة بيانات الجراج
    db_path = st.session_state.get('sub_portal_garage_db_path')
    if not db_path or not os.path.exists(db_path):
        st.error("❌ قاعدة بيانات الجراج غير موجودة")
        if st.button("🔄 من جديد", key="restart_portal"):
            for k in list(st.session_state.keys()):
                if k.startswith('sub_portal_'):
                    st.session_state.pop(k, None)
            st.rerun()
        return

    _init_app_tables(db_path)

    # 4) جلب المشترك
    phone = st.session_state.get('sub_portal_phone')
    sub = get_subscriber_by_phone(db_path, phone)
    if not sub:
        st.error("❌ المشترك غير موجود")
        if st.button("🔄 من جديد", key="restart_portal2"):
            for k in list(st.session_state.keys()):
                if k.startswith('sub_portal_'):
                    st.session_state.pop(k, None)
            st.rerun()
        return

    # 5) فحص الاشتراك
    try:
        end_dt = datetime.fromisoformat(sub['subscription_end']) if sub.get('subscription_end') else None
    except Exception:
        end_dt = None

    if end_dt and end_dt < datetime.now():
        expired_screen(sub)
        footer()
        return

    # 6) فحص اشتراك التطبيق
    app_active = sub.get('app_subscription_active')
    app_end = sub.get('app_subscription_end')
    app_expired = False
    if not app_active:
        app_expired = True
    else:
        try:
            if app_end:
                aed = datetime.fromisoformat(app_end)
                if aed < datetime.now():
                    app_expired = True
        except Exception:
            pass

    if app_expired:
        app_payment_screen(db_path, sub)
        footer()
        return

    # 7) الشاشة الرئيسية
    main_screen(db_path, sub)
    footer()