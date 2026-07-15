import os

basedir = os.path.abspath(os.path.dirname(__file__))


def _normalize_db_url(url: str) -> str:
    # Railway (و بیشتر سرویس‌های میزبانی) متغیر DATABASE_URL را با پیشوند
    # 'postgres://' می‌دهند، اما SQLAlchemy جدید 'postgresql://' می‌خواهد.
    if url and url.startswith('postgres://'):
        url = url.replace('postgres://', 'postgresql://', 1)
    return url


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'hesab_karkhane_2024')

    # ===== در Railway: از متغیر محیطی DATABASE_URL (پلاگین Postgres) استفاده می‌شود =====
    # ===== در حالت محلی (بدون DATABASE_URL): همان SQLite قبلی برای تست سریع =====
    SQLALCHEMY_DATABASE_URI = _normalize_db_url(os.environ.get('DATABASE_URL')) or \
        'sqlite:///' + os.path.join(basedir, 'hesab_karkhane.db')

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {'pool_pre_ping': True}
