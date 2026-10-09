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
import secrets

try:
    import barcode
    from barcode.writer import ImageWriter
    BARCODE_AVAILABLE = True
except ImportError:
    BARCODE_AVAILABLE = False

DEVELOPER_NAME = "مهندس أحمد شعبان"
DEVELOPER_PHONE = "01095387792"


# ============================================================
#  ⭐⭐⭐ Session Token Helpers ⭐⭐⭐
# ============================================================
def _generate_session_token():
    """يولّد token فريد"""
    return secrets.token_urlsafe(32)


def _save_session_token(db_path, subscriber_id, garage_id):
    """يحفظ token في قاعدة البيانات"""
    try:
        token = _generate_session_token()
        expires = (datetime.now() + timedelta(days=30)).isoformat()

        with sqlite3.connect(db_path, timeout=30) as conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS subscriber_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subscriber_id TEXT NOT NULL,
                garage_id INTEGER NOT NULL,
                device_id TEXT,
                device_info TEXT,
                session_token TEXT UNIQUE NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                expires_at TEXT NOT NULL,
                last_seen_at TEXT,
                is_active INTEGER DEFAULT 1,
                revoked_at TEXT,
                revoked_reason TEXT
            )''')

            conn.execute(
                """INSERT INTO subscriber_sessions 
                   (subscriber_id, garage_id, device_id, device_info, session_token, expires_at, last_seen_at) 
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    subscriber_id,
                    garage_id,
                    'web_portal',
                    'web_browser',
                    token,
                    expires,
                    datetime.now().isoformat()
                )
            )
            conn.commit()
        return token
    except Exception as e:
        print(f"❌ Token save error: {e}")
        import traceback
        traceback.print_exc()
        return None


def _validate_session_token(db_path, token):
    """يتحقق من token ويرجع (subscriber_id, garage_id) لو صالح"""
    if not token:
        return None, None
    try:
        with sqlite3.connect(db_path, timeout=30) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.execute(
                """SELECT subscriber_id, garage_id, expires_at 
                   FROM subscriber_sessions 
                   WHERE session_token=? AND is_active=1""",
                (token,)
            )
            row = cur.fetchone()
            if not row:
                return None, None
            try:
                exp_dt = datetime.fromisoformat(row['expires_at'])
                if exp_dt < datetime.now():
                    return None, None
            except Exception:
                pass
            return row['subscriber_id'], row['garage_id']
    except Exception as e:
        print(f"Token validate error: {e}")
        return None, None


def _revoke_session_token(db_path, token):
    """يلغي token (عند تسجيل الخروج)"""
    if not token:
        return
    try:
        with sqlite3.connect(db_path, timeout=30) as conn:
            conn.execute(
                "UPDATE subscriber_sessions SET is_active=0 WHERE session_token=?",
                (token,)
            )
            conn.commit()
    except Exception:
        pass


# ============================================================
#  ⭐⭐⭐ SQLite helpers مباشرة ⭐⭐⭐
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
            if 'app_service_disabled' not in cols:
                cur.execute("ALTER TABLE subscribers ADD COLUMN app_service_disabled INTEGER DEFAULT 0")

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
            cur.execute("INSERT OR IGNORE INTO parking_settings (key, value) VALUES ('instapay_number', '01095387792')")
            conn.commit()
    except Exception:
        pass


# ============================================================
#  قراءة الجراجات من garages_registry.db
# ============================================================
def get_all_garages_from_registry():
    try:
        registry_path = '/data/garages_registry.db' if os.path.exists('/data') else 'garages_registry.db'
        if not os.path.exists(registry_path):
            return []
        return _query_all(
            registry_path,
            "SELECT id, name, address, phone, db_path FROM garages WHERE is_active=1 ORDER BY id"
        )
    except Exception:
        return []


# ============================================================
#  ⭐⭐⭐ حالة اشتراك التطبيق ⭐⭐⭐
# ============================================================
def get_app_status_for_portal(db_path, sub):
    """
    يرجع (status, days, msg)
    status: 'active' | 'trial' | 'expired' | 'disabled' | 'garage_free'
    """
    if not sub:
        return 'expired', 0, 'غير مسجل'

    # 1) الإدارة أوقفت الخدمة يدوياً؟
    if sub.get('app_service_disabled'):
        return 'disabled', 0, '⛔ الخدمة موقوفة من الإدارة'

    # 2) الجراج معفى نهائياً؟
    try:
        r = _query_one(db_path, "SELECT value FROM parking_settings WHERE key='garage_free_forever'")
        if r and r.get('value') == '1':
            return 'garage_free', 999, '🎉 الخدمة مجانية لهذا الجراج'
    except Exception:
        pass

    # 3) الجراج معفى لفترة محددة؟
    try:
        r = _query_one(db_path, "SELECT value FROM parking_settings WHERE key='garage_free_until'")
        if r and r.get('value'):
            free_until = datetime.fromisoformat(str(r['value']).replace('Z', '').split('.')[0])
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
        r = _query_one(db_path, "SELECT value FROM parking_settings WHERE key='trial_enabled'")
        trial_enabled = (r and r.get('value') == '1') if r else True
    except Exception:
        trial_enabled = True

    if trial_enabled:
        reg = sub.get('registration_date')
        if reg:
            try:
                reg_dt = datetime.fromisoformat(str(reg).replace('Z', '').split('.')[0])
                trial_days = 3
                try:
                    r = _query_one(db_path, "SELECT value FROM parking_settings WHERE key='app_trial_days'")
                    if r and r.get('value'):
                        trial_days = int(r['value'])
                except Exception:
                    pass

                trial_end = reg_dt + timedelta(days=trial_days)
                if trial_end >= datetime.now():
                    days = max(0, (trial_end - datetime.now()).days)
                    return 'trial', days, f'🎁 فترة تجريبية — يتبقى {days} يوم'
            except Exception:
                pass

    return 'expired', 0, '❌ انتهى الاشتراك'


def _reset_to_subscriber_portal():
    """يرجع لبوابة المشترك — يمسح الـ token ويسيب view=subscriber"""
    st.query_params.clear()
    st.query_params["view"] = "subscriber"


def _logout_and_redirect():
    """تسجيل خروج موحد — يحتفظ بـ view=subscriber"""
    try:
        db_path = st.session_state.get('sub_portal_garage_db_path')
        token = st.session_state.get('sub_portal_token')
        if db_path and token:
            _revoke_session_token(db_path, token)
    except Exception:
        pass

    for k in list(st.session_state.keys()):
        if k.startswith('sub_portal_'):
            st.session_state.pop(k, None)

    _reset_to_subscriber_portal()


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
    row.setdefault('app_service_disabled', 0)
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
            row = _query_one(db_path, "SELECT value FROM parking_settings WHERE key='garage_floor_names'")
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
    garage_id = st.session_state.get('sub_portal_garage_id', 1)

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
        _reset_to_subscriber_portal()
        st.rerun()

    with st.form("sub_login"):
        phone = st.text_input("📱 رقم التلفون", placeholder="01xxxxxxxxx")
        submit = st.form_submit_button("🚀 دخول", use_container_width=True)

        if submit:
            # ... الكود القديم زي ما هو ...
            pass

    # ⭐ الزر الجديد
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("📲 تحميل التطبيقات", key="download_apps_portal_login", use_container_width=True):
        st.session_state['sub_portal_show_download'] = True
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

    if st.button("🚪 تسجيل الخروج", key="logout_expired"):
        _logout_and_redirect()
        st.rerun()


def show_app_payments(db):
    st.markdown("## 📱 دفعات اشتراك التطبيق")

    c1, c2, c3 = st.columns(3)
    with c1:
        f_name = st.text_input("👤 الاسم", key="pay_f_name")
    with c2:
        f_phone = st.text_input("📱 الهاتف", key="pay_f_phone")
    with c3:
        f_garage = st.text_input("🏢 الجراج", key="pay_f_garage")

    garages = get_all_garages_from_registry()
    all_pending = []

    for g in garages:
        try:
            if f_garage and f_garage.strip().lower() not in g['name'].lower():
                continue

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
                if f_name and f_name.strip().lower() not in (r.get('name') or '').lower():
                    continue
                if f_phone and f_phone.strip() not in (r.get('phone') or ''):
                    continue

                r['garage_id'] = g['id']
                r['garage_name'] = g['name']
                r['db_path'] = db_path
                all_pending.append(r)
        except Exception:
            continue

    if not all_pending:
        st.success("✅ لا توجد دفعات مطابقة")
        return

    st.warning(f"⚠️ يوجد **{len(all_pending)}** دفعة")
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


def app_payment_screen(db_path, sub):
    """صفحة دفع اشتراك التطبيق"""

    # ⭐ تحقق من الإيقاف اليدوي — أول حاجة
    if sub.get('app_service_disabled'):
        st.markdown("""
        <div class="portal-header">
            <div style="font-size: 55px;">⛔</div>
            <h1>الخدمة موقوفة</h1>
        </div>
        <div class="status-expired">
            ⛔ تم إيقاف خدمتك من إدارة النظام<br>
            <span style="font-size: 13px;">تواصل مع الإدارة للاستفسار</span>
        </div>
        """, unsafe_allow_html=True)
        if st.button("← العودة", key="back_disabled"):
            st.session_state.pop('show_payment_screen', None)
            st.rerun()
        return

    # ⭐ جديد: لو الجراج معفى أو السعر صفر → مفيش دفع
    fee = float(get_setting(db_path, 'app_fee', '10'))
    free_forever = get_setting(db_path, 'garage_free_forever', '0') == '1'
    if free_forever or fee <= 0:
        st.markdown("""
        <div class="portal-header">
            <div style="font-size: 55px;">🎉</div>
            <h1>الخدمة مجانية</h1>
        </div>
        <div class="status-ok">
            🎉 خدمة التطبيق مجانية لهذا الجراج<br>
            <span style="font-size: 13px;">يمكنك استخدام الخدمة مباشرة</span>
        </div>
        """, unsafe_allow_html=True)
        if st.button("← العودة", key="back_free"):
            st.session_state.pop('show_payment_screen', None)
            st.rerun()
        return

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

    # ← احذف السطرين دول لأنك حسبتهم فوق خلاص
    # fee = float(get_setting(db_path, 'app_fee', '10'))
    instapay = get_setting(db_path, 'instapay_number', '')
    vodafone = get_setting(db_path, 'vodafone_cash_number', '')

    # ... باقي الكود زي ما هو

def main_screen(db_path, sub):
    garage_name = st.session_state.get('sub_portal_garage_name', '')

    st.markdown(f"""
    <div class="portal-header">
        <h1>🚗 أهلاً {sub.get('name', '')}</h1>
        <p>🏢 {garage_name}</p>
    </div>
    """, unsafe_allow_html=True)

    # ⭐ حالة اشتراك التطبيق
    app_status, app_days, app_msg = get_app_status_for_portal(db_path, sub)

    if app_status in ('active', 'garage_free'):
        st.markdown(f'<div class="status-ok">📱 {app_msg}</div>', unsafe_allow_html=True)

    elif app_status == 'trial':
        st.markdown(f"""
        <div class="status-warning">
            {app_msg}<br>
            <span style="font-size: 12px; opacity: 0.9;">
                بعد انتهاء التجربة لن تتمكن من الدخول حتى تدفع اشتراك التطبيق
            </span>
        </div>
        """, unsafe_allow_html=True)
        if st.button("💳 ادفع الآن", use_container_width=True, key="pay_from_trial"):
            st.session_state['show_payment_screen'] = True
            st.rerun()

    elif app_status == 'disabled':
        st.markdown(f"""
        <div class="status-expired">
            {app_msg}<br>
            <span style="font-size: 12px; opacity: 0.9;">
                تواصل مع الإدارة للاستفسار
            </span>
        </div>
        """, unsafe_allow_html=True)

    else:  # expired
        st.markdown(f"""
        <div class="status-expired">
            {app_msg}<br>
            <span style="font-size: 12px; opacity: 0.9;">
                الكود ظاهر أدناه لكن لن يعمل عند البوابة
            </span>
        </div>
        """, unsafe_allow_html=True)
        if st.button("💳 اذهب لصفحة الدفع", use_container_width=True,
                     type="primary", key="pay_from_expired"):
            st.session_state['show_payment_screen'] = True
            st.rerun()

    # ⭐ حالة اشتراك الجراج
    try:
        end_dt = datetime.fromisoformat(sub['subscription_end']) if sub.get('subscription_end') else None
        if end_dt:
            days_left = (end_dt - datetime.now()).days
            if days_left < 0:
                cls, txt = "status-expired", f"⛔ اشتراك الجراج منتهي منذ {abs(days_left)} يوم"
            elif days_left <= 7:
                cls, txt = "status-warning", f"⚠️ اشتراك الجراج يتبقى {days_left} يوم"
            else:
                cls, txt = "status-ok", f"✅ اشتراك الجراج نشط — يتبقى {days_left} يوم"
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

    # QR يظهر دايماً
    qr_data = sub['car_number']
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

    if st.button("🚪 تسجيل الخروج", key="logout_main"):
        _logout_and_redirect()
        st.rerun()


# ============================================================
#  نقطة الدخول
def download_apps_screen():
    """صفحة تحميل التطبيقات لبوابة المشترك"""
    garage_name = st.session_state.get('sub_portal_garage_name', '')

    st.markdown(f"""
    <div class="portal-header">
        <div style="font-size: 55px;">📲</div>
        <h1>تحميل التطبيقات</h1>
        <p>🏢 {garage_name}</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("### 📱 امسح للتحميل")
    try:
        st.image("static/both_qr.png", use_container_width=True)
    except Exception:
        st.warning("⚠️ الصورة غير موجودة: static/both_qr.png")

    st.markdown("---")

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

    st.markdown("""
    <div class="sub-card" style="text-align: right;">
        <div style="font-size: 14px; color: #444; line-height: 1.8;">
            💡 <b>ملاحظات:</b><br>
            • <b>iPhone:</b> الكود يفتح Safari — اضغط زر المشاركة 📤 ثم
              <b>"إضافة إلى الشاشة الرئيسية"</b>.<br>
            • <b>Android:</b> الكود يحمّل ملف APK مباشرة —
              اسمح بالتحميل من مصادر غير معروفة.
        </div>
    </div>
    """, unsafe_allow_html=True)

    if st.button("← العودة", key="back_from_download_portal", use_container_width=True):
        st.session_state.pop('sub_portal_show_download', None)
        st.rerun()
# ============================================================
def subscriber_portal_page(db=None):
    """db parameter موجود للتوافق فقط — لا يُستخدم"""
    inject_mobile_css()

    token = st.query_params.get("token")

    if not st.session_state.get('sub_portal_logged_in') and token:
        try:
            garages = get_all_garages_from_registry()
            for g in garages:
                db_path = g['db_path']
                if not os.path.exists(db_path):
                    continue
                _init_app_tables(db_path)

                sub_id, gid = _validate_session_token(db_path, token)
                if sub_id:
                    sub = _query_one(db_path, "SELECT * FROM subscribers WHERE id=?", (sub_id,))
                    if sub:
                        st.session_state['sub_portal_logged_in'] = True
                        st.session_state['sub_portal_sub_id'] = sub_id
                        st.session_state['sub_portal_phone'] = sub.get('phone', '')
                        st.session_state['sub_portal_garage_id'] = g['id']
                        st.session_state['sub_portal_garage_name'] = g['name']
                        st.session_state['sub_portal_garage_db_path'] = db_path
                        st.session_state['sub_portal_token'] = token
                        st.rerun()
                    break
        except Exception as e:
            print(f"Token restore error: {e}")
    # ⭐ عرض صفحة تحميل التطبيقات لو مطلوب
    if st.session_state.get('sub_portal_show_download'):
        download_apps_screen()
        footer()
        return
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

    # 3) فتح قاعدة البيانات
    db_path = st.session_state.get('sub_portal_garage_db_path')
    if not db_path or not os.path.exists(db_path):
        st.error("❌ قاعدة بيانات الجراج غير موجودة")
        if st.button("🔄 من جديد", key="restart_portal"):
            for k in list(st.session_state.keys()):
                if k.startswith('sub_portal_'):
                    st.session_state.pop(k, None)
            _reset_to_subscriber_portal()
            st.rerun()
        return

    _init_app_tables(db_path)

    # 4) جلب المشترك
    sub_id = st.session_state.get('sub_portal_sub_id')
    sub = _query_one(db_path, "SELECT * FROM subscribers WHERE id=?", (sub_id,))
    if not sub:
        st.error("❌ المشترك غير موجود")
        if st.button("🔄 من جديد", key="restart_portal2"):
            for k in list(st.session_state.keys()):
                if k.startswith('sub_portal_'):
                    st.session_state.pop(k, None)
            _reset_to_subscriber_portal()
            st.rerun()
        return

    # 5) فحص اشتراك الجراج
    try:
        end_dt = datetime.fromisoformat(
            str(sub['subscription_end']).replace('Z', '').split('.')[0]
        ) if sub.get('subscription_end') else None
    except Exception:
        end_dt = None

    if end_dt and end_dt < datetime.now():
        try:
            _revoke_session_token(db_path, st.session_state.get('sub_portal_token', ''))
        except Exception:
            pass
        _reset_to_subscriber_portal()
        expired_screen(sub)
        footer()
        return

    # 6) زر الدفع المؤقت
    if st.session_state.get('show_payment_screen'):
        if st.button("← العودة", key="back_from_pay"):
            st.session_state.pop('show_payment_screen', None)
            st.rerun()
        app_payment_screen(db_path, sub)
        footer()
        return

    # 7) الشاشة الرئيسية (QR يظهر دايماً)
    main_screen(db_path, sub)
    footer()