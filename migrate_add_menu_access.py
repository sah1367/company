"""
اسکریپت یک‌باره برای فعال‌سازی سیستم «دسترسیهای منو»:
1. ستون 'menu_restricted' را به جدول users اضافه می‌کند.
2. جدول 'user_menu_access' را در صورت نبود می‌سازد.
بدون از دست رفتن هیچ داده‌ای.

نحوه اجرا:
1. این فایل را در همان پوشه‌ای که hesab_karkhane.db قرار دارد کپی کنید
   (همان پوشه‌ای که run.py در آن است).
2. در ترمینال بنویسید:  python migrate_add_menu_access.py
3. سرور Flask را دوباره اجرا کنید.
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'hesab_karkhane.db')

con = sqlite3.connect(DB_PATH)
cur = con.cursor()

# ---------- ستون menu_restricted در جدول users ----------
cur.execute("PRAGMA table_info(users)")
cols = [r[1] for r in cur.fetchall()]
if 'menu_restricted' in cols:
    print("ستون 'menu_restricted' از قبل در جدول users وجود دارد.")
else:
    cur.execute("ALTER TABLE users ADD COLUMN menu_restricted BOOLEAN DEFAULT 0")
    print("ستون 'menu_restricted' با موفقیت به جدول users اضافه شد.")

# ---------- جدول user_menu_access ----------
cur.execute("""
    CREATE TABLE IF NOT EXISTS user_menu_access (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        item_key VARCHAR(100) NOT NULL,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )
""")
print("جدول 'user_menu_access' آماده است.")

con.commit()
con.close()
print("مایگریشن با موفقیت انجام شد. هیچ داده‌ای از بین نرفت.")
