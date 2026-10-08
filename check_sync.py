# check_sync.py
import sqlite3
import os
from sync_manager import LOCAL_DB, _get_local_conn, get_sync_status

print("=" * 60)
print(f"📂 Local DB path: {LOCAL_DB}")
print(f"✅ DB exists: {os.path.exists(LOCAL_DB)}")
print()

try:
    conn = _get_local_conn()
    cur = conn.cursor()

    # الجداول
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [r[0] for r in cur.fetchall()]
    print(f"📋 Tables ({len(tables)}):")
    for t in tables:
        print(f"   - {t}")
    print()

    # sync_log
    if 'sync_log' in tables:
        cur.execute("SELECT COUNT(*) FROM sync_log")
        total = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM sync_log WHERE synced=0")
        pending = cur.fetchone()[0]
        print(f"📊 sync_log: {total} إجمالي | {pending} معلق")
    else:
        print("❌ sync_log غير موجود!")

    conn.close()
except Exception as e:
    print(f"❌ Error: {e}")

print()
print("🔍 Status:", get_sync_status())