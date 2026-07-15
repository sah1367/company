from flask import Flask, flash, redirect, request, session
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from datetime import datetime

db = SQLAlchemy()

# ==========================================
# لیست ارزهای بین‌المللی برای فعال‌سازی خودکار
# (کدهایی که در ACTIVE_CODES هستند به‌صورت پیش‌فرض فعال ثبت می‌شوند)
# ==========================================
ACTIVE_CODES = {"AFN", "USD", "IRR", "EUR"}

CURRENCIES = [
    ("Afghan Afghani", "AFN"), ("Albanian Lek", "ALL"), ("Algerian Dinar", "DZD"),
    ("Angolan Kwanza", "AOA"), ("Argentine Peso", "ARS"), ("Armenian Dram", "AMD"),
    ("Aruban Florin", "AWG"), ("Australian Dollar", "AUD"), ("Azerbaijani Manat", "AZN"),
    ("Bahamian Dollar", "BSD"), ("Bahraini Dinar", "BHD"), ("Bangladeshi Taka", "BDT"),
    ("Barbadian Dollar", "BBD"), ("Belarusian Ruble", "BYN"), ("Belize Dollar", "BZD"),
    ("Bermudian Dollar", "BMD"), ("Bhutanese Ngultrum", "BTN"), ("Bolivian Boliviano", "BOB"),
    ("Bosnia-Herzegovina Convertible Mark", "BAM"), ("Botswana Pula", "BWP"),
    ("Brazilian Real", "BRL"), ("Brunei Dollar", "BND"), ("Bulgarian Lev", "BGN"),
    ("Burundian Franc", "BIF"), ("Cambodian Riel", "KHR"), ("Canadian Dollar", "CAD"),
    ("Cape Verdean Escudo", "CVE"), ("Cayman Islands Dollar", "KYD"),
    ("Central African CFA Franc", "XAF"), ("CFP Franc", "XPF"), ("Chilean Peso", "CLP"),
    ("Chinese Yuan", "CNY"), ("Colombian Peso", "COP"), ("Comorian Franc", "KMF"),
    ("Congolese Franc", "CDF"), ("Costa Rican Colon", "CRC"), ("Croatian Kuna", "HRK"),
    ("Cuban Peso", "CUP"), ("Czech Koruna", "CZK"), ("Danish Krone", "DKK"),
    ("Djiboutian Franc", "DJF"), ("Dominican Peso", "DOP"), ("East Caribbean Dollar", "XCD"),
    ("Egyptian Pound", "EGP"), ("Eritrean Nakfa", "ERN"), ("Ethiopian Birr", "ETB"),
    ("Euro", "EUR"), ("Fiji Dollar", "FJD"), ("Gambian Dalasi", "GMD"),
    ("Georgian Lari", "GEL"), ("Ghanaian Cedi", "GHS"), ("Gibraltar Pound", "GIP"),
    ("Guatemalan Quetzal", "GTQ"), ("Guinean Franc", "GNF"), ("Guyanese Dollar", "GYD"),
    ("Haitian Gourde", "HTG"), ("Honduran Lempira", "HNL"), ("Hong Kong Dollar", "HKD"),
    ("Hungarian Forint", "HUF"), ("Icelandic Krona", "ISK"), ("Indian Rupee", "INR"),
    ("Indonesian Rupiah", "IDR"), ("Iranian Rial", "IRR"), ("Iraqi Dinar", "IQD"),
    ("Israeli New Shekel", "ILS"), ("Jamaican Dollar", "JMD"), ("Japanese Yen", "JPY"),
    ("Jordanian Dinar", "JOD"), ("Kazakhstani Tenge", "KZT"), ("Kenyan Shilling", "KES"),
    ("Kuwaiti Dinar", "KWD"), ("Kyrgystani Som", "KGS"), ("Lao Kip", "LAK"),
    ("Lebanese Pound", "LBP"), ("Lesotho Loti", "LSL"), ("Liberian Dollar", "LRD"),
    ("Libyan Dinar", "LYD"), ("Macanese Pataca", "MOP"), ("Macedonian Denar", "MKD"),
    ("Malagasy Ariary", "MGA"), ("Malawian Kwacha", "MWK"), ("Malaysian Ringgit", "MYR"),
    ("Maldivian Rufiyaa", "MVR"), ("Mauritanian Ouguiya", "MRU"), ("Mauritian Rupee", "MUR"),
    ("Mexican Peso", "MXN"), ("Moldovan Leu", "MDL"), ("Mongolian Tugrik", "MNT"),
    ("Moroccan Dirham", "MAD"), ("Mozambican Metical", "MZN"), ("Myanmar Kyat", "MMK"),
    ("Namibian Dollar", "NAD"), ("Nepalese Rupee", "NPR"),
    ("Netherlands Antillean Guilder", "ANG"), ("New Taiwan Dollar", "TWD"),
    ("New Zealand Dollar", "NZD"), ("Nicaraguan Cordoba", "NIO"), ("Nigerian Naira", "NGN"),
    ("North Korean Won", "KPW"), ("Norwegian Krone", "NOK"), ("Omani Rial", "OMR"),
    ("Pakistani Rupee", "PKR"), ("Panamanian Balboa", "PAB"),
    ("Papua New Guinean Kina", "PGK"), ("Paraguayan Guarani", "PYG"), ("Peruvian Sol", "PEN"),
    ("Philippine Peso", "PHP"), ("Polish Zloty", "PLN"), ("Qatari Rial", "QAR"),
    ("Romanian Leu", "RON"), ("Russian Ruble", "RUB"), ("Rwandan Franc", "RWF"),
    ("Samoan Tala", "WST"), ("Saudi Riyal", "SAR"), ("Serbian Dinar", "RSD"),
    ("Seychellois Rupee", "SCR"), ("Sierra Leonean Leone", "SLL"),
    ("Singapore Dollar", "SGD"), ("Solomon Islands Dollar", "SBD"),
    ("Somali Shilling", "SOS"), ("South African Rand", "ZAR"), ("South Korean Won", "KRW"),
    ("South Sudanese Pound", "SSP"), ("Sri Lankan Rupee", "LKR"), ("Sudanese Pound", "SDG"),
    ("Surinamese Dollar", "SRD"), ("Swazi Lilangeni", "SZL"), ("Swedish Krona", "SEK"),
    ("Swiss Franc", "CHF"), ("Syrian Pound", "SYP"), ("Tajikistani Somoni", "TJS"),
    ("Tanzanian Shilling", "TZS"), ("Thai Baht", "THB"), ("Tongan Pa'anga", "TOP"),
    ("Trinidad and Tobago Dollar", "TTD"), ("Tunisian Dinar", "TND"), ("Turkish Lira", "TRY"),
    ("Turkmenistani Manat", "TMT"), ("Ugandan Shilling", "UGX"), ("Ukrainian Hryvnia", "UAH"),
    ("United Arab Emirates Dirham", "AED"), ("British Pound Sterling", "GBP"),
    ("US Dollar", "USD"), ("Uruguayan Peso", "UYU"), ("Uzbekistani Som", "UZS"),
    ("Vanuatu Vatu", "VUV"), ("Venezuelan Bolivar", "VES"), ("Vietnamese Dong", "VND"),
    ("West African CFA Franc", "XOF"), ("Yemeni Rial", "YER"), ("Zambian Kwacha", "ZMW"),
    ("Zimbabwean Dollar", "ZWL"),
]


def _seed_currencies():
    """ارزهای بین‌المللی را در جدول Currency ثبت می‌کند (در صورت نبود)، بدون نیاز به
    اجرای دستی activate_currencies.py — این تابع هر بار برنامه بالا می‌آید خودکار اجرا می‌شود."""
    from .models import Currency

    existing_codes = {c.code for c in Currency.query.all()}
    added = 0
    for name, code in CURRENCIES:
        if code in existing_codes:
            continue
        db.session.add(Currency(
            country_name=name, code=code,
            is_active=(code in ACTIVE_CODES)
        ))
        added += 1

    if added:
        db.session.commit()
        print(f"✅ {added} ارز جدید به‌صورت خودکار فعال/ثبت شد.")


def create_app():
    app = Flask(__name__)
    app.config.from_object('config.Config')

    db.init_app(app)

    from .routes import main
    app.register_blueprint(main)

    with app.app_context():
        db.create_all()

        # ===== ساخت خودکار کاربر ادمین پیش‌فرض در صورت نبود هیچ کاربری =====
        from .models import User
        if User.query.count() == 0:
            admin = User(username='admin', full_name='مدیر سیستم', role='admin')
            admin.set_password('admin123')
            db.session.add(admin)
            db.session.commit()

        # ===== ساخت خودکار رکورد تنظیمات فروشگاه/شرکت در صورت نبود =====
        from .models import CompanySettings
        if CompanySettings.query.count() == 0:
            db.session.add(CompanySettings(
                name='کارخانه تولید صنایع غذایی و نوشیدنی غیر الکلی تک'
            ))
            db.session.commit()

        # ===== فعال‌سازی خودکار واحدهای پولی (بدون نیاز به اجرای دستی اسکریپت جداگانه) =====
        _seed_currencies()

    @app.context_processor
    def inject_company_settings():
        from .models import CompanySettings
        company = CompanySettings.query.first()
        return dict(company=company)

    @app.context_processor
    def inject_menu_access():
        from .models import User
        from .routes import has_menu_access, menu_item_key
        user_id = session.get('user_id')
        menu_user = User.query.get(user_id) if user_id else None
        return dict(menu_user=menu_user, has_menu_access=has_menu_access, menu_item_key=menu_item_key)

    # ===== مدیریت خودکار خطاهای دیتابیس برای کل برنامه =====
    # هر بار که یک route خطا بدهد (مثلاً حذف رکوردی که جای دیگر استفاده شده)
    # این تابع به جای کرش کردن برنامه، پیام مناسب نشان می‌دهد و کاربر را برمی‌گرداند.

    @app.errorhandler(IntegrityError)
    def handle_integrity_error(e):
        db.session.rollback()
        flash('این عملیات ممکن نیست چون این رکورد در جای دیگری استفاده شده است.', 'danger')
        return redirect(request.referrer or '/')

    @app.errorhandler(SQLAlchemyError)
    def handle_db_error(e):
        db.session.rollback()
        flash('خطا در ارتباط با دیتابیس. دوباره تلاش کنید.', 'danger')
        return redirect(request.referrer or '/')

    @app.errorhandler(500)
    def handle_internal_error(e):
        db.session.rollback()
        flash('خطای داخلی سیستم رخ داد.', 'danger')
        return redirect(request.referrer or '/')

    return app
