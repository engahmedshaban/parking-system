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
    """اكتشاف مسار DB الجراج النشط"""
    env_db = os.environ.get('LOCAL_DB', '')
    if env_db and os.path.exists(env_db):
        return env_db

    registry = '/data/garages_registry.db' if os.path.exists('/data') else 'garages_registry.db'
    if os.path.exists(registry):
        try:
            with sqlite3.connect(registry) as conn:
                conn.row_factory = sqlite3.Row
                row = conn.execute(
                    "SELECT db_path FROM garages WHERE is_active=1 ORDER BY id LIMIT 1"
                ).fetchone()
                if row and row['db_path'] and os.path.exists(row['db_path']):
                    return row['db_path']
        except Exception:
            pass
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


def take_snapshot():
    """snapshot كامل"""
    snap = {
        'device_id': DEVICE_ID,
        'timestamp': datetime.now().isoformat(),
        'dbs': {'main': {}, 'registry': {}},
    }

    if os.path.exists(LOCAL_DB):
        with sqlite3.connect(LOCAL_DB, timeout=30) as conn:
            for table in SYNC_TABLES:
                if table == 'garages':
                    continue
                snap['dbs']['main'][table] = _dump_table(conn, table)

    if os.path.exists(REGISTRY_DB):
        with sqlite3.connect(REGISTRY_DB, timeout=30) as conn:
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


def apply_snapshot(snap):
    """يطبق snapshot خارجي"""
    if not snap or 'dbs' not in snap:
        return {'applied': 0, 'skipped': 0, 'errors': 0}

    ta = ts = te = 0

    # main DB
    main = snap.get('dbs', {}).get('main', {})
    if os.path.exists(LOCAL_DB) and main:
        with sqlite3.connect(LOCAL_DB, timeout=30) as conn:
            for table, rows in main.items():
                if table not in SYNC_TABLES:
                    continue
                a, s, e = _apply_table(conn, table, rows)
                ta += a; ts += s; te += e
            conn.commit()

    # registry DB (garages)
    reg = snap.get('dbs', {}).get('registry', {})
    if os.path.exists(REGISTRY_DB) and reg:
        with sqlite3.connect(REGISTRY_DB, timeout=30) as conn:
            for table, rows in reg.items():
                if table not in SYNC_TABLES:
                    continue
                a, s, e = _apply_table(conn, table, rows)
                ta += a; ts += s; te += e
            conn.commit()

    return {'applied': ta, 'skipped': ts, 'errors': te}


# ============================================================
# Gist
# ============================================================
def _gist_read():
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
        content = files.get('sync_state.json', {}).get('content', '{}')
        return json.loads(content) if content else {}
    except Exception as e:
        print(f"[gist_read] {e}")
        return None


def _gist_write(data):
    if not GITHUB_TOKEN or not GIST_ID:
        return False
    try:
        payload = json.dumps(data, ensure_ascii=False, default=str)
        r = requests.patch(
            f'https://api.github.com/gists/{GIST_ID}',
            headers={'Authorization': f'token {GITHUB_TOKEN}'},
            json={'files': {'sync_state.json': {'content': payload}}},
            timeout=120
        )
        return r.status_code == 200
    except Exception as e:
        print(f"[gist_write] {e}")
        return False


# ============================================================
# Public API
# ============================================================
def push_full_sync():
    ensure_updated_at()
    snap = take_snapshot()
    if _gist_write(snap):
        return {'ok': True, 'device_id': DEVICE_ID, 'timestamp': snap['timestamp']}
    return {'ok': False, 'error': 'فشل رفع الـ snapshot'}


def pull_full_sync():
    ensure_updated_at()
    remote = _gist_read()
    if not remote or not remote.get('dbs'):
        return {'ok': False, 'error': 'مفيش snapshot على Gist'}
    res = apply_snapshot(remote)
    res['ok'] = True
    res['remote_device'] = remote.get('device_id')
    res['remote_timestamp'] = remote.get('timestamp')
    return res


def sync_both_ways():
    """مزامنة كاملة: نزّل + ارفع"""
    ensure_updated_at()

    remote = _gist_read() or {}
    if remote and remote.get('dbs'):
        pull_result = apply_snapshot(remote)
    else:
        pull_result = {'applied': 0, 'skipped': 0, 'errors': 0}

    push_result = push_full_sync()

    return {
        'ok': push_result.get('ok'),
        'pulled': pull_result,
        'pushed_device': push_result.get('device_id'),
    }


def get_status():
    info = {
        'device_id': DEVICE_ID,
        'gist_configured': bool(GITHUB_TOKEN and GIST_ID),
        'local_db': LOCAL_DB,
    }
    if info['gist_configured']:
        remote = _gist_read()
        if remote:
            info['remote_device'] = remote.get('device_id')
            info['remote_timestamp'] = remote.get('timestamp')
        else:
            info['remote_device'] = None
            info['remote_timestamp'] = None
    return info