# setup_db.py
# این فایل را هر زمان مدل جدیدی اضافه شد اجرا کنید تا جدول‌های دیتابیس ساخته شوند.
# اجرا: python setup_db.py

from app import create_app, db

app = create_app()

with app.app_context():
    print("در حال بررسی و ساخت جدول‌ها ...")
    db.create_all()
    print("✅ همه جدول‌ها بررسی/ساخته شدند.")
    print("🎉 آماده است. حالا می‌توانید run.py را اجرا کنید.")
