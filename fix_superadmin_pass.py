import sqlite3
import hashlib
import os
from datetime import datetime

NEW_PASSWORD = "P@ssw0rd_@dmin"
hashed = hashlib.sha256(NEW_PASSWORD.encode()).hexdigest()
now = datetime.now().isoformat()

dbs = ['garage.db', 'garages_registry.db']
if os.path.exists('garages'):
    for f in os.listdir('garages'):
        if f.endswith('.db'):
            dbs.append(os.path.join('garages', f))

for db in dbs:
    if not os.path.exists(db):
        continue
    print(f"🔧 {db}")
    try:
        conn = sqlite3.connect(db, timeout=30)
        cur = conn.cursor()
        # تأكد إن الجدول موجود
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        if not cur.fetchone():
            print("   ⏭️ لا يوجد جدول users")
            conn.close()
            continue

        cur.execute("UPDATE users SET password=?, updated_at=? WHERE username='superadmin'",
                    (hashed, now))
        affected = cur.rowcount
        conn.commit()
        conn.close()

        if affected > 0:
            print(f"   ✅ تم تحديث باسورد superadmin ({affected} صف)")
        else:
            print(f"   ℹ️ لا يوجد user باسم superadmin")
    except Exception as e:
        print(f"   ❌ {e}")

print(f"\n🎉 الباسورد الجديد: {NEW_PASSWORD}")