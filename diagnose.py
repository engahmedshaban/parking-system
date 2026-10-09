# diagnose.py
# تشخيص كامل لنظام المزامنة والداتا
import sqlite3
import os
import json

print("=" * 70)
print("🔍 تشخيص نظام Parking")
print("=" * 70)

# ============================================================
# 1) الـ Registry
# ============================================================
registry = 'garages_registry.db'
if os.path.exists('/data/garages_registry.db'):
    registry = '/data/garages_registry.db'

print(f"\n📁 ملف الـ Registry: {registry}")
if os.path.exists(registry):
    print(f"   الحجم: {os.path.getsize(registry) / 1024:.1f} KB")
    with sqlite3.connect(registry) as conn:
        conn.row_factory = sqlite3.Row
        garages = conn.execute("SELECT id, name, db_path, is_active FROM garages ORDER BY id").fetchall()
        print(f"\n   🏢 الجراجات ({len(garages)}):")
        for g in garages:
            d = dict(g)
            active = "🟢 نشط" if d['is_active'] else "⚪ موقوف"
            print(f"\n   {'─' * 60}")
            print(f"   ID: {d['id']}")
            print(f"   الاسم: {d['name']}")
            print(f"   المسار: {d['db_path']}")
            print(f"   الحالة: {active}")

            db_path = d['db_path']
            if os.path.exists(db_path):
                size = os.path.getsize(db_path) / 1024
                print(f"   📦 الحجم: {size:.1f} KB")
                try:
                    with sqlite3.connect(db_path) as gconn:
                        gconn.row_factory = sqlite3.Row

                        sub_count = gconn.execute("SELECT COUNT(*) as c FROM subscribers").fetchone()['c']
                        spot_count = gconn.execute("SELECT COUNT(*) as c FROM spots").fetchone()['c']
                        try:
                            vis_count = gconn.execute("SELECT COUNT(*) as c FROM visitors").fetchone()['c']
                        except Exception:
                            vis_count = "?"
                        print(f"   👤 المشتركين: {sub_count}")
                        print(f"   🅿️ الأماكن: {spot_count}")
                        print(f"   🚗 الزوار: {vis_count}")

                        sample = gconn.execute("SELECT name, car_number FROM subscribers LIMIT 5").fetchall()
                        if sample:
                            print(f"   📋 عينة:")
                            for s in sample:
                                print(f"      • {s['name']} ({s['car_number']})")
                        else:
                            print(f"   ⚠️ مفيش مشتركين في الملف ده!")
                except Exception as e:
                    print(f"   ❌ خطأ في القراءة: {e}")
            else:
                print(f"   ❌ الملف غير موجود على القرص")
else:
    print("   ❌ ملف الـ Registry غير موجود")

# ============================================================
# 2) ما تراه sync_engine
# ============================================================
print("\n" + "=" * 70)
print("🔄 ما تراه sync_engine")
print("=" * 70)

try:
    from sync_engine import get_local_db, take_snapshot, get_registry_db

    local_db = get_local_db()
    print(f"\n📁 get_local_db() بيستخدم: {local_db}")
    print(f"   موجود: {os.path.exists(local_db)}")
    if os.path.exists(local_db):
        print(f"   الحجم: {os.path.getsize(local_db) / 1024:.1f} KB")

    reg_db = get_registry_db()
    print(f"\n📁 get_registry_db() بيستخدم: {reg_db}")

    print(f"\n📸 محتوى Snapshot:")
    snap = take_snapshot()
    total = 0
    for db_key, tables in snap.get('dbs', {}).items():
        print(f"\n   [{db_key}]:")
        for table, rows in tables.items():
            count = len(rows)
            total += count
            status = "✅" if count > 0 else "⚠️"
            print(f"      {status} {table}: {count} سجل")
    print(f"\n   📊 إجمالي: {total} سجل")

except ImportError as e:
    print(f"\n❌ sync_engine مش موجود: {e}")
except Exception as e:
    print(f"\n❌ خطأ: {e}")
    import traceback
    traceback.print_exc()

# ============================================================
# 3) ملفات DB في المجلد
# ============================================================
print("\n" + "=" * 70)
print("📁 كل ملفات .db في المجلد")
print("=" * 70)

for root, dirs, files in os.walk('.'):
    # تجاهل مجلدات معينة
    if any(x in root for x in ['.git', '__pycache__', 'build', 'dist', '.venv', 'env']):
        continue
    for f in files:
        if f.endswith('.db'):
            path = os.path.join(root, f)
            size = os.path.getsize(path) / 1024
            print(f"\n   📄 {path}")
            print(f"      الحجم: {size:.1f} KB")
            try:
                with sqlite3.connect(path) as conn:
                    conn.row_factory = sqlite3.Row
                    tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
                    table_names = [t['name'] for t in tables]
                    if 'subscribers' in table_names:
                        count = conn.execute("SELECT COUNT(*) as c FROM subscribers").fetchone()['c']
                        print(f"      👤 مشتركين: {count}")
            except Exception:
                pass

# ============================================================
# 4) متغيرات البيئة
# ============================================================
print("\n" + "=" * 70)
print("🌍 متغيرات البيئة")
print("=" * 70)

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

for key in ['LOCAL_DB', 'DEVICE_ID', 'GIST_ID', 'GITHUB_TOKEN', 'SYNC_MODE']:
    val = os.environ.get(key, '')
    if key == 'GITHUB_TOKEN':
        val = (val[:10] + '...') if val else '(فاضي)'
    print(f"   {key} = {val or '(فاضي)'}")

print("\n" + "=" * 70)