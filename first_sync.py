# first_sync.py
# مزامنة أول مرة من السيرفر (Gist) — سحب شامل لكل الداتا
import os
import json
import sqlite3
import requests
from datetime import datetime

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def _get_credentials():
    return (
        os.environ.get('GITHUB_TOKEN', ''),
        os.environ.get('GIST_ID', ''),
        os.environ.get('DEVICE_ID', 'garage-pc-1'),
    )


def get_gist_info():
    """يرجع معلومات الـ Gist (للتحقق قبل السحب)"""
    token, gist_id, device_id = _get_credentials()

    if not token or not gist_id:
        return {'ok': False, 'error': 'GITHUB_TOKEN أو GIST_ID مش موجودين في .env'}

    try:
        r = requests.get(
            f'https://api.github.com/gists/{gist_id}',
            headers={'Authorization': f'token {token}'},
            timeout=15
        )
        if r.status_code != 200:
            return {'ok': False, 'error': f'HTTP {r.status_code}'}

        files = r.json().get('files', {})
        content = files.get('sync.json', {}).get('content', '{}')
        data = json.loads(content)
        pending = data.get('pending', [])

        from collections import Counter
        devices = Counter(p.get('device', '?') for p in pending)
        tables = Counter(p.get('table', '?') for p in pending)

        return {
            'ok': True,
            'total': len(pending),
            'devices': dict(devices),
            'tables': dict(tables),
            'last_update': (data.get('last_update', '—') or '—')[:19],
            'my_device': device_id,
        }
    except Exception as e:
        return {'ok': False, 'error': str(e)}


def force_pull_all(db_path):
    """
    يسحب كل التغييرات من الـ Gist ويطبقها في DB المحلية
    (يتجاهل DEVICE_ID — يسحب كل حاجة)
    """
    token, gist_id, device_id = _get_credentials()

    if not token or not gist_id:
        return {'ok': False, 'error': 'GITHUB_TOKEN أو GIST_ID مش موجودين'}

    if not os.path.exists(db_path):
        return {'ok': False, 'error': f'DB مش موجودة: {db_path}'}

    # 1) اقرأ الـ Gist
    try:
        r = requests.get(
            f'https://api.github.com/gists/{gist_id}',
            headers={'Authorization': f'token {token}'},
            timeout=15
        )
        if r.status_code != 200:
            return {'ok': False, 'error': f'HTTP {r.status_code}'}

        files = r.json().get('files', {})
        content = files.get('sync.json', {}).get('content', '{}')
        gist_data = json.loads(content)
    except Exception as e:
        return {'ok': False, 'error': f'فشل قراءة Gist: {e}'}

    pending = gist_data.get('pending', [])
    if not pending:
        return {'ok': True, 'applied': 0, 'message': 'الـ Gist فاضي — مفيش داتا لسحبها'}

    # 2) طبق كل التغييرات
    conn = sqlite3.connect(db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    applied = 0
    skipped = 0
    errors = 0

    allowed = ['subscribers', 'spots', 'visitors', 'subscriber_attendance',
               'history', 'financial_records']

    for ch in pending:
        try:
            table = ch.get('table')
            op = ch.get('op')
            data = ch.get('data')
            record_id = ch.get('record_id')

            if table not in allowed:
                skipped += 1
                continue

            if op == 'delete':
                cur.execute(f"DELETE FROM {table} WHERE id=?", (record_id,))
                applied += 1
                continue

            if not data:
                skipped += 1
                continue

            cur.execute(f"PRAGMA table_info({table})")
            table_cols = [c[1] for c in cur.fetchall()]

            cols_to_use = [c for c in data.keys() if c in table_cols]
            if not cols_to_use:
                skipped += 1
                continue

            vals = [data[c] for c in cols_to_use]

            if 'updated_at' in table_cols and 'updated_at' not in cols_to_use:
                cols_to_use.append('updated_at')
                vals.append(ch.get('timestamp') or datetime.now().isoformat())

            placeholders = ','.join('?' * len(cols_to_use))
            cols_str = ','.join(cols_to_use)

            cur.execute(
                f"INSERT OR REPLACE INTO {table} ({cols_str}) VALUES ({placeholders})",
                vals
            )
            applied += 1
        except Exception:
            errors += 1

    conn.commit()

    # 3) إحصائيات نهائية
    cur.execute("SELECT COUNT(*) FROM subscribers")
    subs_count = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM spots")
    spots_count = cur.fetchone()[0]
    try:
        cur.execute("SELECT COUNT(*) FROM visitors WHERE status='inside'")
        vis_count = cur.fetchone()[0]
    except Exception:
        vis_count = 0

    conn.close()

    return {
        'ok': True,
        'applied': applied,
        'skipped': skipped,
        'errors': errors,
        'subs_count': subs_count,
        'spots_count': spots_count,
        'vis_count': vis_count,
        'total': len(pending),
    }