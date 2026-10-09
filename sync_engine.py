# sync_engine.py
# مزامنة كاملة — كل الجداول (Snapshot-based)
import sqlite3
import json
import os
import requests
from datetime import datetime

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN', '')
GIST_ID = os.environ.get('GIST_ID', '')
DEVICE_ID = os.environ.get('DEVICE_ID', 'garage-pc-1')


# الجداول اللي هتتزامن (اسم الجدول: اسم PK)
SYNC_TABLES = {
    'subscribers': 'id',
    'spots': 'id',
    'visitors': 'ticket_number',
    'subscriber_attendance': 'id',
    'financial_records': 'id',
    'history': 'id',
    'shifts': 'id',
    'users': 'id',
    'parking_settings': 'key',
    'app_payments': 'id',
    'garages': 'id',          # من registry DB
}

def get_local_db():
    """اكتشاف مسار DB الجراج النشط — الأولوية دائمًا للـ registry"""
    # ⭐ 1) الأولوية القصوى: الجراج النشط من الـ registry
    registry = '/data/garages_registry.db' if os.path.exists('/data') else 'garages_registry.db'
    if os.path.exists(registry):
        try:
            with sqlite3.connect(registry) as conn:
                conn.row_factory = sqlite3.Row
                row = conn.execute(
                    "SELECT db_path FROM garages WHERE is_active=1 ORDER BY id LIMIT 1"
                ).fetchone()
                if row and row['db_path'] and os.path.exists(row['db_path']):
                    print(f"[get_local_db] Using active garage DB: {row['db_path']}")
                    return row['db_path']
        except Exception as e:
            print(f"[get_local_db] Registry error: {e}")

    # ⭐ 2) احتياطي: LOCAL_DB من .env
    env_db = os.environ.get('LOCAL_DB', '')
    if env_db and os.path.exists(env_db):
        print(f"[get_local_db] Fallback to LOCAL_DB: {env_db}")
        return env_db

    # ⭐ 3) الأخير: garage.db
    print("[get_local_db] Fallback to garage.db")
    return 'garage.db'

def get_registry_db():
    return '/data/garages_registry.db' if os.path.exists('/data') else 'garages_registry.db'


LOCAL_DB = get_local_db()
REGISTRY_DB = get_registry_db()


# ============================================================
def ensure_updated_at():
    """يضمن وجود عمود updated_at في كل الجداول"""
    for db_path in [LOCAL_DB, REGISTRY_DB]:
        if not db_path or not os.path.exists(db_path):
            continue
        try:
            with sqlite3.connect(db_path, timeout=30) as conn:
                cur = conn.cursor()
                for table in SYNC_TABLES:
                    try:
                        cur.execute(f"PRAGMA table_info({table})")
                        cols = [c[1] for c in cur.fetchall()]
                        if cols and 'updated_at' not in cols:
                            cur.execute(f"ALTER TABLE {table} ADD COLUMN updated_at TEXT")
                    except Exception:
                        pass
                conn.commit()
        except Exception as e:
            print(f"[ensure_updated_at] {db_path}: {e}")


def _dump_table(conn, table):
    """يرجع dict: {pk: {'data': {...}, '_updated_at': '...'}}"""
    try:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(f"SELECT * FROM {table}")
        rows = {}
        for r in cur.fetchall():
            d = dict(r)
            # اختيار عمود الـ PK
            pk_col = SYNC_TABLES.get(table, 'id')
            pk_val = d.get(pk_col)
            if pk_val is None:
                pk_val = d.get('id') or d.get('key') or d.get('ticket_number')
            if pk_val is None:
                continue
            pk_val = str(pk_val)
            ts = d.get('updated_at') or d.get('created_at') or d.get('date') or ''
            rows[pk_val] = {'data': d, '_updated_at': ts}
        return rows
    except Exception as e:
        print(f"[dump {table}] {e}")
        return {}


def take_snapshot(db_path=None):
    """snapshot كامل للـ DB المحدد"""
    db_path = db_path or get_local_db()
    snap = {
        'device_id': DEVICE_ID,
        'timestamp': datetime.now().isoformat(),
        'db_path': db_path,
        'dbs': {'main': {}, 'registry': {}},
    }

    if db_path and os.path.exists(db_path):
        with sqlite3.connect(db_path, timeout=30) as conn:
            for table in SYNC_TABLES:
                if table == 'garages':
                    continue
                snap['dbs']['main'][table] = _dump_table(conn, table)

    # الـ registry دايمًا نقرأه من مكانه الأساسي
    reg = get_registry_db()
    if os.path.exists(reg):
        with sqlite3.connect(reg, timeout=30) as conn:
            snap['dbs']['registry']['garages'] = _dump_table(conn, 'garages')

    return snap
def _apply_table(conn, table, rows):
    """يطبق صفوف على جدول (last-write-wins بالـ updated_at)"""
    if not rows:
        return 0, 0, 0

    applied = skipped = errors = 0
    pk_col = SYNC_TABLES.get(table, 'id')

    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table})")
    table_cols = [c[1] for c in cur.fetchall()]
    if not table_cols:
        return 0, 0, 0

    has_updated_at = 'updated_at' in table_cols

    for pk_val, entry in rows.items():
        try:
            incoming = entry.get('data', {})
            in_ts = entry.get('_updated_at') or ''

            # شوف الموجود محليًا
            cur.execute(f"SELECT * FROM {table} WHERE {pk_col}=?", (pk_val,))
            ex = cur.fetchone()
            if ex:
                ex_dict = dict(ex)
                local_ts = ex_dict.get('updated_at') or ''
                if local_ts and in_ts and local_ts > in_ts:
                    skipped += 1
                    continue

            cols = [c for c in incoming.keys() if c in table_cols]
            if not cols:
                skipped += 1
                continue
            vals = [incoming[c] for c in cols]

            if has_updated_at and 'updated_at' not in cols:
                cols.append('updated_at')
                vals.append(in_ts or datetime.now().isoformat())

            ph = ','.join('?' * len(cols))
            cur.execute(
                f"INSERT OR REPLACE INTO {table} ({','.join(cols)}) VALUES ({ph})",
                vals
            )
            applied += 1
        except Exception as e:
            print(f"[apply {table}/{pk_val}] {e}")
            errors += 1

    return applied, skipped, errors


def apply_snapshot(snap, db_path=None):
    """يطبق snapshot على الـ DB المحدد"""
    db_path = db_path or get_local_db()

    if not snap or 'dbs' not in snap:
        return {'applied': 0, 'skipped': 0, 'errors': 0}

    ta = ts = te = 0

    main = snap.get('dbs', {}).get('main', {})
    if db_path and os.path.exists(db_path) and main:
        with sqlite3.connect(db_path, timeout=30) as conn:
            for table, rows in main.items():
                if table not in SYNC_TABLES:
                    continue
                a, s, e = _apply_table(conn, table, rows)
                ta += a; ts += s; te += e
            conn.commit()

    # registry
    reg = get_registry_db()
    reg_data = snap.get('dbs', {}).get('registry', {})
    if os.path.exists(reg) and reg_data:
        with sqlite3.connect(reg, timeout=30) as conn:
            for table, rows in reg_data.items():
                if table not in SYNC_TABLES:
                    continue
                a, s, e = _apply_table(conn, table, rows)
                ta += a; ts += s; te += e
            conn.commit()

    return {'applied': ta, 'skipped': ts, 'errors': te}
# ============================================================
# Gist
# ============================================================
def _gist_read(file_name='sync_state.json'):
    if not GITHUB_TOKEN or not GIST_ID:
        return None
    try:
        r = requests.get(
            f'https://api.github.com/gists/{GIST_ID}',
            headers={'Authorization': f'token {GITHUB_TOKEN}'},
            timeout=30
        )
        if r.status_code != 200:
            return None
        files = r.json().get('files', {})
        content = files.get(file_name, {}).get('content', '{}')
        return json.loads(content) if content else {}
    except Exception as e:
        print(f"[gist_read] {e}")
        return None


def _gist_write(data, file_name='sync_state.json'):
    if not GITHUB_TOKEN or not GIST_ID:
        return False
    try:
        payload = json.dumps(data, ensure_ascii=False, default=str)

        # ⭐ اقرأ كل الملفات الحالية عشان نضيف الجديد
        current = requests.get(
            f'https://api.github.com/gists/{GIST_ID}',
            headers={'Authorization': f'token {GITHUB_TOKEN}'},
            timeout=30
        ).json().get('files', {})

        # نبني قائمة الملفات
        files_payload = {file_name: {'content': payload}}
        # نبقي الملفات التانية زي ما هي
        for name in current:
            if name != file_name and name.endswith('.json'):
                files_payload[name] = current[name]

        r = requests.patch(
            f'https://api.github.com/gists/{GIST_ID}',
            headers={'Authorization': f'token {GITHUB_TOKEN}'},
            json={'files': files_payload},
            timeout=120
        )
        return r.status_code == 200
    except Exception as e:
        print(f"[gist_write] {e}")
        return False

# ============================================================
# Public API
# ============================================================

def _merge_snapshots(remote, local):
    """
    يدمج snapshot السيرفر مع snapshot الجهاز الحالي
    - لكل سجل: اللي عنده updated_at أحدث يفوز
    - السجلات الجديدة من أي جهاز تتضاف
    """
    merged = {
        'device_id': DEVICE_ID,
        'timestamp': datetime.now().isoformat(),
        'dbs': {
            'main': {},
            'registry': {},
        }
    }

    r_dbs = (remote or {}).get('dbs', {})
    l_dbs = local.get('dbs', {})

    for db_key in ['main', 'registry']:
        r_tables = r_dbs.get(db_key, {})
        l_tables = l_dbs.get(db_key, {})
        all_tables = set(r_tables.keys()) | set(l_tables.keys())

        merged['dbs'][db_key] = {}
        for table in all_tables:
            r_rows = r_tables.get(table, {})
            l_rows = l_tables.get(table, {})

            # ابدأ بالسجلات من السيرفر
            combined = dict(r_rows)

            # ضيف/حدّث من المحلي
            for pk, l_entry in l_rows.items():
                if pk not in combined:
                    # سجل جديد من المحلي
                    combined[pk] = l_entry
                else:
                    # نفس السجل موجود في الاتنين → اللي updated_at أحدث يفوز
                    r_ts = combined[pk].get('_updated_at') or ''
                    l_ts = l_entry.get('_updated_at') or ''
                    if l_ts >= r_ts:
                        combined[pk] = l_entry

            merged['dbs'][db_key][table] = combined

    return merged


def _count_records(snap):
    total = 0
    for db_key, tables in snap.get('dbs', {}).items():
        for table_name, rows in tables.items():
            total += len(rows)
    return total
def push_full_sync(db_path=None, garage_key='default'):
    """يرفع snapshot للجراج المحدد"""
    db_path = db_path or get_local_db()
    file_name = f'sync_state_{garage_key}.json'

    local_snap = take_snapshot(db_path=db_path)

    has_data = False
    for db_key, tables in local_snap.get('dbs', {}).items():
        for table_name, rows in tables.items():
            if rows:
                has_data = True
                break
        if has_data:
            break

    if not has_data:
        return {
            'ok': False,
            'error': 'الجهاز الحالي فاضي — مش هرفع snapshot فاضي'
        }

    remote_snap = _gist_read(file_name) or {}
    merged = _merge_snapshots(remote_snap, local_snap)

    if _gist_write(merged, file_name):
        return {
            'ok': True,
            'device_id': DEVICE_ID,
            'timestamp': merged['timestamp'],
            'garage_key': garage_key,
        }
    return {'ok': False, 'error': 'فشل رفع الـ snapshot'}


def pull_full_sync(db_path=None, garage_key='default'):
    """ينزّل snapshot للجراج المحدد"""
    db_path = db_path or get_local_db()
    file_name = f'sync_state_{garage_key}.json'

    remote = _gist_read(file_name)
    if not remote or not remote.get('dbs'):
        return {'ok': False, 'error': f'مفيش snapshot للجراج {garage_key} على Gist'}

    res = apply_snapshot(remote, db_path=db_path)
    res['ok'] = True
    res['remote_device'] = remote.get('device_id')
    res['remote_timestamp'] = remote.get('timestamp')
    return res


def sync_both_ways(db_path=None, garage_key='default'):
    """مزامنة كاملة للجراج المحدد"""
    db_path = db_path or get_local_db()
    file_name = f'sync_state_{garage_key}.json'

    remote = _gist_read(file_name) or {}
    if remote and remote.get('dbs'):
        pull_result = apply_snapshot(remote, db_path=db_path)
    else:
        pull_result = {'applied': 0, 'skipped': 0, 'errors': 0}

    push_result = push_full_sync(db_path=db_path, garage_key=garage_key)

    return {
        'ok': push_result.get('ok') or pull_result.get('applied', 0) > 0,
        'pulled': pull_result,
        'pushed_ok': push_result.get('ok'),
        'pushed_error': push_result.get('error'),
        'pushed_device': push_result.get('device_id'),
        'garage_key': garage_key,
    }


def get_status(garage_key='default'):
    """حالة المزامنة للجراج المحدد"""
    file_name = f'sync_state_{garage_key}.json'
    info = {
        'device_id': DEVICE_ID,
        'gist_configured': bool(GITHUB_TOKEN and GIST_ID),
        'garage_key': garage_key,
    }
    if info['gist_configured']:
        remote = _gist_read(file_name)
        if remote:
            info['remote_device'] = remote.get('device_id')
            info['remote_timestamp'] = remote.get('timestamp')
        else:
            info['remote_device'] = None
            info['remote_timestamp'] = None
    return info