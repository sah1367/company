"""
اسکریپت یک‌باره برای:
1. اضافه کردن ستون 'reports_restricted' به جدول users
2. ساخت جدول user_report_access (در صورت نبود)
بدون از دست رفتن هیچ داده‌ای.

نحوه اجرا:
1. این فایل را در همان پوشه‌ای که hesab_karkhane.db قرار دارد کپی کنید
   (همان پوشه‌ای که run.py در آن است).
2. در ترمینال بنویسید:  python migrate_user_report_access.py
3. سرور Flask را دوباره اجرا کنید.
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'hesab_karkhane.db')

con = sqlite3.connect(DB_PATH)
cur = con.cursor()

# --- ستون reports_restricted در جدول users ---
cur.execute("PRAGMA table_info(users)")
cols = [r[1] for r in cur.fetchall()]
if 'reports_restricted' in cols:
    print("ستون 'reports_restricted' از قبل در جدول users وجود دارد.")
else:
    cur.execute("ALTER TABLE users ADD COLUMN reports_restricted BOOLEAN DEFAULT 0")
    con.commit()
    print("ستون 'reports_restricted' با موفقیت به جدول users اضافه شد.")

# --- جدول user_report_access ---
cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user_report_access'")
if cur.fetchone():
    print("جدول 'user_report_access' از قبل وجود دارد.")
else:
    cur.execute("""
        CREATE TABLE user_report_access (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            category VARCHAR(50) NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)
    con.commit()
    print("جدول 'user_report_access' با موفقیت ساخته شد.")

con.close()
print("مهاجرت با موفقیت انجام شد. هیچ داده‌ای از بین نرفت.")
