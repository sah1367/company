"""
اسکریپت یک‌باره برای اضافه کردن ستون 'checked' به جدول stock_transfer
بدون از دست رفتن هیچ داده‌ای.

نحوه اجرا:
1. این فایل را در همان پوشه‌ای که hesab_karkhane.db قرار دارد کپی کنید
   (همان پوشه‌ای که run.py در آن است).
2. در ترمینال بنویسید:  python migrate_add_checked_column.py
3. پیام "ستون با موفقیت اضافه شد" یا "ستون از قبل وجود دارد" را می‌بینید.
4. سرور Flask را دوباره اجرا کنید.
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'hesab_karkhane.db')

con = sqlite3.connect(DB_PATH)
cur = con.cursor()
cur.execute("PRAGMA table_info(stock_transfer)")
cols = [r[1] for r in cur.fetchall()]

if 'checked' in cols:
    print("ستون 'checked' از قبل در جدول stock_transfer وجود دارد. نیازی به کاری نیست.")
else:
    cur.execute("ALTER TABLE stock_transfer ADD COLUMN checked BOOLEAN DEFAULT 0")
    con.commit()
    print("ستون 'checked' با موفقیت به جدول stock_transfer اضافه شد. هیچ داده‌ای از بین نرفت.")

con.close()
