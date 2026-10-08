# sync_manager.py — محرك المزامنة (يعمل مع GitHub Gist أو HTTP)
import sqlite3
import json
import os
import time
import requests
from datetime import datetime
from contextlib import contextmanager

# ============ الإعدادات ============
SYNC_MODE = os.environ.get('SYNC_MODE', 'local')  # local | cloud
LOCAL_DB = os.environ.get('LOCAL_DB', 'garage.db')
DEVICE_ID = os.environ.get('DEVICE_ID', 'garage-pc-1')
SYNC_INTERVAL = int(os.environ.get('SYNC_INTERVAL', '300'))  # 5 دقائق

# GitHub Gist كقناة نقل
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN', '')
GIST_ID = os.environ.get('GIST_ID', '')


# ============ Helpers ============
def _get_local_conn():
    conn = sqlite3.connect(LOCAL_DB, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


# ============ GitHub Gist Transport ============
def _gist_read():
    """يقرأ محتوى الـ Gist"""
    if not GITHUB_TOKEN or not GIST_ID:
        return None
    try:
        r = requests.get(
            f'https://api.github.com/gists/{GIST_ID}',
            headers={'Authorization': f'token {GITHUB_TOKEN}'},
            timeout=15
        )
        if r.status_code != 200:
            return None
        files = r.json().get('files', {})
        sync_file = files.get('sync.json', {})
        content = sync_file.get('content', '{}')
        return json.loads(content)
    except Exception as e:
        print(f"Gist read error: {e}")
        return None


def _gist_write(data):
    """يكتب في الـ Gist"""
    if not GITHUB_TOKEN or not GIST_ID:
        return False
    try:
        r = requests.patch(
            f'https://api.github.com/gists/{GIST_ID}',
            headers={'Authorization': f'token {GITHUB_TOKEN}'},
            json={'files': {'sync.json': {'content': json.dumps(data, ensure_ascii=False, indent=2)}}},
            timeout=15
        )
        return r.status_code == 200
    except Exception as e:
        print(f"Gist write error: {e}")
        return False


# ============ Sync Operations ============
def push_changes():
    """يرفع التغييرات المحلية غير المرسلة"""
    try:
        conn = _get_local_conn()
        cur = conn.cursor()
        cur.execute("SELECT * FROM sync_log WHERE synced=0 ORDER BY id LIMIT 1000")
        changes = [dict(r) for r in cur.fetchall()]
        conn.close()

        if not changes:
            return 0, "no_changes"

        # نقرأ الـ Gist الحالي
        gist_data = _gist_read() or {'pending': [], 'last_update': None}

        # نضيف التغييرات مع tag الجهاز
        for ch in changes:
            gist_data['pending'].append({
                'device': DEVICE_ID,
                'table': ch['table_name'],
                'record_id': ch['record_id'],
                'op': ch['operation'],
                'data': json.loads(ch['data']) if ch['data'] else None,
                'timestamp': ch['timestamp'],
            })

        gist_data['last_update'] = datetime.now().isoformat()

        # نكتب في الـ Gist
        if not _gist_write(gist_data):
            return 0, "gist_write_failed"

        # نحدّث state المحلي
        conn = _get_local_conn()
        cur = conn.cursor()
        ids = [c['id'] for c in changes]
        placeholders = ','.join('?' * len(ids))
        cur.execute(f"UPDATE sync_log SET synced=1 WHERE id IN ({placeholders})", ids)
        conn.commit()
        conn.close()

        return len(changes), "ok"
    except Exception as e:
        return 0, str(e)


def pull_changes():
    """يجيب التغييرات من الأجهزة الأخرى"""
    try:
        gist_data = _gist_read()
        if not gist_data:
            return 0, "gist_read_failed"

        pending = gist_data.get('pending', [])

        # نفلتر التغييرات اللي مش من جهازنا
        incoming = [c for c in pending if c.get('device') != DEVICE_ID]

        if not incoming:
            return 0, "no_changes"

        # نطبّقها
        applied = 0
        remaining = []

        conn = _get_local_conn()
        cur = conn.cursor()

        for ch in incoming:
            try:
                conflict = _apply_change(cur, ch)
                if not conflict:
                    applied += 1
                # لو فيه تعارض → نتجاهله (last-write-wins بالفعل في _apply_change)
                applied += 1
            except Exception as e:
                print(f"Apply error: {e}")
                # نحتفظ بيها لو فشلت
                remaining.append(ch)

        conn.commit()
        conn.close()

        # نحدّث الـ Gist: نحذف اللي طبقناه
        if applied > 0:
            new_pending = [c for c in pending if c.get('device') == DEVICE_ID] + remaining
            gist_data['pending'] = new_pending
            _gist_write(gist_data)

        return applied, "ok"
    except Exception as e:
        return 0, str(e)


def _apply_change(cur, ch):
    """
    يطبق تغيير من جهاز آخر مع كشف التعارض
    يرجع True لو فيه تعارض (تجاهلنا التغيير)
    """
    table = ch['table']
    op = ch['op']
    data = ch.get('data')
    remote_time = ch.get('timestamp', '')

    # Whitelist للجداول (ممنوع نعدّل مستخدمين أو جلسات)
    allowed = ['subscribers', 'spots', 'visitors', 'subscriber_attendance']
    if table not in allowed:
        return True  # تجاهل

    # ---------- كشف التعارض ----------
    # لو نفس الركنة/المشترك اتعدّل محلياً بعد وقت التغيير الوارد
    if table in ('subscribers', 'spots'):
        record_id = str(ch['record_id'])

        # نجيب updated_at المحلي
        cur.execute(f"PRAGMA table_info({table})")
        cols = [c[1] for c in cur.fetchall()]

        if 'updated_at' in cols:
            cur.execute(f"SELECT updated_at FROM {table} WHERE id=?", (record_id,))
            row = cur.fetchone()
            if row and row[0]:
                local_time = row[0]
                # Last-write-wins
                if local_time > remote_time:
                    return True  # نحتفظ بالمحلي، نتجاهل الوارد

    # ---------- تطبيق التغيير ----------
    if op == 'delete':
        cur.execute(f"DELETE FROM {table} WHERE id=?", (ch['record_id'],))
        return False

    if not data:
        return False

    # نبني INSERT OR REPLACE
    cur.execute(f"PRAGMA table_info({table})")
    table_cols = [c[1] for c in cur.fetchall()]

    cols_to_use = [c for c in data.keys() if c in table_cols]
    if not cols_to_use:
        return False

    vals = [data[c] for c in cols_to_use]
    placeholders = ','.join('?' * len(cols_to_use))
    cols_str = ','.join(cols_to_use)

    # INSERT OR REPLACE
    if op in ('insert', 'update'):
        # نتأكد من وجود updated_at
        if 'updated_at' not in cols_to_use and 'updated_at' in table_cols:
            cols_to_use.append('updated_at')
            vals.append(datetime.now().isoformat())
            cols_str = ','.join(cols_to_use)
            placeholders = ','.join('?' * len(cols_to_use))

        cur.execute(
            f"INSERT OR REPLACE INTO {table} ({cols_str}) VALUES ({placeholders})",
            vals
        )

    return False


def sync_now():
    """مزامنة فورية كاملة"""
    pushed, msg1 = push_changes()
    time.sleep(0.5)
    pulled, msg2 = pull_changes()
    return {'pushed': pushed, 'pulled': pulled, 'msgs': [msg1, msg2]}


def get_sync_status():
    """يرجع حالة المزامنة"""
    try:
        conn = _get_local_conn()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM sync_log WHERE synced=0")
        pending = cur.fetchone()[0]
        conn.close()

        return {
            'mode': SYNC_MODE,
            'device_id': DEVICE_ID,
            'pending': pending,
            'gist_configured': bool(GITHUB_TOKEN and GIST_ID),
        }
    except Exception as e:
        return {'error': str(e)}


def sync_loop():
    """الحلقة الرئيسية"""
    print(f"🔄 Sync Worker | Mode: {SYNC_MODE} | Device: {DEVICE_ID}")
    print(f"   Interval: {SYNC_INTERVAL}s | Gist: {'✅' if GIST_ID else '❌'}")

    while True:
        try:
            result = sync_now()
            if result['pushed'] or result['pulled']:
                print(f"✅ Sync | ↑{result['pushed']} | ↓{result['pulled']}")
        except Exception as e:
            print(f"❌ {e}")

        time.sleep(SYNC_INTERVAL)


if __name__ == '__main__':
    sync_loop()