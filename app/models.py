from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from . import db


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    full_name = db.Column(db.String(100))
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default='user')     # admin / user
    is_active = db.Column(db.Boolean, default=True)
    reports_restricted = db.Column(db.Boolean, default=False, nullable=False)
    menu_restricted = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, raw_password):
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password):
        return check_password_hash(self.password_hash, raw_password)

    def __repr__(self):
        return f'{self.username}'


# ==========================================
# دسترسی کاربران به دسته‌های گزارش (تعریف دسترسی راپورها)
# ==========================================
class UserReportAccess(db.Model):
    __tablename__ = 'user_report_access'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    category = db.Column(db.String(50), nullable=False)  # کلید REPORT_PAGES مثل 'general', 'exchange'

    user = db.relationship('User', backref=db.backref('report_access', cascade='all, delete-orphan'))

    def __repr__(self):
        return f'{self.user_id}:{self.category}'


# ==========================================
# دسترسی کاربران به منوها و ریزجزئیات هر صفحه (تعریف دسترسیهای منو)
# ==========================================
class UserMenuAccess(db.Model):
    __tablename__ = 'user_menu_access'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    # کلید به شکل menu__item__row مثل 'warehouse__units__page' یا 'warehouse__units__list'
    item_key = db.Column(db.String(100), nullable=False)

    user = db.relationship('User', backref=db.backref('menu_access', cascade='all, delete-orphan'))

    def __repr__(self):
        return f'{self.user_id}:{self.item_key}'


# ==========================================
# تعریف فروشگاه/شرکت — تنظیمات سراسری (تک‌رکورد)
# ==========================================
class CompanySettings(db.Model):
    __tablename__ = 'company_settings'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False, default='کارخانه تولید صنایع غذایی و نوشیدنی غیر الکلی تک')
    latin_name = db.Column(db.String(200))
    phone1 = db.Column(db.String(30))
    phone2 = db.Column(db.String(30))
    phone_fixed = db.Column(db.String(30))
    address = db.Column(db.String(300))
    email = db.Column(db.String(120))
    logo_filename = db.Column(db.String(255))
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'{self.name}'


# ==========================================
# کارمندان — ثبت کتگوری کارمندان
# ==========================================
class EmployeeCategory(db.Model):
    __tablename__ = 'employee_category'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'{self.name}'


class Employee(db.Model):
    __tablename__ = "employees"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    father_name = db.Column(db.String(100))       # نام پدر
    tazkira_no = db.Column(db.String(50))           # شماره تذکره/کارت هویت
    phone = db.Column(db.String(20))
    category_id = db.Column(db.Integer, db.ForeignKey('employee_category.id'))
    position = db.Column(db.String(100))          # وظیفه/سمت
    address = db.Column(db.String(200))
    photo = db.Column(db.String(200))               # مسیر عکس در static/uploads/employees
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    category = db.relationship('EmployeeCategory')

    def __repr__(self):
        return f'{self.name}'


# ==========================================
# کارمندان — حاضری کارمند
# ==========================================
class EmployeeAttendance(db.Model):
    __tablename__ = 'employee_attendance'
    id = db.Column(db.Integer, primary_key=True)

    date = db.Column(db.Date, nullable=False)
    j_year = db.Column(db.Integer)
    j_month = db.Column(db.Integer)
    j_day = db.Column(db.Integer)

    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    status = db.Column(db.String(20), default='present')   # present / absent / leave
    notes = db.Column(db.String(300))

    check_in = db.Column(db.String(5))          # ساعت ورود واقعی، مثلاً "07:35"
    check_out = db.Column(db.String(5))          # ساعت خروج واقعی، مثلاً "18:10"

    worked_hours = db.Column(db.Float, default=0)      # مجموع ساعت کارکرد
    standard_hours = db.Column(db.Float, default=0)     # ساعت استاندارد همان روز (از قرارداد)
    overtime_hours = db.Column(db.Float, default=0)      # ساعت اضافه‌کاری
    daily_salary = db.Column(db.Float, default=0)          # معاش روزانه استاندارد (از قرارداد)
    overtime_pay = db.Column(db.Float, default=0)           # مقدار اضافه‌کاری به پول
    total_pay = db.Column(db.Float, default=0)               # معاش روزانه + اضافه‌کاری
    currency = db.Column(db.String(10))

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    employee = db.relationship('Employee')

    def __repr__(self):
        return f'{self.employee_id}: {self.status}'


# ==========================================
# کارمندان — قرارداد کارمند
# ==========================================
class EmployeeContract(db.Model):
    __tablename__ = 'employee_contract'
    id = db.Column(db.Integer, primary_key=True)

    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    position = db.Column(db.String(100))
    salary_amount = db.Column(db.Float, default=0)     # معاش ماهوار
    currency = db.Column(db.String(10))

    # ساعت کاری استاندارد روزانه (مثلاً 07:30 الی 17:30)
    standard_start = db.Column(db.String(5), default='07:30')
    standard_end = db.Column(db.String(5), default='17:30')
    work_days = db.Column(db.String(50), default='از شنبه تا پنج‌شنبه')
    duration_years = db.Column(db.Integer, default=1)

    start_j_year = db.Column(db.Integer)
    start_j_month = db.Column(db.Integer)
    start_j_day = db.Column(db.Integer)
    start_date = db.Column(db.Date)

    end_j_year = db.Column(db.Integer)
    end_j_month = db.Column(db.Integer)
    end_j_day = db.Column(db.Integer)
    end_date = db.Column(db.Date)

    notes = db.Column(db.String(300))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    employee = db.relationship('Employee')

    def __repr__(self):
        return f'{self.employee_id}: {self.salary_amount}'


# ==========================================
# کارمندان — کارت معاشات در هر برج (ماه)
# ==========================================
class EmployeeSalaryCard(db.Model):
    __tablename__ = 'employee_salary_card'
    id = db.Column(db.Integer, primary_key=True)

    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    j_year = db.Column(db.Integer, nullable=False)
    j_month = db.Column(db.Integer, nullable=False)      # برج (ماه شمسی)

    net_salary = db.Column(db.Float, default=0)             # معاش خالص (ماهوار، از قرارداد)
    days_in_month = db.Column(db.Integer, default=30)        # تعداد روزهای برج
    daily_salary = db.Column(db.Float, default=0)              # معاش روزانه = معاش خالص ÷ روزهای برج
    attendance_days = db.Column(db.Integer, default=0)          # تعداد روزهای حاضری
    attendance_salary = db.Column(db.Float, default=0)           # معاش روزهای حاضری = معاش روزانه × حاضری
    overtime_hours = db.Column(db.Float, default=0)                # مجموع ساعت اضافه‌کاری برج
    overtime_amount = db.Column(db.Float, default=0)                # مبلغ اضافه‌کاری
    total_amount = db.Column(db.Float, default=0)                    # مجموعه = معاش روزهای حاضری + اضافه‌کاری
    advance_payment = db.Column(db.Float, default=0)                  # پیش‌پرداخت
    payable_amount = db.Column(db.Float, default=0)                    # مبلغ قابل تادیه = مجموعه − پیش‌پرداخت

    currency = db.Column(db.String(10))
    notes = db.Column(db.String(300))                                   # ملاحظات
    is_paid = db.Column(db.Boolean, default=False)                        # پرداخت شده؟
    bank_id = db.Column(db.Integer, db.ForeignKey('bank.id'))              # پرداخت از کدام بانک/صندوق
    cash_transaction_id = db.Column(db.Integer, db.ForeignKey('cash_transaction.id'))  # سند برد مرتبط
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    employee = db.relationship('Employee')
    bank = db.relationship('Bank')

    def __repr__(self):
        return f'{self.employee_id}: {self.j_year}-{self.j_month}'


# ==========================================
# کارمندان — معاش کارمندان (پرداخت واقعی معاش)
# ==========================================
class EmployeeSalaryPayment(db.Model):
    __tablename__ = 'employee_salary_payment'
    id = db.Column(db.Integer, primary_key=True)

    date = db.Column(db.Date, nullable=False)
    j_year = db.Column(db.Integer)
    j_month = db.Column(db.Integer)
    j_day = db.Column(db.Integer)

    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    amount = db.Column(db.Float, default=0)
    currency = db.Column(db.String(10))
    bank_id = db.Column(db.Integer, db.ForeignKey('bank.id'))
    notes = db.Column(db.String(300))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.String(50))

    employee = db.relationship('Employee')
    bank = db.relationship('Bank')

    def __repr__(self):
        return f'{self.employee_id}: {self.amount}'


# ==========================================
# گدام (انبار) — واحد اندازه‌گیری
# ==========================================
class Quantity(db.Model):
    __tablename__ = 'quantity'
    id = db.Column(db.Integer, primary_key=True)
    quantity = db.Column(db.String(100), nullable=False)   # نام واحد: کیلوگرام، لیتر، دانه...
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'{self.quantity}'


# ==========================================
# گدام (انبار) — ثبت کتگوری
# ==========================================
class Category(db.Model):
    __tablename__ = 'category'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)   # نام کتگوری: مواد اولیه، محصول نهایی...
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'{self.name}'


# ==========================================
# گدام (انبار) — ثبت گدام
# ==========================================
class Stock(db.Model):
    __tablename__ = 'stock'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)       # نام گدام
    keeper = db.Column(db.String(100))                      # گدامدار
    phone = db.Column(db.String(30))                         # تلفن گدام
    address = db.Column(db.String(200))                      # آدرس گدام
    is_active = db.Column(db.Boolean, default=True)          # فعال / غیر فعال
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'{self.name}'


# ==========================================
# گدام (انبار) — ثبت کالا (اجناس)
# ==========================================
class Item(db.Model):
    __tablename__ = 'item'
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.Integer, unique=True)                       # کد کالا (خودکار)
    name = db.Column(db.String(150), nullable=False)                # نام جنس
    item_type = db.Column(db.String(20))                             # نوعیت جنس: ماده اولیه / محصول نهایی

    quantity_id = db.Column(db.Integer, db.ForeignKey('quantity.id'))   # واحد اندازه‌گیری
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'))  # کتگوری جنس

    sale_price = db.Column(db.Float, default=0)        # قیمت فروش
    max_price = db.Column(db.Float, default=0)         # حداکثر قیمت فروش
    min_price = db.Column(db.Float, default=0)         # حداقل قیمت فروش

    shelf_row = db.Column(db.String(20))                # آدرس - ردیف
    shelf_floor = db.Column(db.String(20))              # آدرس - طبقه
    shelf_number = db.Column(db.String(20))             # آدرس - شماره

    is_active = db.Column(db.Boolean, default=True)    # حالت جنس
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    unit = db.relationship('Quantity')
    category = db.relationship('Category')

    @property
    def shelf_address(self):
        """آدرس فشرده جنس در گدام، مثل (ر2ط3ش550). اگر هیچ بخشی ثبت نشده باشد '-' برمی‌گرداند."""
        parts = []
        if self.shelf_row:
            parts.append(f'ر{self.shelf_row}')
        if self.shelf_floor:
            parts.append(f'ط{self.shelf_floor}')
        if self.shelf_number:
            parts.append(f'ش{self.shelf_number}')
        return ''.join(parts) if parts else '-'

    def __repr__(self):
        return f'{self.name}'


# ==========================================
# گدام (انبار) — ثبت حساب افتتاحیه
# ==========================================
class OpeningBalance(db.Model):
    __tablename__ = 'opening_balance'
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)               # تاریخ (میلادی ذخیره، نمایش شمسی)
    j_year = db.Column(db.Integer)                            # سال شمسی (برای نمایش مستقیم)
    j_month = db.Column(db.Integer)                           # ماه شمسی
    j_day = db.Column(db.Integer)                             # روز شمسی

    category_id = db.Column(db.Integer, db.ForeignKey('category.id'))   # کتگوری جنس
    name = db.Column(db.String(150), nullable=False)         # نام جنس (متن آزاد)

    opening_qty = db.Column(db.Float, default=0)             # موجودی اولیه
    total_price = db.Column(db.Float, default=0)             # قیمت کل (به واحد پولی انتخابی)
    total_price_usd = db.Column(db.Float, default=0)         # قیمت کل به دالر (ارز پایه — همیشه محاسبه و ذخیره می‌شود)

    currency = db.Column(db.String(20))                       # واحد پولی
    currency_rate = db.Column(db.Float, default=1)           # نرخ روز: ۱ دالر = ؟ واحد پولی انتخابی

    quantity_id = db.Column(db.Integer, db.ForeignKey('quantity.id'))   # واحد اندازه‌گیری (از گزارش جدول)
    stock_id = db.Column(db.Integer, db.ForeignKey('stock.id'))         # گدام

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    category = db.relationship('Category')
    unit = db.relationship('Quantity')
    stock = db.relationship('Stock')

    def __repr__(self):
        return f'{self.name}'


# ==========================================
# گدام (انبار) — انتقال بین گدام‌ها
# ==========================================
class StockTransfer(db.Model):
    __tablename__ = 'stock_transfer'
    id = db.Column(db.Integer, primary_key=True)

    date = db.Column(db.Date, nullable=False)
    j_year = db.Column(db.Integer)
    j_month = db.Column(db.Integer)
    j_day = db.Column(db.Integer)

    item_name = db.Column(db.String(150), nullable=False)   # نام جنس

    source_stock_id = db.Column(db.Integer, db.ForeignKey('stock.id'))   # گدام مبدا
    destination_stock_id = db.Column(db.Integer, db.ForeignKey('stock.id'))  # گدام مقصد

    current_qty = db.Column(db.Float, default=0)   # موجودی کالا (در گدام مبدا، نمایشی)
    amount = db.Column(db.Float, default=0)        # مقدار
    count = db.Column(db.Float, default=0)          # تعداد

    driver_name = db.Column(db.String(100))         # موتروان
    plate_no = db.Column(db.String(50))              # نمبر موتر
    driver_phone = db.Column(db.String(30))          # شماره تماس موتروان

    commission = db.Column(db.Float, default=0)      # کمیشن
    advance_fare = db.Column(db.Float, default=0)     # پیش کرایه
    fare_per_ton = db.Column(db.Float, default=0)     # کرایه فی تن

    notes = db.Column(db.String(300))                  # توضیحات
    checked = db.Column(db.Boolean, default=False)      # چک شد (تایید در گزارش جزئیات انتقال)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    source_stock = db.relationship('Stock', foreign_keys=[source_stock_id])
    destination_stock = db.relationship('Stock', foreign_keys=[destination_stock_id])

    def __repr__(self):
        return f'{self.item_name}'


# ==========================================
# گدام (انبار) — بخش ترکیب اجناس (تولید/BOM)
# ==========================================
class Production(db.Model):
    """محصول نهایی تولید شده"""
    __tablename__ = 'production'
    id = db.Column(db.Integer, primary_key=True)

    item_name = db.Column(db.String(150), nullable=False)   # کالا (محصول تولیدشده)
    production_line = db.Column(db.String(150))               # خط تولید

    amount = db.Column(db.Float, default=0)                    # مقدار (محصول تولیدشده)
    quantity_id = db.Column(db.Integer, db.ForeignKey('quantity.id'))  # واحد اندازه‌گیری
    stock_id = db.Column(db.Integer, db.ForeignKey('stock.id'))         # گدام

    date = db.Column(db.Date, nullable=False)
    j_year = db.Column(db.Integer)
    j_month = db.Column(db.Integer)
    j_day = db.Column(db.Integer)

    unit_price = db.Column(db.Float, default=0)               # فی (قیمت واحد محصول)
    total_price = db.Column(db.Float, default=0)              # قیمت کالای تولید شده (جمع مواد)
    notes = db.Column(db.String(300))                            # توضیحات

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    unit = db.relationship('Quantity')
    stock = db.relationship('Stock')
    lines = db.relationship('ProductionLine', backref='production',
                             cascade='all, delete-orphan', lazy=True)

    def __repr__(self):
        return f'{self.item_name}'


class ProductionLine(db.Model):
    """هر ردیف ماده اولیه مصرفی در یک تولید"""
    __tablename__ = 'production_line'
    id = db.Column(db.Integer, primary_key=True)
    production_id = db.Column(db.Integer, db.ForeignKey('production.id'), nullable=False)

    item_name = db.Column(db.String(150))                       # جنس (ماده اولیه)
    stock_id = db.Column(db.Integer, db.ForeignKey('stock.id'))  # گدام
    quantity_id = db.Column(db.Integer, db.ForeignKey('quantity.id'))  # واحداندازه‌گیری

    available_qty = db.Column(db.Float, default=0)               # موجودی
    amount = db.Column(db.Float, default=0)                        # مقدار مصرفی
    price = db.Column(db.Float, default=0)                          # قیمت فی واحد
    total = db.Column(db.Float, default=0)                          # مجموع (amount * price)

    row_no = db.Column(db.Integer, default=0)                       # شماره ردیف (1 تا 20)

    stock = db.relationship('Stock')
    unit = db.relationship('Quantity')


# ==========================================
# گدام (انبار) — موجودی فعلی (منبع واحد حقیقت)
# ==========================================
class StockBalance(db.Model):
    """
    یک ردیف ثابت برای هر ترکیب (کالا + گدام).
    current_qty همیشه نشان‌دهنده موجودی واقعی و به‌روز است.
    هیچ بخشی مستقیماً این عدد را حدس نمی‌زند — فقط از طریق adjust_balance() در routes.py تغییر می‌کند.
    """
    __tablename__ = 'stock_balance'
    id = db.Column(db.Integer, primary_key=True)

    item_name = db.Column(db.String(150), nullable=False)
    stock_id = db.Column(db.Integer, db.ForeignKey('stock.id'), nullable=False)

    current_qty = db.Column(db.Float, default=0)        # موجودی فعلی (فیزیکی واقعی)
    reserved_qty = db.Column(db.Float, default=0)         # مقدار رزروشده برای سفارشات تأیید نشده
    last_price = db.Column(db.Float, default=0)          # آخرین قیمت فی واحد (دالر)
    quantity_id = db.Column(db.Integer, db.ForeignKey('quantity.id'))  # آخرین واحد اندازه‌گیری

    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    stock = db.relationship('Stock')
    unit = db.relationship('Quantity')

    __table_args__ = (db.UniqueConstraint('item_name', 'stock_id', name='uq_item_stock'),)

    def __repr__(self):
        return f'{self.item_name} @ {self.stock_id}: {self.current_qty}'


# ==========================================
# گدام (انبار) — کم شدن از گدام
# ==========================================
class StockOut(db.Model):
    __tablename__ = 'stock_out'
    id = db.Column(db.Integer, primary_key=True)

    date = db.Column(db.Date, nullable=False)
    j_year = db.Column(db.Integer)
    j_month = db.Column(db.Integer)
    j_day = db.Column(db.Integer)

    category_id = db.Column(db.Integer, db.ForeignKey('category.id'))
    item_name = db.Column(db.String(150), nullable=False)
    amount = db.Column(db.Float, default=0)                      # کاهش از گدام (مقدار)
    stock_id = db.Column(db.Integer, db.ForeignKey('stock.id'))

    balance_after = db.Column(db.Float, default=0)               # بالانس بعد از این کاهش
    notes = db.Column(db.String(300))

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    category = db.relationship('Category')
    stock = db.relationship('Stock')

    def __repr__(self):
        return f'{self.item_name}'


# ==========================================
# گدام (انبار) — افزایش به گدام
# ==========================================
class StockIn(db.Model):
    __tablename__ = 'stock_in'
    id = db.Column(db.Integer, primary_key=True)

    date = db.Column(db.Date, nullable=False)
    j_year = db.Column(db.Integer)
    j_month = db.Column(db.Integer)
    j_day = db.Column(db.Integer)

    category_id = db.Column(db.Integer, db.ForeignKey('category.id'))
    item_name = db.Column(db.String(150), nullable=False)   # نام جنس
    amount = db.Column(db.Float, default=0)                    # افزایش به گدام (مقدار)
    stock_id = db.Column(db.Integer, db.ForeignKey('stock.id'))  # گدام

    balance_after = db.Column(db.Float, default=0)              # بالانس بعد از افزایش (نمایشی)
    notes = db.Column(db.String(300))

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    category = db.relationship('Category')
    stock = db.relationship('Stock')

    def __repr__(self):
        return f'{self.item_name}'


# ==========================================
# خرید از شرکت‌ها — ثبت نام فروشنده کالا
# ==========================================
class Vendor(db.Model):
    __tablename__ = 'vendor'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)     # نام فروشنده کالا
    address = db.Column(db.String(200))                    # آدرس
    book_no = db.Column(db.String(50))                      # شماره کتابچه
    phone = db.Column(db.String(30))                         # تلفن
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'{self.name}'


# ==========================================
# خرید از شرکت‌ها — حساب افتتاحیه فروشنده
# ==========================================
class VendorOpening(db.Model):
    __tablename__ = 'vendor_opening'
    id = db.Column(db.Integer, primary_key=True)

    date = db.Column(db.Date, nullable=False)
    j_year = db.Column(db.Integer)
    j_month = db.Column(db.Integer)
    j_day = db.Column(db.Integer)

    vendor_id = db.Column(db.Integer, db.ForeignKey('vendor.id'), nullable=False)
    currency = db.Column(db.String(10))                       # واحدپول
    amount = db.Column(db.Float, default=0)                     # حساب افتتاحیه (مبلغ)
    account_type = db.Column(db.String(20))                      # نوعیت حساب: payable (بدهی ما) / receivable (طلب ما)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    vendor = db.relationship('Vendor')

    def __repr__(self):
        return f'{self.vendor_id}: {self.amount}'


# ==========================================
# خرید از شرکت‌ها — فاکتور خرید
# ==========================================
class PurchaseInvoice(db.Model):
    __tablename__ = 'purchase_invoice'
    id = db.Column(db.Integer, primary_key=True)

    invoice_no = db.Column(db.Integer, unique=True)            # شماره فاکتور (خودکار)
    time_str = db.Column(db.String(20))                          # ساعت (متن، مثل 07:18:55)

    date = db.Column(db.Date, nullable=False)
    j_year = db.Column(db.Integer)
    j_month = db.Column(db.Integer)
    j_day = db.Column(db.Integer)

    vendor_id = db.Column(db.Integer, db.ForeignKey('vendor.id'), nullable=False)
    bank_id = db.Column(db.Integer, db.ForeignKey('bank.id'))    # بانک (وصل به جدول بانک‌ها)
    bank_name = db.Column(db.String(100))                        # بانک (نگهداری برای سازگاری با رکوردهای قدیمی)
    currency = db.Column(db.String(10))                           # واحدپول
    exchange_rate = db.Column(db.Float, default=1)               # نرخ تبدیل (به دالر)
    delivery = db.Column(db.String(100))                          # تحویل بار

    # پرداخت نقدی
    total_amount = db.Column(db.Float, default=0)                # مجموعه فاکتور (به واحدپول انتخابی)
    total_amount_usd = db.Column(db.Float, default=0)            # مجموعه فاکتور (دالر — ارز پایه)
    loading_fee = db.Column(db.Float, default=0)                 # هزینه بارگیری
    discount = db.Column(db.Float, default=0)                    # تخفیف
    paid_amount = db.Column(db.Float, default=0)                 # مقدار پرداختی
    remaining = db.Column(db.Float, default=0)                   # باقی (بدهی به فروشنده)
    notes = db.Column(db.String(300))

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.String(50))

    vendor = db.relationship('Vendor')
    bank = db.relationship('Bank')
    lines = db.relationship('PurchaseInvoiceLine', backref='invoice',
                             cascade='all, delete-orphan', lazy=True)

    def __repr__(self):
        return f'فاکتور #{self.invoice_no}'


class PurchaseInvoiceLine(db.Model):
    """هر ردیف کالای خریداری‌شده در یک فاکتور"""
    __tablename__ = 'purchase_invoice_line'
    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('purchase_invoice.id'), nullable=False)

    item_name = db.Column(db.String(150))                          # نام جنس
    stock_id = db.Column(db.Integer, db.ForeignKey('stock.id'))      # گدام
    quantity_id = db.Column(db.Integer, db.ForeignKey('quantity.id'))  # واحداندازه‌گیری

    available_qty = db.Column(db.Float, default=0)                   # موجودی گدام (نمایشی، قبل از این خرید)
    price = db.Column(db.Float, default=0)                            # فی (قیمت واحد، به واحدپول فاکتور)
    amount = db.Column(db.Float, default=0)                            # مقدار/توزین
    total = db.Column(db.Float, default=0)                              # مجموع (amount * price)

    row_no = db.Column(db.Integer, default=0)

    stock = db.relationship('Stock')
    unit = db.relationship('Quantity')


# ==========================================
# خرید از شرکت‌ها — بار برگشتی فروشنده (فاکتور برگشت خرید / Debit Note)
# قاعده بین‌المللی: بار برگشتی، دقیقاً مثل فاکتور خرید ثبت می‌شود اما در جهت معکوس:
#   - از موجودی گدام کم می‌شود (کالا به فروشنده برگردانده شده)
#   - بدهی ما به فروشنده به اندازه مبلغ بار برگشتی کاهش می‌یابد
#     (اگر فروشنده قبلاً تمام پول جنس را گرفته باشد، این کاهش از صفر هم می‌گذرد
#      و فروشنده به ما بدهکار می‌شود؛ اگر نگرفته باشد، صرفاً بدهی ما تسویه/کم می‌شود)
# ==========================================
class VendorReturn(db.Model):
    __tablename__ = 'vendor_return'
    id = db.Column(db.Integer, primary_key=True)

    return_no = db.Column(db.Integer, unique=True)              # شماره بار برگشتی (خودکار)
    time_str = db.Column(db.String(20))                            # ساعت

    date = db.Column(db.Date, nullable=False)
    j_year = db.Column(db.Integer)
    j_month = db.Column(db.Integer)
    j_day = db.Column(db.Integer)

    vendor_id = db.Column(db.Integer, db.ForeignKey('vendor.id'), nullable=False)
    currency = db.Column(db.String(10))                             # واحدپول
    exchange_rate = db.Column(db.Float, default=1)                 # نرخ تبدیل (به دالر)

    total_amount = db.Column(db.Float, default=0)                  # مجموعه بار برگشتی (به واحدپول انتخابی)
    total_amount_usd = db.Column(db.Float, default=0)              # مجموعه بار برگشتی (دالر)
    notes = db.Column(db.String(300))

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.String(50))

    vendor = db.relationship('Vendor')
    lines = db.relationship('VendorReturnLine', backref='return_invoice',
                             cascade='all, delete-orphan', lazy=True)

    def __repr__(self):
        return f'بار برگشتی #{self.return_no}'


class VendorReturnLine(db.Model):
    """هر ردیف کالای برگشت‌داده‌شده در یک بار برگشتی"""
    __tablename__ = 'vendor_return_line'
    id = db.Column(db.Integer, primary_key=True)
    return_id = db.Column(db.Integer, db.ForeignKey('vendor_return.id'), nullable=False)

    item_name = db.Column(db.String(150))                            # نام جنس
    stock_id = db.Column(db.Integer, db.ForeignKey('stock.id'))        # گدام
    quantity_id = db.Column(db.Integer, db.ForeignKey('quantity.id'))    # واحداندازه‌گیری

    available_qty = db.Column(db.Float, default=0)                     # موجودی گدام (نمایشی، قبل از این برگشت)
    price = db.Column(db.Float, default=0)                              # فی
    amount = db.Column(db.Float, default=0)                              # مقدار/توزین برگشتی
    total = db.Column(db.Float, default=0)                                # مجموع (amount * price)

    row_no = db.Column(db.Integer, default=0)

    stock = db.relationship('Stock')
    unit = db.relationship('Quantity')


# ==========================================
# مشتریان — بار برگشتی مشتری (مرجوعی)
# دقیقاً برعکس فاکتور فروش: کالا به گدام برمی‌گردد (اضافه می‌شود) و
# طلب ما از مشتری به اندازه مبلغ برگشتی کم می‌شود.
# ==========================================
class CustomerReturn(db.Model):
    __tablename__ = 'customer_return'
    id = db.Column(db.Integer, primary_key=True)

    return_no = db.Column(db.Integer, unique=True)              # شماره بار برگشتی (خودکار)
    time_str = db.Column(db.String(20))                            # ساعت

    date = db.Column(db.Date, nullable=False)
    j_year = db.Column(db.Integer)
    j_month = db.Column(db.Integer)
    j_day = db.Column(db.Integer)

    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'), nullable=False)
    currency = db.Column(db.String(10))                             # واحدپول
    exchange_rate = db.Column(db.Float, default=1)                 # نرخ تبدیل (به دالر)

    total_amount = db.Column(db.Float, default=0)                  # مجموعه بار برگشتی (به واحدپول انتخابی)
    total_amount_usd = db.Column(db.Float, default=0)              # مجموعه بار برگشتی (دالر)
    notes = db.Column(db.String(300))

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.String(50))

    customer = db.relationship('Customer')
    lines = db.relationship('CustomerReturnLine', backref='return_invoice',
                             cascade='all, delete-orphan', lazy=True)

    def __repr__(self):
        return f'بار برگشتی مشتری #{self.return_no}'


class CustomerReturnLine(db.Model):
    """هر ردیف کالای برگشت‌داده‌شده توسط مشتری در یک بار برگشتی"""
    __tablename__ = 'customer_return_line'
    id = db.Column(db.Integer, primary_key=True)
    return_id = db.Column(db.Integer, db.ForeignKey('customer_return.id'), nullable=False)

    item_name = db.Column(db.String(150))                            # نام جنس
    stock_id = db.Column(db.Integer, db.ForeignKey('stock.id'))        # گدام
    quantity_id = db.Column(db.Integer, db.ForeignKey('quantity.id'))    # واحداندازه‌گیری

    available_qty = db.Column(db.Float, default=0)                     # موجودی گدام (نمایشی، قبل از این برگشت)
    price = db.Column(db.Float, default=0)                              # فی
    amount = db.Column(db.Float, default=0)                              # مقدار وزن برگشتی
    count_desc = db.Column(db.String(50))                                # تعداد (اختیاری، مثل فاکتور فروش)
    total = db.Column(db.Float, default=0)                                # مجموع

    row_no = db.Column(db.Integer, default=0)

    stock = db.relationship('Stock')
    unit = db.relationship('Quantity')


# ==========================================
# خرید از شرکت‌ها — پرداخت به فروشنده
# ==========================================
class VendorPayment(db.Model):
    __tablename__ = 'vendor_payment'
    id = db.Column(db.Integer, primary_key=True)

    date = db.Column(db.Date, nullable=False)
    j_year = db.Column(db.Integer)
    j_month = db.Column(db.Integer)
    j_day = db.Column(db.Integer)

    vendor_id = db.Column(db.Integer, db.ForeignKey('vendor.id'), nullable=False)
    amount = db.Column(db.Float, default=0)              # مقدار پرداختی
    currency = db.Column(db.String(10))                     # واحدپول
    notes = db.Column(db.String(300))

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.String(50))

    vendor = db.relationship('Vendor')

    def __repr__(self):
        return f'{self.vendor_id}: {self.amount}'


# ==========================================
# مشتریان — ثبت کتگوری مشتری
# ==========================================
class CustomerCategory(db.Model):
    __tablename__ = 'customer_category'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)   # نام کتگوری مشتری
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'{self.name}'


# ==========================================
# مشتریان — ثبت نام مشتری
# ==========================================
class Customer(db.Model):
    __tablename__ = 'customer'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)      # نام مشتری
    address = db.Column(db.String(200))                      # آدرس
    book_no = db.Column(db.String(50))                        # شماره کتابچه
    phone = db.Column(db.String(30))                           # تلفن
    category_id = db.Column(db.Integer, db.ForeignKey('customer_category.id'))  # ثبت کتگوری
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    category = db.relationship('CustomerCategory')

    def __repr__(self):
        return f'{self.name}'


# ==========================================
# مشتریان — حساب افتتاحیه مشتری
# ==========================================
class CustomerOpening(db.Model):
    __tablename__ = 'customer_opening'
    id = db.Column(db.Integer, primary_key=True)

    date = db.Column(db.Date, nullable=False)
    j_year = db.Column(db.Integer)
    j_month = db.Column(db.Integer)
    j_day = db.Column(db.Integer)

    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'), nullable=False)
    currency = db.Column(db.String(10))                       # واحدپول
    amount = db.Column(db.Float, default=0)                     # حساب افتتاحیه (مبلغ، همیشه مثبت ذخیره می‌شود)
    account_type = db.Column(db.String(20))                      # نوعیت حساب: receivable (طلب ما از مشتری) / payable (بدهی ما به مشتری)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    customer = db.relationship('Customer')

    def __repr__(self):
        return f'{self.customer_id}: {self.amount}'


# ==========================================
# مشتریان — سفارشات مشتری
# ==========================================
class CustomerOrder(db.Model):
    __tablename__ = 'customer_order'
    id = db.Column(db.Integer, primary_key=True)

    order_no = db.Column(db.Integer, unique=True)              # شماره سفارش (خودکار)
    time_str = db.Column(db.String(20))

    date = db.Column(db.Date, nullable=False)
    j_year = db.Column(db.Integer)
    j_month = db.Column(db.Integer)
    j_day = db.Column(db.Integer)

    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'), nullable=False)
    total_amount = db.Column(db.Float, default=0)                # مجموع سفارش

    status = db.Column(db.String(20), default='pending')          # pending (در انتظار) / invoiced (فاکتور شده) / cancelled (لغو شده)
    invoice_ref = db.Column(db.String(50))                          # شماره فاکتور فروش مرتبط (وقتی نهایی شد)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    customer = db.relationship('Customer')
    lines = db.relationship('CustomerOrderLine', backref='order',
                             cascade='all, delete-orphan', lazy=True)

    def __repr__(self):
        return f'سفارش #{self.order_no}'


class CustomerOrderLine(db.Model):
    __tablename__ = 'customer_order_line'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('customer_order.id'), nullable=False)

    item_name = db.Column(db.String(150))
    stock_id = db.Column(db.Integer, db.ForeignKey('stock.id'))
    quantity_id = db.Column(db.Integer, db.ForeignKey('quantity.id'))

    available_qty = db.Column(db.Float, default=0)       # موجودی گدام (نمایشی، قبل از این سفارش)
    price = db.Column(db.Float, default=0)
    amount = db.Column(db.Float, default=0)                        # مقدار وزن (وزن یک واحد/کارتن، یا وزن کل اگر تعداد خالی باشد)
    count_desc = db.Column(db.String(100))                          # تعداد (عدد؛ مثلاً تعداد کارتن). اگر پر شود: جمع = تعداد × فی، رزرو/کسر گدام هم بر اساس تعداد
    total = db.Column(db.Float, default=0)

    row_no = db.Column(db.Integer, default=0)

    stock = db.relationship('Stock')
    unit = db.relationship('Quantity')


# ==========================================
# مشتریان — فاکتور فروش
# ==========================================
class SalesInvoice(db.Model):
    __tablename__ = 'sales_invoice'
    id = db.Column(db.Integer, primary_key=True)

    invoice_no = db.Column(db.Integer, unique=True)            # شماره فاکتور (خودکار، قابل ویرایش)
    time_str = db.Column(db.String(20))

    date = db.Column(db.Date, nullable=False)
    j_year = db.Column(db.Integer)
    j_month = db.Column(db.Integer)
    j_day = db.Column(db.Integer)

    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'), nullable=False)
    bank_id = db.Column(db.Integer, db.ForeignKey('bank.id'))       # بانک/صندوق دریافت‌کننده پرداخت
    bank_name = db.Column(db.String(100))
    currency = db.Column(db.String(10))
    exchange_rate = db.Column(db.Float, default=1)
    delivery = db.Column(db.String(100))                          # تحویل بار

    order_ref_id = db.Column(db.Integer, db.ForeignKey('customer_order.id'))  # سفارش مرتبط (اختیاری)

    total_amount = db.Column(db.Float, default=0)
    total_amount_usd = db.Column(db.Float, default=0)
    loading_fee = db.Column(db.Float, default=0)
    discount = db.Column(db.Float, default=0)
    paid_amount = db.Column(db.Float, default=0)
    remaining = db.Column(db.Float, default=0)
    notes = db.Column(db.String(300))

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.String(50))

    customer = db.relationship('Customer')
    bank = db.relationship('Bank')
    order_ref = db.relationship('CustomerOrder')
    lines = db.relationship('SalesInvoiceLine', backref='invoice',
                             cascade='all, delete-orphan', lazy=True)

    def __repr__(self):
        return f'فاکتور فروش #{self.invoice_no}'


class SalesInvoiceLine(db.Model):
    __tablename__ = 'sales_invoice_line'
    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('sales_invoice.id'), nullable=False)

    item_name = db.Column(db.String(150))
    stock_id = db.Column(db.Integer, db.ForeignKey('stock.id'))
    quantity_id = db.Column(db.Integer, db.ForeignKey('quantity.id'))

    available_qty = db.Column(db.Float, default=0)
    price = db.Column(db.Float, default=0)
    amount = db.Column(db.Float, default=0)                        # مقدار وزن (وزن یک واحد/کارتن، یا وزن کل اگر تعداد خالی باشد)
    count_desc = db.Column(db.String(100))                          # تعداد (عدد؛ مثلاً تعداد کارتن). اگر پر شود: جمع = تعداد × فی و وزن کل = مقدار × تعداد
    total = db.Column(db.Float, default=0)

    row_no = db.Column(db.Integer, default=0)

    stock = db.relationship('Stock')
    unit = db.relationship('Quantity')


# ==========================================
# بانک‌ها — ثبت واحدپولی
# ==========================================
class Currency(db.Model):
    __tablename__ = 'currency'
    id = db.Column(db.Integer, primary_key=True)
    country_name = db.Column(db.String(100), nullable=False)   # نام کشور/ارز (مثل Andorran Peseta)
    code = db.Column(db.String(10), nullable=False)              # کد ارز (مثل ADP)
    is_active = db.Column(db.Boolean, default=False)              # فعال / غیرفعال

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'{self.country_name} ({self.code})'


# ==========================================
# بانک‌ها — نرخ واحدپولی
# ==========================================
class CurrencyRate(db.Model):
    __tablename__ = 'currency_rate'
    id = db.Column(db.Integer, primary_key=True)

    date = db.Column(db.Date, nullable=False)
    j_year = db.Column(db.Integer)
    j_month = db.Column(db.Integer)
    j_day = db.Column(db.Integer)

    currency_id = db.Column(db.Integer, db.ForeignKey('currency.id'), nullable=False)
    rate = db.Column(db.Float, nullable=False, default=1)   # نرخ تبدیل: ۱ دالر = ؟ این واحدپولی

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    currency = db.relationship('Currency')

    def __repr__(self):
        return f'{self.currency_id}: {self.rate}'


# ==========================================
# بانک‌ها — ثبت بانک
# ==========================================
class Bank(db.Model):
    __tablename__ = 'bank'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)       # نام بانک
    account_no = db.Column(db.String(50))                    # شماره حساب
    branch = db.Column(db.String(100))                        # شعبه
    currency_id = db.Column(db.Integer, db.ForeignKey('currency.id'))  # واحدپولی حساب
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    currency = db.relationship('Currency')

    def __repr__(self):
        return f'{self.name}'


# ==========================================
# بانک‌ها — ثبت حساب افتتاحیه بانک
# ==========================================
class BankOpening(db.Model):
    __tablename__ = 'bank_opening'
    id = db.Column(db.Integer, primary_key=True)

    date = db.Column(db.Date, nullable=False)
    j_year = db.Column(db.Integer)
    j_month = db.Column(db.Integer)
    j_day = db.Column(db.Integer)

    bank_id = db.Column(db.Integer, db.ForeignKey('bank.id'), nullable=False)
    currency_id = db.Column(db.Integer, db.ForeignKey('currency.id'))
    amount = db.Column(db.Float, default=0)                      # حساب افتتاحیه
    account_type = db.Column(db.String(20))                        # نوعیت حساب: رسیدگی (دریافتی) / پردگی (پرداختی)
    notes = db.Column(db.String(300))

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    bank = db.relationship('Bank')
    currency = db.relationship('Currency')

    def __repr__(self):
        return f'{self.bank_id}: {self.amount}'


# ==========================================
# مصارف — ثبت کتگوری مصارف
# ==========================================
class ExpenseCategory(db.Model):
    __tablename__ = 'expense_category'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)   # نام کتگوری مصارف
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'{self.name}'


# ==========================================
# مصارف — ثبت مصارف (تعریف نام/شرح مصرف)
# ==========================================
class Expense(db.Model):
    __tablename__ = 'expense'
    id = db.Column(db.Integer, primary_key=True)
    category_id = db.Column(db.Integer, db.ForeignKey('expense_category.id'))  # کتگوری مصارف
    recipient = db.Column(db.String(150), nullable=False)             # گیرنده مصرف (نام مصرف در جدول)
    notes = db.Column(db.String(300))                                  # توضیحات
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    category = db.relationship('ExpenseCategory')

    def __repr__(self):
        return f'{self.recipient}'


# ==========================================
# مصارف — شرح مصارف (ثبت واقعی هزینه)
# ==========================================
class ExpenseDetail(db.Model):
    __tablename__ = 'expense_detail'
    id = db.Column(db.Integer, primary_key=True)

    date = db.Column(db.Date, nullable=False)
    j_year = db.Column(db.Integer)
    j_month = db.Column(db.Integer)
    j_day = db.Column(db.Integer)

    currency_id = db.Column(db.Integer, db.ForeignKey('currency.id'))
    category_id = db.Column(db.Integer, db.ForeignKey('expense_category.id'))
    recipient = db.Column(db.String(150))                          # گیرنده مصرف
    amount = db.Column(db.Float, default=0)                          # مقدار (به واحدپول انتخابی)
    bank_id = db.Column(db.Integer, db.ForeignKey('bank.id'))
    rate = db.Column(db.Float, default=1)                            # نرخ (۱ دالر = ؟ این واحدپولی)
    total_usd = db.Column(db.Float, default=0)                       # مجموعه (معادل دالر)
    notes = db.Column(db.String(300))

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.String(50))

    currency = db.relationship('Currency')
    category = db.relationship('ExpenseCategory')
    bank = db.relationship('Bank')

    def __repr__(self):
        return f'{self.recipient}: {self.amount}'


# ==========================================
# برد و رسید — تراکنش نقدی/بانکی با طرف‌حساب‌های مختلف
# ==========================================
class CashTransaction(db.Model):
    """
    یک رکورد برد (پرداخت) یا رسید (دریافت) بین صندوق/بانک و یک طرف‌حساب.
    طرف‌حساب می‌تواند مشتری، فروشنده، کارمند یا قرض‌گیرنده باشد (party_type/party_id).

    قرارداد علامت (هماهنگ با الگوی vendor_balance/customer_balance موجود):
    transaction_type == 'receipt' (رسید: دریافت از طرف)  → بدهی طرف به ما کم می‌شود
    transaction_type == 'payment' (برد: پرداخت به طرف)    → بدهی طرف به ما زیاد می‌شود (یا طلب او زیاد می‌شود)
    روی بانک/صندوق: رسید = افزایش موجودی، برد = کاهش موجودی.
    """
    __tablename__ = 'cash_transaction'
    id = db.Column(db.Integer, primary_key=True)

    date = db.Column(db.Date, nullable=False)
    j_year = db.Column(db.Integer)
    j_month = db.Column(db.Integer)
    j_day = db.Column(db.Integer)

    party_type = db.Column(db.String(20), nullable=False)   # customer / vendor / employee / borrower
    party_id = db.Column(db.Integer, nullable=False)          # شناسه در جدول مربوطه (Customer/Vendor/Employee/...)
    party_name = db.Column(db.String(150))                     # نام طرف (نمایشی، در لحظه ثبت ذخیره می‌شود)

    currency_id = db.Column(db.Integer, db.ForeignKey('currency.id'))
    transaction_type = db.Column(db.String(10), nullable=False)  # payment (برد) / receipt (رسید)

    bank_id = db.Column(db.Integer, db.ForeignKey('bank.id'))    # صندوق/بانکی که پول از/به آن جابجا شد
    amount = db.Column(db.Float, default=0)
    check_no = db.Column(db.String(50))                            # نمبر چک (اختیاری)
    notes = db.Column(db.String(300))

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.String(50))

    currency = db.relationship('Currency')
    bank = db.relationship('Bank')

    def __repr__(self):
        return f'{self.party_type}#{self.party_id}: {self.transaction_type} {self.amount}'


# ==========================================
# انتقال حساب بین مشتریان (بردگی/رسیدگی بین دو مشتری، بدون اثر بانکی)
# ==========================================
class CustomerTransfer(db.Model):
    """
    انتقال مانده حساب از یک مشتری به مشتری دیگر، بدون هیچ اثری روی بانک/صندوق.

    قرارداد علامت (هماهنگ با customer_balance؛ مثبت = مشتری به ما بدهکار است):
    transaction_type == 'receipt' (رسیدگی): بدهی from_customer کم می‌شود، بدهی to_customer زیاد می‌شود.
    transaction_type == 'payment' (بردگی):  بدهی from_customer زیاد می‌شود، بدهی to_customer کم می‌شود.
    """
    __tablename__ = 'customer_transfer'
    id = db.Column(db.Integer, primary_key=True)

    date = db.Column(db.Date, nullable=False)
    j_year = db.Column(db.Integer)
    j_month = db.Column(db.Integer)
    j_day = db.Column(db.Integer)

    from_customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'), nullable=False)
    to_customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'), nullable=False)

    currency_id = db.Column(db.Integer, db.ForeignKey('currency.id'))
    transaction_type = db.Column(db.String(10), nullable=False)  # payment (بردگی) / receipt (رسیدگی)
    amount = db.Column(db.Float, default=0)
    notes = db.Column(db.String(300))

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    currency = db.relationship('Currency')
    from_customer = db.relationship('Customer', foreign_keys=[from_customer_id])
    to_customer = db.relationship('Customer', foreign_keys=[to_customer_id])

    def __repr__(self):
        return f'{self.from_customer_id} -> {self.to_customer_id}: {self.transaction_type} {self.amount}'


# ==========================================
# پرداختی مشتری — برد/رسید با تبدیل ارز (مثلاً دالر پرداخت می‌شود، افغانی به حساب می‌رود)
# ==========================================
class CustomerPayment(db.Model):
    """
    یک رکورد برد/رسید با تبدیل ارز بین دو واحد پولی مختلف.
    مثال: مشتری 100 دالر بدهکار است؛ ما به او 7000 افغانی از صندوق می‌پردازیم (نرخ تبدیل 70).
    اثر:
      - مانده طرف (party_type/party_id) به ارز pay_currency_id با amount تغییر می‌کند (مثل CashTransaction).
      - موجودی بانک/صندوق (bank_id) به ارز account_currency_id با converted_amount تغییر می‌کند.

    قرارداد علامت (هماهنگ با CashTransaction):
    payment_type == 'payment' (برد: پرداخت به طرف) → بدهی طرف (به pay_currency) زیاد می‌شود، موجودی بانک (به account_currency) کم می‌شود.
    payment_type == 'receipt' (رسید: دریافت از طرف) → بدهی طرف کم می‌شود، موجودی بانک زیاد می‌شود.
    """
    __tablename__ = 'customer_payment'
    id = db.Column(db.Integer, primary_key=True)

    date = db.Column(db.Date, nullable=False)
    j_year = db.Column(db.Integer)
    j_month = db.Column(db.Integer)
    j_day = db.Column(db.Integer)

    party_type = db.Column(db.String(20), nullable=False)   # customer / vendor / employee / borrower
    party_id = db.Column(db.Integer, nullable=False)
    party_name = db.Column(db.String(150))

    # ستون‌های راحتی برای فیلتر مستقیم (اختیاری، هم‌ارز با party_type/party_id)
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'))
    vendor_id = db.Column(db.Integer, db.ForeignKey('vendor.id'))
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'))

    payment_type = db.Column(db.String(10), nullable=False)  # payment (برد) / receipt (رسید)

    pay_currency_id = db.Column(db.Integer, db.ForeignKey('currency.id'))   # نوعیت پول پرداختی
    amount = db.Column(db.Float, default=0)                                  # مقدار (به ارز پرداختی)

    account_currency_id = db.Column(db.Integer, db.ForeignKey('currency.id'))  # نوعیت پول به حساب
    bank_id = db.Column(db.Integer, db.ForeignKey('bank.id'))

    exchange_rate = db.Column(db.Float, default=1)            # نرخ تبدیل
    converted_amount = db.Column(db.Float, default=0)         # مقدار تبدیلی (به ارز حساب)

    notes = db.Column(db.String(300))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.String(50))

    pay_currency = db.relationship('Currency', foreign_keys=[pay_currency_id])
    account_currency = db.relationship('Currency', foreign_keys=[account_currency_id])
    bank = db.relationship('Bank')
    customer = db.relationship('Customer', foreign_keys=[customer_id])
    vendor = db.relationship('Vendor', foreign_keys=[vendor_id])
    employee = db.relationship('Employee', foreign_keys=[employee_id])

    def __repr__(self):
        return f'{self.party_type}#{self.party_id}: {self.payment_type} {self.amount}{self.pay_currency_id}->{self.converted_amount}'


# ==========================================
# تبادله پولی بین حساب مشتری — تبدیل مانده مشتری از یک ارز به ارز دیگر (بدون اثر بانکی)
# ==========================================
class CustomerCurrencyExchange(db.Model):
    """
    تبدیل مانده یک مشتری از یک ارز به ارز دیگر، بدون هیچ جابجایی فیزیکی پول در بانک/صندوق.
    مثال: 6,350,000 افغانی بدهی ما به مشتری، با نرخ 63.5، به 100,000 دالر بدهی تبدیل می‌شود.

    amount و converted_amount همیشه مثبت ذخیره می‌شوند؛ جهت واقعی اثر در لحظه ثبت بر اساس
    مانده فعلی مشتری به ارز مبدا تشخیص داده و در ستون sign ذخیره می‌شود (+1 یا -1) تا محاسبات
    بعدی customer_balance_by_currency نیازی به بازتشخیص نداشته باشند.

    اثر روی مانده مشتری: مانده به from_currency_id با (sign * amount) کم می‌شود
    (یعنی add(from_currency_id, -sign*amount))، و مانده به to_currency_id با همان جهت
    (sign * converted_amount) شکل می‌گیرد (یعنی add(to_currency_id, sign*converted_amount)).
    """
    __tablename__ = 'customer_currency_exchange'
    id = db.Column(db.Integer, primary_key=True)

    date = db.Column(db.Date, nullable=False)
    j_year = db.Column(db.Integer)
    j_month = db.Column(db.Integer)
    j_day = db.Column(db.Integer)

    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'), nullable=False)

    from_currency_id = db.Column(db.Integer, db.ForeignKey('currency.id'))   # تبادله پول از حساب
    amount = db.Column(db.Float, default=0)                                    # مقدار (به ارز مبدا، همیشه مثبت)

    to_currency_id = db.Column(db.Integer, db.ForeignKey('currency.id'))     # تبادله پول به حساب
    exchange_rate = db.Column(db.Float, default=1)                             # نرخ تبدیل
    converted_amount = db.Column(db.Float, default=0)                          # مقدار تبدیلی (به ارز مقصد، همیشه مثبت)

    sign = db.Column(db.Integer, default=1)   # +1 یا -1: جهت تشخیص‌شده در لحظه ثبت بر اساس مانده فعلی

    notes = db.Column(db.String(300))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    customer = db.relationship('Customer')
    from_currency = db.relationship('Currency', foreign_keys=[from_currency_id])
    to_currency = db.relationship('Currency', foreign_keys=[to_currency_id])

    def __repr__(self):
        return f'{self.customer_id}: {self.amount}({self.from_currency_id}) -> {self.converted_amount}({self.to_currency_id})'


# ==========================================
# انتقال بین بانک‌ها — جابجایی پول بین دو بانک/صندوق، با امکان تبدیل ارز هم‌زمان
# ==========================================
class BankTransfer(db.Model):
    """
    انتقال پول از یک بانک/صندوق به بانک/صندوق دیگر (یا حتی همان بانک با ارز دیگر).
    بانک مبدا و مقصد می‌توانند یکسان یا متفاوت باشند؛ همینطور واحد پولی مبدا و مقصد.

    اثر:
      - موجودی بانک مبدا (from_bank_id) به ارز مبدا (from_currency_id) با amount کم می‌شود.
      - موجودی بانک مقصد (to_bank_id) به ارز مقصد (to_currency_id) با converted_amount زیاد می‌شود.
    اگر ارز مبدا و مقصد یکسان باشد، exchange_rate باید 1 و converted_amount برابر amount باشد.
    """
    __tablename__ = 'bank_transfer'
    id = db.Column(db.Integer, primary_key=True)

    date = db.Column(db.Date, nullable=False)
    j_year = db.Column(db.Integer)
    j_month = db.Column(db.Integer)
    j_day = db.Column(db.Integer)

    from_bank_id = db.Column(db.Integer, db.ForeignKey('bank.id'), nullable=False)
    from_currency_id = db.Column(db.Integer, db.ForeignKey('currency.id'))
    amount = db.Column(db.Float, default=0)

    to_bank_id = db.Column(db.Integer, db.ForeignKey('bank.id'), nullable=False)
    to_currency_id = db.Column(db.Integer, db.ForeignKey('currency.id'))
    exchange_rate = db.Column(db.Float, default=1)
    converted_amount = db.Column(db.Float, default=0)

    notes = db.Column(db.String(300))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.String(50))

    from_bank = db.relationship('Bank', foreign_keys=[from_bank_id])
    to_bank = db.relationship('Bank', foreign_keys=[to_bank_id])
    from_currency = db.relationship('Currency', foreign_keys=[from_currency_id])
    to_currency = db.relationship('Currency', foreign_keys=[to_currency_id])

    def __repr__(self):
        return f'{self.from_bank_id}({self.amount}) -> {self.to_bank_id}({self.converted_amount})'


# ==========================================
# حسابات شخصی — کتگوری عواید متفرقه
# ==========================================
class RevenueCategory(db.Model):
    __tablename__ = 'revenue_category'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)   # نام کتگوری عواید متفرقه
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'{self.name}'


# ==========================================
# حسابات شخصی — ثبت عواید متفرقه
# ==========================================
# ==========================================
# حسابات شخصی — ثبت عواید متفرقه (تعریف نام عاید ذیل یک کتگوری)
# ==========================================
class Revenue(db.Model):
    """یک اسم ساده (نام عاید) زیرمجموعهٔ کتگوری انتخاب‌شده — بدون مقدار/تاریخ/بانک."""
    __tablename__ = 'revenue'
    id = db.Column(db.Integer, primary_key=True)
    category_id = db.Column(db.Integer, db.ForeignKey('revenue_category.id'))  # کتگوری
    name = db.Column(db.String(150), nullable=False)                  # نام عاید
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    category = db.relationship('RevenueCategory')

    def __repr__(self):
        return f'{self.name}'


# ==========================================
# حسابات شخصی — عواید متفرقه (ثبت واقعی دریافتی)
# ==========================================
class RevenueDetail(db.Model):
    """
    یک رکورد دریافتی نقدی/بانکی متفرقه (خارج از فروش عادی).
    دقیقاً هم‌ساختار با ExpenseDetail: category_id و recipient مستقیماً اینجا هم تکرار می‌شوند
    (متن آزاد، بدون ارجاع به Revenue.id).
    همیشه از نوع دریافتی است: موجودی بانک/صندوق انتخاب‌شده به همان ارز زیاد می‌شود.
    """
    __tablename__ = 'revenue_detail'
    id = db.Column(db.Integer, primary_key=True)

    date = db.Column(db.Date, nullable=False)
    j_year = db.Column(db.Integer)
    j_month = db.Column(db.Integer)
    j_day = db.Column(db.Integer)

    currency_id = db.Column(db.Integer, db.ForeignKey('currency.id'))
    category_id = db.Column(db.Integer, db.ForeignKey('revenue_category.id'))
    recipient = db.Column(db.String(150))                          # نام عاید
    amount = db.Column(db.Float, default=0)                          # مقدار (به واحدپول انتخابی)
    bank_id = db.Column(db.Integer, db.ForeignKey('bank.id'))
    notes = db.Column(db.String(300))

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.String(50))

    currency = db.relationship('Currency')
    category = db.relationship('RevenueCategory')
    bank = db.relationship('Bank')

    def __repr__(self):
        return f'{self.recipient}: {self.amount}'


# ==========================================
# قرض‌ها — ثبت قرض‌دهنده/قرض‌گیرنده
# ==========================================

# ==========================================
# سرمایه ثابت — کتگوری دارایی‌های ثابت (مثل: ماشین‌آلات، وسایط، مبلمان اداری)
# ==========================================
class FixedAssetCategory(db.Model):
    __tablename__ = 'fixed_asset_category'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)   # نام کتگوری دارایی ثابت
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'{self.name}'


# ==========================================
# سرمایه ثابت — ثبت دارایی‌های ثابت (زمین، ساختمان، ماشین‌آلات، وسایط و ...)
# ==========================================
class FixedAsset(db.Model):
    __tablename__ = 'fixed_asset'
    id = db.Column(db.Integer, primary_key=True)

    category_id = db.Column(db.Integer, db.ForeignKey('fixed_asset_category.id'))
    name = db.Column(db.String(150), nullable=False)          # نام دارایی
    asset_code = db.Column(db.String(50))                      # کد/شماره دارایی (اختیاری)
    location = db.Column(db.String(150))                       # محل استفاده/نگهداری

    date = db.Column(db.Date, nullable=False)                  # تاریخ خرید (میلادی)
    j_year = db.Column(db.Integer)
    j_month = db.Column(db.Integer)
    j_day = db.Column(db.Integer)

    currency_id = db.Column(db.Integer, db.ForeignKey('currency.id'))
    purchase_price = db.Column(db.Float, default=0)            # قیمت خرید (به واحدپول انتخابی)
    rate = db.Column(db.Float, default=1)                       # نرخ روز (۱ دالر = ؟ این واحدپولی)
    purchase_price_usd = db.Column(db.Float, default=0)         # قیمت خرید معادل دالر (همیشه محاسبه می‌شود)

    quantity = db.Column(db.Float, default=1)                   # تعداد

    depreciation_rate = db.Column(db.Float, default=0)          # نرخ استهلاک سالانه (٪) — صفر یعنی بدون استهلاک

    bank_id = db.Column(db.Integer, db.ForeignKey('bank.id'))   # اگر از یک بانک/صندوق پرداخت شده

    status = db.Column(db.String(20), default='active')         # active / sold / disposed
    disposal_date = db.Column(db.Date)                           # تاریخ فروش/اسقاط (اختیاری)

    notes = db.Column(db.String(300))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.String(50))

    category = db.relationship('FixedAssetCategory')
    currency = db.relationship('Currency')
    bank = db.relationship('Bank')

    def __repr__(self):
        return f'{self.name}'

    def book_value_usd(self, as_of=None):
        """
        ارزش دفتری فعلی (به دالر) با استهلاک خطی سالانه محاسبه می‌شود.
        اگر دارایی فروخته/اسقاط شده باشد، ارزش دفتری صفر است (دیگر جزو دارایی‌های
        شرکت محسوب نمی‌شود).
        """
        if self.status != 'active':
            return 0.0
        price = self.purchase_price_usd or 0.0
        if not price:
            return 0.0
        if not self.depreciation_rate or not self.date:
            return price

        from datetime import date as _date
        as_of = as_of or _date.today()
        years_elapsed = (as_of - self.date).days / 365.25
        remaining_fraction = 1 - (self.depreciation_rate / 100.0) * years_elapsed
        remaining_fraction = max(0.0, min(1.0, remaining_fraction))
        return price * remaining_fraction


class Borrower(db.Model):
    __tablename__ = 'borrower'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)     # نام قرض دهنده/گیرنده
    address = db.Column(db.String(200))                    # آدرس
    book_no = db.Column(db.String(50))                      # شماره کتاب
    phone = db.Column(db.String(30))                         # شماره تماس
    notes = db.Column(db.String(300))                        # توضیحات
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'{self.name}'


# ==========================================
# قرض‌ها — ثبت حساب افتتاحیه قرضه
# ==========================================
class BorrowerOpening(db.Model):
    __tablename__ = 'borrower_opening'
    id = db.Column(db.Integer, primary_key=True)

    date = db.Column(db.Date, nullable=False)
    j_year = db.Column(db.Integer)
    j_month = db.Column(db.Integer)
    j_day = db.Column(db.Integer)

    borrower_id = db.Column(db.Integer, db.ForeignKey('borrower.id'), nullable=False)
    currency = db.Column(db.String(10))                       # واحدپول
    amount = db.Column(db.Float, default=0)                     # حساب افتتاحیه (مبلغ)
    account_type = db.Column(db.String(20))                      # نوعیت حساب: receivable (طلب ما از قرض‌گیرنده) / payable (بدهی ما به قرض‌دهنده)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    borrower = db.relationship('Borrower')

    def __repr__(self):
        return f'{self.borrower_id}: {self.amount}'
