# migrations_patch.py
import sqlite3
import os
from datetime import datetime

dbs = set()

# ⭐ اكتشف كل ملفات .db في كل الأماكن المحتملة
if os.path.exists('/data'):
    for root, _, files in os.walk('/data'):
        for f in files:
            if f.endswith('.db'):
                dbs.add(os.path.join(root, f))
else:
    if os.path.exists('garages'):
        for f in os.listdir('garages'):
            if f.endswith('.db'):
                dbs.add(os.path.join('garages', f))
    if os.path.exists('garages_registry.db'):
        dbs.add('garages_registry.db')
    if os.path.exists('garage.db'):
        dbs.add('garage.db')

print(f"📂 عدد قواعد البيانات: {len(dbs)}\n")

for db in sorted(dbs):
    print(f"🔧 {db}")
    try:
        conn = sqlite3.connect(db, timeout=30)
        cur = conn.cursor()
        for tbl, col, typ in [
            ('users', 'updated_at', 'TEXT'),
            ('parking_settings', 'updated_at', 'TEXT'),
            ('subscribers', 'updated_at', 'TEXT'),
            ('visitors', 'updated_at', 'TEXT'),
            ('spots', 'updated_at', 'TEXT'),
        ]:
            try:
                cur.execute(f"PRAGMA table_info({tbl})")
                cols = [c[1] for c in cur.fetchall()]
                if cols and col not in cols:
                    cur.execute(f"ALTER TABLE {tbl} ADD COLUMN {col} {typ}")
                    print(f"   ➕ {tbl}.{col}")
            except Exception as e:
                print(f"   ⚠️ {tbl}: {e}")

        # املأ updated_at الفاضي عشان المزامنة تشتغل
        now = datetime.now().isoformat()
        for tbl in ['subscribers', 'visitors', 'spots', 'users']:
            try:
                cur.execute(f"UPDATE {tbl} SET updated_at=? WHERE updated_at IS NULL", (now,))
            except Exception:
                pass

        conn.commit()
        conn.close()
        print("   ✅ تم")
    except Exception as e:
        print(f"   ❌ {e}")
    print()

print("🎉 انتهى")