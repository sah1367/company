from flask import (Blueprint, render_template, request, redirect, url_for,
                    flash, session, current_app, send_file)
from . import db
from .models import (Employee, Quantity, Category, Stock, Item, OpeningBalance,
                      StockTransfer, Production, ProductionLine, StockBalance, StockOut, StockIn,
                      Vendor, VendorOpening, PurchaseInvoice, PurchaseInvoiceLine, VendorPayment,
                      VendorReturn, VendorReturnLine,
                      CustomerCategory, Customer, CustomerOpening, CustomerOrder, CustomerOrderLine,
                      CustomerReturn, CustomerReturnLine,
                      SalesInvoice, SalesInvoiceLine, Currency, CurrencyRate, Bank, BankOpening,
                      ExpenseCategory, Expense, ExpenseDetail, CashTransaction, CustomerTransfer,
                      CustomerPayment, CustomerCurrencyExchange, BankTransfer,
                      RevenueCategory, Revenue, RevenueDetail, Borrower, BorrowerOpening, User,
                      CompanySettings, UserReportAccess, UserMenuAccess,
                      EmployeeCategory, EmployeeAttendance, EmployeeContract,
                      EmployeeSalaryCard, EmployeeSalaryPayment,
                      FixedAssetCategory, FixedAsset)
import jdatetime
import os
import shutil
import sqlite3
from werkzeug.utils import secure_filename
from functools import wraps
from datetime import date as py_date, timedelta, datetime

main = Blueprint('main', __name__)


# ==========================================
# ساختار ۹ منوی اصلی برنامه — برای «تعریف دسترسیهای منو»
# هر آیتم: (اسلاگ, عنوان, اندپوینت). این لیست باید همیشه هم‌راستا با
# لینک‌های واقعی در app/templates/base.html بماند.
# ==========================================
MENU_STRUCTURE = {
    'warehouse': {
        'title': 'گدام',
        'items': [
            ('diary', 'روزنامچه', 'main.index'),
            ('units', 'واحد اندازه گیری', 'main.units'),
            ('categories', 'ثبت کتگوری', 'main.categories'),
            ('stocks', 'ثبت گدام', 'main.stocks'),
            ('items', 'ثبت کالا', 'main.items'),
            ('opening_balance', 'ثبت حساب افتتاحیه', 'main.opening_balance'),
            ('stock_transfer', 'انتقال بین گدامها', 'main.stock_transfer'),
            ('production', 'بخش ترکیب اجناس', 'main.production'),
            ('stock_out', 'کم شدن از گدام', 'main.stock_out'),
            ('stock_in', 'افزایش به گدام', 'main.stock_in'),
            ('stock_report', 'موجودی انبار', 'main.stock_report'),
        ],
    },
    'purchase': {
        'title': 'خرید از شرکتها',
        'items': [
            ('diary', 'روزنامچه', 'main.index'),
            ('vendors', 'ثبت نام فروشنده کالا', 'main.vendors'),
            ('vendor_opening', 'حساب افتتاحیه فروشنده', 'main.vendor_opening'),
            ('purchase_invoices', 'ثبت فاکتور خرید', 'main.purchase_invoices'),
            ('purchase_returns', 'بار برگشتی فروشنده', 'main.purchase_returns'),
            ('vendor_search', 'حسابات فروشنده کالا', 'main.vendor_search'),
        ],
    },
    'sale': {
        'title': 'مشتریان',
        'items': [
            ('diary', 'روزنامچه', 'main.index'),
            ('customer_category', 'ثبت کتگوری مشتری', 'main.customer_category'),
            ('customers', 'ثبت نام مشتری', 'main.customers'),
            ('customer_opening', 'حساب افتتاحیه مشتری', 'main.customer_opening'),
            ('customer_orders', 'سفارشات مشتریان', 'main.customer_orders'),
            ('sales_invoices', 'ثبت فاکتور فروش', 'main.sales_invoices'),
            ('customer_returns', 'بار برگشتی مشتری', 'main.customer_returns'),
            ('customer_search', 'حسابات مشتری', 'main.customer_search'),
        ],
    },
    'treasury': {
        'title': 'بانکها',
        'items': [
            ('diary', 'روزنامچه', 'main.index'),
            ('currency_registration', 'ثبت واحدپولی', 'main.currency_registration'),
            ('currency_rate', 'نرخ واحدپولی', 'main.currency_rate'),
            ('banks', 'ثبت بانک', 'main.banks'),
            ('bank_opening', 'ثبت افتتاحیه بانک', 'main.bank_opening'),
            ('bank_transfer', 'انتقال بین بانکها', 'main.bank_transfer'),
            ('bank_search', 'حسابات بانکی', 'main.bank_search'),
        ],
    },
    'expenses': {
        'title': 'مصارف',
        'items': [
            ('diary', 'روزنامچه', 'main.index'),
            ('expense_category', 'کتگوری مصارف', 'main.expense_category'),
            ('expense_new', 'ثبت مصارف', 'main.expense_new'),
            ('expense_detail', 'شرح مصارف', 'main.expense_detail'),
        ],
    },
    'receipt': {
        'title': 'برد و رسید',
        'items': [
            ('diary', 'روزنامچه', 'main.index'),
            ('cash_transaction', 'برد و رسید نقدی مشتریان', 'main.cash_transaction'),
            ('customer_transfer', 'برد و رسید نقدی بین مشتریان', 'main.customer_transfer'),
            ('customer_payment', 'پرداختی پول متفاوت به مشتری', 'main.customer_payment'),
            ('customer_exchange', 'تبادله پولی مشتری', 'main.customer_exchange'),
            ('bank_transfer', 'انتقال بین بانکها', 'main.bank_transfer'),
        ],
    },
    'personal': {
        'title': 'حسابات شخصی',
        'items': [
            ('diary', 'روزنامچه', 'main.index'),
            ('revenue_category', 'کتگوری عواید متفرقه', 'main.revenue_category'),
            ('revenue', 'ثبت عواید متفرقه', 'main.revenue'),
            ('revenue_detail', 'عواید متفرقه', 'main.revenue_detail'),
            ('borrowers', 'تعریف قرض گیرنده', 'main.borrowers'),
            ('borrower_opening', 'ثبت حساب افتتاحیه قرضه', 'main.borrower_opening'),
            ('borrower_search', 'حسابات قرضه', 'main.borrower_search'),
        ],
    },
    'employees': {
        'title': 'کارمندان',
        'items': [
            ('diary', 'روزنامچه', 'main.index'),
            ('employee_category', 'ثبت کتگوری کارمندان', 'main.employee_category'),
            ('employees', 'ثبت کارمند', 'main.employees'),
            ('employee_search', 'حسابات کارمند', 'main.employee_search'),
            ('employee_attendance', 'حاضری کارمند', 'main.employee_attendance'),
            ('employee_attendance_monthly', 'لیست حاضری ماهانه', 'main.employee_attendance_monthly'),
            ('employee_contract', 'قرارداد کارمند', 'main.employee_contract'),
            ('employee_salary_card', 'کارت معاشات در هر برج', 'main.employee_salary_card'),
        ],
    },
    'assets': {
        'title': 'سرمایه ثابت',
        'items': [
            ('diary', 'روزنامچه', 'main.index'),
            ('asset_category', 'ثبت کتگوری دارایی', 'main.asset_category'),
            ('fixed_assets', 'ثبت دارایی ثابت', 'main.fixed_assets'),
        ],
    },
    'admin': {
        'title': 'صفحه مدیریت',
        'items': [
            ('diary', 'روزنامچه', 'main.index'),
            ('reports', 'گزارش‌ها', 'main.reports'),
            ('journal_range', 'روزنامچه تاریخ‌وار', 'main.journal_range'),
            ('user_management', 'تعریف کاربری', 'main.user_management'),
            ('company_settings', 'تعریف فروشگاه', 'main.company_settings'),
            ('backup', 'پشتیبان گیری', 'main.backup_page'),
        ],
    },
}

# سه ردیف قابل تیک برای هر آیتم منو، دقیقاً مطابق عکس نمونه (گدام):
# خودِ صفحه / میزان (لیست) / فرم
MENU_ITEM_ROWS = [
    ('page', ''),
    ('list', 'میزان '),
    ('form', 'فرم '),
]

# اندپوینت‌هایی که فقط نمایش لینک در منو را کنترل می‌کنیم، نه مسدودسازی مسیر
# (چون صفحه‌ی اصلی/گزارش‌ها با سازوکار دیگری هم به اشتراک گذاشته می‌شوند)
MENU_ENDPOINT_SKIP_ROUTE_GUARD = {'main.index', 'main.reports'}


def menu_item_key(menu_key, item_slug, row='page'):
    return f'{menu_key}__{item_slug}__{row}'


def user_menu_restricted(user):
    return bool(user and user.role != 'admin' and getattr(user, 'menu_restricted', False))


def user_allowed_menu_items(user):
    """کلیدهای دسترسی منو که این کاربر مجاز است. None یعنی بدون محدودیت (همه چیز مجاز)."""
    if not user_menu_restricted(user):
        return None
    return {a.item_key for a in user.menu_access}


def has_menu_access(user, item_key):
    allowed = user_allowed_menu_items(user)
    if allowed is None:
        return True
    return item_key in allowed


# نگاشت هر اندپوینت به لیست کلیدهای دسترسیِ «صفحه» که آن را مجاز می‌کنند
# (بعضی صفحات مثل «انتقال بین بانکها» در دو منوی متفاوت دیده می‌شوند)
ENDPOINT_MENU_ITEM_MAP = {}
for _menu_key, _menu in MENU_STRUCTURE.items():
    for _slug, _label, _endpoint in _menu['items']:
        if _endpoint in MENU_ENDPOINT_SKIP_ROUTE_GUARD:
            continue
        ENDPOINT_MENU_ITEM_MAP.setdefault(_endpoint, []).append(menu_item_key(_menu_key, _slug, 'page'))


# ==========================================
# سیستم ورود (Login) — محافظت از کل برنامه
# ==========================================
@main.before_request
def require_login():
    open_endpoints = ('main.login', 'main.static', 'static')
    if request.endpoint in open_endpoints or (request.endpoint or '').endswith('.static'):
        return
    if not session.get('user_id'):
        return redirect(url_for('main.login', next=request.path))

    guard_keys = ENDPOINT_MENU_ITEM_MAP.get(request.endpoint)
    if guard_keys:
        user = User.query.get(session.get('user_id'))
        if not any(has_menu_access(user, k) for k in guard_keys):
            flash('شما به این بخش دسترسی ندارید', 'danger')
            return redirect(url_for('main.index'))


def admin_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if session.get('role') != 'admin':
            flash('فقط مدیر سیستم به این بخش دسترسی دارد', 'danger')
            return redirect(url_for('main.index'))
        return view_func(*args, **kwargs)
    return wrapped


@main.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('user_id'):
        return redirect(url_for('main.index'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        user = User.query.filter_by(username=username).first()
        if user and user.is_active and user.check_password(password):
            session['user_id'] = user.id
            session['username'] = user.username
            session['full_name'] = user.full_name or user.username
            session['role'] = user.role
            next_url = request.args.get('next') or url_for('main.index')
            return redirect(next_url)
        flash('نام کاربری یا پسورد اشتباه است', 'danger')

    return render_template('login.html')


@main.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('main.login'))


# ==========================================
# صفحه مدیریت — تعریف کاربری
# ==========================================
@main.route('/admin/users', methods=['GET', 'POST'])
@admin_required
def user_management():
    edit_id = request.args.get('edit', type=int)
    edit_user = User.query.get(edit_id) if edit_id else None

    if request.method == 'POST':
        user_id = request.form.get('user_id', type=int)
        username = request.form.get('username', '').strip()
        full_name = request.form.get('full_name', '').strip()
        password = request.form.get('password', '')
        role = request.form.get('role', 'user')
        is_active = request.form.get('is_active', '1') == '1'

        if not username:
            flash('نام کاربری نمی‌تواند خالی باشد', 'danger')
            return redirect(url_for('main.user_management', edit=user_id))

        duplicate = User.query.filter(User.username == username, User.id != (user_id or 0)).first()
        if duplicate:
            flash('این نام کاربری قبلاً استفاده شده است', 'danger')
            return redirect(url_for('main.user_management', edit=user_id))

        if user_id:
            user = User.query.get_or_404(user_id)
            if user.role == 'admin' and (role != 'admin' or not is_active):
                other_active_admins = User.query.filter(
                    User.role == 'admin', User.is_active == True, User.id != user.id
                ).count()
                if other_active_admins == 0:
                    flash('باید حداقل یک مدیر کل فعال در سیستم باقی بماند', 'danger')
                    return redirect(url_for('main.user_management', edit=user_id))
            user.username = username
            user.full_name = full_name
            user.role = role
            user.is_active = is_active
            if password:
                user.set_password(password)
            db.session.commit()
            flash('اطلاعات کاربر ویرایش شد', 'success')
        else:
            if not password:
                flash('رمز عبور برای کاربر جدید الزامی است', 'danger')
                return redirect(url_for('main.user_management'))
            user = User(username=username, full_name=full_name, role=role, is_active=is_active)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            flash('کاربر جدید ثبت شد', 'success')

        return redirect(url_for('main.user_management'))

    search = request.args.get('q', '').strip()
    query = User.query
    if search:
        query = query.filter(User.username.contains(search) | User.full_name.contains(search))
    users = query.order_by(User.id).all()

    return render_template('admin/user_management.html', users=users, edit_user=edit_user, search=search)


@main.route('/admin/users/delete/<int:id>')
@admin_required
def user_management_delete(id):
    user = User.query.get_or_404(id)
    if user.role == 'admin':
        other_active_admins = User.query.filter(
            User.role == 'admin', User.is_active == True, User.id != user.id
        ).count()
        if other_active_admins == 0:
            flash('باید حداقل یک مدیر کل فعال در سیستم باقی بماند', 'danger')
            return redirect(url_for('main.user_management'))
    if user.id == session.get('user_id'):
        flash('نمی‌توانید حساب کاربری خودتان را حذف کنید', 'danger')
        return redirect(url_for('main.user_management'))
    db.session.delete(user)
    db.session.commit()
    flash('کاربر حذف شد', 'success')
    return redirect(url_for('main.user_management'))


# ==========================================
# ویرایش مشخصات کاربری — صفحهٔ هاب (دو گزینه)
# ==========================================
@main.route('/admin/users/<int:id>/edit-hub')
@admin_required
def user_edit_hub(id):
    user = User.query.get_or_404(id)
    return render_template('admin/user_edit_hub.html', user=user)


# نگاشت هر زیر-گزارش به دستهٔ اصلیِ آن در REPORT_PAGES — برای اعمال دسترسی
REPORT_CATEGORY_MAP = {
    'general': 'general', 'cash_capital': 'general', 'balance': 'general',
    'profit_loss_detail': 'general',

    'revenue_expense': 'revenue_expense', 'expense_total': 'revenue_expense',
    'revenue_total': 'revenue_expense',

    'exchange': 'exchange', 'customer_exchange_total': 'exchange', 'vendors_report': 'exchange',
    'qard_hasana': 'exchange', 'customer_claims_by_category': 'exchange', 'employees_report': 'exchange',

    'customers': 'customers', 'sales_by_item': 'customers', 'sales_invoices_report': 'customers',
    'items_sold': 'customers', 'items_bought_from_customer': 'customers',
    'items_credit_to_customers': 'customers', 'customer_discounts': 'customers',

    'vendors': 'vendors', 'items_bought_by_item': 'vendors', 'purchase_bill_details': 'vendors',

    'warehouse': 'warehouse', 'stock_in_report': 'warehouse', 'stock_out_report': 'warehouse',
    'category_stock': 'warehouse', 'stock_transfer_details': 'warehouse',
    'customer_item_claims': 'warehouse', 'opening_balance_report': 'warehouse',
    'stock_total_all': 'warehouse', 'inactive_items_report': 'warehouse',
    'vendor_item_claims': 'warehouse', 'stock_total_all_2': 'warehouse',
    'stock_by_warehouse': 'warehouse', 'item_claims_credit': 'warehouse',
    'stock_value': 'warehouse', 'production_report': 'warehouse',

    'employees': 'employees',
}


def user_allowed_report_categories(user):
    """کلیدهای REPORT_PAGES که این کاربر مجاز به دیدن آن‌هاست."""
    if not user or user.role == 'admin' or not user.reports_restricted:
        return set(REPORT_PAGES.keys())
    return {ra.category for ra in user.report_access}


def current_user_can_access_report(slug):
    user = User.query.get(session.get('user_id'))
    category = REPORT_CATEGORY_MAP.get(slug, slug)
    return category in user_allowed_report_categories(user)


@main.route('/admin/users/<int:id>/report-access', methods=['GET', 'POST'])
@admin_required
def user_report_access(id):
    user = User.query.get_or_404(id)

    if request.method == 'POST':
        selected = set(request.form.getlist('categories'))
        user.reports_restricted = True
        UserReportAccess.query.filter_by(user_id=user.id).delete()
        for cat in selected:
            if cat in REPORT_PAGES:
                db.session.add(UserReportAccess(user_id=user.id, category=cat))
        db.session.commit()
        flash('دسترسی راپورهای کاربر ذخیره شد', 'success')
        return redirect(url_for('main.user_edit_hub', id=user.id))

    allowed = user_allowed_report_categories(user)
    return render_template('admin/user_report_access.html',
        user=user, report_pages=REPORT_PAGES, allowed=allowed)


# ==========================================
# تعریف دسترسیهای منو — صفحه‌ی هاب (انتخاب یکی از ۹ منو) و صفحه‌ی هر منو
# ==========================================
@main.route('/admin/users/<int:id>/menu-access')
@admin_required
def user_menu_access_hub(id):
    user = User.query.get_or_404(id)
    return render_template('admin/user_menu_access_hub.html', user=user, menus=MENU_STRUCTURE)


@main.route('/admin/users/<int:id>/menu-access/<menu_key>', methods=['GET', 'POST'])
@admin_required
def user_menu_access(id, menu_key):
    user = User.query.get_or_404(id)
    menu = MENU_STRUCTURE.get(menu_key)
    if not menu:
        flash('منوی نامعتبر است', 'danger')
        return redirect(url_for('main.user_menu_access_hub', id=user.id))

    valid_keys = {menu_item_key(menu_key, slug, row)
                  for slug, _, _ in menu['items'] for row, _ in MENU_ITEM_ROWS}

    if request.method == 'POST':
        selected = set(request.form.getlist('access_keys'))
        user.menu_restricted = True
        UserMenuAccess.query.filter(
            UserMenuAccess.user_id == user.id,
            UserMenuAccess.item_key.in_(valid_keys)
        ).delete(synchronize_session=False)
        for key in selected:
            if key in valid_keys:
                db.session.add(UserMenuAccess(user_id=user.id, item_key=key))
        db.session.commit()
        flash(f'دسترسیهای منوی «{menu["title"]}» ذخیره شد', 'success')
        return redirect(url_for('main.user_menu_access_hub', id=user.id))

    allowed = user_allowed_menu_items(user)
    if allowed is None:
        allowed = valid_keys  # کاربر بدون محدودیت: همه به‌صورت تیک‌خورده نمایش داده شود

    rows = []
    for slug, label, endpoint in menu['items']:
        for row, prefix in MENU_ITEM_ROWS:
            key = menu_item_key(menu_key, slug, row)
            rows.append({'key': key, 'label': prefix + label, 'checked': key in allowed})

    return render_template('admin/user_menu_access.html',
        user=user, menu_key=menu_key, menu_title=menu['title'], rows=rows)


def report_category_required(category):
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(*args, **kwargs):
            user = User.query.get(session.get('user_id'))
            if category not in user_allowed_report_categories(user):
                flash('شما به این بخش از گزارش‌ها دسترسی ندارید', 'danger')
                return redirect(url_for('main.reports'))
            return view_func(*args, **kwargs)
        return wrapped
    return decorator


ALLOWED_LOGO_EXT = {'png', 'jpg', 'jpeg', 'webp', 'gif'}


def save_company_logo(logo_file):
    """
    فایل لوگوی آپلودشده را در app/static/uploads/company ذخیره می‌کند.
    خروجی: مسیر نسبی (برای ذخیره در دیتابیس و ساخت url_for('static', filename=...)) یا None.
    """
    if not logo_file or not logo_file.filename:
        return None
    ext = logo_file.filename.rsplit('.', 1)[-1].lower() if '.' in logo_file.filename else ''
    if ext not in ALLOWED_LOGO_EXT:
        flash('فرمت لوگو باید jpg، jpeg، png، gif یا webp باشد', 'danger')
        return None

    upload_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'company')
    os.makedirs(upload_dir, exist_ok=True)

    filename = f"logo_{int(datetime.utcnow().timestamp())}.{ext}"
    logo_file.save(os.path.join(upload_dir, filename))
    return f"uploads/company/{filename}"


@main.route('/admin/company', methods=['GET', 'POST'])
@admin_required
def company_settings():
    settings = CompanySettings.query.first()
    if not settings:
        settings = CompanySettings(name='کارخانه تولید صنایع غذایی و نوشیدنی غیر الکلی تک')
        db.session.add(settings)
        db.session.commit()

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if not name:
            flash('نام فروشگاه نمی‌تواند خالی باشد', 'danger')
            return redirect(url_for('main.company_settings'))

        settings.name = name
        settings.latin_name = request.form.get('latin_name', '').strip()
        settings.phone1 = request.form.get('phone1', '').strip()
        settings.phone2 = request.form.get('phone2', '').strip()
        settings.phone_fixed = request.form.get('phone_fixed', '').strip()
        settings.address = request.form.get('address', '').strip()
        settings.email = request.form.get('email', '').strip()

        logo_file = request.files.get('logo')
        logo_path = save_company_logo(logo_file)
        if logo_path:
            settings.logo_filename = logo_path

        db.session.commit()
        flash('اطلاعات فروشگاه ذخیره شد', 'success')
        return redirect(url_for('main.company_settings'))

    return render_template('admin/company_settings.html', settings=settings)


# ==========================================
# پشتیبان گیری (Backup) — دانلود و بازیابی نسخه پشتیبان از دیتابیس
# ==========================================
def _get_db_path():
    uri = current_app.config['SQLALCHEMY_DATABASE_URI']
    prefix = 'sqlite:///'
    if not uri.startswith(prefix):
        return None
    return uri[len(prefix):]


def _backups_dir():
    path = os.path.join(os.path.dirname(_get_db_path()), 'backups')
    os.makedirs(path, exist_ok=True)
    return path


@main.route('/admin/backup')
@admin_required
def backup_page():
    db_path = _get_db_path()
    db_size_kb = round(os.path.getsize(db_path) / 1024, 1) if db_path and os.path.exists(db_path) else 0

    backups = []
    if db_path:
        for fname in sorted(os.listdir(_backups_dir()), reverse=True):
            if fname.endswith('.db'):
                fpath = os.path.join(_backups_dir(), fname)
                backups.append({
                    'name': fname,
                    'size_kb': round(os.path.getsize(fpath) / 1024, 1),
                    'created': datetime.fromtimestamp(os.path.getmtime(fpath)).strftime('%Y-%m-%d %H:%M'),
                })

    return render_template('admin/backup.html', db_size_kb=db_size_kb, backups=backups)


@main.route('/admin/backup/create', methods=['POST'])
@admin_required
def backup_create():
    """یک نسخه پشتیبان تازه از دیتابیس فعلی می‌سازد و در پوشه backups ذخیره می‌کند."""
    db_path = _get_db_path()
    if not db_path or not os.path.exists(db_path):
        flash('فایل دیتابیس پیدا نشد', 'danger')
        return redirect(url_for('main.backup_page'))

    db.session.commit()  # اطمینان از نوشته‌شدن تغییرات معلق قبل از کپی فایل
    stamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    dest = os.path.join(_backups_dir(), f'backup_{stamp}.db')
    shutil.copy2(db_path, dest)
    flash('نسخه پشتیبان جدید با موفقیت ساخته شد', 'success')
    return redirect(url_for('main.backup_page'))


@main.route('/admin/backup/download')
@admin_required
def backup_download():
    """دانلود مستقیم نسخه فعلی دیتابیس."""
    db_path = _get_db_path()
    if not db_path or not os.path.exists(db_path):
        flash('فایل دیتابیس پیدا نشد', 'danger')
        return redirect(url_for('main.backup_page'))

    db.session.commit()
    stamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    return send_file(db_path, as_attachment=True, download_name=f'hesab_karkhane_backup_{stamp}.db')


@main.route('/admin/backup/download/<path:fname>')
@admin_required
def backup_download_file(fname):
    """دانلود یکی از نسخه‌های پشتیبان قبلاً ساخته‌شده."""
    fname = secure_filename(fname)
    fpath = os.path.join(_backups_dir(), fname)
    if not os.path.exists(fpath):
        flash('فایل پشتیبان پیدا نشد', 'danger')
        return redirect(url_for('main.backup_page'))
    return send_file(fpath, as_attachment=True, download_name=fname)


@main.route('/admin/backup/delete/<path:fname>', methods=['POST'])
@admin_required
def backup_delete_file(fname):
    fname = secure_filename(fname)
    fpath = os.path.join(_backups_dir(), fname)
    if os.path.exists(fpath):
        os.remove(fpath)
        flash('نسخه پشتیبان حذف شد', 'success')
    return redirect(url_for('main.backup_page'))


@main.route('/admin/backup/restore', methods=['POST'])
@admin_required
def backup_restore():
    """
    بازیابی دیتابیس از یک فایل .db آپلودشده.
    قبل از جایگزینی، از دیتابیس فعلی یک نسخه پشتیبان خودکار گرفته می‌شود تا در صورت
    اشتباه، اطلاعات فعلی از بین نرود.
    """
    upload = request.files.get('backup_file')
    if not upload or not upload.filename:
        flash('فایلی انتخاب نشده است', 'danger')
        return redirect(url_for('main.backup_page'))

    if not upload.filename.lower().endswith('.db'):
        flash('فقط فایل با پسوند db. قابل بازیابی است', 'danger')
        return redirect(url_for('main.backup_page'))

    db_path = _get_db_path()
    if not db_path:
        flash('مسیر دیتابیس یافت نشد', 'danger')
        return redirect(url_for('main.backup_page'))

    tmp_path = db_path + '.upload_tmp'
    upload.save(tmp_path)

    # اعتبارسنجی ساده: باید یک فایل SQLite معتبر با جدول users باشد
    try:
        test_con = sqlite3.connect(tmp_path)
        cur = test_con.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        ok = cur.fetchone() is not None
        test_con.close()
    except sqlite3.Error:
        ok = False

    if not ok:
        os.remove(tmp_path)
        flash('فایل انتخاب‌شده یک نسخه پشتیبان معتبر نیست', 'danger')
        return redirect(url_for('main.backup_page'))

    # پشتیبان خودکار از وضعیت فعلی، قبل از جایگزینی
    db.session.commit()
    stamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    shutil.copy2(db_path, os.path.join(_backups_dir(), f'before_restore_{stamp}.db'))

    db.session.remove()
    db.engine.dispose()
    shutil.move(tmp_path, db_path)

    flash('بازیابی با موفقیت انجام شد. لطفاً از سیستم خارج و دوباره وارد شوید.', 'success')
    return redirect(url_for('main.login'))


CURRENCY_PRIORITY = {'AFN': 1, 'USD': 2, 'IRR': 3, 'TMN': 3}


def _cur_sort_key(code):
    return (CURRENCY_PRIORITY.get(code, 99), code)


def get_journal_rows(jy=None, jm=None, jd=None, before_jtuple=None, range_jtuple=None):
    """
    تمام تراکنش‌های پولی سیستم را به شکل یکسان برمی‌گرداند (برای روزنامچه).
    اگر jy/jm/jd داده شود: فقط رکوردهای همان روز شمسی.
    اگر before_jtuple=(jy,jm,jd) داده شود: فقط رکوردهای شمسی قبل از آن روز
    (مقایسه مستقیم روی j_year/j_month/j_day، نه تاریخ میلادی — برای محاسبه دخل دیروز).
    اگر range_jtuple=((from_y,from_m,from_d),(to_y,to_m,to_d)) داده شود: فقط رکوردهای
    شمسیِ بین آن دو تاریخ (شامل خودِ دو سر بازه) — برای «روزنامچه تاریخ‌وار».
    """
    rows = []

    def add(date_obj, jy_, jm_, jd_, currency_code, reference, description, bank_name, in_amt, out_amt, user):
        if before_jtuple is not None:
            if not (jy_ and jm_ and jd_) or (jy_, jm_, jd_) >= before_jtuple:
                return
        if range_jtuple is not None:
            from_t, to_t = range_jtuple
            if not (jy_ and jm_ and jd_) or not (from_t <= (jy_, jm_, jd_) <= to_t):
                return
        rows.append({
            'date': date_obj, 'j_year': jy_, 'j_month': jm_, 'j_day': jd_,
            'currency': currency_code or '-', 'reference': reference,
            'description': description, 'bank': bank_name or '-',
            'in_amt': in_amt or 0, 'out_amt': out_amt or 0, 'user': user or '-'
        })

    def day_filter(q, model):
        if jy is not None:
            return q.filter(model.j_year == jy, model.j_month == jm, model.j_day == jd)
        return q

    for inv in day_filter(SalesInvoice.query, SalesInvoice).all():
        if inv.paid_amount:
            add(inv.date, inv.j_year, inv.j_month, inv.j_day, inv.currency,
                'فاکتور فروش', f'فروش فاکتور #{inv.invoice_no} به {inv.customer.name if inv.customer else "-"}',
                inv.bank_name, inv.paid_amount, 0, inv.created_by)

    for inv in day_filter(PurchaseInvoice.query, PurchaseInvoice).all():
        if inv.paid_amount:
            add(inv.date, inv.j_year, inv.j_month, inv.j_day, inv.currency,
                'فاکتور خرید', f'خرید فاکتور #{inv.invoice_no} از {inv.vendor.name if inv.vendor else "-"}',
                inv.bank_name, 0, inv.paid_amount, inv.created_by)

    for vp in day_filter(VendorPayment.query, VendorPayment).all():
        desc = f'پرداخت به فروشنده({vp.vendor.name if vp.vendor else "-"})' + (f' — {vp.notes}' if vp.notes else '')
        add(vp.date, vp.j_year, vp.j_month, vp.j_day, vp.currency,
            'پرداختی از قسمت فروشنده', desc, '-', 0, vp.amount, vp.created_by)

    for sp in day_filter(EmployeeSalaryPayment.query, EmployeeSalaryPayment).all():
        desc = f'پرداخت معاش به({sp.employee.name if sp.employee else "-"})' + (f' — {sp.notes}' if sp.notes else '')
        add(sp.date, sp.j_year, sp.j_month, sp.j_day, sp.currency,
            'معاش کارمندان', desc, sp.bank.name if sp.bank else None, 0, sp.amount, sp.created_by)

    for ed in day_filter(ExpenseDetail.query, ExpenseDetail).all():
        desc = f'{ed.recipient}' + (f' — {ed.notes}' if ed.notes else '')
        add(ed.date, ed.j_year, ed.j_month, ed.j_day, ed.currency.code if ed.currency else None,
            'مصارف', desc, ed.bank.name if ed.bank else None, 0, ed.amount, ed.created_by)

    for rd in day_filter(RevenueDetail.query, RevenueDetail).all():
        desc = f'{rd.recipient}' + (f' — {rd.notes}' if rd.notes else '')
        add(rd.date, rd.j_year, rd.j_month, rd.j_day, rd.currency.code if rd.currency else None,
            'عواید متفرقه', desc, rd.bank.name if rd.bank else None, rd.amount, 0, rd.created_by)

    for ct in day_filter(CashTransaction.query, CashTransaction).all():
        label = PARTY_TYPE_LABELS.get(ct.party_type, 'طرف حساب')
        verb = 'پرداختی به' if ct.transaction_type == 'payment' else 'دریافتی از'
        desc = f'{verb} {label}({ct.party_name})' + (f' — {ct.notes}' if ct.notes else '')
        in_amt = ct.amount if ct.transaction_type == 'receipt' else 0
        out_amt = ct.amount if ct.transaction_type == 'payment' else 0
        add(ct.date, ct.j_year, ct.j_month, ct.j_day, ct.currency.code if ct.currency else None,
            f'پرداختی/دریافتی از قسمت {label}', desc, ct.bank.name if ct.bank else None,
            in_amt, out_amt, ct.created_by)

    for cp in day_filter(CustomerPayment.query, CustomerPayment).all():
        label = PARTY_TYPE_LABELS.get(cp.party_type, 'طرف حساب')
        verb = 'پرداختی به' if cp.payment_type == 'payment' else 'دریافتی از'
        desc = f'{verb} {label}({cp.party_name}) — تبدیل ارز'
        in_amt = cp.converted_amount if cp.payment_type == 'receipt' else 0
        out_amt = cp.converted_amount if cp.payment_type == 'payment' else 0
        add(cp.date, cp.j_year, cp.j_month, cp.j_day, cp.account_currency.code if cp.account_currency else None,
            f'پرداختی از قسمت صرافی ({label})', desc, cp.bank.name if cp.bank else None,
            in_amt, out_amt, cp.created_by)

    for bt in day_filter(BankTransfer.query, BankTransfer).all():
        desc = f'انتقال از {bt.from_bank.name if bt.from_bank else "-"} به {bt.to_bank.name if bt.to_bank else "-"}'
        add(bt.date, bt.j_year, bt.j_month, bt.j_day, bt.from_currency.code if bt.from_currency else None,
            'انتقال بین بانک‌ها', desc, bt.from_bank.name if bt.from_bank else None, 0, bt.amount, bt.created_by)
        add(bt.date, bt.j_year, bt.j_month, bt.j_day, bt.to_currency.code if bt.to_currency else None,
            'انتقال بین بانک‌ها', desc, bt.to_bank.name if bt.to_bank else None, bt.converted_amount, 0, bt.created_by)

    rows.sort(key=lambda r: r['date'] or py_date.min)
    return rows


@main.route("/")
def index():
    jy = request.args.get('jy', type=int)
    jm = request.args.get('jm', type=int)
    jd = request.args.get('jd', type=int)
    today = jdatetime.date.today()
    if not (jy and jm and jd):
        jy, jm, jd = today.year, today.month, today.day

    rows = get_journal_rows(jy, jm, jd)

    currencies = sorted({r['currency'] for r in rows if r['currency'] and r['currency'] != '-'}, key=_cur_sort_key)

    totals_today = {c: {'in': 0.0, 'out': 0.0} for c in currencies}
    for r in rows:
        if r['currency'] in totals_today:
            totals_today[r['currency']]['in'] += r['in_amt']
            totals_today[r['currency']]['out'] += r['out_amt']

    # ===== دخل دیروز: حساب افتتاحیه بانک‌ها + تمام تراکنش‌های قبل از امروز =====
    opening_by_cur = {}
    for bo in BankOpening.query.all():
        code = bo.currency.code if bo.currency else None
        if not code:
            continue
        opening_by_cur.setdefault(code, 0.0)
        sign = -1 if bo.account_type == 'payable' else 1
        opening_by_cur[code] += sign * (bo.amount or 0)

    prior_rows = get_journal_rows(before_jtuple=(jy, jm, jd))
    prior_by_cur = {}
    for r in prior_rows:
        c = r['currency']
        if not c or c == '-':
            continue
        prior_by_cur.setdefault(c, 0.0)
        prior_by_cur[c] += r['in_amt'] - r['out_amt']

    cashbox = {}
    for c in currencies:
        yesterday = opening_by_cur.get(c, 0.0) + prior_by_cur.get(c, 0.0)
        in_amt = totals_today[c]['in']
        out_amt = totals_today[c]['out']
        cashbox[c] = {
            'yesterday': yesterday,
            'in': in_amt,
            'out': out_amt,
            'balance': yesterday + in_amt - out_amt,
        }

    prev_j = jdatetime.date(jy, jm, jd) - timedelta(days=1)
    next_j = jdatetime.date(jy, jm, jd) + timedelta(days=1)

    return render_template("index.html",
        rows=rows, currencies=currencies, cashbox=cashbox,
        jy=jy, jm=jm, jd=jd, today=today,
        prev_j=prev_j, next_j=next_j)


# ==========================================
# روزنامچه تاریخ‌وار — همان روزنامچه، با امکان انتخاب بازه‌ی تاریخ (از/تا)
# فقط در «صفحه مدیریت» در دسترس است.
# ==========================================
@main.route('/admin/journal-range')
def journal_range():
    today = jdatetime.date.today()

    from_y = request.args.get('from_y', type=int) or today.year
    from_m = request.args.get('from_m', type=int) or 1
    from_d = request.args.get('from_d', type=int) or 1
    to_y = request.args.get('to_y', type=int) or today.year
    to_m = request.args.get('to_m', type=int) or today.month
    to_d = request.args.get('to_d', type=int) or today.day

    from_t = (from_y, from_m, from_d)
    to_t = (to_y, to_m, to_d)
    if from_t > to_t:
        from_t, to_t = to_t, from_t
        from_y, from_m, from_d = from_t
        to_y, to_m, to_d = to_t

    rows = get_journal_rows(range_jtuple=(from_t, to_t))

    currencies = sorted({r['currency'] for r in rows if r['currency'] and r['currency'] != '-'}, key=_cur_sort_key)

    totals = {c: {'in': 0.0, 'out': 0.0} for c in currencies}
    for r in rows:
        if r['currency'] in totals:
            totals[r['currency']]['in'] += r['in_amt']
            totals[r['currency']]['out'] += r['out_amt']

    # ===== مانده‌ی ابتدای بازه: افتتاحیه بانک‌ها + تمام تراکنش‌های قبل از from_t =====
    opening_by_cur = {}
    for bo in BankOpening.query.all():
        code = bo.currency.code if bo.currency else None
        if not code:
            continue
        opening_by_cur.setdefault(code, 0.0)
        sign = -1 if bo.account_type == 'payable' else 1
        opening_by_cur[code] += sign * (bo.amount or 0)

    prior_rows = get_journal_rows(before_jtuple=from_t)
    prior_by_cur = {}
    for r in prior_rows:
        c = r['currency']
        if not c or c == '-':
            continue
        prior_by_cur.setdefault(c, 0.0)
        prior_by_cur[c] += r['in_amt'] - r['out_amt']

    cashbox = {}
    for c in currencies:
        opening = opening_by_cur.get(c, 0.0) + prior_by_cur.get(c, 0.0)
        in_amt = totals[c]['in']
        out_amt = totals[c]['out']
        cashbox[c] = {
            'opening': opening, 'in': in_amt, 'out': out_amt,
            'balance': opening + in_amt - out_amt,
        }

    return render_template('admin/journal_range.html',
        rows=rows, currencies=currencies, cashbox=cashbox,
        from_y=from_y, from_m=from_m, from_d=from_d,
        to_y=to_y, to_m=to_m, to_d=to_d)


# ==========================================
# گزارش‌ها — صفحه‌ی اصلی گزارشات سیستم
# ==========================================
REPORT_PAGES = {
    'general':         'عمومی',
    'revenue_expense':  'عواید و مصارف',
    'exchange':          'راپور صرافی',
    'customers':        'مشتریان',
    'vendors':           'فروشنده',
    'warehouse':         'گدام',
    'employees':         'کارمندان',
}

# زیرگزارش‌های صفحه‌ی «عمومی»
GENERAL_REPORT_PAGES = {
    'profit_loss_detail': 'جزئیات راپور مفاد و ضرر',
    'balance':             'بلانس',
    'cash_capital':        'سرمایه نقدی',
}

# زیرگزارش‌های صفحه‌ی «راپور صرافی»
EXCHANGE_REPORT_PAGES = {
    'customer_exchange_total':     'راپور کلی صرافی مشتریان',
    'vendors_report':               'راپور فروشندگان',
    'qard_hasana':                  'راپور قرض الحسنه',
    'customer_claims_by_category':  'راپور طلبات مشتریان بر حسب کتگوری',
    'employees_report':             'راپور کارمندان',
}

# زیرگزارش‌های صفحه‌ی «گزارش‌های بخش مشتریان»
CUSTOMERS_REPORT_PAGES = {
    'sales_by_item':                 'میزان فروشات از یک جنس',
    'sales_invoices_report':         'فاکتورهای فروش شده',
    'items_sold':                     'اجناس برده شده',
    'items_bought_from_customer':    'اجناس خرید شده از مشتری',
    'items_credit_to_customers':     'اجناس Credit شده مشتریان',
    'customer_discounts':             'تخفیفات به مشتریان',
}

# زیرگزارش‌های صفحه‌ی «راپورهای فروشنده کالا»
VENDORS_REPORT_PAGES = {
    'items_bought_by_item':   'میزان خریداری‌ها از یک جنس',
    'purchase_bill_details':  'جزئیات بل',
}

WAREHOUSE_REPORT_PAGES = {
    'stock_in_report':          'ازدیاد به گدام',
    'stock_out_report':         'کاهش از گدام',
    'category_stock':           'کتگوری / گدام',
    'stock_transfer_details':   'جزئیات انتقال بین گدامها',
    'customer_item_claims':     'طلبات جنسی مشتریان',
    'opening_balance_report':   'موجودی اولیه',
    'stock_total_all':          'موجودی کلی گدامها',
    'inactive_items_report':    'راپور اجناس غیر فعال',
    'vendor_item_claims':       'طلبات جنسی از فروشنده گان',
    'stock_total_all_2':        'موجودی کلی گدام2',
    'stock_by_warehouse':       'موجودی بر اساس هر گدام',
    'item_claims_credit':       'طلبات جنسی credite',
    'stock_value':              'ارزش مقداری گدام',
    'production_report':        'راپور تولیدی',
}


@main.route('/reports')
def reports():
    user = User.query.get(session.get('user_id'))
    allowed = user_allowed_report_categories(user)
    visible_pages = {k: v for k, v in REPORT_PAGES.items() if k in allowed}
    return render_template('reports/index.html', report_pages=visible_pages)


@main.route('/debug/currencies')
def debug_currencies():
    all_currencies = Currency.query.order_by(Currency.code).all()
    db_path = current_app.config.get('SQLALCHEMY_DATABASE_URI', '')
    return render_template('reports/debug_currencies.html',
        all_currencies=all_currencies, db_path=db_path)


def cash_capital_summary():
    """
    سرمایهٔ نقدی کل شرکت: مجموع موجودی تمام بانک‌ها/صندوق‌ها به تفکیک ارز.
    از bank_balances_by_currency() استفاده می‌کند که موجودی واقعیِ هر بانک
    (شامل حساب افتتاحیه + تمام تراکنش‌های بعدی) را برمی‌گرداند.
    خروجی: (per_bank, totals)
      per_bank: لیست {'bank': Bank, 'balances': {code: amount}} برای هر بانک/صندوق
      totals:   دیکشنری {code: amount} — مجموع کل بانک‌ها به تفکیک ارز
    """
    banks = Bank.query.order_by(Bank.name).all()
    per_bank = []
    totals = {}
    for b in banks:
        bal = bank_balances_by_currency(b.id)
        bal = {code: amt for code, amt in bal.items() if abs(amt or 0) > 0.0001}
        per_bank.append({'bank': b, 'balances': bal})
        for code, amt in bal.items():
            totals[code] = totals.get(code, 0.0) + amt
    return per_bank, totals


def _latest_currency_rate(currency_id):
    """آخرین نرخ ثبت‌شده برای یک ارز (۱ دالر = ؟ واحد آن ارز) را برمی‌گرداند؛ اگر ثبت نشده None."""
    cr = (CurrencyRate.query.filter_by(currency_id=currency_id)
          .order_by(CurrencyRate.date.desc(), CurrencyRate.id.desc())
          .first())
    return cr.rate if cr and cr.rate else None


def amount_to_usd(amount, currency_id):
    """
    مبلغی به یک ارز مشخص را بر اساس آخرین نرخ ثبت‌شده در «نرخ اسعار» به دالر تبدیل می‌کند.
    اگر ارز خودِ دالر باشد، بدون تغییر برمی‌گردد. اگر نرخی برای آن ارز ثبت نشده باشد،
    برای افغانی از نرخ پیش‌فرض (get_default_afn_rate) و برای بقیه بدون تبدیل (نرخ ۱) استفاده می‌شود.
    """
    amount = amount or 0.0
    if not currency_id or not amount:
        return amount
    cur = Currency.query.get(currency_id)
    if not cur or cur.code == 'USD':
        return amount
    rate = _latest_currency_rate(currency_id)
    if not rate:
        rate = get_default_afn_rate() if cur.code == 'AFN' else 1
    return amount / rate


def balance_sheet_summary():
    """
    ترازنامهٔ مالی ساده (دارایی‌ها = بدهی‌ها + سرمایه)، همه‌چیز به دالر:
      - پول نقد: مجموع موجودی همهٔ بانک‌ها/صندوق‌ها (cash_capital_summary)
      - حساب‌های قابل دریافت: مجموع مانده تمام مشتریان (مثبت = مشتری به ما بدهکار است)
      - موجودی انبار: مجموع (موجودی فعلی × آخرین قیمت) تمام اجناس در StockBalance
      - حساب‌های پرداختنی: مجموع مانده تمام فروشنده‌ها (مثبت = ما به فروشنده بدهکاریم)
      - سرمایه خالص: مابه‌التفاوت جمع دارایی‌ها و جمع بدهی‌ها (رقم موازنه‌کننده)
    """
    _, cash_totals = cash_capital_summary()
    cash_usd = 0.0
    for code, amt in cash_totals.items():
        cur = Currency.query.filter_by(code=code).first()
        cash_usd += amount_to_usd(amt, cur.id) if cur else amt

    receivable_totals = {}
    for c in Customer.query.all():
        for cid, amt in customer_balance_by_currency(c.id).items():
            # توجه: customer_balance_by_currency اکنون منفی=بدهکار برمی‌گرداند؛ برای اینکه
            # «حساب‌های قابل دریافت» در ترازنامه مثبت باشد (طلب ما از مشتری)، علامت را برعکس می‌کنیم.
            receivable_totals[cid] = receivable_totals.get(cid, 0.0) - amt
    receivable_usd = sum(amount_to_usd(amt, cid) for cid, amt in receivable_totals.items())

    payable_totals = {}
    for v in Vendor.query.all():
        for cid, amt in vendor_balance_by_currency(v.id).items():
            payable_totals[cid] = payable_totals.get(cid, 0.0) + amt
    payable_usd = sum(amount_to_usd(amt, cid) for cid, amt in payable_totals.items())

    inventory_usd = 0.0
    for bal in StockBalance.query.all():
        inventory_usd += (bal.current_qty or 0) * (bal.last_price or 0)

    total_current_assets = cash_usd + receivable_usd + inventory_usd

    fixed_assets = 0.0
    for a in FixedAsset.query.filter_by(status='active').all():
        fixed_assets += a.book_value_usd()

    total_assets = total_current_assets + fixed_assets

    total_liabilities = payable_usd
    net_equity = total_assets - total_liabilities

    return {
        'cash': cash_usd,
        'receivable': receivable_usd,
        'inventory': inventory_usd,
        'total_current_assets': total_current_assets,
        'fixed_assets': fixed_assets,
        'total_assets': total_assets,
        'payable': payable_usd,
        'total_liabilities': total_liabilities,
        'net_equity': net_equity,
    }


def _line_qty(line):
    """
    مقدار (وزن/تعداد) واقعی یک ردیف فاکتور فروش یا برگشتی را برمی‌گرداند.
    اگر «تعداد» (count_desc) پر شده باشد: مقدار کل = amount (وزن یک واحد) × تعداد.
    در غیر این صورت: amount خودش وزن کل است.
    """
    amt = line.amount or 0
    c = None
    if line.count_desc and str(line.count_desc).strip():
        try:
            c = float(line.count_desc)
        except (TypeError, ValueError):
            c = None
    return amt * c if c else amt


def _line_total_afn(total, currency, exchange_rate):
    """مبلغ یک ردیف را به افغانی برمی‌گرداند (فاکتورهای دالری بر اساس نرخ روز تبدیل می‌شوند)."""
    total = total or 0
    if currency == 'USD':
        return total * (exchange_rate or get_default_afn_rate())
    return total


def profit_loss_report(search=None):
    """
    جزئیات مفاد و ضرر به تفکیک هر جنس (تمام تاریخچه، بدون فیلتر تاریخ):
      تعداد   = مجموع مقدار فروخته‌شده منهای مقدار برگشتی
      فروشات  = مجموع مبلغ فروش (به افغانی) منهای مبلغ برگشتی
      قیمت تمام = آخرین قیمت خرید ثبت‌شده برای آن جنس (به افغانی) — last_purchase_price_afn
      هزینه    = تعداد × قیمت تمام
      مفاد     = فروشات − هزینه
    """
    totals = {}

    for line in SalesInvoiceLine.query.join(SalesInvoice, SalesInvoiceLine.invoice_id == SalesInvoice.id).all():
        inv = line.invoice
        name = line.item_name or '-'
        d = totals.setdefault(name, {'qty': 0.0, 'sales': 0.0})
        d['qty'] += _line_qty(line)
        d['sales'] += _line_total_afn(line.total, inv.currency if inv else None, inv.exchange_rate if inv else 1)

    for line in CustomerReturnLine.query.join(CustomerReturn, CustomerReturnLine.return_id == CustomerReturn.id).all():
        ret = line.return_invoice
        name = line.item_name or '-'
        d = totals.setdefault(name, {'qty': 0.0, 'sales': 0.0})
        d['qty'] -= _line_qty(line)
        d['sales'] -= _line_total_afn(line.total, ret.currency if ret else None, ret.exchange_rate if ret else 1)

    rows = []
    grand_total_profit = 0.0
    for name in sorted(totals.keys()):
        if search and search.strip() and search.strip() not in name:
            continue
        d = totals[name]
        unit_cost = last_purchase_price_afn(name)
        cost_total = d['qty'] * unit_cost
        profit = d['sales'] - cost_total
        rows.append({
            'name': name, 'qty': d['qty'], 'sales': d['sales'],
            'unit_cost': unit_cost, 'cost_total': cost_total, 'profit': profit,
        })
        grand_total_profit += profit

    for i, r in enumerate(rows, start=1):
        r['no'] = i

    return rows, grand_total_profit


def expense_totals_summary():
    """جمع کل مصارف ثبت‌شده (ExpenseDetail) به تفکیک کتگوری، به دالر (از فیلد total_usd هر رکورد)."""
    by_cat = {}
    grand_total = 0.0
    for ed in ExpenseDetail.query.all():
        cat = ed.category.name if ed.category else 'سایر'
        usd = ed.total_usd or 0.0
        by_cat[cat] = by_cat.get(cat, 0.0) + usd
        grand_total += usd
    rows = [{'name': k, 'total_usd': v} for k, v in sorted(by_cat.items())]
    return rows, grand_total


@main.route('/reports/expense-total', methods=['GET'])
@report_category_required('revenue_expense')
def expense_total_report():
    """
    مصارف کلی: کاربر بازه تاریخ (شمسی) و نوعیت پول را انتخاب می‌کند، سپس
    لیست ریز تمام مصارف (ExpenseDetail) در آن بازه — به شکل راپور قابل چاپ — نمایش داده می‌شود.
    """
    today = jdatetime.date.today()

    from_jy = request.args.get('from_year', type=int) or today.year
    from_jm = request.args.get('from_month', type=int) or today.month
    from_jd = request.args.get('from_day', type=int) or today.day
    to_jy = request.args.get('to_year', type=int) or today.year
    to_jm = request.args.get('to_month', type=int) or today.month
    to_jd = request.args.get('to_day', type=int) or today.day
    currency_id = request.args.get('currency_id', type=int)
    searched = request.args.get('searched') == '1'

    start_date = jalali_to_gregorian(from_jy, from_jm, from_jd)
    end_date = jalali_to_gregorian(to_jy, to_jm, to_jd)

    records = []
    totals_by_currency = {}
    grand_total_usd = 0.0

    if searched:
        query = ExpenseDetail.query
        if start_date:
            query = query.filter(ExpenseDetail.date >= start_date)
        if end_date:
            query = query.filter(ExpenseDetail.date <= end_date)
        if currency_id:
            query = query.filter(ExpenseDetail.currency_id == currency_id)
        records = query.order_by(ExpenseDetail.date, ExpenseDetail.id).all()

        for r in records:
            code = r.currency.code if r.currency else '-'
            totals_by_currency[code] = totals_by_currency.get(code, 0.0) + (r.amount or 0)
            grand_total_usd += r.total_usd or 0.0

    active_currencies = Currency.query.filter_by(is_active=True).order_by(Currency.code).all()
    selected_currency_obj = Currency.query.get(currency_id) if currency_id else None

    return render_template('reports/expense_total.html',
        today=today, active_currencies=active_currencies,
        records=records, totals_by_currency=totals_by_currency, grand_total_usd=grand_total_usd,
        searched=searched,
        from_year=from_jy, from_month=from_jm, from_day=from_jd,
        to_year=to_jy, to_month=to_jm, to_day=to_jd,
        selected_currency=currency_id, selected_currency_obj=selected_currency_obj,
        back_url=url_for('main.report_page', slug='revenue_expense'))


def revenue_totals_summary():
    """جمع کل عواید متفرقه ثبت‌شده (RevenueDetail) به تفکیک کتگوری، به دالر (با آخرین نرخ ارز)."""
    by_cat = {}
    grand_total = 0.0
    for rd in RevenueDetail.query.all():
        cat = rd.category.name if rd.category else 'سایر'
        usd = amount_to_usd(rd.amount, rd.currency_id)
        by_cat[cat] = by_cat.get(cat, 0.0) + usd
        grand_total += usd
    rows = [{'name': k, 'total_usd': v} for k, v in sorted(by_cat.items())]
    return rows, grand_total


@main.route('/reports/revenue-total', methods=['GET'])
@report_category_required('revenue_expense')
def revenue_total_report():
    """
    عواید متفرقه کلی: کاربر بازه تاریخ (شمسی) و نوعیت پول را انتخاب می‌کند، سپس
    لیست ریز تمام عواید متفرقه (RevenueDetail) در آن بازه — به شکل راپور قابل چاپ — نمایش داده می‌شود.
    """
    today = jdatetime.date.today()

    from_jy = request.args.get('from_year', type=int) or today.year
    from_jm = request.args.get('from_month', type=int) or today.month
    from_jd = request.args.get('from_day', type=int) or today.day
    to_jy = request.args.get('to_year', type=int) or today.year
    to_jm = request.args.get('to_month', type=int) or today.month
    to_jd = request.args.get('to_day', type=int) or today.day
    currency_id = request.args.get('currency_id', type=int)
    searched = request.args.get('searched') == '1'

    start_date = jalali_to_gregorian(from_jy, from_jm, from_jd)
    end_date = jalali_to_gregorian(to_jy, to_jm, to_jd)

    records = []
    totals_by_currency = {}
    grand_total_usd = 0.0

    if searched:
        query = RevenueDetail.query
        if start_date:
            query = query.filter(RevenueDetail.date >= start_date)
        if end_date:
            query = query.filter(RevenueDetail.date <= end_date)
        if currency_id:
            query = query.filter(RevenueDetail.currency_id == currency_id)
        records = query.order_by(RevenueDetail.date, RevenueDetail.id).all()

        for r in records:
            code = r.currency.code if r.currency else '-'
            r.usd_value = amount_to_usd(r.amount, r.currency_id)
            r.rate_value = 1 if (r.currency and r.currency.code == 'USD') else (
                _latest_currency_rate(r.currency_id) or (get_default_afn_rate() if r.currency and r.currency.code == 'AFN' else 1)
            )
            totals_by_currency[code] = totals_by_currency.get(code, 0.0) + (r.amount or 0)
            grand_total_usd += r.usd_value

    active_currencies = Currency.query.filter_by(is_active=True).order_by(Currency.code).all()
    selected_currency_obj = Currency.query.get(currency_id) if currency_id else None

    return render_template('reports/revenue_total.html',
        today=today, active_currencies=active_currencies,
        records=records, totals_by_currency=totals_by_currency, grand_total_usd=grand_total_usd,
        searched=searched,
        from_year=from_jy, from_month=from_jm, from_day=from_jd,
        to_year=to_jy, to_month=to_jm, to_day=to_jd,
        selected_currency=currency_id, selected_currency_obj=selected_currency_obj,
        back_url=url_for('main.report_page', slug='revenue_expense'))


@main.route('/reports/sales-by-item', methods=['GET'])
@report_category_required('customers')
def sales_by_item_report():
    """
    میزان فروشات از یک جنس: کاربر بازه تاریخ (شمسی) و نام جنس را انتخاب می‌کند،
    سپس لیست ریز تمام ردیف‌های فاکتور فروش آن جنس در آن بازه نمایش داده می‌شود.
    """
    today = jdatetime.date.today()

    to_jy = request.args.get('to_year', type=int) or today.year
    to_jm = request.args.get('to_month', type=int) or today.month
    to_jd = request.args.get('to_day', type=int) or today.day
    from_jy = request.args.get('from_year', type=int) or today.year
    from_jm = request.args.get('from_month', type=int) or today.month
    from_jd = request.args.get('from_day', type=int) or today.day
    item_id = request.args.get('item_id', type=int)
    searched = request.args.get('searched') == '1'

    start_date = jalali_to_gregorian(from_jy, from_jm, from_jd)
    end_date = jalali_to_gregorian(to_jy, to_jm, to_jd)

    item_list = Item.query.filter_by(is_active=True).order_by(Item.name).all()
    selected_item = Item.query.get(item_id) if item_id else None

    rows = []
    total_qty = 0.0
    total_amount = 0.0

    if searched:
        query = SalesInvoiceLine.query.join(SalesInvoice)
        if start_date:
            query = query.filter(SalesInvoice.date >= start_date)
        if end_date:
            query = query.filter(SalesInvoice.date <= end_date)
        if selected_item:
            query = query.filter(SalesInvoiceLine.item_name == selected_item.name)
        lines = query.order_by(SalesInvoice.date, SalesInvoice.invoice_no).all()

        for line in lines:
            inv = line.invoice
            qty = _line_qty(line)
            rows.append({
                'invoice_no': inv.invoice_no,
                'item_name': line.item_name,
                'j_year': inv.j_year, 'j_month': inv.j_month, 'j_day': inv.j_day,
                'customer': inv.customer.name if inv.customer else '-',
                'price': line.price or 0,
                'qty': qty,
                'total': line.total or 0,
            })
            total_qty += qty
            total_amount += line.total or 0

    return render_template('reports/sales_by_item.html',
        today=today, item_list=item_list, selected_item_id=item_id, selected_item=selected_item,
        rows=rows, total_qty=total_qty, total_amount=total_amount, searched=searched,
        from_year=from_jy, from_month=from_jm, from_day=from_jd,
        to_year=to_jy, to_month=to_jm, to_day=to_jd,
        back_url=url_for('main.report_page', slug='customers'))


@main.route('/reports/items-taken', methods=['GET'])
@report_category_required('customers')
def items_taken_report():
    """
    اجناس برده شده: کاربر بازه تاریخ (شمسی) و نام جنس را انتخاب می‌کند، سپس
    لیست اجناسی که از یک گدام به گدام دیگر انتقال داده شده‌اند (StockTransfer)
    در آن بازه نمایش داده می‌شود.
    """
    today = jdatetime.date.today()

    from_jy = request.args.get('from_year', type=int) or today.year
    from_jm = request.args.get('from_month', type=int) or today.month
    from_jd = request.args.get('from_day', type=int) or today.day
    to_jy = request.args.get('to_year', type=int) or today.year
    to_jm = request.args.get('to_month', type=int) or today.month
    to_jd = request.args.get('to_day', type=int) or today.day
    item_id = request.args.get('item_id', type=int)
    searched = request.args.get('searched') == '1'

    start_date = jalali_to_gregorian(from_jy, from_jm, from_jd)
    end_date = jalali_to_gregorian(to_jy, to_jm, to_jd)

    item_list = Item.query.filter_by(is_active=True).order_by(Item.name).all()
    selected_item = Item.query.get(item_id) if item_id else None

    records = []
    total_qty = 0.0
    total_count = 0.0

    if searched:
        query = StockTransfer.query
        if start_date:
            query = query.filter(StockTransfer.date >= start_date)
        if end_date:
            query = query.filter(StockTransfer.date <= end_date)
        if selected_item:
            query = query.filter(StockTransfer.item_name == selected_item.name)
        records = query.order_by(StockTransfer.date, StockTransfer.id).all()
        total_qty = sum(r.amount or 0 for r in records)
        total_count = sum(r.count or 0 for r in records)

    return render_template('reports/items_taken.html',
        today=today, item_list=item_list, selected_item_id=item_id, selected_item=selected_item,
        records=records, total_qty=total_qty, total_count=total_count, searched=searched,
        from_year=from_jy, from_month=from_jm, from_day=from_jd,
        to_year=to_jy, to_month=to_jm, to_day=to_jd,
        back_url=url_for('main.report_page', slug='customers'))


@main.route('/reports/items-credit', methods=['GET'])
@report_category_required('customers')
def customer_returns_report():
    """
    اجناس Credit شده مشتریان: کاربر بازه تاریخ (شمسی) و نام جنس را انتخاب می‌کند، سپس
    لیست ریز تمام ردیف‌های بار برگشتی مشتریان (CustomerReturnLine) در آن بازه نمایش داده می‌شود.
    """
    today = jdatetime.date.today()

    from_jy = request.args.get('from_year', type=int) or today.year
    from_jm = request.args.get('from_month', type=int) or today.month
    from_jd = request.args.get('from_day', type=int) or today.day
    to_jy = request.args.get('to_year', type=int) or today.year
    to_jm = request.args.get('to_month', type=int) or today.month
    to_jd = request.args.get('to_day', type=int) or today.day
    item_id = request.args.get('item_id', type=int)
    searched = request.args.get('searched') == '1'

    start_date = jalali_to_gregorian(from_jy, from_jm, from_jd)
    end_date = jalali_to_gregorian(to_jy, to_jm, to_jd)

    item_list = Item.query.filter_by(is_active=True).order_by(Item.name).all()
    selected_item = Item.query.get(item_id) if item_id else None

    rows = []
    total_qty = 0.0
    total_amount = 0.0

    if searched:
        query = CustomerReturnLine.query.join(CustomerReturn)
        if start_date:
            query = query.filter(CustomerReturn.date >= start_date)
        if end_date:
            query = query.filter(CustomerReturn.date <= end_date)
        if selected_item:
            query = query.filter(CustomerReturnLine.item_name == selected_item.name)
        lines = query.order_by(CustomerReturn.date, CustomerReturn.return_no).all()

        for line in lines:
            ret = line.return_invoice
            qty = _line_qty(line)
            rows.append({
                'return_no': ret.return_no,
                'item_name': line.item_name,
                'j_year': ret.j_year, 'j_month': ret.j_month, 'j_day': ret.j_day,
                'customer': ret.customer.name if ret.customer else '-',
                'price': line.price or 0,
                'qty': qty,
                'total': line.total or 0,
            })
            total_qty += qty
            total_amount += line.total or 0

    return render_template('reports/customer_returns_report.html',
        today=today, item_list=item_list, selected_item_id=item_id, selected_item=selected_item,
        rows=rows, total_qty=total_qty, total_amount=total_amount, searched=searched,
        from_year=from_jy, from_month=from_jm, from_day=from_jd,
        to_year=to_jy, to_month=to_jm, to_day=to_jd,
        back_url=url_for('main.report_page', slug='customers'))


@main.route('/reports/customer-discounts', methods=['GET'])
@report_category_required('customers')
def customer_discounts_report():
    """
    تخفیفات به مشتریان: کاربر بازه تاریخ (شمسی) را انتخاب می‌کند، سپس لیست
    فاکتورهای فروش دارای تخفیف (SalesInvoice.discount) در آن بازه نمایش داده می‌شود.
    """
    today = jdatetime.date.today()

    from_jy = request.args.get('from_year', type=int) or today.year
    from_jm = request.args.get('from_month', type=int) or today.month
    from_jd = request.args.get('from_day', type=int) or today.day
    to_jy = request.args.get('to_year', type=int) or today.year
    to_jm = request.args.get('to_month', type=int) or today.month
    to_jd = request.args.get('to_day', type=int) or today.day
    searched = request.args.get('searched') == '1'

    start_date = jalali_to_gregorian(from_jy, from_jm, from_jd)
    end_date = jalali_to_gregorian(to_jy, to_jm, to_jd)

    rows = []
    total_discount = 0.0

    if searched:
        query = SalesInvoice.query.filter(SalesInvoice.discount > 0)
        if start_date:
            query = query.filter(SalesInvoice.date >= start_date)
        if end_date:
            query = query.filter(SalesInvoice.date <= end_date)
        invoices = query.order_by(SalesInvoice.date, SalesInvoice.invoice_no).all()

        for inv in invoices:
            rows.append({
                'invoice_no': inv.invoice_no,
                'customer': inv.customer.name if inv.customer else '-',
                'j_year': inv.j_year, 'j_month': inv.j_month, 'j_day': inv.j_day,
                'currency': inv.currency or '-',
                'discount': inv.discount or 0,
                'total_amount': inv.total_amount or 0,
            })
            total_discount += inv.discount or 0

    return render_template('reports/customer_discounts.html',
        today=today, rows=rows, total_discount=total_discount, searched=searched,
        from_year=from_jy, from_month=from_jm, from_day=from_jd,
        to_year=to_jy, to_month=to_jm, to_day=to_jd,
        back_url=url_for('main.report_page', slug='customers'))


@main.route('/reports/items-bought-by-item', methods=['GET'])
@report_category_required('vendors')
def items_bought_by_item_report():
    """
    میزان خریداری‌ها از یک جنس: کاربر بازه تاریخ (شمسی) و نام جنس را انتخاب می‌کند،
    سپس لیست ریز تمام ردیف‌های فاکتور خرید آن جنس در آن بازه نمایش داده می‌شود.
    """
    today = jdatetime.date.today()

    to_jy = request.args.get('to_year', type=int) or today.year
    to_jm = request.args.get('to_month', type=int) or today.month
    to_jd = request.args.get('to_day', type=int) or today.day
    from_jy = request.args.get('from_year', type=int) or today.year
    from_jm = request.args.get('from_month', type=int) or today.month
    from_jd = request.args.get('from_day', type=int) or today.day
    item_id = request.args.get('item_id', type=int)
    searched = request.args.get('searched') == '1'

    start_date = jalali_to_gregorian(from_jy, from_jm, from_jd)
    end_date = jalali_to_gregorian(to_jy, to_jm, to_jd)

    item_list = Item.query.filter_by(is_active=True).order_by(Item.name).all()
    selected_item = Item.query.get(item_id) if item_id else None

    rows = []
    total_qty = 0.0
    total_amount = 0.0

    if searched:
        query = PurchaseInvoiceLine.query.join(PurchaseInvoice)
        if start_date:
            query = query.filter(PurchaseInvoice.date >= start_date)
        if end_date:
            query = query.filter(PurchaseInvoice.date <= end_date)
        if selected_item:
            query = query.filter(PurchaseInvoiceLine.item_name == selected_item.name)
        lines = query.order_by(PurchaseInvoice.date, PurchaseInvoice.invoice_no).all()

        for line in lines:
            inv = line.invoice
            qty = line.amount or 0
            rows.append({
                'invoice_no': inv.invoice_no,
                'item_name': line.item_name,
                'j_year': inv.j_year, 'j_month': inv.j_month, 'j_day': inv.j_day,
                'vendor': inv.vendor.name if inv.vendor else '-',
                'price': line.price or 0,
                'qty': qty,
                'total': line.total or 0,
            })
            total_qty += qty
            total_amount += line.total or 0

    return render_template('reports/items_bought_by_item.html',
        today=today, item_list=item_list, selected_item_id=item_id, selected_item=selected_item,
        rows=rows, total_qty=total_qty, total_amount=total_amount, searched=searched,
        from_year=from_jy, from_month=from_jm, from_day=from_jd,
        to_year=to_jy, to_month=to_jm, to_day=to_jd,
        back_url=url_for('main.report_page', slug='vendors'))


@main.route('/reports/purchase-bill-details', methods=['GET'])
@report_category_required('vendors')
def purchase_bill_details_report():
    """
    جزئیات بل: کاربر بازه تاریخ (شمسی) را انتخاب می‌کند، سپس لیست ریز تمام
    ردیف‌های فاکتورهای خرید (PurchaseInvoiceLine) در آن بازه نمایش داده می‌شود.
    """
    today = jdatetime.date.today()

    from_jy = request.args.get('from_year', type=int) or today.year
    from_jm = request.args.get('from_month', type=int) or today.month
    from_jd = request.args.get('from_day', type=int) or today.day
    to_jy = request.args.get('to_year', type=int) or today.year
    to_jm = request.args.get('to_month', type=int) or today.month
    to_jd = request.args.get('to_day', type=int) or today.day
    searched = request.args.get('searched') == '1'

    start_date = jalali_to_gregorian(from_jy, from_jm, from_jd)
    end_date = jalali_to_gregorian(to_jy, to_jm, to_jd)

    rows = []
    total_qty = 0.0
    total_amount = 0.0

    if searched:
        query = PurchaseInvoiceLine.query.join(PurchaseInvoice)
        if start_date:
            query = query.filter(PurchaseInvoice.date >= start_date)
        if end_date:
            query = query.filter(PurchaseInvoice.date <= end_date)
        lines = query.order_by(PurchaseInvoice.date, PurchaseInvoice.invoice_no).all()

        for line in lines:
            inv = line.invoice
            qty = line.amount or 0
            rows.append({
                'invoice_no': inv.invoice_no,
                'vendor': inv.vendor.name if inv.vendor else '-',
                'item_name': line.item_name,
                'j_year': inv.j_year, 'j_month': inv.j_month, 'j_day': inv.j_day,
                'stock_name': line.stock.name if line.stock else '-',
                'unit_name': line.unit.quantity if line.unit else '-',
                'currency': inv.currency or '-',
                'price': line.price or 0,
                'qty': qty,
                'total': line.total or 0,
            })
            total_qty += qty
            total_amount += line.total or 0

    return render_template('reports/purchase_bill_details.html',
        today=today, rows=rows, total_qty=total_qty, total_amount=total_amount, searched=searched,
        from_year=from_jy, from_month=from_jm, from_day=from_jd,
        to_year=to_jy, to_month=to_jm, to_day=to_jd,
        back_url=url_for('main.report_page', slug='vendors'))


@main.route('/reports/sales-invoices-list', methods=['GET'])
@report_category_required('customers')
def sales_invoices_list_report():
    """
    فاکتورهای فروش شده: کاربر بازه تاریخ (شمسی) را انتخاب می‌کند، سپس لیست ریز
    تمام ردیف‌های فاکتورهای فروش (SalesInvoiceLine) در آن بازه نمایش داده می‌شود.
    """
    today = jdatetime.date.today()

    to_jy = request.args.get('to_year', type=int) or today.year
    to_jm = request.args.get('to_month', type=int) or today.month
    to_jd = request.args.get('to_day', type=int) or today.day
    from_jy = request.args.get('from_year', type=int) or today.year
    from_jm = request.args.get('from_month', type=int) or today.month
    from_jd = request.args.get('from_day', type=int) or today.day
    searched = request.args.get('searched') == '1'

    start_date = jalali_to_gregorian(from_jy, from_jm, from_jd)
    end_date = jalali_to_gregorian(to_jy, to_jm, to_jd)

    rows = []
    total_qty = 0.0
    total_amount = 0.0

    if searched:
        query = SalesInvoiceLine.query.join(SalesInvoice)
        if start_date:
            query = query.filter(SalesInvoice.date >= start_date)
        if end_date:
            query = query.filter(SalesInvoice.date <= end_date)
        lines = query.order_by(SalesInvoice.date, SalesInvoice.invoice_no).all()

        for line in lines:
            inv = line.invoice
            qty = _line_qty(line)
            rows.append({
                'invoice_no': inv.invoice_no,
                'customer': inv.customer.name if inv.customer else '-',
                'item_name': line.item_name,
                'j_year': inv.j_year, 'j_month': inv.j_month, 'j_day': inv.j_day,
                'price': line.price or 0,
                'qty': qty,
                'total': line.total or 0,
            })
            total_qty += qty
            total_amount += line.total or 0

    return render_template('reports/sales_invoices_list.html',
        today=today, rows=rows, total_qty=total_qty, total_amount=total_amount, searched=searched,
        from_year=from_jy, from_month=from_jm, from_day=from_jd,
        to_year=to_jy, to_month=to_jm, to_day=to_jd,
        back_url=url_for('main.report_page', slug='customers'))


@main.route('/reports/<slug>')
def report_page(slug):
    if not current_user_can_access_report(slug):
        flash('شما به این بخش از گزارش‌ها دسترسی ندارید', 'danger')
        return redirect(url_for('main.reports'))

    if slug == 'general':
        return render_template('reports/general.html', general_pages=GENERAL_REPORT_PAGES)

    if slug == 'cash_capital':
        per_bank, totals = cash_capital_summary()
        return render_template('reports/cash_capital.html',
            per_bank=per_bank, totals=totals,
            back_url=url_for('main.report_page', slug='general'))

    if slug == 'balance':
        data = balance_sheet_summary()
        today = jdatetime.date.today()
        return render_template('reports/balance_sheet.html',
            data=data, today=today,
            back_url=url_for('main.report_page', slug='general'))

    if slug == 'profit_loss_detail':
        search = request.args.get('q', '').strip()
        rows, grand_total_profit = profit_loss_report(search=search)
        return render_template('reports/profit_loss.html',
            rows=rows, grand_total_profit=grand_total_profit, search=search,
            back_url=url_for('main.report_page', slug='general'))

    if slug == 'revenue_expense':
        return render_template('reports/revenue_expense.html')

    if slug == 'exchange':
        return render_template('reports/exchange.html', exchange_pages=EXCHANGE_REPORT_PAGES)

    if slug == 'customer_exchange_total':
        search = request.args.get('q', '').strip()
        query = Customer.query.filter_by(is_active=True)
        if search:
            query = query.filter(Customer.name.contains(search))
        customer_list = query.order_by(Customer.name).all()

        report_currencies = [
            ('USD', 'دالری'), ('AFN', 'افغانی'), ('IRR', 'تومان'),
            ('PKR', 'کالدار'), ('INR', 'روپیه'),
        ]
        currency_ids = {code: _currency_code_to_id(code) for code, _ in report_currencies}

        rows = []
        for i, c in enumerate(customer_list, start=1):
            totals = customer_balance_by_currency(c.id)
            # customer_balance_by_currency اکنون خودش منفی=بدهکار برمی‌گرداند؛ نیازی به معکوس‌کردن دستی نیست.
            balances = {code: (totals.get(currency_ids[code], 0.0) or 0.0) for code, _ in report_currencies}
            rows.append({'no': i, 'id': c.id, 'name': c.name, 'phone': c.phone, 'balances': balances})

        return render_template('reports/customer_exchange_total.html',
            rows=rows, report_currencies=report_currencies, search=search,
            back_url=url_for('main.report_page', slug='exchange'))

    if slug == 'vendors_report':
        search = request.args.get('q', '').strip()
        query = Vendor.query.filter_by(is_active=True)
        if search:
            query = query.filter(Vendor.name.contains(search))
        vendor_list = query.order_by(Vendor.name).all()

        report_currencies = [
            ('USD', 'دالری'), ('AFN', 'افغانی'), ('IRR', 'تومان'),
            ('PKR', 'کالدار'), ('INR', 'روپیه'),
        ]
        currency_ids = {code: _currency_code_to_id(code) for code, _ in report_currencies}

        rows = []
        totals_row = {code: 0.0 for code, _ in report_currencies}
        for i, v in enumerate(vendor_list, start=1):
            totals = vendor_balance_by_currency(v.id)
            # قرارداد vendor_balance_by_currency: مثبت یعنی ما به فروشنده بدهکاریم (بستانکار او)،
            # منفی یعنی فروشنده به ما بدهکار است — همین علامت مستقیماً برای نمایش استفاده می‌شود.
            balances = {code: (totals.get(currency_ids[code], 0.0) or 0.0) for code, _ in report_currencies}
            for code in balances:
                totals_row[code] += balances[code]
            rows.append({'no': i, 'id': v.id, 'name': v.name, 'phone': v.phone, 'balances': balances})

        return render_template('reports/vendors_report.html',
            rows=rows, report_currencies=report_currencies, totals_row=totals_row, search=search,
            back_url=url_for('main.report_page', slug='exchange'))

    if slug == 'qard_hasana':
        search = request.args.get('q', '').strip()
        query = Borrower.query.filter_by(is_active=True)
        if search:
            query = query.filter(Borrower.name.contains(search))
        borrower_list = query.order_by(Borrower.name).all()

        report_currencies = [
            ('USD', 'دالری'), ('AFN', 'افغانی'), ('IRR', 'تومان'),
            ('PKR', 'کالدار'), ('INR', 'روپیه'),
        ]
        currency_ids = {code: _currency_code_to_id(code) for code, _ in report_currencies}

        rows = []
        totals_row = {code: 0.0 for code, _ in report_currencies}
        for i, b in enumerate(borrower_list, start=1):
            totals = borrower_balance_by_currency(b.id)
            # قرارداد borrower_balance_by_currency: مثبت یعنی ما به او بدهکاریم (بستانکار)،
            # منفی یعنی او به ما بدهکار است — مثل فروشنده، بدون معکوس‌سازی نمایش داده می‌شود.
            balances = {code: (totals.get(currency_ids[code], 0.0) or 0.0) for code, _ in report_currencies}
            for code in balances:
                totals_row[code] += balances[code]
            rows.append({'no': i, 'id': b.id, 'name': b.name, 'phone': b.phone, 'balances': balances})

        return render_template('reports/vendors_report.html',
            rows=rows, report_currencies=report_currencies, totals_row=totals_row, search=search,
            title_company_line='لیست حساب قرض الحسنه', page_title='راپور قرض الحسنه',
            name_col_title='نام قرض‌دهنده/گیرنده', search_placeholder='جستجو نام...',
            empty_label='قرض‌دهنده/گیرنده‌ای',
            back_url=url_for('main.report_page', slug='exchange'))

    if slug == 'employees_report':
        search = request.args.get('q', '').strip()
        query = Employee.query.filter_by(is_active=True)
        if search:
            query = query.filter(Employee.name.contains(search))
        employee_list = query.order_by(Employee.name).all()

        report_currencies = [
            ('USD', 'دالری'), ('AFN', 'افغانی'), ('IRR', 'تومان'),
            ('PKR', 'کالدار'), ('INR', 'روپیه'),
        ]
        currency_ids = {code: _currency_code_to_id(code) for code, _ in report_currencies}

        rows = []
        totals_row = {code: 0.0 for code, _ in report_currencies}
        for i, e in enumerate(employee_list, start=1):
            totals = employee_balance_by_currency(e.id)
            # employee_balance_by_currency اکنون خودش منفی=بدهکار برمی‌گرداند؛ نیازی به معکوس‌کردن دستی نیست.
            balances = {code: (totals.get(currency_ids[code], 0.0) or 0.0) for code, _ in report_currencies}
            for code in balances:
                totals_row[code] += balances[code]
            rows.append({'no': i, 'id': e.id, 'name': e.name, 'phone': e.phone, 'balances': balances})

        return render_template('reports/vendors_report.html',
            rows=rows, report_currencies=report_currencies, totals_row=totals_row, search=search,
            title_company_line='لیست حساب کارمندان', page_title='راپور کارمندان',
            name_col_title='نام کارمند', search_placeholder='جستجو نام کارمند...',
            empty_label='کارمندی',
            back_url=url_for('main.report_page', slug='exchange'))

    if slug == 'customer_claims_by_category':
        category_list = CustomerCategory.query.order_by(CustomerCategory.name).all()
        category_id = request.args.get('category_id', type=int)
        selected_category = CustomerCategory.query.get(category_id) if category_id else None

        report_currencies = [
            ('USD', 'دالری'), ('AFN', 'افغانی'), ('IRR', 'تومان'),
            ('PKR', 'کالدار'), ('INR', 'روپیه'),
        ]
        rows = None
        totals_row = None
        if category_id:
            currency_ids = {code: _currency_code_to_id(code) for code, _ in report_currencies}
            customer_list = (Customer.query.filter_by(category_id=category_id, is_active=True)
                              .order_by(Customer.name).all())
            rows = []
            totals_row = {code: 0.0 for code, _ in report_currencies}
            for i, c in enumerate(customer_list, start=1):
                totals = customer_balance_by_currency(c.id)
                balances = {code: (totals.get(currency_ids[code], 0.0) or 0.0) for code, _ in report_currencies}
                for code in balances:
                    totals_row[code] += balances[code]
                rows.append({'no': i, 'id': c.id, 'name': c.name, 'phone': c.phone, 'balances': balances})

        return render_template('reports/customer_claims_by_category.html',
            category_list=category_list, category_id=category_id, selected_category=selected_category,
            report_currencies=report_currencies, rows=rows, totals_row=totals_row,
            back_url=url_for('main.report_page', slug='exchange'))

    if slug == 'customers':
        return render_template('reports/customers_menu.html', customers_pages=CUSTOMERS_REPORT_PAGES)

    if slug == 'vendors':
        return render_template('reports/vendors_menu.html', vendors_pages=VENDORS_REPORT_PAGES)

    if slug == 'warehouse':
        return render_template('reports/warehouse_menu.html', warehouse_pages=WAREHOUSE_REPORT_PAGES)

    if slug == 'stock_out_report':
        return redirect(url_for('main.stock_out_report'))

    if slug == 'stock_in_report':
        return redirect(url_for('main.stock_in_report'))

    if slug == 'opening_balance_report':
        return redirect(url_for('main.opening_balance_report'))

    if slug == 'stock_total_all':
        return redirect(url_for('main.stock_total_all_report'))

    if slug == 'stock_by_warehouse':
        return redirect(url_for('main.stock_by_warehouse_report'))

    if slug == 'inactive_items_report':
        return redirect(url_for('main.inactive_items_report'))

    if slug == 'production_report':
        return redirect(url_for('main.production_report'))

    if slug == 'stock_value':
        return redirect(url_for('main.stock_value_report'))

    if slug == 'stock_transfer_details':
        return redirect(url_for('main.stock_transfer_details_report'))

    if slug in WAREHOUSE_REPORT_PAGES:
        return render_template('reports/placeholder.html',
            slug=slug, title=WAREHOUSE_REPORT_PAGES[slug],
            back_url=url_for('main.report_page', slug='warehouse'))

    if slug == 'items_bought_by_item':
        return redirect(url_for('main.items_bought_by_item_report'))

    if slug == 'purchase_bill_details':
        return redirect(url_for('main.purchase_bill_details_report'))

    if slug in VENDORS_REPORT_PAGES:
        return render_template('reports/placeholder.html',
            slug=slug, title=VENDORS_REPORT_PAGES[slug],
            back_url=url_for('main.report_page', slug='vendors'))

    if slug == 'sales_invoices_report':
        return redirect(url_for('main.sales_invoices_list_report'))

    if slug == 'sales_by_item':
        return redirect(url_for('main.sales_by_item_report'))

    if slug == 'items_sold':
        return redirect(url_for('main.items_taken_report'))

    if slug == 'items_credit_to_customers':
        return redirect(url_for('main.customer_returns_report'))

    if slug == 'customer_discounts':
        return redirect(url_for('main.customer_discounts_report'))

    if slug in CUSTOMERS_REPORT_PAGES:
        return render_template('reports/placeholder.html',
            slug=slug, title=CUSTOMERS_REPORT_PAGES[slug],
            back_url=url_for('main.report_page', slug='customers'))

    if slug in EXCHANGE_REPORT_PAGES:
        return render_template('reports/placeholder.html',
            slug=slug, title=EXCHANGE_REPORT_PAGES[slug],
            back_url=url_for('main.report_page', slug='exchange'))

    if slug == 'expense_total':
        return redirect(url_for('main.expense_total_report'))

    if slug == 'revenue_total':
        return redirect(url_for('main.revenue_total_report'))

    if slug in GENERAL_REPORT_PAGES:
        return render_template('reports/placeholder.html',
            slug=slug, title=GENERAL_REPORT_PAGES[slug],
            back_url=url_for('main.report_page', slug='general'))

    title = REPORT_PAGES.get(slug)
    if not title:
        flash('گزارش نامعتبر است', 'danger')
        return redirect(url_for('main.reports'))

    if slug == 'employees':
        transactions = (CashTransaction.query.filter_by(party_type='employee')
                         .order_by(CashTransaction.j_year.desc(), CashTransaction.j_month.desc(),
                                   CashTransaction.j_day.desc(), CashTransaction.id.desc()).all())

        employee_list = Employee.query.filter_by(is_active=True).order_by(Employee.name).all()
        balances = [{'employee': e, 'balance': employee_balance(e.id)} for e in employee_list]

        return render_template('reports/employees_report.html',
            title=title, transactions=transactions, balances=balances, employee_list=employee_list)

    return render_template('reports/placeholder.html', slug=slug, title=title)


# ==========================================
# کارمندان — ثبت کتگوری کارمندان
# ==========================================
@main.route('/employees/category', methods=['GET', 'POST'])
def employee_category():
    edit_id = request.args.get('edit', type=int)
    edit_ec = EmployeeCategory.query.get(edit_id) if edit_id else None

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        ec_id = request.form.get('ec_id', type=int)
        if not name:
            flash('نام کتگوری نمی‌تواند خالی باشد', 'danger')
        elif ec_id:
            ec = EmployeeCategory.query.get_or_404(ec_id)
            ec.name = name
            db.session.commit()
            flash('کتگوری ویرایش شد', 'success')
        else:
            db.session.add(EmployeeCategory(name=name))
            db.session.commit()
            flash('کتگوری ثبت شد', 'success')
        return redirect(url_for('main.employee_category'))

    search = request.args.get('q', '').strip()
    query = EmployeeCategory.query
    if search:
        query = query.filter(EmployeeCategory.name.contains(search))
    categories = query.order_by(EmployeeCategory.id).all()

    return render_template('employees/employee_category.html', categories=categories, edit_ec=edit_ec, search=search)


@main.route('/employees/category/delete/<int:id>')
def employee_category_delete(id):
    ec = EmployeeCategory.query.get_or_404(id)
    db.session.delete(ec)
    db.session.commit()
    flash('کتگوری حذف شد', 'success')
    return redirect(url_for('main.employee_category'))


# ==========================================
# کارمندان — ثبت کارمند
# ==========================================
ALLOWED_PHOTO_EXT = {'png', 'jpg', 'jpeg', 'webp'}


def save_employee_photo(photo_file, emp_id=None):
    """
    فایل عکس آپلودشده را در app/static/uploads/employees ذخیره می‌کند.
    خروجی: مسیر نسبی (برای ذخیره در دیتابیس و ساخت url_for('static', filename=...)) یا None.
    """
    if not photo_file or not photo_file.filename:
        return None
    ext = photo_file.filename.rsplit('.', 1)[-1].lower() if '.' in photo_file.filename else ''
    if ext not in ALLOWED_PHOTO_EXT:
        flash('فرمت عکس باید jpg، jpeg، png یا webp باشد', 'danger')
        return None

    upload_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'employees')
    os.makedirs(upload_dir, exist_ok=True)

    base_name = secure_filename(f"emp_{emp_id or 'new'}_{int(datetime.utcnow().timestamp())}")
    filename = f"{base_name}.{ext}"
    photo_file.save(os.path.join(upload_dir, filename))
    return f"uploads/employees/{filename}"


@main.route('/employees', methods=['GET', 'POST'])
def employees():
    edit_id = request.args.get('edit', type=int)
    edit_emp = Employee.query.get(edit_id) if edit_id else None

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        father_name = request.form.get('father_name', '').strip()
        tazkira_no = request.form.get('tazkira_no', '').strip()
        phone = request.form.get('phone', '').strip()
        category_id = request.form.get('category_id', type=int)
        position = request.form.get('position', '').strip()
        address = request.form.get('address', '').strip()
        emp_id = request.form.get('emp_id', type=int)
        photo_file = request.files.get('photo')
        photo_path = save_employee_photo(photo_file, emp_id)

        if not name:
            flash('نام کارمند نمی‌تواند خالی باشد', 'danger')
        elif Employee.query.filter(
                db.func.lower(Employee.name) == name.lower(),
                Employee.id != (emp_id or 0)).first():
            flash('کارمندی با همین نام قبلاً ثبت شده است', 'danger')
        elif emp_id:
            emp = Employee.query.get_or_404(emp_id)
            emp.name, emp.phone = name, phone
            emp.father_name, emp.tazkira_no = father_name, tazkira_no
            emp.category_id, emp.position, emp.address = category_id, position, address
            if photo_path:
                emp.photo = photo_path
            db.session.commit()
            flash('اطلاعات کارمند ویرایش شد', 'success')
        else:
            emp = Employee(
                name=name, phone=phone, father_name=father_name, tazkira_no=tazkira_no,
                category_id=category_id, position=position, address=address, photo=photo_path
            )
            db.session.add(emp)
            db.session.commit()
            flash('کارمند ثبت شد', 'success')
        return redirect(url_for('main.employees'))

    search = request.args.get('q', '').strip()
    query = Employee.query
    if search:
        query = query.filter(Employee.name.contains(search))
    employee_list = query.order_by(Employee.id.desc()).all()
    categories = EmployeeCategory.query.order_by(EmployeeCategory.name).all()

    return render_template('employees/employees.html',
        employee_list=employee_list, edit_emp=edit_emp, categories=categories, search=search)


@main.route('/employees/delete/<int:id>')
def employee_delete(id):
    emp = Employee.query.get_or_404(id)
    db.session.delete(emp)
    db.session.commit()
    flash('کارمند حذف شد', 'success')
    return redirect(url_for('main.employees'))


# ---- خلاصه حسابات کارمند ----
@main.route('/employees/search', methods=['GET'])
def employee_search():
    employee_list = Employee.query.filter_by(is_active=True).order_by(Employee.name).all()
    return render_template('employees/employee_search.html', employee_list=employee_list)


# ---- خلاصه حسابات کارمند ----
@main.route('/employees/account/<int:employee_id>')
def employee_account(employee_id):
    employee = Employee.query.get_or_404(employee_id)
    balance = employee_balance(employee.id)

    salary_cards = EmployeeSalaryCard.query.filter_by(employee_id=employee_id).all()
    total_salary = sum(sc.total_amount or 0 for sc in salary_cards)
    total_advance = sum(sc.advance_payment or 0 for sc in salary_cards)

    total_salary_payments = sum(
        (sp.amount or 0) for sp in EmployeeSalaryPayment.query.filter_by(employee_id=employee_id).all()
    )
    total_ct_payments = sum(
        (ct.amount or 0) for ct in CashTransaction.query.filter_by(party_type='employee', party_id=employee_id).all()
        if ct.transaction_type == 'payment'
    )
    total_cp_payments = sum(
        (cp.amount or 0) for cp in CustomerPayment.query.filter_by(party_type='employee', employee_id=employee_id).all()
        if cp.payment_type == 'payment'
    )
    total_payments = total_salary_payments + total_ct_payments + total_cp_payments

    total_receipts_ct = sum(
        (ct.amount or 0) for ct in CashTransaction.query.filter_by(party_type='employee', party_id=employee_id).all()
        if ct.transaction_type == 'receipt'
    )
    total_receipts_cp = sum(
        (cp.amount or 0) for cp in CustomerPayment.query.filter_by(party_type='employee', employee_id=employee_id).all()
        if cp.payment_type == 'receipt'
    )
    total_receipts = total_receipts_ct + total_receipts_cp

    return render_template('employees/employee_account.html',
        employee=employee, balance=balance,
        total_salary=total_salary, total_advance=total_advance,
        total_payments=total_payments, total_receipts=total_receipts)


# ---- حساب جاری کارمند: لیست تراکنش‌ها با مانده در حرکت ----
@main.route('/employees/account/<int:employee_id>/current')
def employee_current_account(employee_id):
    employee = Employee.query.get_or_404(employee_id)

    entries = []
    for sc in EmployeeSalaryCard.query.filter_by(employee_id=employee_id).all():
        g_date = jalali_to_gregorian(sc.j_year, sc.j_month, 1)
        entries.append({'date': g_date, 'j_year': sc.j_year, 'j_month': sc.j_month, 'j_day': 1,
                         'desc': f'معاش برج {sc.j_month} سال {sc.j_year}',
                         'debit': 0, 'credit': sc.total_amount or 0})
        if sc.advance_payment:
            entries.append({'date': g_date, 'j_year': sc.j_year, 'j_month': sc.j_month, 'j_day': 1,
                             'desc': f'پیش پرداخت معاش برج {sc.j_month} سال {sc.j_year}',
                             'debit': sc.advance_payment or 0, 'credit': 0})
    for sp in EmployeeSalaryPayment.query.filter_by(employee_id=employee_id).all():
        entries.append({'date': sp.date, 'j_year': sp.j_year, 'j_month': sp.j_month, 'j_day': sp.j_day,
                         'desc': sp.notes or 'پرداخت معاش',
                         'debit': sp.amount or 0, 'credit': 0})
    for ct in CashTransaction.query.filter_by(party_type='employee', party_id=employee_id).all():
        amt = ct.amount or 0
        entries.append({'date': ct.date, 'j_year': ct.j_year, 'j_month': ct.j_month, 'j_day': ct.j_day,
                         'desc': ct.notes or 'برد و رسید نقدی',
                         'debit': amt if ct.transaction_type == 'payment' else 0,
                         'credit': 0 if ct.transaction_type == 'payment' else amt})
    for cp in CustomerPayment.query.filter_by(party_type='employee', employee_id=employee_id).all():
        amt = cp.amount or 0
        entries.append({'date': cp.date, 'j_year': cp.j_year, 'j_month': cp.j_month, 'j_day': cp.j_day,
                         'desc': 'برد و رسید (تبدیل ارزی)',
                         'debit': amt if cp.payment_type == 'payment' else 0,
                         'credit': 0 if cp.payment_type == 'payment' else amt})

    entries.sort(key=lambda e: e['date'])

    running = 0
    for e in entries:
        e['amount'] = (e['credit'] or 0) - (e['debit'] or 0)
        running += e['amount']
        e['balance'] = running

    return render_template('employees/employee_current.html', employee=employee, entries=entries)


# ---- صورت حساب کلی کارمند (ریز تراکنش‌ها همراه با معاشات، شبیه صورت حساب مشتری) ----
@main.route('/employees/account/<int:employee_id>/summary')
def employee_summary(employee_id):
    employee = Employee.query.get_or_404(employee_id)

    entries = []

    for sc in EmployeeSalaryCard.query.filter_by(employee_id=employee_id).all():
        g_date = jalali_to_gregorian(sc.j_year, sc.j_month, 1)
        entries.append({'date': g_date, 'j_year': sc.j_year, 'j_month': sc.j_month, 'j_day': 1,
                         'currency': sc.currency or 'AFN', 'ref': 'معاش',
                         'desc': f'معاش برج {sc.j_month} سال {sc.j_year}',
                         'debit': 0, 'credit': sc.total_amount or 0})
        if sc.advance_payment:
            entries.append({'date': g_date, 'j_year': sc.j_year, 'j_month': sc.j_month, 'j_day': 1,
                             'currency': sc.currency or 'AFN', 'ref': 'معاش',
                             'desc': f'پیش پرداخت معاش برج {sc.j_month} سال {sc.j_year}',
                             'debit': sc.advance_payment or 0, 'credit': 0})

    for sp in EmployeeSalaryPayment.query.filter_by(employee_id=employee_id).all():
        entries.append({'date': sp.date, 'j_year': sp.j_year, 'j_month': sp.j_month, 'j_day': sp.j_day,
                         'currency': sp.currency or 'AFN', 'ref': 'معاش',
                         'desc': sp.notes or 'پرداخت معاش',
                         'debit': sp.amount or 0, 'credit': 0})

    for ct in CashTransaction.query.filter_by(party_type='employee', party_id=employee_id).all():
        amt = ct.amount or 0
        entries.append({'date': ct.date, 'j_year': ct.j_year, 'j_month': ct.j_month, 'j_day': ct.j_day,
                         'currency': (ct.currency.code if ct.currency else 'AFN'), 'ref': 'برد و رسید',
                         'desc': ct.notes or '',
                         'debit': amt if ct.transaction_type == 'payment' else 0,
                         'credit': 0 if ct.transaction_type == 'payment' else amt})

    for cp in CustomerPayment.query.filter_by(party_type='employee', employee_id=employee_id).all():
        amt = cp.amount or 0
        entries.append({'date': cp.date, 'j_year': cp.j_year, 'j_month': cp.j_month, 'j_day': cp.j_day,
                         'currency': (cp.pay_currency.code if cp.pay_currency else 'AFN'),
                         'ref': 'برد و رسید (تبدیل ارزی)', 'desc': cp.notes or '',
                         'debit': amt if cp.payment_type == 'payment' else 0,
                         'credit': 0 if cp.payment_type == 'payment' else amt})

    entries.sort(key=lambda e: e['date'] or py_date.min)

    active_currencies = sorted({e['currency'] for e in entries})
    currency_filter = request.args.get('currency', '').strip()
    if currency_filter:
        entries = [e for e in entries if e['currency'] == currency_filter]

    running = 0
    for e in entries:
        running += e['debit'] - e['credit']
        e['balance'] = running

    return render_template('employees/employee_summary.html', employee=employee, entries=entries,
                            active_currencies=active_currencies, currency_filter=currency_filter,
                            balance=running)


# ==========================================
# کارمندان — حاضری کارمند
# ==========================================
def _hhmm_to_hours(s):
    """تبدیل رشته 'HH:MM' به عدد اعشاری ساعت. اگر نامعتبر بود None برمی‌گرداند."""
    if not s:
        return None
    try:
        h, m = s.strip().split(':')
        return int(h) + int(m) / 60.0
    except (ValueError, AttributeError):
        return None


def _get_active_contract(employee_id):
    """آخرین قرارداد ثبت‌شده‌ی کارمند را برمی‌گرداند (برای ساعت استاندارد و معاش)."""
    return (EmployeeContract.query.filter_by(employee_id=employee_id)
            .order_by(EmployeeContract.id.desc()).first())


def compute_attendance_pay(employee_id, status, check_in, check_out):
    """
    بر اساس قرارداد کارمند، ساعت کارکرد/استاندارد/اضافه‌کاری و معاش روزانه را حساب می‌کند.
    خروجی: دیکشنری با تمام مقادیر محاسبه‌شده.
    """
    result = {
        'worked_hours': 0.0, 'standard_hours': 0.0, 'overtime_hours': 0.0,
        'daily_salary': 0.0, 'overtime_pay': 0.0, 'total_pay': 0.0, 'currency': None,
    }
    contract = _get_active_contract(employee_id)
    if not contract:
        return result

    result['currency'] = contract.currency
    std_start = _hhmm_to_hours(contract.standard_start) or 7.5
    std_end = _hhmm_to_hours(contract.standard_end) or 17.5
    standard_hours = max(0.0, std_end - std_start)
    result['standard_hours'] = standard_hours

    # معاش روزانه = معاش ماهوار قرارداد ÷ ۳۰
    daily_salary = (contract.salary_amount or 0) / 30.0
    result['daily_salary'] = daily_salary

    if status != 'present':
        # غایب/رخصتی: بدون ساعت کارکرد و بدون معاش روزانه
        return result

    in_h = _hhmm_to_hours(check_in)
    out_h = _hhmm_to_hours(check_out)
    worked_hours = max(0.0, out_h - in_h) if (in_h is not None and out_h is not None) else standard_hours
    result['worked_hours'] = worked_hours

    overtime_hours = max(0.0, worked_hours - standard_hours)
    result['overtime_hours'] = overtime_hours

    hourly_rate = (daily_salary / standard_hours) if standard_hours else 0
    overtime_pay = overtime_hours * hourly_rate
    result['overtime_pay'] = overtime_pay
    result['total_pay'] = daily_salary + overtime_pay
    return result


@main.route('/employees/attendance', methods=['GET', 'POST'])
def employee_attendance():
    edit_id = request.args.get('edit', type=int)
    edit_at = EmployeeAttendance.query.get(edit_id) if edit_id else None
    today = jdatetime.date.today()

    if request.method == 'POST':
        jy = request.form.get('j_year', type=int)
        jm = request.form.get('j_month', type=int)
        jd = request.form.get('j_day', type=int)
        g_date = jalali_to_gregorian(jy, jm, jd)
        employee_id = request.form.get('employee_id', type=int)
        status = request.form.get('status', 'present')
        check_in = request.form.get('check_in', '').strip()
        check_out = request.form.get('check_out', '').strip()
        notes = request.form.get('notes', '').strip()
        at_id = request.form.get('at_id', type=int)

        if not employee_id or not g_date:
            flash('انتخاب کارمند و تاریخ الزامی است', 'danger')
        elif EmployeeAttendance.query.filter(
                EmployeeAttendance.employee_id == employee_id,
                EmployeeAttendance.j_year == jy,
                EmployeeAttendance.j_month == jm,
                EmployeeAttendance.j_day == jd,
                EmployeeAttendance.id != (at_id or 0)).first():
            flash('حاضری این کارمند برای همین تاریخ قبلاً ثبت شده است', 'danger')
        else:
            pay = compute_attendance_pay(employee_id, status, check_in, check_out)
            if at_id:
                at = EmployeeAttendance.query.get_or_404(at_id)
                at.date, at.j_year, at.j_month, at.j_day = g_date, jy, jm, jd
                at.employee_id, at.status, at.notes = employee_id, status, notes
                at.check_in, at.check_out = check_in or None, check_out or None
                at.worked_hours, at.standard_hours = pay['worked_hours'], pay['standard_hours']
                at.overtime_hours, at.daily_salary = pay['overtime_hours'], pay['daily_salary']
                at.overtime_pay, at.total_pay, at.currency = pay['overtime_pay'], pay['total_pay'], pay['currency']
                db.session.commit()
                flash('حاضری ویرایش شد', 'success')
            else:
                db.session.add(EmployeeAttendance(
                    date=g_date, j_year=jy, j_month=jm, j_day=jd,
                    employee_id=employee_id, status=status, notes=notes,
                    check_in=check_in or None, check_out=check_out or None,
                    worked_hours=pay['worked_hours'], standard_hours=pay['standard_hours'],
                    overtime_hours=pay['overtime_hours'], daily_salary=pay['daily_salary'],
                    overtime_pay=pay['overtime_pay'], total_pay=pay['total_pay'], currency=pay['currency'],
                ))
                db.session.commit()
                flash('حاضری ثبت شد', 'success')
        return redirect(url_for('main.employee_attendance'))

    search = request.args.get('q', '').strip()
    query = EmployeeAttendance.query
    if search:
        query = query.join(Employee).filter(Employee.name.contains(search))
    records = query.order_by(EmployeeAttendance.id.desc()).all()
    employee_list = Employee.query.filter_by(is_active=True).order_by(Employee.name).all()

    return render_template('employees/attendance.html',
        records=records, edit_at=edit_at, employee_list=employee_list, today=today, search=search)


@main.route('/employees/attendance/delete/<int:id>')
def employee_attendance_delete(id):
    at = EmployeeAttendance.query.get_or_404(id)
    db.session.delete(at)
    db.session.commit()
    flash('رکورد حذف شد', 'success')
    return redirect(url_for('main.employee_attendance'))


@main.route('/employees/attendance/monthly')
def employee_attendance_monthly():
    today = jdatetime.date.today()
    jy = request.args.get('jy', type=int) or today.year
    jm = request.args.get('jm', type=int) or today.month
    days_in_month = _days_in_jalali_month(jy, jm)
    day_range = list(range(1, days_in_month + 1))

    friday_days = set()
    for d in day_range:
        try:
            if jdatetime.date(jy, jm, d).weekday() == 6:   # جمعه
                friday_days.add(d)
        except Exception:
            pass

    employee_list = Employee.query.filter_by(is_active=True).order_by(Employee.name).all()
    records = EmployeeAttendance.query.filter_by(j_year=jy, j_month=jm).all()

    grid = {}       # {employee_id: {day: EmployeeAttendance}}
    totals = {}     # {employee_id: تعداد روز حاضر}
    for r in records:
        grid.setdefault(r.employee_id, {})[r.j_day] = r
        if r.status == 'present':
            totals[r.employee_id] = totals.get(r.employee_id, 0) + 1

    prev_jm, prev_jy = (jm - 1, jy) if jm > 1 else (12, jy - 1)
    next_jm, next_jy = (jm + 1, jy) if jm < 12 else (1, jy + 1)

    return render_template('employees/attendance_monthly.html',
        employee_list=employee_list, grid=grid, totals=totals, day_range=day_range,
        friday_days=friday_days, jy=jy, jm=jm, today=today,
        prev_jy=prev_jy, prev_jm=prev_jm, next_jy=next_jy, next_jm=next_jm)


# ==========================================
# کارمندان — قرارداد کارمند
# ==========================================
@main.route('/employees/contract', methods=['GET', 'POST'])
def employee_contract():
    edit_id = request.args.get('edit', type=int)
    edit_c = EmployeeContract.query.get(edit_id) if edit_id else None
    today = jdatetime.date.today()

    if request.method == 'POST':
        employee_id = request.form.get('employee_id', type=int)
        position = request.form.get('position', '').strip()
        salary_amount = request.form.get('salary_amount', type=float) or 0
        currency = request.form.get('currency', '').strip()
        standard_start = request.form.get('standard_start', '07:30').strip() or '07:30'
        standard_end = request.form.get('standard_end', '17:30').strip() or '17:30'
        work_days = request.form.get('work_days', 'از شنبه تا پنج‌شنبه').strip() or 'از شنبه تا پنج‌شنبه'
        duration_years = request.form.get('duration_years', type=int) or 1
        notes = request.form.get('notes', '').strip()

        sjy = request.form.get('start_j_year', type=int)
        sjm = request.form.get('start_j_month', type=int)
        sjd = request.form.get('start_j_day', type=int)
        s_gdate = jalali_to_gregorian(sjy, sjm, sjd)

        ejy = request.form.get('end_j_year', type=int)
        ejm = request.form.get('end_j_month', type=int)
        ejd = request.form.get('end_j_day', type=int)
        e_gdate = jalali_to_gregorian(ejy, ejm, ejd) if (ejy and ejm and ejd) else None

        c_id = request.form.get('c_id', type=int)

        if not employee_id or not s_gdate:
            flash('انتخاب کارمند و تاریخ شروع قرارداد الزامی است', 'danger')
        elif c_id:
            c = EmployeeContract.query.get_or_404(c_id)
            c.employee_id, c.position = employee_id, position
            c.salary_amount, c.currency, c.notes = salary_amount, currency, notes
            c.standard_start, c.standard_end = standard_start, standard_end
            c.work_days, c.duration_years = work_days, duration_years
            c.start_date, c.start_j_year, c.start_j_month, c.start_j_day = s_gdate, sjy, sjm, sjd
            c.end_date, c.end_j_year, c.end_j_month, c.end_j_day = e_gdate, ejy, ejm, ejd
            db.session.commit()
            flash('قرارداد ویرایش شد', 'success')
        else:
            db.session.add(EmployeeContract(
                employee_id=employee_id, position=position,
                salary_amount=salary_amount, currency=currency, notes=notes,
                standard_start=standard_start, standard_end=standard_end,
                work_days=work_days, duration_years=duration_years,
                start_date=s_gdate, start_j_year=sjy, start_j_month=sjm, start_j_day=sjd,
                end_date=e_gdate, end_j_year=ejy, end_j_month=ejm, end_j_day=ejd
            ))
            db.session.commit()
            flash('قرارداد ثبت شد', 'success')
        return redirect(url_for('main.employee_contract'))

    search = request.args.get('q', '').strip()
    query = EmployeeContract.query
    if search:
        query = query.join(Employee).filter(Employee.name.contains(search))
    records = query.order_by(EmployeeContract.id.desc()).all()
    employee_list = Employee.query.filter_by(is_active=True).order_by(Employee.name).all()

    return render_template('employees/contract.html',
        records=records, edit_c=edit_c, employee_list=employee_list, today=today, search=search)


@main.route('/employees/contract/delete/<int:id>')
def employee_contract_delete(id):
    c = EmployeeContract.query.get_or_404(id)
    db.session.delete(c)
    db.session.commit()
    flash('رکورد حذف شد', 'success')
    return redirect(url_for('main.employee_contract'))


@main.route('/employees/contract/print/<int:id>')
def employee_contract_print(id):
    c = EmployeeContract.query.get_or_404(id)
    salary_words = number_to_persian_words(c.salary_amount or 0)
    return render_template('employees/contract_print.html', c=c, salary_words=salary_words)


# ==========================================
# کارمندان — کارت معاشات در هر برج
# ==========================================
def _days_in_jalali_month(jy, jm):
    """تعداد روزهای یک ماه شمسی (بدون نیاز به قابلیت خاص کتابخانه jdatetime)."""
    if jm <= 6:
        return 31
    if jm <= 11:
        return 30
    # ماه اسفند/حوت: در سال کبیسه ۳۰ روز، در غیر آن ۲۹ روز
    try:
        is_leap = jdatetime.date(jy, 1, 1).isleap()
    except Exception:
        is_leap = False
    return 30 if is_leap else 29


def compute_salary_card(employee_id, jy, jm):
    """
    از روی قرارداد (معاش ماهوار) و رکوردهای حاضری همان برج، تمام مقادیر کارت معاش را حساب می‌کند.
    """
    result = {
        'net_salary': 0.0, 'days_in_month': 30, 'daily_salary': 0.0,
        'attendance_days': 0, 'attendance_salary': 0.0,
        'overtime_hours': 0.0, 'overtime_amount': 0.0,
        'total_amount': 0.0, 'currency': None,
    }
    contract = _get_active_contract(employee_id)
    days_in_month = _days_in_jalali_month(jy, jm)
    result['days_in_month'] = days_in_month

    if not contract:
        return result

    net_salary = contract.salary_amount or 0
    daily_salary = net_salary / days_in_month if days_in_month else 0
    result['net_salary'] = net_salary
    result['daily_salary'] = daily_salary
    result['currency'] = contract.currency

    attendance_list = EmployeeAttendance.query.filter_by(
        employee_id=employee_id, j_year=jy, j_month=jm, status='present').all()

    attendance_days = len(attendance_list)
    overtime_hours = sum(a.overtime_hours or 0 for a in attendance_list)
    overtime_amount = sum(a.overtime_pay or 0 for a in attendance_list)

    result['attendance_days'] = attendance_days
    result['attendance_salary'] = daily_salary * attendance_days
    result['overtime_hours'] = overtime_hours
    result['overtime_amount'] = overtime_amount
    result['total_amount'] = result['attendance_salary'] + overtime_amount
    return result


@main.route('/employees/salary-card', methods=['GET', 'POST'])
def employee_salary_card():
    edit_id = request.args.get('edit', type=int)
    edit_sc = EmployeeSalaryCard.query.get(edit_id) if edit_id else None
    today = jdatetime.date.today()

    if request.method == 'POST':
        employee_id = request.form.get('employee_id', type=int)
        jy = request.form.get('j_year', type=int)
        jm = request.form.get('j_month', type=int)
        advance_payment = request.form.get('advance_payment', type=float) or 0
        notes = request.form.get('notes', '').strip()
        sc_id = request.form.get('sc_id', type=int)

        if not employee_id or not jy or not jm:
            flash('انتخاب کارمند و برج (سال/ماه) الزامی است', 'danger')
        elif EmployeeSalaryCard.query.filter(
                EmployeeSalaryCard.employee_id == employee_id,
                EmployeeSalaryCard.j_year == jy, EmployeeSalaryCard.j_month == jm,
                EmployeeSalaryCard.id != (sc_id or 0)).first():
            flash('کارت معاش این کارمند برای همین برج قبلاً ثبت شده است', 'danger')
        else:
            calc = compute_salary_card(employee_id, jy, jm)
            payable_amount = calc['total_amount'] - advance_payment
            if sc_id:
                sc = EmployeeSalaryCard.query.get_or_404(sc_id)
                sc.employee_id, sc.j_year, sc.j_month = employee_id, jy, jm
                sc.net_salary, sc.days_in_month, sc.daily_salary = calc['net_salary'], calc['days_in_month'], calc['daily_salary']
                sc.attendance_days, sc.attendance_salary = calc['attendance_days'], calc['attendance_salary']
                sc.overtime_hours, sc.overtime_amount = calc['overtime_hours'], calc['overtime_amount']
                sc.total_amount, sc.currency = calc['total_amount'], calc['currency']
                sc.advance_payment, sc.payable_amount, sc.notes = advance_payment, payable_amount, notes
                db.session.commit()
                flash('کارت معاش ویرایش شد', 'success')
            else:
                db.session.add(EmployeeSalaryCard(
                    employee_id=employee_id, j_year=jy, j_month=jm,
                    net_salary=calc['net_salary'], days_in_month=calc['days_in_month'], daily_salary=calc['daily_salary'],
                    attendance_days=calc['attendance_days'], attendance_salary=calc['attendance_salary'],
                    overtime_hours=calc['overtime_hours'], overtime_amount=calc['overtime_amount'],
                    total_amount=calc['total_amount'], currency=calc['currency'],
                    advance_payment=advance_payment, payable_amount=payable_amount, notes=notes,
                ))
                db.session.commit()
                flash('کارت معاش ثبت شد', 'success')
        return redirect(url_for('main.employee_salary_card'))

    # پیش‌نمایش محاسبه (وقتی کارمند/برج از طریق GET انتخاب شده - قبل از ذخیره)
    preview_employee_id = request.args.get('employee_id', type=int)
    preview_jy = request.args.get('preview_jy', type=int)
    preview_jm = request.args.get('preview_jm', type=int)
    preview = None
    if preview_employee_id and preview_jy and preview_jm:
        preview = compute_salary_card(preview_employee_id, preview_jy, preview_jm)

    search = request.args.get('q', '').strip()
    query = EmployeeSalaryCard.query
    if search:
        query = query.join(Employee).filter(Employee.name.contains(search))
    records = query.order_by(EmployeeSalaryCard.id.desc()).all()
    employee_list = Employee.query.filter_by(is_active=True).order_by(Employee.name).all()

    return render_template('employees/salary_card.html',
        records=records, edit_sc=edit_sc, employee_list=employee_list, today=today, search=search,
        preview=preview, preview_employee_id=preview_employee_id, preview_jy=preview_jy, preview_jm=preview_jm)


@main.route('/employees/salary-card/delete/<int:id>')
def employee_salary_card_delete(id):
    sc = EmployeeSalaryCard.query.get_or_404(id)
    db.session.delete(sc)
    db.session.commit()
    flash('رکورد حذف شد', 'success')
    return redirect(url_for('main.employee_salary_card'))


@main.route('/employees/salary-card/print/<int:id>')
def employee_salary_card_print(id):
    sc = EmployeeSalaryCard.query.get_or_404(id)
    jalali_month_names = ['حمل', 'ثور', 'جوزا', 'سرطان', 'اسد', 'سنبله',
                           'میزان', 'عقرب', 'قوس', 'جدی', 'دلو', 'حوت']
    month_name = jalali_month_names[sc.j_month - 1] if 1 <= sc.j_month <= 12 else ''
    return render_template('employees/salary_card_print.html', sc=sc, month_name=month_name)


@main.route('/employees/salary-card/pay/<int:id>', methods=['GET', 'POST'])
def employee_salary_card_pay(id):
    sc = EmployeeSalaryCard.query.get_or_404(id)
    bank_list = Bank.query.filter_by(is_active=True).order_by(Bank.name).all()

    if sc.is_paid:
        flash('این کارت معاش قبلاً پرداخت شده است', 'danger')
        return redirect(url_for('main.employee_salary_card'))

    if request.method == 'POST':
        bank_id = request.form.get('bank_id', type=int)
        bank = Bank.query.get(bank_id) if bank_id else None
        if not bank:
            flash('انتخاب بانک/صندوق الزامی است', 'danger')
            return redirect(url_for('main.employee_salary_card_pay', id=id))

        today = jdatetime.date.today()
        g_date = jalali_to_gregorian(today.year, today.month, today.day)
        currency_obj = Currency.query.filter_by(code=sc.currency).first() if sc.currency else None

        ct = CashTransaction(
            date=g_date, j_year=today.year, j_month=today.month, j_day=today.day,
            party_type='employee', party_id=sc.employee_id,
            party_name=sc.employee.name if sc.employee else '',
            transaction_type='payment', amount=sc.payable_amount,
            currency_id=currency_obj.id if currency_obj else None,
            bank_id=bank.id, notes=f'پرداخت معاش برج {sc.j_year}-{sc.j_month}',
            created_by=session.get('username'),
        )
        db.session.add(ct)
        db.session.flush()

        if currency_obj:
            adjust_bank_balance(bank.id, currency_obj.id, -sc.payable_amount, g_date=g_date,
                                 notes=f'پرداخت معاش کارمند — {sc.employee.name if sc.employee else ""} (برج {sc.j_year}-{sc.j_month})')

        sc.is_paid = True
        sc.bank_id = bank.id
        sc.cash_transaction_id = ct.id
        db.session.commit()
        flash('پرداخت معاش ثبت شد و از بانک کسر گردید', 'success')
        return redirect(url_for('main.employee_salary_card'))

    return render_template('employees/salary_card_pay.html', sc=sc, bank_list=bank_list)


# ==========================================
# کارمندان — معاش کارمندان (پرداخت واقعی)
# ==========================================
@main.route('/employees/salary-payment', methods=['GET', 'POST'])
def employee_salary_payment():
    edit_id = request.args.get('edit', type=int)
    edit_sp = EmployeeSalaryPayment.query.get(edit_id) if edit_id else None
    today = jdatetime.date.today()
    bank_list = Bank.query.filter_by(is_active=True).order_by(Bank.name).all()

    if request.method == 'POST':
        jy = request.form.get('j_year', type=int)
        jm = request.form.get('j_month', type=int)
        jd = request.form.get('j_day', type=int)
        g_date = jalali_to_gregorian(jy, jm, jd)
        employee_id = request.form.get('employee_id', type=int)
        amount = request.form.get('amount', type=float) or 0
        currency = request.form.get('currency', '').strip()
        bank_id = request.form.get('bank_id', type=int) or None
        notes = request.form.get('notes', '').strip()
        sp_id = request.form.get('sp_id', type=int)

        if not employee_id or not g_date:
            flash('انتخاب کارمند و تاریخ الزامی است', 'danger')
        elif sp_id:
            sp = EmployeeSalaryPayment.query.get_or_404(sp_id)
            # برگرداندن اثر قبلی از موجودی بانک قبل از اعمال مقدار جدید
            if sp.bank_id:
                old_currency_id = _currency_code_to_id(sp.currency)
                adjust_bank_balance(sp.bank_id, old_currency_id, sp.amount or 0,
                                     notes='برگشت تعدیل پرداخت معاش (ویرایش)')

            sp.date, sp.j_year, sp.j_month, sp.j_day = g_date, jy, jm, jd
            sp.employee_id, sp.amount, sp.currency = employee_id, amount, currency
            sp.bank_id, sp.notes = bank_id, notes

            if bank_id:
                new_currency_id = _currency_code_to_id(currency)
                adjust_bank_balance(bank_id, new_currency_id, -amount, g_date=g_date,
                                     notes='پرداخت معاش (ویرایش)')

            db.session.commit()
            flash('پرداخت معاش ویرایش شد', 'success')
        else:
            sp = EmployeeSalaryPayment(
                date=g_date, j_year=jy, j_month=jm, j_day=jd,
                employee_id=employee_id, amount=amount, currency=currency,
                bank_id=bank_id, notes=notes, created_by=session.get('username')
            )
            db.session.add(sp)

            if bank_id:
                currency_id = _currency_code_to_id(currency)
                adjust_bank_balance(bank_id, currency_id, -amount, g_date=g_date,
                                     notes='پرداخت معاش')

            db.session.commit()
            flash('پرداخت معاش ثبت شد', 'success')
        return redirect(url_for('main.employee_salary_payment'))

    search = request.args.get('q', '').strip()
    query = EmployeeSalaryPayment.query
    if search:
        query = query.join(Employee).filter(Employee.name.contains(search))
    records = query.order_by(EmployeeSalaryPayment.id.desc()).all()
    employee_list = Employee.query.filter_by(is_active=True).order_by(Employee.name).all()

    return render_template('employees/salary_payment.html',
        records=records, edit_sp=edit_sp, employee_list=employee_list,
        bank_list=bank_list, today=today, search=search)


@main.route('/employees/salary-payment/delete/<int:id>')
def employee_salary_payment_delete(id):
    sp = EmployeeSalaryPayment.query.get_or_404(id)
    if sp.bank_id:
        currency_id = _currency_code_to_id(sp.currency)
        adjust_bank_balance(sp.bank_id, currency_id, sp.amount or 0,
                             notes='برگشت تعدیل پرداخت معاش (حذف)')
    db.session.delete(sp)
    db.session.commit()
    flash('رکورد حذف شد', 'success')
    return redirect(url_for('main.employee_salary_payment'))


# ==========================================
# گدام — واحد اندازه‌گیری
# ==========================================
@main.route('/warehouse/units')
def units():
    units = Quantity.query.order_by(Quantity.id.desc()).all()
    return render_template('warehouse/units.html', units=units)


@main.route('/warehouse/units/add', methods=['GET', 'POST'])
def unit_add():
    if request.method == 'POST':
        name = request.form.get('quantity', '').strip()
        if name:
            unit = Quantity(quantity=name)
            db.session.add(unit)
            db.session.commit()
            flash('واحد اندازه‌گیری ثبت شد', 'success')
        else:
            flash('نام واحد نمی‌تواند خالی باشد', 'danger')
        return redirect(url_for('main.units'))
    return render_template('warehouse/unit_form.html')


@main.route('/warehouse/units/edit/<int:id>', methods=['GET', 'POST'])
def unit_edit(id):
    unit = Quantity.query.get_or_404(id)
    if request.method == 'POST':
        unit.quantity = request.form.get('quantity', '').strip()
        db.session.commit()
        flash('واحد ویرایش شد', 'success')
        return redirect(url_for('main.units'))
    return render_template('warehouse/unit_form.html', unit=unit)


@main.route('/warehouse/units/delete/<int:id>')
def unit_delete(id):
    unit = Quantity.query.get_or_404(id)
    db.session.delete(unit)
    db.session.commit()
    flash('واحد حذف شد', 'success')
    return redirect(url_for('main.units'))


# ==========================================
# گدام — ثبت کتگوری (یک صفحه: فرم + لیست)
# ==========================================
@main.route('/warehouse/categories', methods=['GET', 'POST'])
def categories():
    edit_id = request.args.get('edit', type=int)
    edit_category = Category.query.get(edit_id) if edit_id else None

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        cat_id = request.form.get('cat_id', type=int)
        if not name:
            flash('نام کتگوری نمی‌تواند خالی باشد', 'danger')
        elif cat_id:
            cat = Category.query.get_or_404(cat_id)
            cat.name = name
            db.session.commit()
            flash('کتگوری ویرایش شد', 'success')
        else:
            db.session.add(Category(name=name))
            db.session.commit()
            flash('کتگوری ثبت شد', 'success')
        return redirect(url_for('main.categories'))

    search = request.args.get('q', '').strip()
    query = Category.query
    if search:
        query = query.filter(Category.name.contains(search))
    categories = query.order_by(Category.id).all()

    return render_template('warehouse/categories.html',
        categories=categories, edit_category=edit_category, search=search)


@main.route('/warehouse/categories/delete/<int:id>')
def category_delete(id):
    cat = Category.query.get_or_404(id)
    db.session.delete(cat)
    db.session.commit()
    flash('کتگوری حذف شد', 'success')
    return redirect(url_for('main.categories'))


# ==========================================
# گدام — ثبت گدام (یک صفحه: فرم + لیست)
# ==========================================
@main.route('/warehouse/stocks', methods=['GET', 'POST'])
def stocks():
    edit_id = request.args.get('edit', type=int)
    edit_stock = Stock.query.get(edit_id) if edit_id else None

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        keeper = request.form.get('keeper', '').strip()
        phone = request.form.get('phone', '').strip()
        address = request.form.get('address', '').strip()
        stock_id = request.form.get('stock_id', type=int)

        if not name:
            flash('نام گدام نمی‌تواند خالی باشد', 'danger')
        elif stock_id:
            s = Stock.query.get_or_404(stock_id)
            s.name, s.keeper, s.phone, s.address = name, keeper, phone, address
            db.session.commit()
            flash('گدام ویرایش شد', 'success')
        else:
            db.session.add(Stock(name=name, keeper=keeper, phone=phone, address=address))
            db.session.commit()
            flash('گدام ثبت شد', 'success')
        return redirect(url_for('main.stocks'))

    search = request.args.get('q', '').strip()
    query = Stock.query
    if search:
        query = query.filter(Stock.name.contains(search))
    stocks = query.order_by(Stock.id).all()

    return render_template('warehouse/stocks.html',
        stocks=stocks, edit_stock=edit_stock, search=search)


@main.route('/warehouse/stocks/toggle/<int:id>')
def stock_toggle(id):
    s = Stock.query.get_or_404(id)
    s.is_active = not s.is_active
    db.session.commit()
    return redirect(url_for('main.stocks'))


@main.route('/warehouse/stocks/delete/<int:id>')
def stock_delete(id):
    s = Stock.query.get_or_404(id)
    db.session.delete(s)
    db.session.commit()
    flash('گدام حذف شد', 'success')
    return redirect(url_for('main.stocks'))


# ==========================================
# گدام — ثبت کالا (اجناس)
# ==========================================
@main.route('/warehouse/items', methods=['GET', 'POST'])
def items():
    edit_id = request.args.get('edit', type=int)
    edit_item = Item.query.get(edit_id) if edit_id else None

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        item_type = request.form.get('item_type', '').strip()
        quantity_id = request.form.get('quantity_id', type=int)
        category_id = request.form.get('category_id', type=int)
        sale_price = request.form.get('sale_price', type=float) or 0
        max_price = request.form.get('max_price', type=float) or 0
        min_price = request.form.get('min_price', type=float) or 0
        shelf_row = request.form.get('shelf_row', '').strip()
        shelf_floor = request.form.get('shelf_floor', '').strip()
        shelf_number = request.form.get('shelf_number', '').strip()
        is_active = request.form.get('is_active', '1') == '1'
        item_id = request.form.get('item_id', type=int)

        if not name:
            flash('نام جنس نمی‌تواند خالی باشد', 'danger')
        elif item_id:
            it = Item.query.get_or_404(item_id)
            it.name = name
            it.item_type = item_type
            it.quantity_id = quantity_id
            it.category_id = category_id
            it.sale_price = sale_price
            it.max_price = max_price
            it.min_price = min_price
            it.shelf_row = shelf_row
            it.shelf_floor = shelf_floor
            it.shelf_number = shelf_number
            it.is_active = is_active
            db.session.commit()
            flash('جنس ویرایش شد', 'success')
        else:
            last = Item.query.order_by(Item.code.desc()).first()
            next_code = (last.code + 1) if last and last.code else 1
            db.session.add(Item(
                code=next_code, name=name, item_type=item_type,
                quantity_id=quantity_id, category_id=category_id,
                sale_price=sale_price, max_price=max_price, min_price=min_price,
                shelf_row=shelf_row, shelf_floor=shelf_floor, shelf_number=shelf_number,
                is_active=is_active
            ))
            db.session.commit()
            flash('جنس ثبت شد', 'success')
        return redirect(url_for('main.items'))

    items = Item.query.order_by(Item.id).all()
    units = Quantity.query.order_by(Quantity.quantity).all()
    categories = Category.query.order_by(Category.name).all()

    return render_template('warehouse/items.html',
        items=items, edit_item=edit_item, units=units, categories=categories)


@main.route('/warehouse/items/toggle/<int:id>')
def item_toggle(id):
    it = Item.query.get_or_404(id)
    it.is_active = not it.is_active
    db.session.commit()
    return redirect(url_for('main.items'))


@main.route('/warehouse/items/delete/<int:id>')
def item_delete(id):
    it = Item.query.get_or_404(id)
    db.session.delete(it)
    db.session.commit()
    flash('جنس حذف شد', 'success')
    return redirect(url_for('main.items'))


# ==========================================
# گدام — ثبت حساب افتتاحیه
# ==========================================
def vendor_balance(vendor_id):
    """
    مانده حساب یک فروشنده را برمی‌گرداند.
    منطق: بدهی ما = افتتاحیه (payable) + جمع باقی فاکتورهای خرید - جمع پرداخت‌های ما به او
          اگر افتتاحیه از نوع receivable باشد (طلب ما از او)، با علامت منفی اثر می‌گذارد.
    عدد مثبت یعنی ما به فروشنده بدهکاریم؛ منفی یعنی او به ما بدهکار است.

    برد و رسید عمومی (CashTransaction) با همین قرارداد:
    برد (ما به فروشنده می‌پردازیم) → بدهی ما کم می‌شود.
    رسید (فروشنده به ما می‌پردازد) → بدهی ما زیاد می‌شود (یا طلب ما از او شکل می‌گیرد).
    """
    total = 0.0
    openings = VendorOpening.query.filter_by(vendor_id=vendor_id).all()
    for o in openings:
        if o.account_type == 'receivable':
            total -= (o.amount or 0)
        else:
            total += (o.amount or 0)

    invoices = PurchaseInvoice.query.filter_by(vendor_id=vendor_id).all()
    for inv in invoices:
        total += (inv.remaining or 0)

    # بار برگشتی فروشنده: بدهی ما به فروشنده به اندازه مبلغ برگشتی کم می‌شود.
    # اگر بدهی به صفر برسد و باز هم برگشتی باقی بماند، مانده منفی می‌شود یعنی فروشنده به ما بدهکار است
    # (این یعنی فروشنده قبلاً پول جنس را گرفته بوده) — دقیقاً طبق قاعده بین‌المللی بار برگشتی خرید.
    returns = VendorReturn.query.filter_by(vendor_id=vendor_id).all()
    for r in returns:
        total -= (r.total_amount or 0)

    payments = VendorPayment.query.filter_by(vendor_id=vendor_id).all()
    for p in payments:
        total -= (p.amount or 0)

    for ct in CashTransaction.query.filter_by(party_type='vendor', party_id=vendor_id).all():
        if ct.transaction_type == 'payment':       # برد: ما به فروشنده پرداختیم
            total -= (ct.amount or 0)
        else:                                          # رسید: فروشنده به ما پرداخت
            total += (ct.amount or 0)

    for cp in CustomerPayment.query.filter_by(party_type='vendor', vendor_id=vendor_id).all():
        total += (cp.amount or 0) if cp.payment_type == 'payment' else -(cp.amount or 0)

    return total


def customer_balance(customer_id):
    """
    مانده حساب یک مشتری را برمی‌گرداند.
    قرارداد (هماهنگ با vendor_balance/borrower_balance): عدد منفی یعنی مشتری به ما بدهکار/قرضدار
    است (طلب ما)؛ مثبت یعنی ما به او بدهکاریم.

    رسید (دریافت پول از مشتری) → بدهی مشتری کم می‌شود.
    برد (پرداخت پول به مشتری) → بدهی مشتری زیاد می‌شود (مثل وام‌دادن دوباره به او).

    (محاسبه‌ی داخلی طبق قرارداد قدیمی [مثبت=بدهکار] انجام می‌شود و در پایان علامت آن
    برای هماهنگی با vendor_balance/borrower_balance معکوس می‌شود.)
    """
    total = 0.0
    openings = CustomerOpening.query.filter_by(customer_id=customer_id).all()
    for o in openings:
        if o.account_type == 'payable':
            total -= (o.amount or 0)
        else:
            total += (o.amount or 0)

    invoices = SalesInvoice.query.filter_by(customer_id=customer_id).all()
    for inv in invoices:
        total += (inv.remaining or 0)

    # بار برگشتی مشتری: طلب ما از مشتری به اندازه مبلغ برگشتی کم می‌شود
    for r in CustomerReturn.query.filter_by(customer_id=customer_id).all():
        total -= (r.total_amount or 0)

    for ct in CashTransaction.query.filter_by(party_type='customer', party_id=customer_id).all():
        if ct.transaction_type == 'payment':       # برد: ما به مشتری پرداختیم → بدهی او زیاد می‌شود
            total += (ct.amount or 0)
        else:                                          # رسید: از مشتری گرفتیم → بدهی او کم می‌شود
            total -= (ct.amount or 0)

    # انتقال حساب بین مشتریان (بدون اثر بانکی)
    for tr in CustomerTransfer.query.filter_by(from_customer_id=customer_id).all():
        if tr.transaction_type == 'payment':        # بردگی: بدهی مبدا زیاد می‌شود
            total += (tr.amount or 0)
        else:                                            # رسیدگی: بدهی مبدا کم می‌شود
            total -= (tr.amount or 0)

    for tr in CustomerTransfer.query.filter_by(to_customer_id=customer_id).all():
        if tr.transaction_type == 'payment':        # بردگی: بدهی مقصد کم می‌شود
            total -= (tr.amount or 0)
        else:                                            # رسیدگی: بدهی مقصد زیاد می‌شود
            total += (tr.amount or 0)

    for cp in CustomerPayment.query.filter_by(customer_id=customer_id).all():
        total += (cp.amount or 0) if cp.payment_type == 'payment' else -(cp.amount or 0)

    return -total


def customer_balance_as_of(customer_id, doc):
    """
    مانده حساب مشتری را دقیقاً تا لحظه‌ی یک سند مشخص (فاکتور فروش یا بار برگشتی) و فقط به همان
    واحدپولِ آن سند محاسبه می‌کند (نه مانده‌ی کلی امروز، و نه مخلوط با واحدپول‌های دیگر).
    این برای چاپ سند لازم است: اگر بعد از این سند، اسناد یا تراکنش‌های دیگری (حتی به ارز دیگر)
    برای همین مشتری ثبت شده باشند، نباید در «حساب قبلی/جاری» این سند اثر بگذارند — چون جمع‌زدنِ
    مبالغِ افغانی و دلاری با هم (بدون تبدیل) یک عدد بی‌معنی می‌سازد.
    تراکنش‌های با تاریخ بعد از تاریخ سند، حذف می‌شوند. برای فاکتورهای فروشِ هم‌تاریخ با این سند
    (وقتی خود سند هم یک فاکتور فروش است)، فقط آن‌هایی که شماره‌ی (id) کوچک‌تر یا مساوی دارند
    به‌حساب می‌آیند (ترتیب ثبت). همین قاعده برای بار برگشتی‌های هم‌تاریخ با یک بار برگشتی اعمال می‌شود.
    """
    as_of_date = doc.date
    doc_currency = getattr(doc, 'currency', None)
    doc_currency_id = _currency_code_to_id(doc_currency)
    is_invoice = isinstance(doc, SalesInvoice)
    is_return = isinstance(doc, CustomerReturn)
    total = 0.0

    for o in (CustomerOpening.query.filter_by(customer_id=customer_id)
              .filter(CustomerOpening.date <= as_of_date, CustomerOpening.currency == doc_currency).all()):
        if o.account_type == 'payable':
            total -= (o.amount or 0)
        else:
            total += (o.amount or 0)

    invoices = (SalesInvoice.query.filter_by(customer_id=customer_id)
                .filter(SalesInvoice.date <= as_of_date, SalesInvoice.currency == doc_currency).all())
    for inv in invoices:
        if is_invoice and inv.date == as_of_date and inv.id > doc.id:
            continue
        total += (inv.remaining or 0)

    for r in (CustomerReturn.query.filter_by(customer_id=customer_id)
              .filter(CustomerReturn.date <= as_of_date, CustomerReturn.currency == doc_currency).all()):
        if is_return and r.date == as_of_date and r.id > doc.id:
            continue
        total -= (r.total_amount or 0)

    for ct in (CashTransaction.query.filter_by(party_type='customer', party_id=customer_id, currency_id=doc_currency_id)
               .filter(CashTransaction.date <= as_of_date).all()):
        if ct.transaction_type == 'payment':
            total += (ct.amount or 0)
        else:
            total -= (ct.amount or 0)

    for tr in (CustomerTransfer.query.filter_by(from_customer_id=customer_id, currency_id=doc_currency_id)
               .filter(CustomerTransfer.date <= as_of_date).all()):
        if tr.transaction_type == 'payment':
            total += (tr.amount or 0)
        else:
            total -= (tr.amount or 0)

    for tr in (CustomerTransfer.query.filter_by(to_customer_id=customer_id, currency_id=doc_currency_id)
               .filter(CustomerTransfer.date <= as_of_date).all()):
        if tr.transaction_type == 'payment':
            total -= (tr.amount or 0)
        else:
            total += (tr.amount or 0)

    for cp in (CustomerPayment.query.filter_by(customer_id=customer_id, pay_currency_id=doc_currency_id)
               .filter(CustomerPayment.date <= as_of_date).all()):
        total += (cp.amount or 0) if cp.payment_type == 'payment' else -(cp.amount or 0)

    return -total


def employee_balance(employee_id):
    """
    مانده حساب کارمند — شامل معاش (کارت معاش/پرداخت معاش) و برد/رسید نقدی.
    قرارداد (هماهنگ با customer_balance/vendor_balance/borrower_balance): منفی = کارمند به ما
    بدهکار/قرضدار است، مثبت = شرکت به کارمند بدهکار است.
    برد (پرداخت به کارمند) → بدهی کارمند زیاد می‌شود (طلب کارمند کم می‌شود).
    رسید (دریافت از کارمند) → بدهی کارمند کم می‌شود.
    معاش ثبت‌شده (کارت معاش) → طلب کارمند زیاد می‌شود (بدهی شرکت به کارمند).
    پیش‌پرداخت معاش / پرداخت معاش → طلب کارمند کم می‌شود.
    """
    total = 0.0
    for sc in EmployeeSalaryCard.query.filter_by(employee_id=employee_id).all():
        total -= (sc.total_amount or 0)
        total += (sc.advance_payment or 0)

    for sp in EmployeeSalaryPayment.query.filter_by(employee_id=employee_id).all():
        total += (sp.amount or 0)

    for ct in CashTransaction.query.filter_by(party_type='employee', party_id=employee_id).all():
        if ct.transaction_type == 'payment':
            total += (ct.amount or 0)
        else:
            total -= (ct.amount or 0)

    for cp in CustomerPayment.query.filter_by(party_type='employee', employee_id=employee_id).all():
        total += (cp.amount or 0) if cp.payment_type == 'payment' else -(cp.amount or 0)

    return -total


def party_balance(party_type, party_id):
    """مانده حساب طرف را بر اساس نوع آن برمی‌گرداند (مشتری/فروشنده/کارمند/قرض‌گیرنده)."""
    if party_type == 'customer':
        return customer_balance(party_id)
    if party_type == 'vendor':
        return vendor_balance(party_id)
    if party_type == 'employee':
        return employee_balance(party_id)
    if party_type == 'borrower':
        return borrower_balance(party_id)
    return 0.0


# ==========================================
# مانده‌های تفکیکی بر اساس ارز (برای فرم‌هایی که چند ارز را هم‌زمان نگه می‌دارند)
# هر تابع یک دیکشنری {currency_id: amount} برمی‌گرداند.
# قرارداد علامت دقیقاً همان قرارداد توابع ساده بالا است.
#
# نکته فنی: جداول قدیمی‌تر (CustomerOpening/VendorOpening/SalesInvoice/PurchaseInvoice/VendorPayment)
# ارز را به‌صورت کد رشته‌ای (مثل "AFN") در ستون currency ذخیره می‌کنند، نه currency_id.
# تابع _currency_code_to_id این کد را به شناسه عددی نگاشت می‌کند تا با جداول جدیدتر یکپارچه شود.
# ==========================================
_currency_code_cache = {}


def _currency_code_to_id(code):
    """کد رشته‌ای ارز (مثل 'AFN') را به شناسه عددی Currency نگاشت می‌کند."""
    if not code:
        return None
    code = code.strip().upper()
    if code in _currency_code_cache:
        return _currency_code_cache[code]
    cur = Currency.query.filter_by(code=code).first()
    cid = cur.id if cur else None
    _currency_code_cache[code] = cid
    return cid


def customer_balance_by_currency(customer_id, exclude_exchange_id=None):
    totals = {}

    def add(currency_id, delta):
        if not currency_id:
            return
        totals[currency_id] = totals.get(currency_id, 0.0) + delta

    for o in CustomerOpening.query.filter_by(customer_id=customer_id).all():
        cid = _currency_code_to_id(o.currency)
        add(cid, -(o.amount or 0) if o.account_type == 'payable' else (o.amount or 0))

    for inv in SalesInvoice.query.filter_by(customer_id=customer_id).all():
        cid = _currency_code_to_id(getattr(inv, 'currency', None))
        add(cid, inv.remaining or 0)

    for r in CustomerReturn.query.filter_by(customer_id=customer_id).all():
        cid = _currency_code_to_id(getattr(r, 'currency', None))
        add(cid, -(r.total_amount or 0))

    for ct in CashTransaction.query.filter_by(party_type='customer', party_id=customer_id).all():
        delta = (ct.amount or 0) if ct.transaction_type == 'payment' else -(ct.amount or 0)
        add(ct.currency_id, delta)

    for tr in CustomerTransfer.query.filter_by(from_customer_id=customer_id).all():
        delta = (tr.amount or 0) if tr.transaction_type == 'payment' else -(tr.amount or 0)
        add(tr.currency_id, delta)

    for tr in CustomerTransfer.query.filter_by(to_customer_id=customer_id).all():
        delta = -(tr.amount or 0) if tr.transaction_type == 'payment' else (tr.amount or 0)
        add(tr.currency_id, delta)

    for cp in CustomerPayment.query.filter_by(customer_id=customer_id).all():
        # مانده طرف به ارز پرداختی (pay_currency) با مقدار پرداختی (amount) تسویه می‌شود
        delta = (cp.amount or 0) if cp.payment_type == 'payment' else -(cp.amount or 0)
        add(cp.pay_currency_id, delta)

    for ex in CustomerCurrencyExchange.query.filter_by(customer_id=customer_id).all():
        if exclude_exchange_id and ex.id == exclude_exchange_id:
            continue
        # sign جهت واقعی این تبادله را نشان می‌دهد (در لحظه ثبت تشخیص داده شده).
        # مانده ارز مبدا دقیقا به اندازه amount (با همین جهت) تسویه/کم می‌شود.
        # مانده ارز مقصد معادل آن (converted_amount، با همان جهت) شکل می‌گیرد/زیاد می‌شود.
        sign = ex.sign or 1
        add(ex.from_currency_id, -sign * (ex.amount or 0))
        add(ex.to_currency_id, sign * (ex.converted_amount or 0))

    # هماهنگی با customer_balance: علامت خروجی برای نمایش معکوس می‌شود
    # (منفی = مشتری بدهکار است). محاسبات داخلی بالا دست‌نخورده می‌ماند.
    return {cid: -v for cid, v in totals.items()}


# ==========================================
# قرض‌ها — محاسبه مانده حساب قرضه
# ==========================================
def borrower_balance(borrower_id):
    """
    مانده حساب یک قرضه (قرض‌دهنده/گیرنده) را برمی‌گرداند.
    قرارداد علامت (هماهنگ با vendor_balance):
    عدد مثبت یعنی ما به او بدهکاریم (payable)؛ منفی یعنی او به ما بدهکار است (طلب ما / receivable).
    """
    total = 0.0
    openings = BorrowerOpening.query.filter_by(borrower_id=borrower_id).all()
    for o in openings:
        if o.account_type == 'receivable':
            total -= (o.amount or 0)
        else:
            total += (o.amount or 0)

    for ct in CashTransaction.query.filter_by(party_type='borrower', party_id=borrower_id).all():
        if ct.transaction_type == 'payment':       # برد: ما به قرضه پرداختیم
            total -= (ct.amount or 0)
        else:                                          # رسید: قرضه به ما پرداخت
            total += (ct.amount or 0)

    for cp in CustomerPayment.query.filter_by(party_type='borrower', party_id=borrower_id).all():
        if cp.payment_type == 'payment':
            total -= (cp.amount or 0)
        else:
            total += (cp.amount or 0)

    return total


def borrower_balance_by_currency(borrower_id):
    """مانده تفکیکی-بر-اساس-ارز یک قرضه، هم‌قرارداد با borrower_balance."""
    totals = {}

    def add(currency_id, delta):
        if not currency_id:
            return
        totals[currency_id] = totals.get(currency_id, 0.0) + delta

    for o in BorrowerOpening.query.filter_by(borrower_id=borrower_id).all():
        cid = _currency_code_to_id(o.currency)
        add(cid, -(o.amount or 0) if o.account_type == 'receivable' else (o.amount or 0))

    for ct in CashTransaction.query.filter_by(party_type='borrower', party_id=borrower_id).all():
        delta = -(ct.amount or 0) if ct.transaction_type == 'payment' else (ct.amount or 0)
        add(ct.currency_id, delta)

    for cp in CustomerPayment.query.filter_by(party_type='borrower', party_id=borrower_id).all():
        delta = -(cp.amount or 0) if cp.payment_type == 'payment' else (cp.amount or 0)
        add(cp.pay_currency_id, delta)

    return totals


def vendor_balance_by_currency(vendor_id):
    totals = {}

    def add(currency_id, delta):
        if not currency_id:
            return
        totals[currency_id] = totals.get(currency_id, 0.0) + delta

    for o in VendorOpening.query.filter_by(vendor_id=vendor_id).all():
        cid = _currency_code_to_id(o.currency)
        add(cid, -(o.amount or 0) if o.account_type == 'receivable' else (o.amount or 0))

    for inv in PurchaseInvoice.query.filter_by(vendor_id=vendor_id).all():
        cid = _currency_code_to_id(getattr(inv, 'currency', None))
        add(cid, inv.remaining or 0)

    for r in VendorReturn.query.filter_by(vendor_id=vendor_id).all():
        cid = _currency_code_to_id(getattr(r, 'currency', None))
        add(cid, -(r.total_amount or 0))

    for p in VendorPayment.query.filter_by(vendor_id=vendor_id).all():
        cid = _currency_code_to_id(getattr(p, 'currency', None))
        add(cid, -(p.amount or 0))

    for ct in CashTransaction.query.filter_by(party_type='vendor', party_id=vendor_id).all():
        delta = -(ct.amount or 0) if ct.transaction_type == 'payment' else (ct.amount or 0)
        add(ct.currency_id, delta)

    for cp in CustomerPayment.query.filter_by(party_type='vendor', vendor_id=vendor_id).all():
        delta = (cp.amount or 0) if cp.payment_type == 'payment' else -(cp.amount or 0)
        add(cp.pay_currency_id, delta)

    return totals


def employee_balance_by_currency(employee_id):
    totals = {}

    def add(currency_id, delta):
        if not currency_id:
            return
        totals[currency_id] = totals.get(currency_id, 0.0) + delta

    for sc in EmployeeSalaryCard.query.filter_by(employee_id=employee_id).all():
        cid = _currency_code_to_id(sc.currency or 'AFN')
        add(cid, -(sc.total_amount or 0))
        add(cid, (sc.advance_payment or 0))

    for sp in EmployeeSalaryPayment.query.filter_by(employee_id=employee_id).all():
        add(_currency_code_to_id(sp.currency or 'AFN'), (sp.amount or 0))

    for ct in CashTransaction.query.filter_by(party_type='employee', party_id=employee_id).all():
        delta = (ct.amount or 0) if ct.transaction_type == 'payment' else -(ct.amount or 0)
        add(ct.currency_id, delta)

    for cp in CustomerPayment.query.filter_by(party_type='employee', employee_id=employee_id).all():
        delta = (cp.amount or 0) if cp.payment_type == 'payment' else -(cp.amount or 0)
        add(cp.pay_currency_id, delta)

    # هماهنگی با employee_balance: علامت خروجی برای نمایش معکوس می‌شود (منفی = کارمند بدهکار است)
    return {cid: -v for cid, v in totals.items()}


def party_balance_by_currency(party_type, party_id):
    """مانده تفکیکی-بر-اساس-ارز یک طرف را برمی‌گرداند: دیکشنری {currency_id: amount}."""
    if party_type == 'customer':
        return customer_balance_by_currency(party_id)
    if party_type == 'vendor':
        return vendor_balance_by_currency(party_id)
    if party_type == 'employee':
        return employee_balance_by_currency(party_id)
    if party_type == 'borrower':
        return borrower_balance_by_currency(party_id)
    return {}


def bank_balance_by_currency(bank_id):
    """موجودی یک بانک/صندوق را به تفکیک هر ارز برمی‌گرداند: دیکشنری {currency_id: amount}."""
    totals = {}
    for o in BankOpening.query.filter_by(bank_id=bank_id).all():
        delta = (o.amount or 0) if o.account_type != 'payable' else -(o.amount or 0)
        totals[o.currency_id] = totals.get(o.currency_id, 0.0) + delta
    return totals


def format_balance_by_currency(totals):
    """دیکشنری {currency_id: amount} را به یک ساختار قابل‌نمایش (لیست با کد ارز) تبدیل می‌کند."""
    result = []
    for currency_id, amount in totals.items():
        if abs(amount or 0) < 0.0001:
            continue
        cur = Currency.query.get(currency_id)
        result.append({
            'currency_id': currency_id,
            'code': cur.code if cur else '?',
            'amount': amount,
        })
    return result


def number_to_persian_words(n):
    """تبدیل یک عدد صحیح به حروف فارسی (مثلاً 230 -> دوصد و سی)."""
    n = int(round(n or 0))
    if n == 0:
        return 'صفر'

    ones = ['', 'یک', 'دو', 'سه', 'چهار', 'پنج', 'شش', 'هفت', 'هشت', 'نه']
    tens = ['', 'ده', 'بیست', 'سی', 'چهل', 'پنجاه', 'شصت', 'هفتاد', 'هشتاد', 'نود']
    teens = ['ده', 'یازده', 'دوازده', 'سیزده', 'چهارده', 'پانزده', 'شانزده', 'هفده', 'هجده', 'نوزده']
    hundreds = ['', 'یکصد', 'دوصد', 'سیصد', 'چهارصد', 'پانصد', 'ششصد', 'هفتصد', 'هشتصد', 'نهصد']
    scales = ['', 'هزار', 'میلیون', 'میلیارد']

    def three_digit(num):
        parts = []
        h, rem = divmod(num, 100)
        if h:
            parts.append(hundreds[h])
        if rem >= 10 and rem < 20:
            parts.append(teens[rem - 10])
        else:
            t, o = divmod(rem, 10)
            if t:
                parts.append(tens[t])
            if o:
                parts.append(ones[o])
        return ' و '.join(parts)

    if n < 0:
        return 'منفی ' + number_to_persian_words(-n)

    groups = []
    temp = n
    while temp > 0:
        groups.append(temp % 1000)
        temp //= 1000

    words = []
    for i in range(len(groups) - 1, -1, -1):
        if groups[i] == 0:
            continue
        part = three_digit(groups[i])
        if scales[i]:
            part += ' ' + scales[i]
        words.append(part)

    return ' و '.join(words)


def jalali_to_gregorian(jy, jm, jd):
    try:
        return jdatetime.date(int(jy), int(jm), int(jd)).togregorian()
    except Exception:
        return None


# ==========================================
# تابع مرکزی موجودی — تنها دروازه تغییر StockBalance
# ==========================================
def adjust_balance(item_name, stock_id, delta_qty, price=None, quantity_id=None):
    """
    موجودی یک کالا در یک گدام را تغییر می‌دهد.
    delta_qty مثبت = افزایش موجودی (افتتاحیه، ورود، انتقال‌ورودی، تولید محصول)
    delta_qty منفی = کاهش موجودی (خروج، انتقال‌خروجی، مصرف مواد در تولید)
    اگر رکورد (کالا, گدام) وجود نداشته باشد، می‌سازد.
    """
    if not item_name or not stock_id:
        return None
    balance = StockBalance.query.filter_by(item_name=item_name, stock_id=stock_id).first()
    if not balance:
        balance = StockBalance(item_name=item_name, stock_id=stock_id, current_qty=0)
        db.session.add(balance)
    balance.current_qty = (balance.current_qty or 0) + delta_qty
    if price is not None:
        balance.last_price = price
    if quantity_id is not None:
        balance.quantity_id = quantity_id
    return balance


def get_default_afn_rate():
    """آخرین نرخ ثبت‌شده افغانی در جدول نرخ ارز؛ در صورت نبود، نرخ پیش‌فرض ۶۵."""
    cr = (CurrencyRate.query.join(Currency, CurrencyRate.currency_id == Currency.id)
          .filter(Currency.code == 'AFN')
          .order_by(CurrencyRate.date.desc(), CurrencyRate.id.desc())
          .first())
    return (cr.rate if cr and cr.rate else 65)


def last_purchase_price_afn(item_name):
    """
    آخرین قیمت خرید یک جنس را برمی‌گرداند (به افغانی).
    منبع قیمت، جدیدترین رکورد بین «فاکتور خرید» و «موجودی افتتاحیه» همان جنس است
    (هرکدام تاریخ جدیدتری داشته باشد). اگر جنس فقط از طریق افتتاحیه وارد شده باشد
    (بدون فاکتور خرید)، همان قیمت افتتاحیه به افغانی محاسبه می‌شود.
    اگر هیچ‌کدام موجود نبود، به آخرین قیمت ثبت‌شده در موجودی گدام (به افغانی) برمی‌گردد.
    """
    if not item_name:
        return 0

    candidates = []  # (date, price_afn)

    line = (PurchaseInvoiceLine.query
            .join(PurchaseInvoice, PurchaseInvoiceLine.invoice_id == PurchaseInvoice.id)
            .filter(PurchaseInvoiceLine.item_name == item_name)
            .order_by(PurchaseInvoice.date.desc(), PurchaseInvoiceLine.id.desc())
            .first())
    if line:
        inv = line.invoice
        price = line.price or 0
        if inv and inv.currency == 'USD':
            price = price * (inv.exchange_rate or get_default_afn_rate())
        candidates.append((inv.date if inv else None, price))

    ob = (OpeningBalance.query
          .filter(OpeningBalance.name == item_name)
          .order_by(OpeningBalance.date.desc(), OpeningBalance.id.desc())
          .first())
    if ob and (ob.opening_qty or 0):
        unit_price = ob.total_price / ob.opening_qty if ob.currency == 'AFN' else \
                     (ob.total_price_usd / ob.opening_qty) * get_default_afn_rate()
        candidates.append((ob.date, unit_price))

    candidates = [c for c in candidates if c[0] is not None]
    if candidates:
        candidates.sort(key=lambda c: c[0])
        return candidates[-1][1]

    # جنس نه در فاکتور خرید و نه در افتتاحیه سابقه دارد؛ آخرین قیمت موجودی گدام (دالر) را به افغانی تبدیل کن
    balance = StockBalance.query.filter_by(item_name=item_name).first()
    if balance and balance.last_price:
        return balance.last_price * get_default_afn_rate()

    return 0


def sales_line_stock_qty(row_or_line):
    """
    مقداری که باید از موجودی گدام کم/اضافه شود برای یک ردیف فاکتور فروش.
    اگر «تعداد» عدد داده شده باشد (مثلاً تعداد کارتن)، همان تعداد از گدام کم می‌شود
    (چون گدام بر اساس تعداد واحد/کارتن حساب می‌شود، نه وزن).
    اگر «تعداد» خالی باشد، همان مقدار وزن از گدام کم می‌شود (حالت ساده).
    row_or_line می‌تواند dict یا شیء SalesInvoiceLine باشد.
    """
    if isinstance(row_or_line, dict):
        count_desc = row_or_line.get('count_desc')
        amount = row_or_line.get('amount') or 0
    else:
        count_desc = getattr(row_or_line, 'count_desc', None)
        amount = getattr(row_or_line, 'amount', None) or 0
    try:
        count_num = float(count_desc) if count_desc else None
    except (ValueError, TypeError):
        count_num = None
    return count_num if count_num else amount


def adjust_reservation(item_name, stock_id, delta_qty, quantity_id=None):
    """
    مقدار رزروشده (تخصیص‌یافته به سفارش) یک کالا در یک گدام را تغییر می‌دهد.
    delta_qty مثبت = افزایش رزرو (ثبت سفارش جدید)
    delta_qty منفی = کاهش رزرو (لغو سفارش، یا تبدیل سفارش به فاکتور فروش نهایی)
    موجودی فیزیکی (current_qty) را تغییر نمی‌دهد — فقط جدا نگه می‌دارد.
    """
    if not item_name or not stock_id:
        return None
    balance = StockBalance.query.filter_by(item_name=item_name, stock_id=stock_id).first()
    if not balance:
        balance = StockBalance(item_name=item_name, stock_id=stock_id, current_qty=0, reserved_qty=0)
        db.session.add(balance)
    balance.reserved_qty = (balance.reserved_qty or 0) + delta_qty
    if balance.reserved_qty < 0:
        balance.reserved_qty = 0
    if quantity_id is not None:
        balance.quantity_id = quantity_id
    return balance


def get_stock_info(item_name, stock_id=None):
    """آخرین موجودی/قیمت/واحد یک کالا را برمی‌گرداند (برای پر کردن خودکار فرم‌ها)."""
    query = StockBalance.query.filter_by(item_name=item_name)
    if stock_id:
        query = query.filter_by(stock_id=stock_id)
    return query.order_by(StockBalance.updated_at.desc()).first()


@main.route('/warehouse/opening', methods=['GET', 'POST'])
def opening_balance():
    edit_id = request.args.get('edit', type=int)
    edit_ob = OpeningBalance.query.get(edit_id) if edit_id else None

    if request.method == 'POST':
        jy = request.form.get('j_year', type=int)
        jm = request.form.get('j_month', type=int)
        jd = request.form.get('j_day', type=int)
        g_date = jalali_to_gregorian(jy, jm, jd)

        category_id = request.form.get('category_id', type=int)
        name = request.form.get('name', '').strip()
        opening_qty = request.form.get('opening_qty', type=float) or 0
        total_price = request.form.get('total_price', type=float) or 0
        currency = request.form.get('currency', '').strip()
        currency_rate = request.form.get('currency_rate', type=float) or 1
        quantity_id = request.form.get('quantity_id', type=int)
        stock_id = request.form.get('stock_id', type=int)
        ob_id = request.form.get('ob_id', type=int)

        # ارز پایه = دالر. تبدیل قیمت کل به دالر طبق نرخ روز.
        if currency == 'USD' or not currency:
            total_price_usd = total_price
        else:
            # currency_rate = نرخ روز: ۱ دالر = ؟ واحد پولی انتخابی (مثلاً ۱ دالر = ۷۲ افغانی)
            total_price_usd = (total_price / currency_rate) if currency_rate else 0

        if not name or not g_date:
            flash('نام جنس و تاریخ الزامی است', 'danger')
        elif ob_id:
            ob = OpeningBalance.query.get_or_404(ob_id)
            # برگرداندن اثر قبلی این رکورد از موجودی قبل از اعمال مقدار جدید
            adjust_balance(ob.name, ob.stock_id, -(ob.opening_qty or 0))
            ob.date, ob.j_year, ob.j_month, ob.j_day = g_date, jy, jm, jd
            ob.category_id, ob.name = category_id, name
            ob.opening_qty, ob.total_price = opening_qty, total_price
            ob.total_price_usd = total_price_usd
            ob.currency, ob.currency_rate = currency, currency_rate
            ob.quantity_id, ob.stock_id = quantity_id, stock_id
            unit_cost = (total_price_usd / opening_qty) if opening_qty else 0
            adjust_balance(name, stock_id, opening_qty, price=unit_cost, quantity_id=quantity_id)
            db.session.commit()
            flash('حساب افتتاحیه ویرایش شد', 'success')
        else:
            db.session.add(OpeningBalance(
                date=g_date, j_year=jy, j_month=jm, j_day=jd,
                category_id=category_id, name=name,
                opening_qty=opening_qty, total_price=total_price,
                total_price_usd=total_price_usd,
                currency=currency, currency_rate=currency_rate,
                quantity_id=quantity_id, stock_id=stock_id
            ))
            unit_cost = (total_price_usd / opening_qty) if opening_qty else 0
            adjust_balance(name, stock_id, opening_qty, price=unit_cost, quantity_id=quantity_id)
            db.session.commit()
            flash('حساب افتتاحیه ثبت شد', 'success')
        return redirect(url_for('main.opening_balance'))

    records = OpeningBalance.query.order_by(OpeningBalance.id).all()
    categories = Category.query.order_by(Category.name).all()
    units = Quantity.query.order_by(Quantity.quantity).all()
    stocks = Stock.query.order_by(Stock.name).all()
    items = Item.query.filter_by(is_active=True).order_by(Item.name).all()
    today = jdatetime.date.today()

    return render_template('warehouse/opening_balance.html',
        records=records, edit_ob=edit_ob,
        categories=categories, units=units, stocks=stocks, items=items, today=today)


@main.route('/warehouse/opening/item-info/<int:item_id>')
def opening_balance_item_info(item_id):
    """کتگوری و واحد اندازه‌گیری یک جنس ثبت‌شده را برمی‌گرداند (برای پر کردن خودکار فرم حساب افتتاحیه)."""
    from flask import jsonify
    item = Item.query.get(item_id)
    if not item:
        return jsonify({'found': False})
    return jsonify({
        'found': True,
        'name': item.name,
        'category_id': item.category_id or '',
        'quantity_id': item.quantity_id or ''
    })


# ==========================================
# گدام — انتقال بین گدام‌ها
# ==========================================
@main.route('/warehouse/transfer', methods=['GET', 'POST'])
def stock_transfer():
    edit_id = request.args.get('edit', type=int)
    edit_t = StockTransfer.query.get(edit_id) if edit_id else None

    if request.method == 'POST':
        jy = request.form.get('j_year', type=int)
        jm = request.form.get('j_month', type=int)
        jd = request.form.get('j_day', type=int)
        g_date = jalali_to_gregorian(jy, jm, jd)

        item_name = request.form.get('item_name', '').strip()
        source_stock_id = request.form.get('source_stock_id', type=int)
        destination_stock_id = request.form.get('destination_stock_id', type=int)
        current_qty = request.form.get('current_qty', type=float) or 0
        amount = request.form.get('amount', type=float) or 0
        count = request.form.get('count', type=float) or 0
        driver_name = request.form.get('driver_name', '').strip()
        plate_no = request.form.get('plate_no', '').strip()
        driver_phone = request.form.get('driver_phone', '').strip()
        commission = request.form.get('commission', type=float) or 0
        advance_fare = request.form.get('advance_fare', type=float) or 0
        fare_per_ton = request.form.get('fare_per_ton', type=float) or 0
        notes = request.form.get('notes', '').strip()
        t_id = request.form.get('t_id', type=int)

        if not item_name or not g_date:
            flash('نام جنس و تاریخ الزامی است', 'danger')
        else:
            data = dict(
                date=g_date, j_year=jy, j_month=jm, j_day=jd,
                item_name=item_name,
                source_stock_id=source_stock_id, destination_stock_id=destination_stock_id,
                current_qty=current_qty, amount=amount, count=count,
                driver_name=driver_name, plate_no=plate_no, driver_phone=driver_phone,
                commission=commission, advance_fare=advance_fare, fare_per_ton=fare_per_ton,
                notes=notes
            )
            if t_id:
                t = StockTransfer.query.get_or_404(t_id)
                # برگرداندن اثر انتقال قبلی قبل از اعمال مقدار جدید
                adjust_balance(t.item_name, t.source_stock_id, t.amount or 0)
                adjust_balance(t.item_name, t.destination_stock_id, -(t.amount or 0))
                for k, v in data.items():
                    setattr(t, k, v)
                adjust_balance(item_name, source_stock_id, -amount)
                adjust_balance(item_name, destination_stock_id, amount)
                db.session.commit()
                flash('انتقال ویرایش شد', 'success')
            else:
                db.session.add(StockTransfer(**data))
                # کم از گدام مبدا، زیاد در گدام مقصد
                adjust_balance(item_name, source_stock_id, -amount)
                adjust_balance(item_name, destination_stock_id, amount)
                db.session.commit()
                flash('انتقال ثبت شد', 'success')
        return redirect(url_for('main.stock_transfer'))

    records = StockTransfer.query.order_by(StockTransfer.id).all()
    stocks = Stock.query.order_by(Stock.name).all()
    items = Item.query.filter_by(is_active=True).order_by(Item.name).all()
    today = jdatetime.date.today()

    return render_template('warehouse/stock_transfer.html',
        records=records, edit_t=edit_t, stocks=stocks, items=items, today=today)


@main.route('/warehouse/transfer/balance-info')
def transfer_balance_info():
    """موجودی واقعی یک جنس را در یک گدام مشخص برمی‌گرداند (برای پر شدن خودکار فرم انتقال)."""
    from flask import jsonify
    item_name = request.args.get('item_name', '').strip()
    stock_id = request.args.get('stock_id', type=int)

    if not item_name or not stock_id:
        return jsonify({'found': False})

    bal = StockBalance.query.filter_by(item_name=item_name, stock_id=stock_id).first()
    if not bal:
        return jsonify({'found': True, 'current_qty': 0})

    return jsonify({'found': True, 'current_qty': bal.current_qty or 0})


@main.route('/warehouse/transfer/delete/<int:id>')
def stock_transfer_delete(id):
    t = StockTransfer.query.get_or_404(id)
    adjust_balance(t.item_name, t.source_stock_id, t.amount or 0)
    adjust_balance(t.item_name, t.destination_stock_id, -(t.amount or 0))
    db.session.delete(t)
    db.session.commit()
    flash('رکورد حذف شد', 'success')
    return redirect(url_for('main.stock_transfer'))


# ==========================================
# گدام — چاپ سند انتقال بین گدام‌ها
# ==========================================
@main.route('/warehouse/transfer/print/<int:id>')
def stock_transfer_print(id):
    t = StockTransfer.query.get_or_404(id)
    return render_template('warehouse/stock_transfer_print.html', t=t)


# ==========================================
# گدام — جزئیات انتقال بین گدام‌ها (راپور)
# ==========================================
@main.route('/reports/stock-transfer-details', methods=['GET'])
@report_category_required('warehouse')
def stock_transfer_details_report():
    """
    جزئیات انتقال بین گدامها: کاربر بازه تاریخ (شمسی)، گدام مبدا، گدام مقصد و نام کالا
    را انتخاب می‌کند، سپس لیست تمام انتقال‌های بین گدامی (StockTransfer) در آن بازه
    نمایش داده می‌شود، همراه با مجموع وزن و تعداد.
    """
    today = jdatetime.date.today()

    from_jy = request.args.get('from_year', type=int) or today.year
    from_jm = request.args.get('from_month', type=int) or today.month
    from_jd = request.args.get('from_day', type=int) or today.day
    to_jy = request.args.get('to_year', type=int) or today.year
    to_jm = request.args.get('to_month', type=int) or today.month
    to_jd = request.args.get('to_day', type=int) or today.day
    source_stock_id = request.args.get('source_stock_id', type=int)
    destination_stock_id = request.args.get('destination_stock_id', type=int)
    item_id = request.args.get('item_id', type=int)
    searched = request.args.get('searched') == '1'

    start_date = jalali_to_gregorian(from_jy, from_jm, from_jd)
    end_date = jalali_to_gregorian(to_jy, to_jm, to_jd)

    stock_list = Stock.query.order_by(Stock.name).all()
    item_list = Item.query.filter_by(is_active=True).order_by(Item.name).all()
    selected_item = Item.query.get(item_id) if item_id else None

    records = []
    total_weight = 0.0
    total_count = 0.0

    if searched:
        query = StockTransfer.query
        if start_date:
            query = query.filter(StockTransfer.date >= start_date)
        if end_date:
            query = query.filter(StockTransfer.date <= end_date)
        if source_stock_id:
            query = query.filter(StockTransfer.source_stock_id == source_stock_id)
        if destination_stock_id:
            query = query.filter(StockTransfer.destination_stock_id == destination_stock_id)
        if selected_item:
            query = query.filter(StockTransfer.item_name == selected_item.name)
        records = query.order_by(StockTransfer.date, StockTransfer.id).all()
        total_weight = sum(r.amount or 0 for r in records)
        total_count = sum(r.count or 0 for r in records)

    return render_template('reports/stock_transfer_details.html',
        today=today, stock_list=stock_list, item_list=item_list,
        selected_source_id=source_stock_id, selected_destination_id=destination_stock_id,
        selected_item_id=item_id,
        records=records, total_weight=total_weight, total_count=total_count, searched=searched,
        from_year=from_jy, from_month=from_jm, from_day=from_jd,
        to_year=to_jy, to_month=to_jm, to_day=to_jd,
        back_url=url_for('main.report_page', slug='warehouse'))


@main.route('/reports/stock-transfer-details/save-checked', methods=['POST'])
def stock_transfer_details_save_checked():
    """چک‌باکس‌های «چک شد» صفحه جزئیات انتقال را ذخیره می‌کند و به همان جستجو برمی‌گردد."""
    checked_ids = set(request.form.getlist('checked_ids', type=int))
    all_ids = set(request.form.getlist('all_ids', type=int))

    for tid in all_ids:
        t = StockTransfer.query.get(tid)
        if t:
            t.checked = tid in checked_ids
    db.session.commit()
    flash('وضعیت چک شد ذخیره شد', 'success')

    query_string = request.form.get('query_string', '')
    return redirect(url_for('main.stock_transfer_details_report') + ('?' + query_string if query_string else ''))


# ==========================================
# گدام — بخش ترکیب اجناس (تولید/BOM)
# ==========================================
@main.route('/warehouse/production', methods=['GET', 'POST'])
def production():
    edit_id = request.args.get('edit', type=int)
    edit_p = Production.query.get(edit_id) if edit_id else None

    if request.method == 'POST':
        jy = request.form.get('j_year', type=int)
        jm = request.form.get('j_month', type=int)
        jd = request.form.get('j_day', type=int)
        g_date = jalali_to_gregorian(jy, jm, jd)

        item_id = request.form.get('item_id', type=int)
        produced_item = Item.query.get(item_id) if item_id else None
        item_name = produced_item.name if produced_item else ''

        amount = request.form.get('amount', type=float) or 0
        quantity_id = request.form.get('quantity_id', type=int)
        stock_id = request.form.get('stock_id', type=int)
        notes = request.form.get('notes', '').strip()
        p_id = request.form.get('p_id', type=int)

        # ردیف‌های مواد اولیه (تا ۲۰ ردیف)
        rows = []
        total_price = 0
        # تعداد ردیف‌ها نامحدود است؛ هر row_item_N که در فرم ارسال شده بخوان
        row_indexes = set()
        for key in request.form.keys():
            if key.startswith('row_item_'):
                row_indexes.add(int(key.replace('row_item_', '')))

        for i in sorted(row_indexes):
            row_item_id = request.form.get(f'row_item_{i}', type=int)
            if not row_item_id:
                continue
            row_item_obj = Item.query.get(row_item_id)
            row_stock_id = request.form.get(f'row_stock_{i}', type=int)
            row_quantity_id = request.form.get(f'row_quantity_{i}', type=int)
            row_available = request.form.get(f'row_available_{i}', type=float) or 0
            row_amount = request.form.get(f'row_amount_{i}', type=float) or 0
            row_price = request.form.get(f'row_price_{i}', type=float) or 0
            row_total = row_amount * row_price
            total_price += row_total
            rows.append(dict(
                item_name=row_item_obj.name if row_item_obj else '',
                stock_id=row_stock_id, quantity_id=row_quantity_id,
                available_qty=row_available, amount=row_amount, price=row_price,
                total=row_total, row_no=i
            ))

        # قیمت فی واحد تولیدی = مجموع قیمت مواد ÷ مقدار محصول تولیدشده (محاسبه خودکار، نه از فرم)
        unit_price = (total_price / amount) if amount else 0

        if not item_name or not g_date:
            flash('کالا و تاریخ الزامی است', 'danger')
        else:
            if p_id:
                p = Production.query.get_or_404(p_id)
                # برگرداندن اثر تولید قبلی: زیاد کردن مواد قبلی، کم کردن محصول قبلی
                for old_line in p.lines:
                    adjust_balance(old_line.item_name, old_line.stock_id, old_line.amount or 0)
                adjust_balance(p.item_name, p.stock_id, -(p.amount or 0))

                p.item_name = item_name
                p.amount, p.quantity_id, p.stock_id = amount, quantity_id, stock_id
                p.date, p.j_year, p.j_month, p.j_day = g_date, jy, jm, jd
                p.unit_price, p.total_price, p.notes = unit_price, total_price, notes
                ProductionLine.query.filter_by(production_id=p.id).delete()
                for r in rows:
                    db.session.add(ProductionLine(production_id=p.id, **r))
                    # کم کردن ماده اولیه از گدامش
                    adjust_balance(r['item_name'], r['stock_id'], -(r['amount'] or 0))
                # افزایش محصول تولیدشده در گدام مقصد
                adjust_balance(item_name, stock_id, amount, price=unit_price, quantity_id=quantity_id)
                db.session.commit()
                flash('تولید ویرایش شد', 'success')
            else:
                # شماره خط تولید خودکار و شمارشی
                last = Production.query.order_by(Production.id.desc()).first()
                next_line_no = (int(last.production_line) + 1) if (last and last.production_line and last.production_line.isdigit()) else 1

                p = Production(
                    item_name=item_name, production_line=str(next_line_no),
                    amount=amount, quantity_id=quantity_id, stock_id=stock_id,
                    date=g_date, j_year=jy, j_month=jm, j_day=jd,
                    unit_price=unit_price, total_price=total_price, notes=notes
                )
                db.session.add(p)
                db.session.flush()
                for r in rows:
                    db.session.add(ProductionLine(production_id=p.id, **r))
                    # کم کردن ماده اولیه مصرفی از موجودی گدامش
                    adjust_balance(r['item_name'], r['stock_id'], -(r['amount'] or 0))
                # افزایش محصول تولیدشده در گدام مقصد
                adjust_balance(item_name, stock_id, amount, price=unit_price, quantity_id=quantity_id)
                db.session.commit()
                flash('تولید ثبت شد', 'success')
        return redirect(url_for('main.production'))

    records = Production.query.order_by(Production.id).all()
    stocks = Stock.query.order_by(Stock.name).all()
    units = Quantity.query.order_by(Quantity.quantity).all()
    items = Item.query.filter_by(is_active=True).order_by(Item.name).all()
    today = jdatetime.date.today()

    edit_lines = {}
    if edit_p:
        for l in edit_p.lines:
            edit_lines[l.row_no] = l

    return render_template('warehouse/production.html',
        records=records, edit_p=edit_p, edit_lines=edit_lines,
        stocks=stocks, units=units, items=items, today=today)


@main.route('/warehouse/production/item-info/<int:item_id>')
def production_item_info(item_id):
    """برمی‌گرداند موجودی واقعی، گدام، واحد و آخرین قیمت یک جنس از StockBalance (JSON)."""
    from flask import jsonify
    item = Item.query.get(item_id)
    if not item:
        return jsonify({'found': False})

    # اگر کالا در چند گدام موجودی دارد، رکوردی با بیشترین موجودی را پیشنهاد بده
    record = (StockBalance.query
              .filter_by(item_name=item.name)
              .order_by(StockBalance.current_qty.desc())
              .first())
    if not record:
        return jsonify({'found': False})

    # قیمت بر اساس آخرین خرید همین جنس محاسبه می‌شود (به افغانی)، نه آخرین قیمت ثبت‌شده در موجودی
    return jsonify({
        'found': True,
        'stock_id': record.stock_id or '',
        'quantity_id': record.quantity_id or '',
        'available_qty': record.current_qty or 0,
        'price': round(last_purchase_price_afn(item.name), 2)
    })


@main.route('/warehouse/stock-balance-info')
def stock_balance_info():
    """
    برمی‌گرداند موجودی واقعی یک جنس در یک گدام مشخص (برای انتقال بین گدام‌ها).
    پارامترهای querystring: item_name, stock_id
    """
    from flask import jsonify
    item_name = request.args.get('item_name', '').strip()
    stock_id = request.args.get('stock_id', type=int)

    if not item_name or not stock_id:
        return jsonify({'found': False})

    record = StockBalance.query.filter_by(item_name=item_name, stock_id=stock_id).first()
    if not record:
        return jsonify({'found': True, 'available_qty': 0})

    return jsonify({
        'found': True,
        'available_qty': record.current_qty or 0
    })


@main.route('/warehouse/production/delete/<int:id>')
def production_delete(id):
    p = Production.query.get_or_404(id)
    # برگرداندن اثر تولید از موجودی: زیاد کردن مواد، کم کردن محصول
    for line in p.lines:
        adjust_balance(line.item_name, line.stock_id, line.amount or 0)
    adjust_balance(p.item_name, p.stock_id, -(p.amount or 0))
    db.session.delete(p)
    db.session.commit()
    flash('رکورد حذف شد', 'success')
    return redirect(url_for('main.production'))


@main.route('/reports/production', methods=['GET'])
@report_category_required('warehouse')
def production_report():
    """
    راپور تولیدی: کاربر یک خط تولید (یک رکورد Production) را از لیست انتخاب می‌کند
    و گزارش کامل آن (مشخصات محصول تولیدشده + جدول تمام مواد اولیه مصرف‌شده) نمایش داده می‌شود.
    """
    production_list = Production.query.order_by(Production.id.desc()).all()

    production_id = request.args.get('production_id', type=int)
    searched = request.args.get('searched') == '1'

    selected = Production.query.get(production_id) if production_id else None
    lines = []
    if selected:
        lines = (ProductionLine.query
                 .filter_by(production_id=selected.id)
                 .order_by(ProductionLine.row_no).all())

    return render_template('reports/production_report.html',
        production_list=production_list, production_id=production_id,
        selected=selected, lines=lines, searched=searched,
        back_url=url_for('main.report_page', slug='warehouse'))


# ==========================================
# گدام — کم شدن از گدام
# ==========================================
@main.route('/warehouse/stock-out', methods=['GET', 'POST'])
def stock_out():
    edit_id = request.args.get('edit', type=int)
    edit_so = StockOut.query.get(edit_id) if edit_id else None

    if request.method == 'POST':
        jy = request.form.get('j_year', type=int)
        jm = request.form.get('j_month', type=int)
        jd = request.form.get('j_day', type=int)
        g_date = jalali_to_gregorian(jy, jm, jd)

        category_id = request.form.get('category_id', type=int)
        item_name = request.form.get('item_name', '').strip()
        amount = request.form.get('amount', type=float) or 0
        stock_id = request.form.get('stock_id', type=int)
        notes = request.form.get('notes', '').strip()
        so_id = request.form.get('so_id', type=int)

        if not item_name or not g_date or not stock_id:
            flash('نام جنس، گدام و تاریخ الزامی است', 'danger')
        else:
            if so_id:
                so = StockOut.query.get_or_404(so_id)
                # برگرداندن اثر قبلی این کاهش از موجودی
                adjust_balance(so.item_name, so.stock_id, so.amount or 0)
                so.date, so.j_year, so.j_month, so.j_day = g_date, jy, jm, jd
                so.category_id, so.item_name = category_id, item_name
                so.amount, so.stock_id, so.notes = amount, stock_id, notes
                bal = adjust_balance(item_name, stock_id, -amount)
                so.balance_after = bal.current_qty
                db.session.commit()
                flash('رکورد ویرایش شد', 'success')
            else:
                bal = adjust_balance(item_name, stock_id, -amount)
                db.session.add(StockOut(
                    date=g_date, j_year=jy, j_month=jm, j_day=jd,
                    category_id=category_id, item_name=item_name,
                    amount=amount, stock_id=stock_id, notes=notes,
                    balance_after=bal.current_qty
                ))
                db.session.commit()
                flash('کاهش از گدام ثبت شد', 'success')
        return redirect(url_for('main.stock_out'))

    records = StockOut.query.order_by(StockOut.id).all()
    categories = Category.query.order_by(Category.name).all()
    stocks = Stock.query.order_by(Stock.name).all()
    items = Item.query.filter_by(is_active=True).order_by(Item.name).all()
    today = jdatetime.date.today()

    return render_template('warehouse/stock_out.html',
        records=records, edit_so=edit_so, categories=categories, stocks=stocks, items=items, today=today)


@main.route('/reports/stock-out', methods=['GET'])
@report_category_required('warehouse')
def stock_out_report():
    """
    کاهش از گدام: کاربر بازه تاریخ (شمسی)، کتگوری و نام جنس را انتخاب می‌کند، سپس
    لیست تمام اجناسی که از گدام کم شده‌اند (StockOut) در آن بازه نمایش داده می‌شود.
    """
    today = jdatetime.date.today()

    from_jy = request.args.get('from_year', type=int) or today.year
    from_jm = request.args.get('from_month', type=int) or today.month
    from_jd = request.args.get('from_day', type=int) or today.day
    to_jy = request.args.get('to_year', type=int) or today.year
    to_jm = request.args.get('to_month', type=int) or today.month
    to_jd = request.args.get('to_day', type=int) or today.day
    category_id = request.args.get('category_id', type=int)
    item_id = request.args.get('item_id', type=int)
    searched = request.args.get('searched') == '1'

    start_date = jalali_to_gregorian(from_jy, from_jm, from_jd)
    end_date = jalali_to_gregorian(to_jy, to_jm, to_jd)

    category_list = Category.query.order_by(Category.name).all()
    item_list = Item.query.filter_by(is_active=True).order_by(Item.name).all()
    selected_category = Category.query.get(category_id) if category_id else None
    selected_item = Item.query.get(item_id) if item_id else None

    records = []
    total_qty = 0.0

    if searched:
        query = StockOut.query
        if start_date:
            query = query.filter(StockOut.date >= start_date)
        if end_date:
            query = query.filter(StockOut.date <= end_date)
        if selected_category:
            query = query.filter(StockOut.category_id == selected_category.id)
        if selected_item:
            query = query.filter(StockOut.item_name == selected_item.name)
        records = query.order_by(StockOut.date, StockOut.id).all()
        total_qty = sum(r.amount or 0 for r in records)

    return render_template('reports/stock_out_report.html',
        today=today, category_list=category_list, item_list=item_list,
        selected_category_id=category_id, selected_item_id=item_id,
        records=records, total_qty=total_qty, searched=searched,
        from_year=from_jy, from_month=from_jm, from_day=from_jd,
        to_year=to_jy, to_month=to_jm, to_day=to_jd,
        back_url=url_for('main.report_page', slug='warehouse'))


@main.route('/warehouse/stock-out/delete/<int:id>')
def stock_out_delete(id):
    so = StockOut.query.get_or_404(id)
    adjust_balance(so.item_name, so.stock_id, so.amount or 0)  # برگرداندن موجودی
    db.session.delete(so)
    db.session.commit()
    flash('رکورد حذف شد', 'success')
    return redirect(url_for('main.stock_out'))


# ==========================================
# گدام — افزایش به گدام
# ==========================================
@main.route('/warehouse/stock-in', methods=['GET', 'POST'])
def stock_in():
    edit_id = request.args.get('edit', type=int)
    edit_si = StockIn.query.get(edit_id) if edit_id else None

    if request.method == 'POST':
        jy = request.form.get('j_year', type=int)
        jm = request.form.get('j_month', type=int)
        jd = request.form.get('j_day', type=int)
        g_date = jalali_to_gregorian(jy, jm, jd)

        category_id = request.form.get('category_id', type=int)
        item_name = request.form.get('item_name', '').strip()
        amount = request.form.get('amount', type=float) or 0
        stock_id = request.form.get('stock_id', type=int)
        notes = request.form.get('notes', '').strip()
        si_id = request.form.get('si_id', type=int)

        if not item_name or not g_date or not stock_id:
            flash('نام جنس، گدام و تاریخ الزامی است', 'danger')
        else:
            if si_id:
                si = StockIn.query.get_or_404(si_id)
                # برگرداندن اثر قبلی این افزایش از موجودی
                adjust_balance(si.item_name, si.stock_id, -(si.amount or 0))
                si.date, si.j_year, si.j_month, si.j_day = g_date, jy, jm, jd
                si.category_id, si.item_name = category_id, item_name
                si.amount, si.stock_id, si.notes = amount, stock_id, notes
                bal = adjust_balance(item_name, stock_id, amount)
                si.balance_after = bal.current_qty
                db.session.commit()
                flash('رکورد ویرایش شد', 'success')
            else:
                bal = adjust_balance(item_name, stock_id, amount)
                db.session.add(StockIn(
                    date=g_date, j_year=jy, j_month=jm, j_day=jd,
                    category_id=category_id, item_name=item_name,
                    amount=amount, stock_id=stock_id, notes=notes,
                    balance_after=bal.current_qty
                ))
                db.session.commit()
                flash('افزایش به گدام ثبت شد', 'success')
        return redirect(url_for('main.stock_in'))

    records = StockIn.query.order_by(StockIn.id).all()
    categories = Category.query.order_by(Category.name).all()
    stocks = Stock.query.order_by(Stock.name).all()
    items = Item.query.filter_by(is_active=True).order_by(Item.name).all()
    today = jdatetime.date.today()

    return render_template('warehouse/stock_in.html',
        records=records, edit_si=edit_si, categories=categories, stocks=stocks, items=items, today=today)


@main.route('/reports/stock-in', methods=['GET'])
@report_category_required('warehouse')
def stock_in_report():
    """
    افزایش به گدام: کاربر بازه تاریخ (شمسی)، کتگوری و نام جنس را انتخاب می‌کند، سپس
    لیست تمام اجناسی که به گدام اضافه شده‌اند (StockIn) در آن بازه نمایش داده می‌شود.
    """
    today = jdatetime.date.today()

    from_jy = request.args.get('from_year', type=int) or today.year
    from_jm = request.args.get('from_month', type=int) or today.month
    from_jd = request.args.get('from_day', type=int) or today.day
    to_jy = request.args.get('to_year', type=int) or today.year
    to_jm = request.args.get('to_month', type=int) or today.month
    to_jd = request.args.get('to_day', type=int) or today.day
    category_id = request.args.get('category_id', type=int)
    item_id = request.args.get('item_id', type=int)
    searched = request.args.get('searched') == '1'

    start_date = jalali_to_gregorian(from_jy, from_jm, from_jd)
    end_date = jalali_to_gregorian(to_jy, to_jm, to_jd)

    category_list = Category.query.order_by(Category.name).all()
    item_list = Item.query.filter_by(is_active=True).order_by(Item.name).all()
    selected_category = Category.query.get(category_id) if category_id else None
    selected_item = Item.query.get(item_id) if item_id else None

    records = []
    total_qty = 0.0

    if searched:
        query = StockIn.query
        if start_date:
            query = query.filter(StockIn.date >= start_date)
        if end_date:
            query = query.filter(StockIn.date <= end_date)
        if selected_category:
            query = query.filter(StockIn.category_id == selected_category.id)
        if selected_item:
            query = query.filter(StockIn.item_name == selected_item.name)
        records = query.order_by(StockIn.date, StockIn.id).all()
        total_qty = sum(r.amount or 0 for r in records)

    return render_template('reports/stock_in_report.html',
        today=today, category_list=category_list, item_list=item_list,
        selected_category_id=category_id, selected_item_id=item_id,
        records=records, total_qty=total_qty, searched=searched,
        from_year=from_jy, from_month=from_jm, from_day=from_jd,
        to_year=to_jy, to_month=to_jm, to_day=to_jd,
        back_url=url_for('main.report_page', slug='warehouse'))


@main.route('/reports/opening-balance', methods=['GET'])
@report_category_required('warehouse')
def opening_balance_report():
    """
    موجودی اولیه: کاربر بازه تاریخ (شمسی)، کتگوری و نام جنس را انتخاب می‌کند، سپس
    لیست تمام رکوردهای موجودی اولیه (OpeningBalance) در آن بازه نمایش داده می‌شود.
    """
    today = jdatetime.date.today()

    from_jy = request.args.get('from_year', type=int) or today.year
    from_jm = request.args.get('from_month', type=int) or today.month
    from_jd = request.args.get('from_day', type=int) or today.day
    to_jy = request.args.get('to_year', type=int) or today.year
    to_jm = request.args.get('to_month', type=int) or today.month
    to_jd = request.args.get('to_day', type=int) or today.day
    category_id = request.args.get('category_id', type=int)
    item_id = request.args.get('item_id', type=int)
    searched = request.args.get('searched') == '1'

    start_date = jalali_to_gregorian(from_jy, from_jm, from_jd)
    end_date = jalali_to_gregorian(to_jy, to_jm, to_jd)

    category_list = Category.query.order_by(Category.name).all()
    item_list = Item.query.filter_by(is_active=True).order_by(Item.name).all()
    selected_category = Category.query.get(category_id) if category_id else None
    selected_item = Item.query.get(item_id) if item_id else None

    records = []
    total_qty = 0.0
    total_price_usd = 0.0

    if searched:
        query = OpeningBalance.query
        if start_date:
            query = query.filter(OpeningBalance.date >= start_date)
        if end_date:
            query = query.filter(OpeningBalance.date <= end_date)
        if selected_category:
            query = query.filter(OpeningBalance.category_id == selected_category.id)
        if selected_item:
            query = query.filter(OpeningBalance.name == selected_item.name)
        records = query.order_by(OpeningBalance.date, OpeningBalance.id).all()
        total_qty = sum(r.opening_qty or 0 for r in records)
        total_price_usd = sum(r.total_price_usd or 0 for r in records)

    return render_template('reports/opening_balance_report.html',
        today=today, category_list=category_list, item_list=item_list,
        selected_category_id=category_id, selected_item_id=item_id,
        records=records, total_qty=total_qty, total_price_usd=total_price_usd, searched=searched,
        from_year=from_jy, from_month=from_jm, from_day=from_jd,
        to_year=to_jy, to_month=to_jm, to_day=to_jd,
        back_url=url_for('main.report_page', slug='warehouse'))


@main.route('/reports/stock-total-all', methods=['GET'])
@report_category_required('warehouse')
def stock_total_all_report():
    """
    موجودی کلی گدامها: برای هر جنس، موجودی به تفکیک هر گدام (در ستون‌های کنار هم) نمایش
    داده می‌شود — هر گدام با ۳ ستون: موجود / رزرو / قابل موجود — و در انتها ستون «مجموع»
    که جمع کلی (قابل موجود) روی تمام گدامها را نشان می‌دهد.
    """
    category_id = request.args.get('category_id', type=int)
    item_id = request.args.get('item_id', type=int)
    searched = request.args.get('searched') == '1'

    category_list = Category.query.order_by(Category.name).all()
    item_list = Item.query.filter_by(is_active=True).order_by(Item.name).all()
    stock_list = Stock.query.filter_by(is_active=True).order_by(Stock.id).all()
    selected_category = Category.query.get(category_id) if category_id else None
    selected_item = Item.query.get(item_id) if item_id else None

    rows = []
    grand_totals = [{'current': 0.0, 'reserved': 0.0, 'available': 0.0} for _ in stock_list]
    grand_total = 0.0

    if searched:
        item_query = Item.query.filter_by(is_active=True)
        if selected_category:
            item_query = item_query.filter_by(category_id=selected_category.id)
        if selected_item:
            item_query = item_query.filter_by(id=selected_item.id)
        items = item_query.order_by(Item.name).all()

        for it in items:
            balances_by_stock = {
                b.stock_id: b for b in StockBalance.query.filter_by(item_name=it.name).all()
            }
            if not balances_by_stock:
                continue

            cells = []
            row_total = 0.0
            for idx, st in enumerate(stock_list):
                bal = balances_by_stock.get(st.id)
                current = bal.current_qty or 0 if bal else 0
                reserved = bal.reserved_qty or 0 if bal else 0
                available = current - reserved
                cells.append({'current': current, 'reserved': reserved, 'available': available})
                grand_totals[idx]['current'] += current
                grand_totals[idx]['reserved'] += reserved
                grand_totals[idx]['available'] += available
                row_total += available

            rows.append({
                'item_name': it.name,
                'category_name': it.category.name if it.category else '-',
                'unit_name': it.unit.quantity if it.unit else '-',
                'cells': cells,
                'row_total': row_total,
            })
            grand_total += row_total

    return render_template('reports/stock_total_all_report.html',
        category_list=category_list, item_list=item_list, stock_list=stock_list,
        selected_category_id=category_id, selected_item_id=item_id,
        rows=rows, grand_totals=grand_totals, grand_total=grand_total, searched=searched,
        back_url=url_for('main.report_page', slug='warehouse'))


@main.route('/reports/stock-by-warehouse', methods=['GET'])
@report_category_required('warehouse')
def stock_by_warehouse_report():
    """
    موجودی بر اساس هر گدام: موجودی هر جنس به تفکیک هر گدام نمایش داده می‌شود
    (بر خلاف «موجودی کلی گدامها» که همه گدامها را با هم جمع می‌کند).
    """
    category_id = request.args.get('category_id', type=int)
    item_id = request.args.get('item_id', type=int)
    stock_id = request.args.get('stock_id', type=int)
    searched = request.args.get('searched') == '1'

    category_list = Category.query.order_by(Category.name).all()
    item_list = Item.query.filter_by(is_active=True).order_by(Item.name).all()
    stock_list = Stock.query.order_by(Stock.name).all()
    selected_category = Category.query.get(category_id) if category_id else None
    selected_item = Item.query.get(item_id) if item_id else None
    selected_stock = Stock.query.get(stock_id) if stock_id else None

    groups = []
    total_qty = 0.0
    total_value = 0.0

    if searched:
        matching_items = None
        if selected_category:
            matching_items = {it.name for it in Item.query.filter_by(category_id=selected_category.id).all()}

        stocks_to_show = [selected_stock] if selected_stock else stock_list

        for st in stocks_to_show:
            balance_query = StockBalance.query.filter_by(stock_id=st.id)
            if selected_item:
                balance_query = balance_query.filter_by(item_name=selected_item.name)
            balances = balance_query.order_by(StockBalance.item_name).all()

            rows = []
            group_qty = 0.0
            group_value = 0.0
            for bal in balances:
                if matching_items is not None and bal.item_name not in matching_items:
                    continue
                item_obj = Item.query.filter_by(name=bal.item_name).first()
                qty = bal.current_qty or 0
                price = bal.last_price or 0
                value = qty * price
                rows.append({
                    'item_name': bal.item_name,
                    'category_name': item_obj.category.name if (item_obj and item_obj.category) else '-',
                    'unit_name': bal.unit.quantity if bal.unit else '-',
                    'qty': qty,
                    'price': price,
                    'value': value,
                })
                group_qty += qty
                group_value += value

            if rows:
                groups.append({
                    'stock_name': st.name,
                    'rows': rows,
                    'group_qty': group_qty,
                    'group_value': group_value,
                })
                total_qty += group_qty
                total_value += group_value

    return render_template('reports/stock_by_warehouse_report.html',
        category_list=category_list, item_list=item_list, stock_list=stock_list,
        selected_category_id=category_id, selected_item_id=item_id, selected_stock_id=stock_id,
        groups=groups, total_qty=total_qty, total_value=total_value, searched=searched,
        back_url=url_for('main.report_page', slug='warehouse'))


@main.route('/reports/stock-value', methods=['GET'])
@report_category_required('warehouse')
def stock_value_report():
    """
    ارزش مقداری گدام: برای هر جنس فعال، موجودی کلی (روی تمام گدامها)، بهای تمام‌شده
    واحد (میانگین وزنی آخرین قیمت‌ها) و ارزش کل موجودی نمایش داده می‌شود. جستجوی زنده
    روی نام کالا در خود صفحه (سمت کاربر) انجام می‌شود، بدون نیاز به فرم جستجوی جداگانه.
    """
    rows = []
    grand_total_value = 0.0

    items = Item.query.filter_by(is_active=True).order_by(Item.name).all()
    for i, it in enumerate(items, start=1):
        balances = StockBalance.query.filter_by(item_name=it.name).all()
        qty_total = sum(b.current_qty or 0 for b in balances)
        value_total = sum((b.current_qty or 0) * (b.last_price or 0) for b in balances)
        unit_price = (value_total / qty_total) if qty_total else 0

        rows.append({
            'no': i,
            'item_name': it.name,
            'qty': qty_total,
            'unit_price': unit_price,
            'value': value_total,
        })
        grand_total_value += value_total

    today = jdatetime.date.today()

    return render_template('reports/stock_value_report.html',
        rows=rows, grand_total_value=grand_total_value, today=today,
        back_url=url_for('main.report_page', slug='warehouse'))


@main.route('/reports/inactive-items', methods=['GET'])
@report_category_required('warehouse')
def inactive_items_report():
    """
    راپور اجناس غیر فعال: لیست تمام اجناسی که is_active=False هستند، همراه با موجودی فعلی
    (جمع روی تمام گدامها) و امکان فعال‌سازی مجدد مستقیم از همین گزارش.
    """
    category_id = request.args.get('category_id', type=int)

    category_list = Category.query.order_by(Category.name).all()
    selected_category = Category.query.get(category_id) if category_id else None

    item_query = Item.query.filter_by(is_active=False)
    if selected_category:
        item_query = item_query.filter_by(category_id=selected_category.id)
    items = item_query.order_by(Item.name).all()

    rows = []
    for it in items:
        balances = StockBalance.query.filter_by(item_name=it.name).all()
        total_qty = sum(b.current_qty or 0 for b in balances)
        rows.append({
            'id': it.id,
            'code': it.code,
            'name': it.name,
            'category_name': it.category.name if it.category else '-',
            'unit_name': it.unit.quantity if it.unit else '-',
            'sale_price': it.sale_price or 0,
            'total_qty': total_qty,
            'shelf': ' / '.join(filter(None, [it.shelf_row, it.shelf_floor, it.shelf_number])) or '-',
        })

    return render_template('reports/inactive_items_report.html',
        category_list=category_list, selected_category_id=category_id,
        rows=rows,
        back_url=url_for('main.report_page', slug='warehouse'))


@main.route('/warehouse/stock-in/delete/<int:id>')
def stock_in_delete(id):
    si = StockIn.query.get_or_404(id)
    adjust_balance(si.item_name, si.stock_id, -(si.amount or 0))  # برگرداندن موجودی
    db.session.delete(si)
    db.session.commit()
    flash('رکورد حذف شد', 'success')
    return redirect(url_for('main.stock_in'))


# ==========================================
# گدام — موجودی انبار (گزارش)
# ==========================================
@main.route('/warehouse/stock-report', methods=['GET'])
def stock_report():
    category_id = request.args.get('category_id', type=int)
    stock_id = request.args.get('stock_id', type=int)

    categories = Category.query.order_by(Category.name).all()
    stocks = Stock.query.order_by(Stock.name).all()

    results = []
    # لیست کالاهایی که با کتگوری انتخاب‌شده مطابقت دارند
    item_query = Item.query
    if category_id:
        item_query = item_query.filter_by(category_id=category_id)
    matching_items = {it.name for it in item_query.all()} if category_id else None

    balance_query = StockBalance.query
    if stock_id:
        balance_query = balance_query.filter_by(stock_id=stock_id)

    for bal in balance_query.order_by(StockBalance.item_name).all():
        if matching_items is not None and bal.item_name not in matching_items:
            continue
        item_obj = Item.query.filter_by(name=bal.item_name).first()
        results.append({
            'item_name': bal.item_name,
            'category_name': item_obj.category.name if (item_obj and item_obj.category) else '-',
            'stock_name': bal.stock.name if bal.stock else '-',
            'current_qty': bal.current_qty or 0,
            'reserved_qty': bal.reserved_qty or 0,
            'available_qty': (bal.current_qty or 0) - (bal.reserved_qty or 0),
            'unit_name': bal.unit.quantity if bal.unit else '-',
            'last_price': bal.last_price or 0,
        })

    return render_template('warehouse/stock_report.html',
        categories=categories, stocks=stocks, results=results,
        selected_category=category_id, selected_stock=stock_id,
        searched=True)


# ==========================================
# خرید از شرکت‌ها — ثبت نام فروشنده کالا
# ==========================================
@main.route('/purchase/vendors', methods=['GET', 'POST'])
def vendors():
    edit_id = request.args.get('edit', type=int)
    edit_v = Vendor.query.get(edit_id) if edit_id else None

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        address = request.form.get('address', '').strip()
        book_no = request.form.get('book_no', '').strip()
        phone = request.form.get('phone', '').strip()
        v_id = request.form.get('v_id', type=int)

        if not name:
            flash('نام فروشنده کالا نمی‌تواند خالی باشد', 'danger')
        elif v_id:
            v = Vendor.query.get_or_404(v_id)
            v.name, v.address, v.book_no, v.phone = name, address, book_no, phone
            db.session.commit()
            flash('فروشنده ویرایش شد', 'success')
        else:
            db.session.add(Vendor(name=name, address=address, book_no=book_no, phone=phone))
            db.session.commit()
            flash('فروشنده ثبت شد', 'success')
        return redirect(url_for('main.vendors'))

    search = request.args.get('q', '').strip()
    query = Vendor.query
    if search:
        query = query.filter(Vendor.name.contains(search))
    vendors = query.order_by(Vendor.id).all()

    return render_template('purchase/vendors.html', vendors=vendors, edit_v=edit_v, search=search)


@main.route('/purchase/vendors/delete/<int:id>')
def vendor_delete(id):
    v = Vendor.query.get_or_404(id)

    # ===== بررسی وابستگی‌ها قبل از حذف =====
    has_opening = VendorOpening.query.filter_by(vendor_id=id).first() is not None
    has_invoices = PurchaseInvoice.query.filter_by(vendor_id=id).first() is not None
    has_payments = VendorPayment.query.filter_by(vendor_id=id).first() is not None

    if has_opening or has_invoices or has_payments:
        flash('این فروشنده دارای فاکتور، حساب افتتاحیه یا پرداخت است — ابتدا آن‌ها را حذف کنید', 'danger')
        return redirect(url_for('main.vendors'))

    db.session.delete(v)
    db.session.commit()
    flash('فروشنده حذف شد', 'success')
    return redirect(url_for('main.vendors'))


# ==========================================
# خرید از شرکت‌ها — حساب افتتاحیه فروشنده
# ==========================================
@main.route('/purchase/vendor-opening', methods=['GET', 'POST'])
def vendor_opening():
    edit_id = request.args.get('edit', type=int)
    edit_vo = VendorOpening.query.get(edit_id) if edit_id else None

    if request.method == 'POST':
        jy = request.form.get('j_year', type=int)
        jm = request.form.get('j_month', type=int)
        jd = request.form.get('j_day', type=int)
        g_date = jalali_to_gregorian(jy, jm, jd)

        vendor_name = request.form.get('vendor_name', '').strip()
        vendor = Vendor.query.filter_by(name=vendor_name).first()
        currency = request.form.get('currency', '').strip()
        amount = request.form.get('amount', type=float) or 0
        account_type = request.form.get('account_type', '').strip()
        vo_id = request.form.get('vo_id', type=int)

        if not vendor or not g_date:
            flash('نام فروشنده (از لیست) و تاریخ الزامی است', 'danger')
        elif vo_id:
            vo = VendorOpening.query.get_or_404(vo_id)
            vo.date, vo.j_year, vo.j_month, vo.j_day = g_date, jy, jm, jd
            vo.vendor_id, vo.currency = vendor.id, currency
            vo.amount, vo.account_type = amount, account_type
            db.session.commit()
            flash('حساب افتتاحیه ویرایش شد', 'success')
        else:
            db.session.add(VendorOpening(
                date=g_date, j_year=jy, j_month=jm, j_day=jd,
                vendor_id=vendor.id, currency=currency,
                amount=amount, account_type=account_type
            ))
            db.session.commit()
            flash('حساب افتتاحیه ثبت شد', 'success')
        return redirect(url_for('main.vendor_opening'))

    records = VendorOpening.query.order_by(VendorOpening.id).all()
    vendor_list = Vendor.query.order_by(Vendor.name).all()
    today = jdatetime.date.today()

    return render_template('purchase/vendor_opening.html',
        records=records, edit_vo=edit_vo, vendor_list=vendor_list, today=today)


@main.route('/purchase/vendor-opening/delete/<int:id>')
def vendor_opening_delete(id):
    vo = VendorOpening.query.get_or_404(id)
    db.session.delete(vo)
    db.session.commit()
    flash('رکورد حذف شد', 'success')
    return redirect(url_for('main.vendor_opening'))


# ==========================================
# خرید از شرکت‌ها — ثبت فاکتور خرید
# ==========================================
@main.route('/purchase/invoices', methods=['GET', 'POST'])
def purchase_invoices():
    edit_id = request.args.get('edit', type=int)
    edit_inv = PurchaseInvoice.query.get(edit_id) if edit_id else None

    if request.method == 'POST':
        jy = request.form.get('j_year', type=int)
        jm = request.form.get('j_month', type=int)
        jd = request.form.get('j_day', type=int)
        g_date = jalali_to_gregorian(jy, jm, jd)

        vendor_name = request.form.get('vendor_name', '').strip()
        vendor = Vendor.query.filter_by(name=vendor_name).first()
        bank_id = request.form.get('bank_id', type=int)
        bank_obj = Bank.query.get(bank_id) if bank_id else None
        bank_name = bank_obj.name if bank_obj else ''
        currency = request.form.get('currency', '').strip()
        exchange_rate = request.form.get('exchange_rate', type=float) or 1
        delivery = request.form.get('delivery', '').strip()
        loading_fee = request.form.get('loading_fee', type=float) or 0
        discount = request.form.get('discount', type=float) or 0
        paid_amount = request.form.get('paid_amount', type=float) or 0
        notes = request.form.get('notes', '').strip()
        inv_id = request.form.get('inv_id', type=int)
        time_str = jdatetime.datetime.now().strftime('%H:%M:%S')

        # ردیف‌های کالا (تعداد نامحدود، مثل ترکیب مواد)
        row_indexes = set()
        for key in request.form.keys():
            if key.startswith('row_item_'):
                row_indexes.add(int(key.replace('row_item_', '')))

        rows = []
        total_amount = 0
        for i in sorted(row_indexes):
            row_item_id = request.form.get(f'row_item_{i}', type=int)
            if not row_item_id:
                continue
            row_item_obj = Item.query.get(row_item_id)
            row_stock_id = request.form.get(f'row_stock_{i}', type=int)
            row_quantity_id = request.form.get(f'row_quantity_{i}', type=int)
            row_available = request.form.get(f'row_available_{i}', type=float) or 0
            row_price = request.form.get(f'row_price_{i}', type=float) or 0
            row_amount = request.form.get(f'row_amount_{i}', type=float) or 0
            row_total = row_amount * row_price
            total_amount += row_total
            rows.append(dict(
                item_name=row_item_obj.name if row_item_obj else '',
                stock_id=row_stock_id, quantity_id=row_quantity_id,
                available_qty=row_available, price=row_price, amount=row_amount,
                total=row_total, row_no=i
            ))

        # ارز پایه = دالر
        total_amount_usd = (total_amount / exchange_rate) if (currency != 'USD' and exchange_rate) else total_amount
        remaining = total_amount + loading_fee - discount - paid_amount

        if not vendor or not g_date or not rows:
            flash('فروشنده، تاریخ و حداقل یک کالا الزامی است', 'danger')
        else:
            if inv_id:
                inv = PurchaseInvoice.query.get_or_404(inv_id)
                # برگرداندن اثر قبلی این فاکتور از موجودی گدام
                for old_line in inv.lines:
                    adjust_balance(old_line.item_name, old_line.stock_id, -(old_line.amount or 0))

                # برگرداندن اثر قبلی پرداخت این فاکتور از موجودی بانک قبل از اعمال مقدار جدید
                if inv.bank_id and inv.paid_amount:
                    old_currency_id = _currency_code_to_id(inv.currency)
                    adjust_bank_balance(inv.bank_id, old_currency_id, inv.paid_amount,
                                         notes='برگشت پرداخت فاکتور خرید (ویرایش)')

                inv.date, inv.j_year, inv.j_month, inv.j_day = g_date, jy, jm, jd
                inv.vendor_id, inv.bank_id, inv.bank_name = vendor.id, bank_id, bank_name
                inv.currency, inv.exchange_rate, inv.delivery = currency, exchange_rate, delivery
                inv.total_amount, inv.total_amount_usd = total_amount, total_amount_usd
                inv.loading_fee, inv.discount = loading_fee, discount
                inv.paid_amount, inv.remaining, inv.notes = paid_amount, remaining, notes

                if bank_id and paid_amount:
                    new_currency_id = _currency_code_to_id(currency)
                    adjust_bank_balance(bank_id, new_currency_id, -paid_amount, g_date=g_date,
                                         notes=f'پرداخت فاکتور خرید #{inv.invoice_no} — {vendor.name}' + ' (ویرایش)')

                PurchaseInvoiceLine.query.filter_by(invoice_id=inv.id).delete()
                for r in rows:
                    db.session.add(PurchaseInvoiceLine(invoice_id=inv.id, **r))
                    # افزایش موجودی گدام برای هر کالای این فاکتور
                    unit_price_usd = (r['price'] / exchange_rate) if (currency != 'USD' and exchange_rate) else r['price']
                    adjust_balance(r['item_name'], r['stock_id'], r['amount'],
                                    price=unit_price_usd, quantity_id=r['quantity_id'])
                db.session.commit()
                flash('فاکتور ویرایش شد', 'success')
            else:
                last = PurchaseInvoice.query.order_by(PurchaseInvoice.invoice_no.desc()).first()
                next_no = (last.invoice_no + 1) if (last and last.invoice_no) else 1

                inv = PurchaseInvoice(
                    invoice_no=next_no, time_str=time_str,
                    date=g_date, j_year=jy, j_month=jm, j_day=jd,
                    vendor_id=vendor.id, bank_id=bank_id, bank_name=bank_name,
                    currency=currency, exchange_rate=exchange_rate, delivery=delivery,
                    total_amount=total_amount, total_amount_usd=total_amount_usd,
                    loading_fee=loading_fee, discount=discount,
                    paid_amount=paid_amount, remaining=remaining, notes=notes,
                    created_by=session.get('username')
                )
                db.session.add(inv)
                db.session.flush()

                if bank_id and paid_amount:
                    currency_id = _currency_code_to_id(currency)
                    adjust_bank_balance(bank_id, currency_id, -paid_amount, g_date=g_date,
                                         notes=f'پرداخت فاکتور خرید #{inv.invoice_no} — {vendor.name}')

                for r in rows:
                    db.session.add(PurchaseInvoiceLine(invoice_id=inv.id, **r))
                    unit_price_usd = (r['price'] / exchange_rate) if (currency != 'USD' and exchange_rate) else r['price']
                    adjust_balance(r['item_name'], r['stock_id'], r['amount'],
                                    price=unit_price_usd, quantity_id=r['quantity_id'])

                db.session.commit()
                flash('فاکتور خرید ثبت شد', 'success')
        return redirect(url_for('main.purchase_invoices'))

    records = PurchaseInvoice.query.order_by(PurchaseInvoice.id).all()
    vendor_list = Vendor.query.order_by(Vendor.name).all()
    stocks = Stock.query.order_by(Stock.name).all()
    units = Quantity.query.order_by(Quantity.quantity).all()
    items = Item.query.filter_by(is_active=True).order_by(Item.name).all()
    banks = Bank.query.filter_by(is_active=True).order_by(Bank.name).all()
    today = jdatetime.date.today()

    edit_lines = {}
    if edit_inv:
        for l in edit_inv.lines:
            edit_lines[l.row_no] = l

    return render_template('purchase/invoices.html',
        records=records, edit_inv=edit_inv, edit_lines=edit_lines,
        vendor_list=vendor_list, stocks=stocks, units=units, items=items, banks=banks, today=today)


@main.route('/purchase/invoices/item-info/<int:item_id>')
def purchase_item_info(item_id):
    """موجودی فعلی و واحد یک کالا را برمی‌گرداند (برای پر کردن خودکار فرم فاکتور خرید)."""
    from flask import jsonify
    item = Item.query.get(item_id)
    if not item:
        return jsonify({'found': False})

    record = (StockBalance.query
              .filter_by(item_name=item.name)
              .order_by(StockBalance.current_qty.desc())
              .first())
    if not record:
        return jsonify({'found': False})

    return jsonify({
        'found': True,
        'stock_id': record.stock_id or '',
        'quantity_id': record.quantity_id or '',
        'available_qty': record.current_qty or 0
    })


@main.route('/purchase/invoices/print/<int:id>')
def purchase_invoice_print(id):
    inv = PurchaseInvoice.query.get_or_404(id)
    total_words = number_to_persian_words(inv.total_amount)
    g_date_str = inv.date.strftime('%Y-%m-%d') if inv.date else ''
    return render_template('purchase/invoice_print.html', inv=inv, total_words=total_words, g_date_str=g_date_str)


@main.route('/purchase/invoices/delete/<int:id>')
def purchase_invoice_delete(id):
    inv = PurchaseInvoice.query.get_or_404(id)
    for line in inv.lines:
        adjust_balance(line.item_name, line.stock_id, -(line.amount or 0))
    if inv.bank_id and inv.paid_amount:
        currency_id = _currency_code_to_id(inv.currency)
        adjust_bank_balance(inv.bank_id, currency_id, inv.paid_amount,
                             notes='برگشت پرداخت فاکتور خرید (حذف)')
    db.session.delete(inv)
    db.session.commit()
    flash('فاکتور حذف شد', 'success')
    return redirect(url_for('main.purchase_invoices'))


# ==========================================
# خرید از شرکت‌ها — بار برگشتی فروشنده (فاکتور برگشت خرید)
# دقیقاً مثل فاکتور خرید ثبت می‌شود؛ اما اثر آن روی گدام و حساب فروشنده معکوس فاکتور خرید است:
#   - از موجودی گدام کم می‌شود (کالا به فروشنده برگردانده شده)
#   - بدهی ما به فروشنده به اندازه مبلغ بار برگشتی کم می‌شود (vendor_balance این را خودکار محاسبه می‌کند):
#       اگر بدهی ما صفر بود (فروشنده قبلاً پول جنس را گرفته بود) → فروشنده به ما بدهکار می‌شود.
#       اگر بدهی ما مثبت بود (فروشنده هنوز پول جنس را نگرفته بود) → همان بدهی به‌اندازه برگشتی تسویه/کم می‌شود.
# ==========================================
@main.route('/purchase/returns', methods=['GET', 'POST'])
def purchase_returns():
    edit_id = request.args.get('edit', type=int)
    edit_ret = VendorReturn.query.get(edit_id) if edit_id else None

    if request.method == 'POST':
        jy = request.form.get('j_year', type=int)
        jm = request.form.get('j_month', type=int)
        jd = request.form.get('j_day', type=int)
        g_date = jalali_to_gregorian(jy, jm, jd)

        vendor_name = request.form.get('vendor_name', '').strip()
        vendor = Vendor.query.filter_by(name=vendor_name).first()
        currency = request.form.get('currency', '').strip()
        exchange_rate = request.form.get('exchange_rate', type=float) or 1
        notes = request.form.get('notes', '').strip()
        ret_id = request.form.get('ret_id', type=int)
        time_str = jdatetime.datetime.now().strftime('%H:%M:%S')

        row_indexes = set()
        for key in request.form.keys():
            if key.startswith('row_item_'):
                row_indexes.add(int(key.replace('row_item_', '')))

        rows = []
        total_amount = 0
        for i in sorted(row_indexes):
            row_item_id = request.form.get(f'row_item_{i}', type=int)
            if not row_item_id:
                continue
            row_item_obj = Item.query.get(row_item_id)
            row_stock_id = request.form.get(f'row_stock_{i}', type=int)
            row_quantity_id = request.form.get(f'row_quantity_{i}', type=int)
            row_available = request.form.get(f'row_available_{i}', type=float) or 0
            row_price = request.form.get(f'row_price_{i}', type=float) or 0
            row_amount = request.form.get(f'row_amount_{i}', type=float) or 0
            row_total = row_amount * row_price
            total_amount += row_total
            rows.append(dict(
                item_name=row_item_obj.name if row_item_obj else '',
                stock_id=row_stock_id, quantity_id=row_quantity_id,
                available_qty=row_available, price=row_price, amount=row_amount,
                total=row_total, row_no=i
            ))

        total_amount_usd = (total_amount / exchange_rate) if (currency != 'USD' and exchange_rate) else total_amount

        if not vendor or not g_date or not rows:
            flash('فروشنده، تاریخ و حداقل یک کالا الزامی است', 'danger')
        else:
            if ret_id:
                ret = VendorReturn.query.get_or_404(ret_id)
                # برگرداندن اثر قبلی این بار برگشتی از موجودی گدام (قبلاً کم شده بود، دوباره اضافه می‌شود)
                for old_line in ret.lines:
                    adjust_balance(old_line.item_name, old_line.stock_id, (old_line.amount or 0))

                ret.date, ret.j_year, ret.j_month, ret.j_day = g_date, jy, jm, jd
                ret.vendor_id = vendor.id
                ret.currency, ret.exchange_rate = currency, exchange_rate
                ret.total_amount, ret.total_amount_usd = total_amount, total_amount_usd
                ret.notes = notes

                VendorReturnLine.query.filter_by(return_id=ret.id).delete()
                for r in rows:
                    db.session.add(VendorReturnLine(return_id=ret.id, **r))
                    unit_price_usd = (r['price'] / exchange_rate) if (currency != 'USD' and exchange_rate) else r['price']
                    # کاهش موجودی گدام (کالا برگردانده شده)
                    adjust_balance(r['item_name'], r['stock_id'], -(r['amount'] or 0),
                                    price=unit_price_usd, quantity_id=r['quantity_id'])
                db.session.commit()
                flash('بار برگشتی ویرایش شد', 'success')
            else:
                last = VendorReturn.query.order_by(VendorReturn.return_no.desc()).first()
                next_no = (last.return_no + 1) if (last and last.return_no) else 1

                ret = VendorReturn(
                    return_no=next_no, time_str=time_str,
                    date=g_date, j_year=jy, j_month=jm, j_day=jd,
                    vendor_id=vendor.id, currency=currency, exchange_rate=exchange_rate,
                    total_amount=total_amount, total_amount_usd=total_amount_usd, notes=notes,
                    created_by=session.get('username')
                )
                db.session.add(ret)
                db.session.flush()

                for r in rows:
                    db.session.add(VendorReturnLine(return_id=ret.id, **r))
                    unit_price_usd = (r['price'] / exchange_rate) if (currency != 'USD' and exchange_rate) else r['price']
                    # کاهش موجودی گدام (کالا برگردانده شده به فروشنده)
                    adjust_balance(r['item_name'], r['stock_id'], -(r['amount'] or 0),
                                    price=unit_price_usd, quantity_id=r['quantity_id'])

                db.session.commit()
                flash('بار برگشتی فروشنده ثبت شد', 'success')
        return redirect(url_for('main.purchase_returns'))

    records = VendorReturn.query.order_by(VendorReturn.id).all()
    vendor_list = Vendor.query.order_by(Vendor.name).all()
    stocks = Stock.query.order_by(Stock.name).all()
    units = Quantity.query.order_by(Quantity.quantity).all()
    items = Item.query.filter_by(is_active=True).order_by(Item.name).all()
    today = jdatetime.date.today()

    edit_lines = {}
    if edit_ret:
        for l in edit_ret.lines:
            edit_lines[l.row_no] = l

    return render_template('purchase/vendor_return.html',
        records=records, edit_ret=edit_ret, edit_lines=edit_lines,
        vendor_list=vendor_list, stocks=stocks, units=units, items=items, today=today)


@main.route('/purchase/returns/print/<int:id>')
def purchase_return_print(id):
    ret = VendorReturn.query.get_or_404(id)
    total_words = number_to_persian_words(ret.total_amount)
    g_date_str = ret.date.strftime('%Y-%m-%d') if ret.date else ''
    return render_template('purchase/vendor_return_print.html', ret=ret, total_words=total_words, g_date_str=g_date_str)


@main.route('/purchase/returns/delete/<int:id>')
def purchase_return_delete(id):
    ret = VendorReturn.query.get_or_404(id)
    for line in ret.lines:
        # برگرداندن اثر کاهش موجودی: کالا دوباره به گدام اضافه می‌شود
        adjust_balance(line.item_name, line.stock_id, (line.amount or 0))
    db.session.delete(ret)
    db.session.commit()
    flash('بار برگشتی حذف شد', 'success')
    return redirect(url_for('main.purchase_returns'))


# ==========================================
# خرید از شرکت‌ها — حسابات فروشنده کالا (جستجو)
# ==========================================
@main.route('/purchase/vendor-search', methods=['GET'])
def vendor_search():
    vendor_list = Vendor.query.order_by(Vendor.name).all()
    return render_template('purchase/vendor_search.html', vendor_list=vendor_list)


@main.route('/purchase/vendor-account/<int:vendor_id>')
def vendor_account(vendor_id):
    vendor = Vendor.query.get_or_404(vendor_id)
    balance = vendor_balance(vendor.id)
    return render_template('purchase/vendor_account.html', vendor=vendor, balance=balance)


# ---- حساب جاری: لیست تراکنش‌ها با مانده در حرکت ----
@main.route('/purchase/vendor-account/<int:vendor_id>/current')
def vendor_current_account(vendor_id):
    vendor = Vendor.query.get_or_404(vendor_id)

    entries = []
    for o in VendorOpening.query.filter_by(vendor_id=vendor_id).all():
        amt = o.amount if o.account_type != 'receivable' else -o.amount
        entries.append({'date': o.date, 'j_year': o.j_year, 'j_month': o.j_month, 'j_day': o.j_day,
                         'desc': 'حساب افتتاحیه', 'debit': amt if amt > 0 else 0, 'credit': -amt if amt < 0 else 0})
    for inv in PurchaseInvoice.query.filter_by(vendor_id=vendor_id).all():
        entries.append({'date': inv.date, 'j_year': inv.j_year, 'j_month': inv.j_month, 'j_day': inv.j_day,
                         'desc': f'فاکتور خرید #{inv.invoice_no}', 'debit': inv.remaining or 0, 'credit': 0})
    for r in VendorReturn.query.filter_by(vendor_id=vendor_id).all():
        entries.append({'date': r.date, 'j_year': r.j_year, 'j_month': r.j_month, 'j_day': r.j_day,
                         'desc': f'بار برگشتی فروشنده #{r.return_no}', 'debit': 0, 'credit': r.total_amount or 0})
    for p in VendorPayment.query.filter_by(vendor_id=vendor_id).all():
        entries.append({'date': p.date, 'j_year': p.j_year, 'j_month': p.j_month, 'j_day': p.j_day,
                         'desc': 'پرداخت', 'debit': 0, 'credit': p.amount or 0})
    for ct in CashTransaction.query.filter_by(party_type='vendor', party_id=vendor_id).all():
        amt = ct.amount or 0
        entries.append({'date': ct.date, 'j_year': ct.j_year, 'j_month': ct.j_month, 'j_day': ct.j_day,
                         'desc': 'برد و رسید نقدی',
                         'debit': 0 if ct.transaction_type == 'payment' else amt,
                         'credit': amt if ct.transaction_type == 'payment' else 0})
    for cp in CustomerPayment.query.filter_by(party_type='vendor', vendor_id=vendor_id).all():
        amt = cp.amount or 0
        entries.append({'date': cp.date, 'j_year': cp.j_year, 'j_month': cp.j_month, 'j_day': cp.j_day,
                         'desc': 'برد و رسید (تبدیل ارزی)',
                         'debit': amt if cp.payment_type == 'payment' else 0,
                         'credit': 0 if cp.payment_type == 'payment' else amt})

    entries.sort(key=lambda e: e['date'])

    running = 0
    for e in entries:
        e['amount'] = (e['debit'] or 0) - (e['credit'] or 0)
        running += e['amount']
        e['balance'] = running

    return render_template('purchase/vendor_current.html', vendor=vendor, entries=entries)


# ---- صورت حساب کلی فروشنده ----
@main.route('/purchase/vendor-account/<int:vendor_id>/summary')
def vendor_summary(vendor_id):
    vendor = Vendor.query.get_or_404(vendor_id)

    total_opening = sum(
        (o.amount if o.account_type != 'receivable' else -o.amount)
        for o in VendorOpening.query.filter_by(vendor_id=vendor_id).all()
    )
    invoices = PurchaseInvoice.query.filter_by(vendor_id=vendor_id).all()
    total_purchase = sum(inv.total_amount or 0 for inv in invoices)
    total_remaining_invoices = sum(inv.remaining or 0 for inv in invoices)
    total_paid_on_invoices = sum(inv.paid_amount or 0 for inv in invoices)

    payments = VendorPayment.query.filter_by(vendor_id=vendor_id).all()
    total_payments = sum(p.amount or 0 for p in payments)

    returns = VendorReturn.query.filter_by(vendor_id=vendor_id).all()
    total_returns = sum(r.total_amount or 0 for r in returns)

    balance = vendor_balance(vendor.id)

    return render_template('purchase/vendor_summary.html',
        vendor=vendor, total_opening=total_opening, total_purchase=total_purchase,
        total_paid_on_invoices=total_paid_on_invoices, total_payments=total_payments,
        total_returns=total_returns, return_count=len(returns),
        invoice_count=len(invoices), balance=balance)


# ---- گزارش پرداختی ----
@main.route('/purchase/vendor-account/<int:vendor_id>/payments')
def vendor_payments_report(vendor_id):
    vendor = Vendor.query.get_or_404(vendor_id)
    payments = VendorPayment.query.filter_by(vendor_id=vendor_id).order_by(VendorPayment.date).all()
    total = sum(p.amount or 0 for p in payments)
    return render_template('purchase/vendor_payments_report.html', vendor=vendor, payments=payments, total=total)


# ---- صورت حساب تاریخ‌وار (فیلتر بازه) ----
@main.route('/purchase/vendor-account/<int:vendor_id>/date-range')
def vendor_date_range(vendor_id):
    vendor = Vendor.query.get_or_404(vendor_id)

    from_jy = request.args.get('from_year', type=int)
    from_jm = request.args.get('from_month', type=int)
    from_jd = request.args.get('from_day', type=int)
    to_jy = request.args.get('to_year', type=int)
    to_jm = request.args.get('to_month', type=int)
    to_jd = request.args.get('to_day', type=int)

    start_date = jalali_to_gregorian(from_jy, from_jm, from_jd) if (from_jy and from_jm and from_jd) else None
    end_date = jalali_to_gregorian(to_jy, to_jm, to_jd) if (to_jy and to_jm and to_jd) else None

    entries = []
    for o in VendorOpening.query.filter_by(vendor_id=vendor_id).all():
        amt = o.amount if o.account_type != 'receivable' else -o.amount
        entries.append({'date': o.date, 'j_year': o.j_year, 'j_month': o.j_month, 'j_day': o.j_day,
                         'desc': 'حساب افتتاحیه', 'debit': amt if amt > 0 else 0, 'credit': -amt if amt < 0 else 0})
    for inv in PurchaseInvoice.query.filter_by(vendor_id=vendor_id).all():
        entries.append({'date': inv.date, 'j_year': inv.j_year, 'j_month': inv.j_month, 'j_day': inv.j_day,
                         'desc': f'فاکتور خرید #{inv.invoice_no}', 'debit': inv.remaining or 0, 'credit': 0})
    for r in VendorReturn.query.filter_by(vendor_id=vendor_id).all():
        entries.append({'date': r.date, 'j_year': r.j_year, 'j_month': r.j_month, 'j_day': r.j_day,
                         'desc': f'بار برگشتی فروشنده #{r.return_no}', 'debit': 0, 'credit': r.total_amount or 0})
    for p in VendorPayment.query.filter_by(vendor_id=vendor_id).all():
        entries.append({'date': p.date, 'j_year': p.j_year, 'j_month': p.j_month, 'j_day': p.j_day,
                         'desc': 'پرداخت', 'debit': 0, 'credit': p.amount or 0})
    for ct in CashTransaction.query.filter_by(party_type='vendor', party_id=vendor_id).all():
        amt = ct.amount or 0
        entries.append({'date': ct.date, 'j_year': ct.j_year, 'j_month': ct.j_month, 'j_day': ct.j_day,
                         'desc': 'برد و رسید نقدی',
                         'debit': 0 if ct.transaction_type == 'payment' else amt,
                         'credit': amt if ct.transaction_type == 'payment' else 0})
    for cp in CustomerPayment.query.filter_by(party_type='vendor', vendor_id=vendor_id).all():
        amt = cp.amount or 0
        entries.append({'date': cp.date, 'j_year': cp.j_year, 'j_month': cp.j_month, 'j_day': cp.j_day,
                         'desc': 'برد و رسید (تبدیل ارزی)',
                         'debit': amt if cp.payment_type == 'payment' else 0,
                         'credit': 0 if cp.payment_type == 'payment' else amt})

    entries.sort(key=lambda e: e['date'])

    if start_date:
        entries = [e for e in entries if e['date'] >= start_date]
    if end_date:
        entries = [e for e in entries if e['date'] <= end_date]

    running = 0
    for e in entries:
        e['amount'] = (e['debit'] or 0) - (e['credit'] or 0)
        running += e['amount']
        e['balance'] = running

    today = jdatetime.date.today()
    return render_template('purchase/vendor_date_range.html',
        vendor=vendor, entries=entries, today=today,
        from_year=from_jy, from_month=from_jm, from_day=from_jd,
        to_year=to_jy, to_month=to_jm, to_day=to_jd)


# ---- پرداخت به فروشنده کالا ----
@main.route('/purchase/vendor-payment', methods=['GET', 'POST'])
def vendor_payment_form():
    edit_id = request.args.get('edit', type=int)
    edit_vp = VendorPayment.query.get(edit_id) if edit_id else None

    if request.method == 'POST':
        jy = request.form.get('j_year', type=int)
        jm = request.form.get('j_month', type=int)
        jd = request.form.get('j_day', type=int)
        g_date = jalali_to_gregorian(jy, jm, jd)

        vendor_name = request.form.get('vendor_name', '').strip()
        vendor = Vendor.query.filter_by(name=vendor_name).first()
        amount = request.form.get('amount', type=float) or 0
        currency = request.form.get('currency', '').strip()
        notes = request.form.get('notes', '').strip()
        vp_id = request.form.get('vp_id', type=int)

        if not vendor or not g_date:
            flash('نام فروشنده (از لیست) و تاریخ الزامی است', 'danger')
        elif vp_id:
            vp = VendorPayment.query.get_or_404(vp_id)
            vp.date, vp.j_year, vp.j_month, vp.j_day = g_date, jy, jm, jd
            vp.vendor_id, vp.amount, vp.currency, vp.notes = vendor.id, amount, currency, notes
            db.session.commit()
            flash('پرداخت ویرایش شد', 'success')
        else:
            db.session.add(VendorPayment(
                date=g_date, j_year=jy, j_month=jm, j_day=jd,
                vendor_id=vendor.id, amount=amount, currency=currency, notes=notes,
                created_by=session.get('username')
            ))
            db.session.commit()
            flash('پرداخت ثبت شد', 'success')
        return redirect(url_for('main.vendor_payment_form'))

    records = VendorPayment.query.order_by(VendorPayment.id).all()
    vendor_list = Vendor.query.order_by(Vendor.name).all()
    today = jdatetime.date.today()

    return render_template('purchase/vendor_payment_form.html',
        records=records, edit_vp=edit_vp, vendor_list=vendor_list, today=today)


@main.route('/purchase/vendor-payment/delete/<int:id>')
def vendor_payment_delete(id):
    vp = VendorPayment.query.get_or_404(id)
    db.session.delete(vp)
    db.session.commit()
    flash('رکورد حذف شد', 'success')
    return redirect(url_for('main.vendor_payment_form'))


# ==========================================
# مشتریان — ثبت کتگوری مشتری (یک صفحه: فرم + لیست)
# ==========================================
@main.route('/sale/customer-category', methods=['GET', 'POST'])
def customer_category():
    edit_id = request.args.get('edit', type=int)
    edit_cc = CustomerCategory.query.get(edit_id) if edit_id else None

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        cc_id = request.form.get('cc_id', type=int)
        if not name:
            flash('نام کتگوری نمی‌تواند خالی باشد', 'danger')
        elif cc_id:
            cc = CustomerCategory.query.get_or_404(cc_id)
            cc.name = name
            db.session.commit()
            flash('کتگوری ویرایش شد', 'success')
        else:
            db.session.add(CustomerCategory(name=name))
            db.session.commit()
            flash('کتگوری ثبت شد', 'success')
        return redirect(url_for('main.customer_category'))

    categories = CustomerCategory.query.order_by(CustomerCategory.id).all()
    return render_template('sale/customer_category.html', categories=categories, edit_cc=edit_cc)


@main.route('/sale/customer-category/delete/<int:id>')
def customer_category_delete(id):
    cc = CustomerCategory.query.get_or_404(id)
    db.session.delete(cc)
    db.session.commit()
    flash('کتگوری حذف شد', 'success')
    return redirect(url_for('main.customer_category'))


# ==========================================
# مشتریان — ثبت نام مشتری
# ==========================================
@main.route('/sale/customers', methods=['GET', 'POST'])
def customers():
    edit_id = request.args.get('edit', type=int)
    edit_c = Customer.query.get(edit_id) if edit_id else None

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        address = request.form.get('address', '').strip()
        book_no = request.form.get('book_no', '').strip()
        phone = request.form.get('phone', '').strip()
        category_id = request.form.get('category_id', type=int)
        c_id = request.form.get('c_id', type=int)

        if not name:
            flash('نام مشتری نمی‌تواند خالی باشد', 'danger')
        elif c_id:
            c = Customer.query.get_or_404(c_id)
            c.name, c.address, c.book_no, c.phone, c.category_id = name, address, book_no, phone, category_id
            db.session.commit()
            flash('مشتری ویرایش شد', 'success')
        else:
            db.session.add(Customer(name=name, address=address, book_no=book_no,
                                     phone=phone, category_id=category_id))
            db.session.commit()
            flash('مشتری ثبت شد', 'success')
        return redirect(url_for('main.customers'))

    search = request.args.get('q', '').strip()
    query = Customer.query
    if search:
        query = query.filter(Customer.name.contains(search))
    customer_list = query.order_by(Customer.id).all()
    category_list = CustomerCategory.query.order_by(CustomerCategory.name).all()

    return render_template('sale/customers.html',
        customer_list=customer_list, edit_c=edit_c, category_list=category_list, search=search)


@main.route('/sale/customers/delete/<int:id>')
def customer_delete(id):
    c = Customer.query.get_or_404(id)

    # ===== بررسی وابستگی‌ها قبل از حذف =====
    has_invoices = SalesInvoice.query.filter_by(customer_id=id).first() is not None
    has_opening = CustomerOpening.query.filter_by(customer_id=id).first() is not None
    has_orders = CustomerOrder.query.filter_by(customer_id=id).first() is not None
    has_transfers = CustomerTransfer.query.filter(
        (CustomerTransfer.from_customer_id == id) | (CustomerTransfer.to_customer_id == id)
    ).first() is not None
    has_payments = CustomerPayment.query.filter_by(customer_id=id).first() is not None
    has_exchange = CustomerCurrencyExchange.query.filter_by(customer_id=id).first() is not None

    if has_invoices or has_opening or has_orders or has_transfers or has_payments or has_exchange:
        flash('این مشتری دارای فاکتور، حساب افتتاحیه، سفارش یا تراکنش است — ابتدا آن‌ها را حذف کنید', 'danger')
        return redirect(url_for('main.customers'))

    db.session.delete(c)
    db.session.commit()
    flash('مشتری حذف شد', 'success')
    return redirect(url_for('main.customers'))


# ---- حسابات مشتری (جستجو) ----
@main.route('/sale/customer-search', methods=['GET'])
def customer_search():
    customer_list = Customer.query.order_by(Customer.name).all()
    return render_template('sale/customer_search.html', customer_list=customer_list)


# ---- خلاصه حسابات مشتری ----
@main.route('/sale/customer-account/<int:customer_id>')
def customer_account(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    balance = customer_balance(customer.id)

    invoices = SalesInvoice.query.filter_by(customer_id=customer_id).all()
    total_invoice = sum(inv.total_amount or 0 for inv in invoices)
    total_transport = sum(inv.loading_fee or 0 for inv in invoices)
    total_paid_on_invoices = sum(inv.paid_amount or 0 for inv in invoices)

    total_receipts_ct = sum(
        (ct.amount or 0) for ct in CashTransaction.query.filter_by(party_type='customer', party_id=customer_id).all()
        if ct.transaction_type == 'receipt'
    )
    total_receipts_cp = sum(
        (cp.amount or 0) for cp in CustomerPayment.query.filter_by(customer_id=customer_id).all()
        if cp.payment_type == 'receipt'
    )
    total_payments = total_paid_on_invoices + total_receipts_ct + total_receipts_cp

    returns = CustomerReturn.query.filter_by(customer_id=customer_id).all()
    total_returns = sum(r.total_amount or 0 for r in returns)

    # «خریداریهای ما»: در این نسخه از سیستم، خرید مستقیم از مشتری ثبت نمی‌شود (فقط بار برگشتی)
    total_our_purchases = 0.0

    return render_template('sale/customer_account.html',
        customer=customer, balance=balance,
        total_invoice=total_invoice, total_our_purchases=total_our_purchases,
        total_transport=total_transport, total_payments=total_payments,
        total_returns=total_returns)


# ---- حساب جاری مشتری: لیست تراکنش‌ها با مانده در حرکت ----
@main.route('/sale/customer-account/<int:customer_id>/current')
def customer_current_account(customer_id):
    customer = Customer.query.get_or_404(customer_id)

    entries = []
    for o in CustomerOpening.query.filter_by(customer_id=customer_id).all():
        amt = -o.amount if o.account_type == 'payable' else o.amount
        entries.append({'date': o.date, 'j_year': o.j_year, 'j_month': o.j_month, 'j_day': o.j_day,
                         'currency': o.currency or 'AFN',
                         'desc': 'حساب افتتاحیه', 'debit': amt if amt > 0 else 0, 'credit': -amt if amt < 0 else 0})
    for inv in SalesInvoice.query.filter_by(customer_id=customer_id).all():
        entries.append({'date': inv.date, 'j_year': inv.j_year, 'j_month': inv.j_month, 'j_day': inv.j_day,
                         'currency': inv.currency or 'AFN',
                         'desc': f'فاکتور فروش #{inv.invoice_no}', 'debit': inv.remaining or 0, 'credit': 0})
    for r in CustomerReturn.query.filter_by(customer_id=customer_id).all():
        entries.append({'date': r.date, 'j_year': r.j_year, 'j_month': r.j_month, 'j_day': r.j_day,
                         'currency': getattr(r, 'currency', None) or 'AFN',
                         'desc': f'بار برگشتی مشتری #{r.return_no}', 'debit': 0, 'credit': r.total_amount or 0})
    for ct in CashTransaction.query.filter_by(party_type='customer', party_id=customer_id).all():
        amt = ct.amount or 0
        entries.append({'date': ct.date, 'j_year': ct.j_year, 'j_month': ct.j_month, 'j_day': ct.j_day,
                         'currency': (ct.currency.code if ct.currency else 'AFN'),
                         'desc': 'برد و رسید نقدی',
                         'debit': amt if ct.transaction_type == 'payment' else 0,
                         'credit': 0 if ct.transaction_type == 'payment' else amt})
    for tr in CustomerTransfer.query.filter_by(from_customer_id=customer_id).all():
        amt = tr.amount or 0
        entries.append({'date': tr.date, 'j_year': tr.j_year, 'j_month': tr.j_month, 'j_day': tr.j_day,
                         'currency': (tr.currency.code if tr.currency else 'AFN'),
                         'desc': 'انتقال حساب (مبدا)',
                         'debit': amt if tr.transaction_type == 'payment' else 0,
                         'credit': 0 if tr.transaction_type == 'payment' else amt})
    for tr in CustomerTransfer.query.filter_by(to_customer_id=customer_id).all():
        amt = tr.amount or 0
        entries.append({'date': tr.date, 'j_year': tr.j_year, 'j_month': tr.j_month, 'j_day': tr.j_day,
                         'currency': (tr.currency.code if tr.currency else 'AFN'),
                         'desc': 'انتقال حساب (مقصد)',
                         'debit': 0 if tr.transaction_type == 'payment' else amt,
                         'credit': amt if tr.transaction_type == 'payment' else 0})
    for cp in CustomerPayment.query.filter_by(customer_id=customer_id).all():
        amt = cp.amount or 0
        entries.append({'date': cp.date, 'j_year': cp.j_year, 'j_month': cp.j_month, 'j_day': cp.j_day,
                         'currency': (cp.pay_currency.code if cp.pay_currency else 'AFN'),
                         'desc': 'برد و رسید (تبدیل ارزی)',
                         'debit': amt if cp.payment_type == 'payment' else 0,
                         'credit': 0 if cp.payment_type == 'payment' else amt})

    entries.sort(key=lambda e: e['date'])

    # واحدپول‌های موجود در این حساب (برای دراپ‌داون فیلتر)
    available_currencies = sorted({e['currency'] for e in entries})

    # جلوگیری از جمع‌زدن نادرست چند واحدپول با هم: همیشه فقط یک واحدپول در آن‌واحد محاسبه می‌شود.
    currency_filter = request.args.get('currency', '').strip()
    if not currency_filter:
        currency_filter = available_currencies[0] if available_currencies else 'AFN'

    entries = [e for e in entries if e['currency'] == currency_filter]

    running = 0
    for e in entries:
        e['amount'] = (e['credit'] or 0) - (e['debit'] or 0)
        running += e['amount']
        e['balance'] = running

    return render_template('sale/customer_current.html', customer=customer, entries=entries,
                            available_currencies=available_currencies, currency_filter=currency_filter)


# ---- صورت حساب کلی مشتری (ریز تراکنش‌ها با فیلتر واحد پولی) ----
@main.route('/sale/customer-account/<int:customer_id>/summary')
def customer_summary(customer_id):
    customer = Customer.query.get_or_404(customer_id)

    entries = []
    for o in CustomerOpening.query.filter_by(customer_id=customer_id).all():
        amt = -o.amount if o.account_type == 'payable' else o.amount
        # قرارداد این صفحه: عدد منفی یعنی مشتری به ما بدهکار است (اکنون هم‌راستا با customer_balance)
        entries.append({'date': o.date, 'j_year': o.j_year, 'j_month': o.j_month, 'j_day': o.j_day,
                         'currency': o.currency or '-', 'ref': 'حساب افتتاحیه', 'invoice_no': 0,
                         'desc': '', 'debit': -amt if amt < 0 else 0, 'credit': amt if amt > 0 else 0,
                         'invoice_total': None})
    for inv in SalesInvoice.query.filter_by(customer_id=customer_id).all():
        entries.append({'date': inv.date, 'j_year': inv.j_year, 'j_month': inv.j_month, 'j_day': inv.j_day,
                         'currency': inv.currency or '-', 'ref': 'فروشات', 'invoice_no': inv.invoice_no or 0,
                         'desc': '', 'debit': 0, 'credit': inv.remaining or 0,
                         'invoice_total': inv.total_amount or 0})
    for r in CustomerReturn.query.filter_by(customer_id=customer_id).all():
        entries.append({'date': r.date, 'j_year': r.j_year, 'j_month': r.j_month, 'j_day': r.j_day,
                         'currency': getattr(r, 'currency', None) or '-', 'ref': 'بار برگشتی', 'invoice_no': r.return_no or 0,
                         'desc': '', 'debit': r.total_amount or 0, 'credit': 0,
                         'invoice_total': None})
    for ct in CashTransaction.query.filter_by(party_type='customer', party_id=customer_id).all():
        amt = ct.amount or 0
        entries.append({'date': ct.date, 'j_year': ct.j_year, 'j_month': ct.j_month, 'j_day': ct.j_day,
                         'currency': (ct.currency.code if ct.currency else '-'), 'ref': 'برد و رسید', 'invoice_no': 0,
                         'desc': ct.notes or '', 'debit': 0 if ct.transaction_type == 'payment' else amt,
                         'credit': amt if ct.transaction_type == 'payment' else 0, 'invoice_total': None})
    for tr in CustomerTransfer.query.filter_by(from_customer_id=customer_id).all():
        amt = tr.amount or 0
        entries.append({'date': tr.date, 'j_year': tr.j_year, 'j_month': tr.j_month, 'j_day': tr.j_day,
                         'currency': (tr.currency.code if tr.currency else '-'), 'ref': 'انتقال حساب (مبدا)', 'invoice_no': 0,
                         'desc': tr.notes or '', 'debit': 0 if tr.transaction_type == 'payment' else amt,
                         'credit': amt if tr.transaction_type == 'payment' else 0, 'invoice_total': None})
    for tr in CustomerTransfer.query.filter_by(to_customer_id=customer_id).all():
        amt = tr.amount or 0
        entries.append({'date': tr.date, 'j_year': tr.j_year, 'j_month': tr.j_month, 'j_day': tr.j_day,
                         'currency': (tr.currency.code if tr.currency else '-'), 'ref': 'انتقال حساب (مقصد)', 'invoice_no': 0,
                         'desc': tr.notes or '', 'debit': amt if tr.transaction_type == 'payment' else 0,
                         'credit': 0 if tr.transaction_type == 'payment' else amt, 'invoice_total': None})
    for cp in CustomerPayment.query.filter_by(customer_id=customer_id).all():
        amt = cp.amount or 0
        entries.append({'date': cp.date, 'j_year': cp.j_year, 'j_month': cp.j_month, 'j_day': cp.j_day,
                         'currency': (cp.pay_currency.code if cp.pay_currency else '-'), 'ref': 'برد و رسید (تبدیل ارزی)',
                         'invoice_no': 0, 'desc': cp.notes or '',
                         'debit': 0 if cp.payment_type == 'payment' else amt,
                         'credit': amt if cp.payment_type == 'payment' else 0, 'invoice_total': None})

    entries.sort(key=lambda e: e['date'])

    # فیلتر واحد پولی (اختیاری)
    currency_filter = request.args.get('currency', '').strip()
    if currency_filter:
        entries = [e for e in entries if e['currency'] == currency_filter]

    running = 0
    for e in entries:
        running += e['debit'] - e['credit']
        e['balance'] = running

    active_currencies = Currency.query.filter_by(is_active=True).order_by(Currency.code).all()
    balance = customer_balance(customer.id)

    return render_template('sale/customer_summary.html',
        customer=customer, entries=entries, active_currencies=active_currencies,
        currency_filter=currency_filter, balance=balance)


# ---- گزارش پرداختی مشتری ----
@main.route('/sale/customer-account/<int:customer_id>/payments')
def customer_payments_report(customer_id):
    customer = Customer.query.get_or_404(customer_id)

    payments = []
    for ct in CashTransaction.query.filter_by(party_type='customer', party_id=customer_id, transaction_type='receipt').all():
        payments.append({'date': ct.date, 'j_year': ct.j_year, 'j_month': ct.j_month, 'j_day': ct.j_day,
                          'amount': ct.amount or 0, 'currency': (ct.currency.code if ct.currency else '-'),
                          'notes': ct.notes or 'برد و رسید نقدی'})
    for cp in CustomerPayment.query.filter_by(customer_id=customer_id, payment_type='receipt').all():
        payments.append({'date': cp.date, 'j_year': cp.j_year, 'j_month': cp.j_month, 'j_day': cp.j_day,
                          'amount': cp.amount or 0, 'currency': (cp.pay_currency.code if cp.pay_currency else '-'),
                          'notes': cp.notes or 'برد و رسید (تبدیل ارزی)'})

    payments.sort(key=lambda p: p['date'])
    total = sum(p['amount'] for p in payments)

    return render_template('sale/customer_payments_report.html', customer=customer, payments=payments, total=total)


# ---- صورت حساب تاریخ‌وار مشتری (فیلتر بازه) ----
@main.route('/sale/customer-account/<int:customer_id>/date-range')
def customer_date_range(customer_id):
    customer = Customer.query.get_or_404(customer_id)

    from_jy = request.args.get('from_year', type=int)
    from_jm = request.args.get('from_month', type=int)
    from_jd = request.args.get('from_day', type=int)
    to_jy = request.args.get('to_year', type=int)
    to_jm = request.args.get('to_month', type=int)
    to_jd = request.args.get('to_day', type=int)

    start_date = jalali_to_gregorian(from_jy, from_jm, from_jd) if (from_jy and from_jm and from_jd) else None
    end_date = jalali_to_gregorian(to_jy, to_jm, to_jd) if (to_jy and to_jm and to_jd) else None

    entries = []
    for o in CustomerOpening.query.filter_by(customer_id=customer_id).all():
        amt = -o.amount if o.account_type == 'payable' else o.amount
        entries.append({'date': o.date, 'j_year': o.j_year, 'j_month': o.j_month, 'j_day': o.j_day,
                         'desc': 'حساب افتتاحیه', 'debit': amt if amt > 0 else 0, 'credit': -amt if amt < 0 else 0})
    for inv in SalesInvoice.query.filter_by(customer_id=customer_id).all():
        entries.append({'date': inv.date, 'j_year': inv.j_year, 'j_month': inv.j_month, 'j_day': inv.j_day,
                         'desc': f'فاکتور فروش #{inv.invoice_no}', 'debit': inv.remaining or 0, 'credit': 0})
    for r in CustomerReturn.query.filter_by(customer_id=customer_id).all():
        entries.append({'date': r.date, 'j_year': r.j_year, 'j_month': r.j_month, 'j_day': r.j_day,
                         'desc': f'بار برگشتی مشتری #{r.return_no}', 'debit': 0, 'credit': r.total_amount or 0})
    for ct in CashTransaction.query.filter_by(party_type='customer', party_id=customer_id).all():
        amt = ct.amount or 0
        entries.append({'date': ct.date, 'j_year': ct.j_year, 'j_month': ct.j_month, 'j_day': ct.j_day,
                         'desc': 'برد و رسید نقدی',
                         'debit': amt if ct.transaction_type == 'payment' else 0,
                         'credit': 0 if ct.transaction_type == 'payment' else amt})
    for tr in CustomerTransfer.query.filter_by(from_customer_id=customer_id).all():
        amt = tr.amount or 0
        entries.append({'date': tr.date, 'j_year': tr.j_year, 'j_month': tr.j_month, 'j_day': tr.j_day,
                         'desc': 'انتقال حساب (مبدا)',
                         'debit': amt if tr.transaction_type == 'payment' else 0,
                         'credit': 0 if tr.transaction_type == 'payment' else amt})
    for tr in CustomerTransfer.query.filter_by(to_customer_id=customer_id).all():
        amt = tr.amount or 0
        entries.append({'date': tr.date, 'j_year': tr.j_year, 'j_month': tr.j_month, 'j_day': tr.j_day,
                         'desc': 'انتقال حساب (مقصد)',
                         'debit': 0 if tr.transaction_type == 'payment' else amt,
                         'credit': amt if tr.transaction_type == 'payment' else 0})
    for cp in CustomerPayment.query.filter_by(customer_id=customer_id).all():
        amt = cp.amount or 0
        entries.append({'date': cp.date, 'j_year': cp.j_year, 'j_month': cp.j_month, 'j_day': cp.j_day,
                         'desc': 'برد و رسید (تبدیل ارزی)',
                         'debit': amt if cp.payment_type == 'payment' else 0,
                         'credit': 0 if cp.payment_type == 'payment' else amt})

    entries.sort(key=lambda e: e['date'])

    if start_date:
        entries = [e for e in entries if e['date'] >= start_date]
    if end_date:
        entries = [e for e in entries if e['date'] <= end_date]

    running = 0
    for e in entries:
        e['amount'] = (e['credit'] or 0) - (e['debit'] or 0)
        running += e['amount']
        e['balance'] = running

    today = jdatetime.date.today()
    return render_template('sale/customer_date_range.html',
        customer=customer, entries=entries, today=today,
        from_year=from_jy, from_month=from_jm, from_day=from_jd,
        to_year=to_jy, to_month=to_jm, to_day=to_jd)


# ---- صورت حساب فاکتور وار (لیست فاکتورهای مشتری) ----
@main.route('/sale/customer-account/<int:customer_id>/invoices')
def customer_invoice_statement(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    invoices = SalesInvoice.query.filter_by(customer_id=customer_id).order_by(SalesInvoice.invoice_no).all()
    total_amount = sum(inv.total_amount or 0 for inv in invoices)
    total_paid = sum(inv.paid_amount or 0 for inv in invoices)
    total_remaining = sum(inv.remaining or 0 for inv in invoices)
    return render_template('sale/customer_invoice_statement.html',
        customer=customer, invoices=invoices,
        total_amount=total_amount, total_paid=total_paid, total_remaining=total_remaining)


# ---- صورت حساب جزوار مشتری (ردیف‌های کالای هر فاکتور) ----
@main.route('/sale/customer-account/<int:customer_id>/itemized')
def customer_itemized_statement(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    invoices = SalesInvoice.query.filter_by(customer_id=customer_id).order_by(SalesInvoice.invoice_no).all()

    rows = []
    for inv in invoices:
        for line in sorted(inv.lines, key=lambda l: l.row_no or 0):
            rows.append({
                'invoice_no': inv.invoice_no, 'j_year': inv.j_year, 'j_month': inv.j_month, 'j_day': inv.j_day,
                'item_name': line.item_name, 'quantity_id': line.unit.quantity if line.unit else '',
                'amount': line.amount or 0, 'count_desc': line.count_desc, 'price': line.price or 0,
                'total': line.total or 0,
            })

    grand_total = sum(r['total'] for r in rows)
    return render_template('sale/customer_itemized_statement.html', customer=customer, rows=rows, grand_total=grand_total)


# ==========================================
# مشتریان — حساب افتتاحیه مشتری
# ==========================================
@main.route('/sale/customer-opening', methods=['GET', 'POST'])
def customer_opening():
    edit_id = request.args.get('edit', type=int)
    edit_co = CustomerOpening.query.get(edit_id) if edit_id else None

    if request.method == 'POST':
        jy = request.form.get('j_year', type=int)
        jm = request.form.get('j_month', type=int)
        jd = request.form.get('j_day', type=int)
        g_date = jalali_to_gregorian(jy, jm, jd)

        customer_name = request.form.get('customer_name', '').strip()
        customer = Customer.query.filter_by(name=customer_name).first()
        currency = request.form.get('currency', '').strip()
        amount = request.form.get('amount', type=float) or 0
        account_type = request.form.get('account_type', '').strip()
        co_id = request.form.get('co_id', type=int)

        if not customer or not g_date:
            flash('نام مشتری (از لیست) و تاریخ الزامی است', 'danger')
        elif co_id:
            co = CustomerOpening.query.get_or_404(co_id)
            co.date, co.j_year, co.j_month, co.j_day = g_date, jy, jm, jd
            co.customer_id, co.currency = customer.id, currency
            co.amount, co.account_type = amount, account_type
            db.session.commit()
            flash('حساب افتتاحیه ویرایش شد', 'success')
        else:
            db.session.add(CustomerOpening(
                date=g_date, j_year=jy, j_month=jm, j_day=jd,
                customer_id=customer.id, currency=currency,
                amount=amount, account_type=account_type
            ))
            db.session.commit()
            flash('حساب افتتاحیه ثبت شد', 'success')
        return redirect(url_for('main.customer_opening'))

    search = request.args.get('q', '').strip()
    query = CustomerOpening.query
    if search:
        query = query.join(Customer).filter(Customer.name.contains(search))
    records = query.order_by(CustomerOpening.id).all()

    customer_list = Customer.query.order_by(Customer.name).all()
    today = jdatetime.date.today()

    return render_template('sale/customer_opening.html',
        records=records, edit_co=edit_co, customer_list=customer_list, today=today, search=search)


@main.route('/sale/customer-opening/delete/<int:id>')
def customer_opening_delete(id):
    co = CustomerOpening.query.get_or_404(id)
    db.session.delete(co)
    db.session.commit()
    flash('رکورد حذف شد', 'success')
    return redirect(url_for('main.customer_opening'))


# ==========================================
# مشتریان — ثبت سفارشات
# ==========================================
@main.route('/sale/orders', methods=['GET', 'POST'])
def customer_orders():
    edit_id = request.args.get('edit', type=int)
    edit_o = CustomerOrder.query.get(edit_id) if edit_id else None

    if request.method == 'POST':
        jy = request.form.get('j_year', type=int)
        jm = request.form.get('j_month', type=int)
        jd = request.form.get('j_day', type=int)
        g_date = jalali_to_gregorian(jy, jm, jd)

        customer_name = request.form.get('customer_name', '').strip()
        customer = Customer.query.filter_by(name=customer_name).first()
        o_id = request.form.get('o_id', type=int)
        time_str = jdatetime.datetime.now().strftime('%H:%M:%S')

        row_indexes = set()
        for key in request.form.keys():
            if key.startswith('row_item_'):
                row_indexes.add(int(key.replace('row_item_', '')))

        rows = []
        total_amount = 0
        for i in sorted(row_indexes):
            row_item_id = request.form.get(f'row_item_{i}', type=int)
            if not row_item_id:
                continue
            row_item_obj = Item.query.get(row_item_id)
            row_stock_id = request.form.get(f'row_stock_{i}', type=int)
            row_quantity_id = request.form.get(f'row_quantity_{i}', type=int)
            row_available = request.form.get(f'row_available_{i}', type=float) or 0
            row_price = request.form.get(f'row_price_{i}', type=float) or 0
            row_amount = request.form.get(f'row_amount_{i}', type=float) or 0
            row_count_raw = request.form.get(f'row_count_{i}', '').strip()

            # اگر «تعداد» عدد داده شده باشد: جمع = تعداد × فی، و رزرو/کسر گدام هم بر اساس همان تعداد است
            # اگر «تعداد» خالی باشد: جمع = مقدار وزن × فی (حالت ساده)، و رزرو/کسر گدام بر اساس وزن است
            try:
                row_count_num = float(row_count_raw) if row_count_raw else None
            except ValueError:
                row_count_num = None

            if row_count_num:
                row_total = row_count_num * row_price
            else:
                row_total = row_amount * row_price
            total_amount += row_total

            rows.append(dict(
                item_name=row_item_obj.name if row_item_obj else '',
                stock_id=row_stock_id, quantity_id=row_quantity_id,
                available_qty=row_available, price=row_price, amount=row_amount,
                count_desc=row_count_raw, total=row_total, row_no=i
            ))

        if not customer or not g_date or not rows:
            flash('مشتری، تاریخ و حداقل یک کالا الزامی است', 'danger')
        else:
            if o_id:
                order = CustomerOrder.query.get_or_404(o_id)
                # آزاد کردن رزرو قبلی این سفارش قبل از اعمال مقدار جدید (فقط اگر هنوز در انتظار است)
                if order.status == 'pending':
                    for old_line in order.lines:
                        adjust_reservation(old_line.item_name, old_line.stock_id, -sales_line_stock_qty(old_line))

                order.date, order.j_year, order.j_month, order.j_day = g_date, jy, jm, jd
                order.customer_id, order.total_amount = customer.id, total_amount

                CustomerOrderLine.query.filter_by(order_id=order.id).delete()
                for r in rows:
                    db.session.add(CustomerOrderLine(order_id=order.id, **r))
                    if order.status == 'pending':
                        adjust_reservation(r['item_name'], r['stock_id'], sales_line_stock_qty(r),
                                            quantity_id=r['quantity_id'])
                db.session.commit()
                flash('سفارش ویرایش شد', 'success')
            else:
                last = CustomerOrder.query.order_by(CustomerOrder.order_no.desc()).first()
                next_no = (last.order_no + 1) if (last and last.order_no) else 1

                order = CustomerOrder(
                    order_no=next_no, time_str=time_str,
                    date=g_date, j_year=jy, j_month=jm, j_day=jd,
                    customer_id=customer.id, total_amount=total_amount, status='pending'
                )
                db.session.add(order)
                db.session.flush()

                for r in rows:
                    db.session.add(CustomerOrderLine(order_id=order.id, **r))
                    # رزرو موجودی برای این سفارش (موجودی فیزیکی دست نمی‌خورد) — بر اساس تعداد اگر پر شده، وگرنه وزن
                    adjust_reservation(r['item_name'], r['stock_id'], sales_line_stock_qty(r),
                                        quantity_id=r['quantity_id'])

                db.session.commit()
                flash('سفارش ثبت شد و موجودی رزرو شد', 'success')
        return redirect(url_for('main.customer_orders'))

    records = CustomerOrder.query.order_by(CustomerOrder.id).all()
    customer_list = Customer.query.order_by(Customer.name).all()
    stocks = Stock.query.order_by(Stock.name).all()
    units = Quantity.query.order_by(Quantity.quantity).all()
    items = Item.query.filter_by(is_active=True).order_by(Item.name).all()
    today = jdatetime.date.today()

    edit_lines = {}
    if edit_o:
        for l in edit_o.lines:
            edit_lines[l.row_no] = l

    return render_template('sale/orders.html',
        records=records, edit_o=edit_o, edit_lines=edit_lines,
        customer_list=customer_list, stocks=stocks, units=units, items=items, today=today)


@main.route('/sale/orders/item-info/<int:item_id>')
def order_item_info(item_id):
    """موجودی قابل‌فروش (فیزیکی منهای رزروشده) یک کالا را برمی‌گرداند."""
    from flask import jsonify
    item = Item.query.get(item_id)
    if not item:
        return jsonify({'found': False})

    record = (StockBalance.query
              .filter_by(item_name=item.name)
              .order_by(StockBalance.current_qty.desc())
              .first())
    if not record:
        return jsonify({'found': False})

    available = (record.current_qty or 0) - (record.reserved_qty or 0)
    return jsonify({
        'found': True,
        'stock_id': record.stock_id or '',
        'quantity_id': record.quantity_id or '',
        'available_qty': available
    })


@main.route('/sale/orders/cancel/<int:id>')
def customer_order_cancel(id):
    order = CustomerOrder.query.get_or_404(id)
    if order.status == 'pending':
        for line in order.lines:
            adjust_reservation(line.item_name, line.stock_id, -sales_line_stock_qty(line))
        order.status = 'cancelled'
        db.session.commit()
        flash('سفارش لغو شد و رزرو موجودی آزاد شد', 'success')
    return redirect(url_for('main.customer_orders'))


@main.route('/sale/orders/complete/<int:id>')
def customer_order_complete(id):
    """
    سفارش را 'انجام شد' می‌کند: رزرو آزاد می‌شود و هم‌زمان موجودی فیزیکی واقعاً کسر می‌شود.
    (موقتاً دستی — بعداً وقتی فاکتور فروش ساخته شود، این اتفاق خودکار با صدور فاکتور می‌افتد.)
    """
    order = CustomerOrder.query.get_or_404(id)
    if order.status == 'pending':
        for line in order.lines:
            qty = sales_line_stock_qty(line)
            adjust_reservation(line.item_name, line.stock_id, -qty)  # آزاد کردن رزرو
            adjust_balance(line.item_name, line.stock_id, -qty)       # کسر قطعی از موجودی فیزیکی
        order.status = 'invoiced'
        db.session.commit()
        flash('سفارش انجام شد و از موجودی کسر شد', 'success')
    return redirect(url_for('main.customer_orders'))


@main.route('/sale/orders/delete/<int:id>')
def customer_order_delete(id):
    order = CustomerOrder.query.get_or_404(id)
    if order.status == 'pending':
        for line in order.lines:
            adjust_reservation(line.item_name, line.stock_id, -sales_line_stock_qty(line))
    db.session.delete(order)
    db.session.commit()
    flash('سفارش حذف شد', 'success')
    return redirect(url_for('main.customer_orders'))


# ==========================================
# مشتریان — ثبت فاکتور فروش
# ==========================================
@main.route('/sale/invoices', methods=['GET', 'POST'])
def sales_invoices():
    edit_id = request.args.get('edit', type=int)
    edit_inv = SalesInvoice.query.get(edit_id) if edit_id else None

    if request.method == 'POST':
        jy = request.form.get('j_year', type=int)
        jm = request.form.get('j_month', type=int)
        jd = request.form.get('j_day', type=int)
        g_date = jalali_to_gregorian(jy, jm, jd)

        customer_name = request.form.get('customer_name', '').strip()
        customer = Customer.query.filter_by(name=customer_name).first()
        bank_id = request.form.get('bank_id', type=int)
        bank_obj = Bank.query.get(bank_id) if bank_id else None
        bank_name = bank_obj.name if bank_obj else request.form.get('bank_name', '').strip()
        currency = request.form.get('currency', '').strip()
        exchange_rate = request.form.get('exchange_rate', type=float) or 1
        delivery = request.form.get('delivery', '').strip()
        order_ref_id = request.form.get('order_ref_id', type=int) or None
        loading_fee = request.form.get('loading_fee', type=float) or 0
        discount = request.form.get('discount', type=float) or 0
        paid_amount = request.form.get('paid_amount', type=float) or 0
        notes = request.form.get('notes', '').strip()
        inv_id = request.form.get('inv_id', type=int)
        time_str = jdatetime.datetime.now().strftime('%H:%M:%S')

        row_indexes = set()
        for key in request.form.keys():
            if key.startswith('row_item_'):
                row_indexes.add(int(key.replace('row_item_', '')))

        rows = []
        total_amount = 0
        for i in sorted(row_indexes):
            row_item_id = request.form.get(f'row_item_{i}', type=int)
            if not row_item_id:
                continue
            row_item_obj = Item.query.get(row_item_id)
            row_stock_id = request.form.get(f'row_stock_{i}', type=int)
            row_quantity_id = request.form.get(f'row_quantity_{i}', type=int)
            row_available = request.form.get(f'row_available_{i}', type=float) or 0
            row_price = request.form.get(f'row_price_{i}', type=float) or 0
            row_amount = request.form.get(f'row_amount_{i}', type=float) or 0
            row_count_raw = request.form.get(f'row_count_{i}', '').strip()

            # اگر «تعداد» عدد داده شده باشد: جمع = تعداد × فی (فی به‌ازای هر واحد/کارتن است)
            # اگر «تعداد» خالی باشد: جمع = مقدار وزن × فی (حالت ساده، فی به‌ازای هر کیلو/واحد است)
            try:
                row_count_num = float(row_count_raw) if row_count_raw else None
            except ValueError:
                row_count_num = None

            if row_count_num:
                row_total = row_count_num * row_price
            else:
                row_total = row_amount * row_price
            total_amount += row_total

            rows.append(dict(
                item_name=row_item_obj.name if row_item_obj else '',
                stock_id=row_stock_id, quantity_id=row_quantity_id,
                available_qty=row_available, price=row_price, amount=row_amount,
                count_desc=row_count_raw, total=row_total, row_no=i
            ))

        total_amount_usd = (total_amount / exchange_rate) if (currency != 'USD' and exchange_rate) else total_amount
        remaining = total_amount + loading_fee - discount - paid_amount

        if not customer or not g_date or not rows:
            flash('مشتری، تاریخ و حداقل یک کالا الزامی است', 'danger')
        else:
            if inv_id:
                inv = SalesInvoice.query.get_or_404(inv_id)
                # برگرداندن اثر قبلی این فاکتور روی موجودی (افزایش، چون قبلاً کم شده بود)
                for old_line in inv.lines:
                    adjust_balance(old_line.item_name, old_line.stock_id, sales_line_stock_qty(old_line))

                # برگرداندن اثر قبلی پرداخت این فاکتور از موجودی بانک قبل از اعمال مقدار جدید
                if inv.bank_id and inv.paid_amount:
                    old_currency_id = _currency_code_to_id(inv.currency)
                    adjust_bank_balance(inv.bank_id, old_currency_id, -inv.paid_amount,
                                         notes='برگشت دریافتی فاکتور فروش (ویرایش)')

                inv.date, inv.j_year, inv.j_month, inv.j_day = g_date, jy, jm, jd
                inv.customer_id, inv.bank_id, inv.bank_name = customer.id, bank_id, bank_name
                inv.currency, inv.exchange_rate, inv.delivery = currency, exchange_rate, delivery
                inv.order_ref_id = order_ref_id
                inv.total_amount, inv.total_amount_usd = total_amount, total_amount_usd
                inv.loading_fee, inv.discount = loading_fee, discount
                inv.paid_amount, inv.remaining, inv.notes = paid_amount, remaining, notes

                if bank_id and paid_amount:
                    new_currency_id = _currency_code_to_id(currency)
                    adjust_bank_balance(bank_id, new_currency_id, paid_amount, g_date=g_date,
                                         notes=f'دریافتی فاکتور فروش #{inv.invoice_no} — {customer.name}' + ' (ویرایش)')

                SalesInvoiceLine.query.filter_by(invoice_id=inv.id).delete()
                for r in rows:
                    db.session.add(SalesInvoiceLine(invoice_id=inv.id, **r))
                    unit_price_usd = (r['price'] / exchange_rate) if (currency != 'USD' and exchange_rate) else r['price']
                    adjust_balance(r['item_name'], r['stock_id'], -sales_line_stock_qty(r),
                                    price=unit_price_usd, quantity_id=r['quantity_id'])
                db.session.commit()
                flash('فاکتور فروش ویرایش شد', 'success')
            else:
                last = SalesInvoice.query.order_by(SalesInvoice.invoice_no.desc()).first()
                next_no = (last.invoice_no + 1) if (last and last.invoice_no) else 1

                inv = SalesInvoice(
                    invoice_no=next_no, time_str=time_str,
                    date=g_date, j_year=jy, j_month=jm, j_day=jd,
                    customer_id=customer.id, bank_id=bank_id, bank_name=bank_name,
                    currency=currency, exchange_rate=exchange_rate, delivery=delivery,
                    order_ref_id=order_ref_id,
                    total_amount=total_amount, total_amount_usd=total_amount_usd,
                    loading_fee=loading_fee, discount=discount,
                    paid_amount=paid_amount, remaining=remaining, notes=notes,
                    created_by=session.get('username')
                )
                db.session.add(inv)
                db.session.flush()

                if bank_id and paid_amount:
                    currency_id = _currency_code_to_id(currency)
                    adjust_bank_balance(bank_id, currency_id, paid_amount, g_date=g_date,
                                         notes=f'دریافتی فاکتور فروش #{inv.invoice_no} — {customer.name}')

                for r in rows:
                    db.session.add(SalesInvoiceLine(invoice_id=inv.id, **r))
                    unit_price_usd = (r['price'] / exchange_rate) if (currency != 'USD' and exchange_rate) else r['price']
                    # کسر قطعی از موجودی فیزیکی (بر اساس تعداد اگر پر شده باشد، وگرنه وزن)
                    adjust_balance(r['item_name'], r['stock_id'], -sales_line_stock_qty(r),
                                    price=unit_price_usd, quantity_id=r['quantity_id'])
                    # اگر این فاکتور از یک سفارش آمده، رزرو همان مقدار را آزاد کن (بر اساس تعداد اگر پر شده، وگرنه وزن)
                    if order_ref_id:
                        adjust_reservation(r['item_name'], r['stock_id'], -sales_line_stock_qty(r))

                # اگر فاکتور به سفارشی وصل است، آن سفارش را invoiced علامت بزن
                if order_ref_id:
                    order = CustomerOrder.query.get(order_ref_id)
                    if order and order.status == 'pending':
                        order.status = 'invoiced'
                        order.invoice_ref = str(next_no)

                db.session.commit()
                flash('فاکتور فروش ثبت شد', 'success')
        return redirect(url_for('main.sales_invoices'))

    records = SalesInvoice.query.order_by(SalesInvoice.id).all()
    customer_list = Customer.query.order_by(Customer.name).all()
    stocks = Stock.query.order_by(Stock.name).all()
    units = Quantity.query.order_by(Quantity.quantity).all()
    items = Item.query.filter_by(is_active=True).order_by(Item.name).all()
    pending_orders = CustomerOrder.query.filter_by(status='pending').order_by(CustomerOrder.order_no).all()
    bank_list = Bank.query.filter_by(is_active=True).order_by(Bank.name).all()
    active_currencies = Currency.query.filter_by(is_active=True).order_by(Currency.code).all()
    today = jdatetime.date.today()

    edit_lines = {}
    if edit_inv:
        for l in edit_inv.lines:
            edit_lines[l.row_no] = l

    return render_template('sale/invoices.html',
        records=records, edit_inv=edit_inv, edit_lines=edit_lines,
        customer_list=customer_list, stocks=stocks, units=units, items=items,
        pending_orders=pending_orders, bank_list=bank_list, active_currencies=active_currencies,
        today=today)


@main.route('/sale/invoices/item-info/<int:item_id>')
def sales_item_info(item_id):
    """موجودی قابل‌فروش (فیزیکی منهای رزروشده) یک کالا را برمی‌گرداند."""
    from flask import jsonify
    item = Item.query.get(item_id)
    if not item:
        return jsonify({'found': False})

    record = (StockBalance.query
              .filter_by(item_name=item.name)
              .order_by(StockBalance.current_qty.desc())
              .first())
    if not record:
        return jsonify({'found': False})

    available = (record.current_qty or 0) - (record.reserved_qty or 0)
    return jsonify({
        'found': True,
        'stock_id': record.stock_id or '',
        'quantity_id': record.quantity_id or '',
        'available_qty': available
    })


@main.route('/sale/invoices/order-lines/<int:order_id>')
def sales_order_lines(order_id):
    """ردیف‌های یک سفارش مشتری را برمی‌گرداند تا در فاکتور فروش خودکار پر شوند."""
    from flask import jsonify
    order = CustomerOrder.query.get(order_id)
    if not order:
        return jsonify({'found': False})

    lines = []
    for l in order.lines:
        item = Item.query.filter_by(name=l.item_name).first()
        lines.append({
            'item_id': item.id if item else None,
            'item_name': l.item_name,
            'stock_id': l.stock_id,
            'quantity_id': l.quantity_id,
            'available_qty': l.available_qty,
            'price': l.price,
            'amount': l.amount,
            'count_desc': l.count_desc,
        })
    return jsonify({'found': True, 'lines': lines, 'customer_name': order.customer.name if order.customer else ''})


@main.route('/sale/invoices/print/<int:id>')
def sales_invoice_print(id):
    inv = SalesInvoice.query.get_or_404(id)
    total_words = number_to_persian_words(inv.total_amount)
    g_date_str = inv.date.strftime('%Y-%m-%d') if inv.date else ''

    total_weight = 0
    for l in inv.lines:
        try:
            count_num = float(l.count_desc) if l.count_desc else None
        except ValueError:
            count_num = None
        total_weight += (l.amount or 0) * count_num if count_num else (l.amount or 0)

    current_balance = customer_balance_as_of(inv.customer_id, inv) if inv.customer_id else 0
    # customer_balance_as_of اکنون منفی=بدهکار برمی‌گرداند، پس سهم این فاکتور در مانده هم منفی شده؛
    # برای برداشتنِ همان سهم و رسیدن به مانده‌ی قبلی، باید آن را جمع کنیم (نه کم).
    previous_balance = current_balance + (inv.remaining or 0)
    return render_template('sale/invoice_print.html', inv=inv, total_words=total_words, g_date_str=g_date_str,
                            total_weight=total_weight, previous_balance=previous_balance, current_balance=current_balance)


@main.route('/sale/invoices/warehouse-check/<int:id>')
def sales_invoice_warehouse_check(id):
    """چک گدام (حواله انبار) — سند جدا از فاکتور مالی برای تحویل کالا توسط گدامدار."""
    inv = SalesInvoice.query.get_or_404(id)
    item_count = len(inv.lines)
    return render_template('sale/warehouse_check.html', inv=inv, item_count=item_count)


@main.route('/sale/invoices/delete/<int:id>')
def sales_invoice_delete(id):
    inv = SalesInvoice.query.get_or_404(id)
    for line in inv.lines:
        adjust_balance(line.item_name, line.stock_id, sales_line_stock_qty(line))  # برگرداندن موجودی
    if inv.bank_id and inv.paid_amount:
        currency_id = _currency_code_to_id(inv.currency)
        adjust_bank_balance(inv.bank_id, currency_id, -inv.paid_amount,
                             notes='برگشت دریافتی فاکتور فروش (حذف)')
    db.session.delete(inv)
    db.session.commit()
    flash('فاکتور حذف شد', 'success')
    return redirect(url_for('main.sales_invoices'))


# ==========================================
# مشتریان — بار برگشتی مشتری (مرجوعی)
# دقیقاً مثل فاکتور فروش عمل می‌کند (همان ساختار ردیف‌ها: مقدار وزن + تعداد)
# اما محاسبه برعکس فاکتور فروش است:
#   - کالای برگشتی به موجودی گدام اضافه می‌شود (نه کسر)
#   - طلب ما از مشتری به اندازه مبلغ برگشتی کم می‌شود (نه زیاد)
# ==========================================
@main.route('/sale/returns', methods=['GET', 'POST'])
def customer_returns():
    edit_id = request.args.get('edit', type=int)
    edit_ret = CustomerReturn.query.get(edit_id) if edit_id else None

    if request.method == 'POST':
        jy = request.form.get('j_year', type=int)
        jm = request.form.get('j_month', type=int)
        jd = request.form.get('j_day', type=int)
        g_date = jalali_to_gregorian(jy, jm, jd)

        customer_name = request.form.get('customer_name', '').strip()
        customer = Customer.query.filter_by(name=customer_name).first()
        currency = request.form.get('currency', '').strip()
        exchange_rate = request.form.get('exchange_rate', type=float) or 1
        notes = request.form.get('notes', '').strip()
        ret_id = request.form.get('ret_id', type=int)
        time_str = jdatetime.datetime.now().strftime('%H:%M:%S')

        row_indexes = set()
        for key in request.form.keys():
            if key.startswith('row_item_'):
                row_indexes.add(int(key.replace('row_item_', '')))

        rows = []
        total_amount = 0
        for i in sorted(row_indexes):
            row_item_id = request.form.get(f'row_item_{i}', type=int)
            if not row_item_id:
                continue
            row_item_obj = Item.query.get(row_item_id)
            row_stock_id = request.form.get(f'row_stock_{i}', type=int)
            row_quantity_id = request.form.get(f'row_quantity_{i}', type=int)
            row_available = request.form.get(f'row_available_{i}', type=float) or 0
            row_price = request.form.get(f'row_price_{i}', type=float) or 0
            row_amount = request.form.get(f'row_amount_{i}', type=float) or 0
            row_count_raw = request.form.get(f'row_count_{i}', '').strip()
            try:
                row_count_num = float(row_count_raw) if row_count_raw else None
            except ValueError:
                row_count_num = None
            if row_count_num:
                row_total = row_count_num * row_price
            else:
                row_total = row_amount * row_price
            total_amount += row_total
            rows.append(dict(
                item_name=row_item_obj.name if row_item_obj else '',
                stock_id=row_stock_id, quantity_id=row_quantity_id,
                available_qty=row_available, price=row_price, amount=row_amount,
                count_desc=row_count_raw, total=row_total, row_no=i
            ))

        total_amount_usd = (total_amount / exchange_rate) if (currency != 'USD' and exchange_rate) else total_amount

        if not customer or not g_date or not rows:
            flash('مشتری، تاریخ و حداقل یک کالا الزامی است', 'danger')
        else:
            if ret_id:
                ret = CustomerReturn.query.get_or_404(ret_id)
                # برگرداندن اثر قبلی این بار برگشتی از موجودی گدام (قبلاً اضافه شده بود، دوباره کم می‌شود)
                for old_line in ret.lines:
                    adjust_balance(old_line.item_name, old_line.stock_id, -sales_line_stock_qty(old_line))

                ret.date, ret.j_year, ret.j_month, ret.j_day = g_date, jy, jm, jd
                ret.customer_id = customer.id
                ret.currency, ret.exchange_rate = currency, exchange_rate
                ret.total_amount, ret.total_amount_usd = total_amount, total_amount_usd
                ret.notes = notes

                CustomerReturnLine.query.filter_by(return_id=ret.id).delete()
                for r in rows:
                    line = CustomerReturnLine(return_id=ret.id, **r)
                    db.session.add(line)
                    unit_price_usd = (r['price'] / exchange_rate) if (currency != 'USD' and exchange_rate) else r['price']
                    # افزایش موجودی گدام (کالا از مشتری برگشته)
                    adjust_balance(r['item_name'], r['stock_id'], sales_line_stock_qty(r),
                                    price=unit_price_usd, quantity_id=r['quantity_id'])
                db.session.commit()
                flash('بار برگشتی مشتری ویرایش شد', 'success')
            else:
                last = CustomerReturn.query.order_by(CustomerReturn.return_no.desc()).first()
                next_no = (last.return_no + 1) if (last and last.return_no) else 1

                ret = CustomerReturn(
                    return_no=next_no, time_str=time_str,
                    date=g_date, j_year=jy, j_month=jm, j_day=jd,
                    customer_id=customer.id, currency=currency, exchange_rate=exchange_rate,
                    total_amount=total_amount, total_amount_usd=total_amount_usd, notes=notes,
                    created_by=session.get('username')
                )
                db.session.add(ret)
                db.session.flush()

                for r in rows:
                    db.session.add(CustomerReturnLine(return_id=ret.id, **r))
                    unit_price_usd = (r['price'] / exchange_rate) if (currency != 'USD' and exchange_rate) else r['price']
                    # افزایش موجودی گدام (کالا از مشتری برگشته)
                    adjust_balance(r['item_name'], r['stock_id'], sales_line_stock_qty(r),
                                    price=unit_price_usd, quantity_id=r['quantity_id'])

                db.session.commit()
                flash('بار برگشتی مشتری ثبت شد', 'success')
        return redirect(url_for('main.customer_returns'))

    records = CustomerReturn.query.order_by(CustomerReturn.id).all()
    customer_list = Customer.query.order_by(Customer.name).all()
    stocks = Stock.query.order_by(Stock.name).all()
    units = Quantity.query.order_by(Quantity.quantity).all()
    items = Item.query.filter_by(is_active=True).order_by(Item.name).all()
    today = jdatetime.date.today()

    edit_lines = {}
    if edit_ret:
        for l in edit_ret.lines:
            edit_lines[l.row_no] = l

    return render_template('sale/customer_return.html',
        records=records, edit_ret=edit_ret, edit_lines=edit_lines,
        customer_list=customer_list, stocks=stocks, units=units, items=items, today=today)


@main.route('/sale/returns/print/<int:id>')
def customer_return_print(id):
    ret = CustomerReturn.query.get_or_404(id)
    total_words = number_to_persian_words(ret.total_amount)
    g_date_str = ret.date.strftime('%Y-%m-%d') if ret.date else ''

    total_weight = 0
    for l in ret.lines:
        try:
            count_num = float(l.count_desc) if l.count_desc else None
        except ValueError:
            count_num = None
        total_weight += (l.amount or 0) * count_num if count_num else (l.amount or 0)

    current_balance = customer_balance_as_of(ret.customer_id, ret) if ret.customer_id else 0
    # customer_balance_as_of اکنون منفی=بدهکار برمی‌گرداند، پس سهم بار برگشتی در مانده هم برعکس شده؛
    # برای برداشتنِ همان سهم و رسیدن به مانده‌ی قبلی، باید آن را کم کنیم (نه جمع).
    previous_balance = current_balance - (ret.total_amount or 0)
    return render_template('sale/customer_return_print.html', ret=ret, total_words=total_words, g_date_str=g_date_str,
                            total_weight=total_weight, previous_balance=previous_balance, current_balance=current_balance)


@main.route('/sale/returns/delete/<int:id>')
def customer_return_delete(id):
    ret = CustomerReturn.query.get_or_404(id)
    for line in ret.lines:
        # برگرداندن اثر افزایش موجودی: کالا دوباره از گدام کم می‌شود
        adjust_balance(line.item_name, line.stock_id, -sales_line_stock_qty(line))
    db.session.delete(ret)
    db.session.commit()
    flash('بار برگشتی حذف شد', 'success')
    return redirect(url_for('main.customer_returns'))


# ==========================================
# بانک‌ها — ثبت واحدپولی
# ==========================================
@main.route('/treasury/currency', methods=['GET', 'POST'])
def currency_registration():
    edit_id = request.args.get('edit', type=int)
    edit_cur = Currency.query.get(edit_id) if edit_id else None

    if request.method == 'POST':
        currency_id = request.form.get('currency_id', type=int)
        is_active = request.form.get('is_active') == '1'

        cur = Currency.query.get(currency_id) if currency_id else None
        if not cur:
            flash('واحدپولی معتبر انتخاب کنید', 'danger')
        else:
            cur.is_active = is_active
            db.session.commit()
            flash('واحدپولی ذخیره شد', 'success')
        return redirect(url_for('main.currency_registration'))

    search = request.args.get('q', '').strip()
    query = Currency.query
    if search:
        query = query.filter(Currency.country_name.contains(search) | Currency.code.contains(search))
    currency_list = query.order_by(Currency.country_name).all()
    all_currencies = Currency.query.order_by(Currency.country_name).all()

    return render_template('treasury/currency.html',
        currency_list=currency_list, all_currencies=all_currencies, edit_cur=edit_cur, search=search)


# ==========================================
# بانک‌ها — نرخ واحدپولی
# ==========================================
@main.route('/treasury/currency-rate', methods=['GET', 'POST'])
def currency_rate():
    edit_id = request.args.get('edit', type=int)
    edit_cr = CurrencyRate.query.get(edit_id) if edit_id else None

    if request.method == 'POST':
        jy = request.form.get('j_year', type=int)
        jm = request.form.get('j_month', type=int)
        jd = request.form.get('j_day', type=int)
        g_date = jalali_to_gregorian(jy, jm, jd)

        currency_id = request.form.get('currency_id', type=int)
        rate = request.form.get('rate', type=float) or 0
        cr_id = request.form.get('cr_id', type=int)

        if not currency_id or not g_date or not rate:
            flash('واحدپولی، نرخ و تاریخ الزامی است', 'danger')
        elif cr_id:
            cr = CurrencyRate.query.get_or_404(cr_id)
            cr.date, cr.j_year, cr.j_month, cr.j_day = g_date, jy, jm, jd
            cr.currency_id, cr.rate = currency_id, rate
            db.session.commit()
            flash('نرخ ویرایش شد', 'success')
        else:
            db.session.add(CurrencyRate(
                date=g_date, j_year=jy, j_month=jm, j_day=jd,
                currency_id=currency_id, rate=rate
            ))
            db.session.commit()
            flash('نرخ ثبت شد', 'success')
        return redirect(url_for('main.currency_rate'))

    search = request.args.get('q', '').strip()
    query = CurrencyRate.query
    if search:
        query = query.join(Currency).filter(Currency.code.contains(search))
    records = query.order_by(CurrencyRate.id).all()

    active_currencies = Currency.query.filter_by(is_active=True).order_by(Currency.code).all()
    today = jdatetime.date.today()

    return render_template('treasury/currency_rate.html',
        records=records, edit_cr=edit_cr, active_currencies=active_currencies, today=today, search=search)


@main.route('/treasury/currency-rate/delete/<int:id>')
def currency_rate_delete(id):
    cr = CurrencyRate.query.get_or_404(id)
    db.session.delete(cr)
    db.session.commit()
    flash('رکورد حذف شد', 'success')
    return redirect(url_for('main.currency_rate'))


# ==========================================
# بانک‌ها — ثبت بانک
# ==========================================
@main.route('/treasury/banks', methods=['GET', 'POST'])
def banks():
    edit_id = request.args.get('edit', type=int)
    edit_b = Bank.query.get(edit_id) if edit_id else None

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        account_no = request.form.get('account_no', '').strip()
        branch = request.form.get('branch', '').strip()
        currency_id = request.form.get('currency_id', type=int)
        b_id = request.form.get('b_id', type=int)

        if not name:
            flash('نام بانک نمی‌تواند خالی باشد', 'danger')
        elif b_id:
            b = Bank.query.get_or_404(b_id)
            b.name, b.account_no, b.branch, b.currency_id = name, account_no, branch, currency_id
            db.session.commit()
            flash('بانک ویرایش شد', 'success')
        else:
            db.session.add(Bank(name=name, account_no=account_no, branch=branch, currency_id=currency_id))
            db.session.commit()
            flash('بانک ثبت شد', 'success')
        return redirect(url_for('main.banks'))

    search = request.args.get('q', '').strip()
    query = Bank.query
    if search:
        query = query.filter(Bank.name.contains(search))
    bank_list = query.order_by(Bank.id).all()
    active_currencies = Currency.query.filter_by(is_active=True).order_by(Currency.code).all()

    return render_template('treasury/banks.html',
        bank_list=bank_list, edit_b=edit_b, active_currencies=active_currencies, search=search)


@main.route('/treasury/banks/toggle/<int:id>')
def bank_toggle(id):
    b = Bank.query.get_or_404(id)
    b.is_active = not b.is_active
    db.session.commit()
    return redirect(url_for('main.banks'))


@main.route('/treasury/banks/delete/<int:id>')
def bank_delete(id):
    b = Bank.query.get_or_404(id)
    db.session.delete(b)
    db.session.commit()
    flash('بانک حذف شد', 'success')
    return redirect(url_for('main.banks'))


# ==========================================
# بانک‌ها — ثبت حساب افتتاحیه بانک
# ==========================================
@main.route('/treasury/bank-opening', methods=['GET', 'POST'])
def bank_opening():
    edit_id = request.args.get('edit', type=int)
    edit_bo = BankOpening.query.get(edit_id) if edit_id else None

    if request.method == 'POST':
        jy = request.form.get('j_year', type=int)
        jm = request.form.get('j_month', type=int)
        jd = request.form.get('j_day', type=int)
        g_date = jalali_to_gregorian(jy, jm, jd)

        bank_name = request.form.get('bank_name', '').strip()
        bank = Bank.query.filter_by(name=bank_name).first()
        currency_id = request.form.get('currency_id', type=int)
        amount = request.form.get('amount', type=float) or 0
        account_type = request.form.get('account_type', '').strip()
        notes = request.form.get('notes', '').strip()
        bo_id = request.form.get('bo_id', type=int)

        if not bank or not g_date:
            flash('نام بانک (از لیست) و تاریخ الزامی است', 'danger')
        elif bo_id:
            bo = BankOpening.query.get_or_404(bo_id)
            bo.date, bo.j_year, bo.j_month, bo.j_day = g_date, jy, jm, jd
            bo.bank_id, bo.currency_id = bank.id, currency_id
            bo.amount, bo.account_type, bo.notes = amount, account_type, notes
            db.session.commit()
            flash('حساب افتتاحیه ویرایش شد', 'success')
        else:
            db.session.add(BankOpening(
                date=g_date, j_year=jy, j_month=jm, j_day=jd,
                bank_id=bank.id, currency_id=currency_id,
                amount=amount, account_type=account_type, notes=notes
            ))
            db.session.commit()
            flash('حساب افتتاحیه ثبت شد', 'success')
        return redirect(url_for('main.bank_opening'))

    search = request.args.get('q', '').strip()
    query = BankOpening.query
    if search:
        query = query.join(Bank).filter(Bank.name.contains(search))
    records = query.order_by(BankOpening.id).all()

    bank_list = Bank.query.order_by(Bank.name).all()
    active_currencies = Currency.query.filter_by(is_active=True).order_by(Currency.code).all()
    today = jdatetime.date.today()

    return render_template('treasury/bank_opening.html',
        records=records, edit_bo=edit_bo, bank_list=bank_list,
        active_currencies=active_currencies, today=today, search=search)


@main.route('/treasury/bank-opening/delete/<int:id>')
def bank_opening_delete(id):
    bo = BankOpening.query.get_or_404(id)
    db.session.delete(bo)
    db.session.commit()
    flash('رکورد حذف شد', 'success')
    return redirect(url_for('main.bank_opening'))


# ==========================================
# بانک‌ها — حسابات بانکی (جستجو)
# ==========================================
def _currency_code_from(val):
    """val می‌تواند یک آبجکت Currency (دارای .code) یا مستقیماً یک رشتهٔ کد ارز باشد."""
    if val is None:
        return None
    if isinstance(val, str):
        return val or None
    return getattr(val, 'code', None)


def bank_ledger_entries(bank_id):
    """
    دفتر کامل تراکنش‌های یک بانک/صندوق را برمی‌گرداند.

    نکتهٔ مهم دربارهٔ ساختار این برنامه: هرجا مصرف، عاید متفرقه، برد و رسید، انتقال بین
    بانک‌ها، پرداخت معاش یا پرداخت/دریافت فاکتور ثبت می‌شود، تابع adjust_bank_balance()
    به‌طور خودکار یک رکورد در همین جدول BankOpening اضافه می‌کند (با notes توضیحی مثل
    "مصرف — برنج"). یعنی BankOpening همان دفتر کل بانک است، نه فقط حساب افتتاحیهٔ دستی.
    بنابراین تنها منبع صحیح برای استتمنت همین جدول است؛ خواندن مستقیم و اضافی از
    جدول‌های مبدا (ExpenseDetail، RevenueDetail، CashTransaction و ...) باعث می‌شود هر
    تراکنش دوبار شمرده شود — همان اشکالی که قبلاً رخ داد.

    خروجی: لیستی از دیکشنری‌ها شامل date, j_year/j_month/j_day, currency (کد ارز),
    ref (مرجع), name (نام طرف، در صورت تشخیص از روی notes), desc (توضیحات),
    debit (بردگی), credit (رسیدگی).
    """
    entries = []

    for o in BankOpening.query.filter_by(bank_id=bank_id).all():
        amt = o.amount or 0
        notes = (o.notes or '').strip() or 'حساب افتتاحیه'

        # الگوی معمول notes های خودکار: "مرجع — جزئیات" یا "مرجع — برچسب: نام طرف"
        if ' — ' in notes:
            ref, detail = notes.split(' — ', 1)
        else:
            ref, detail = notes, ''
        ref = ref.strip() or 'حساب افتتاحیه'
        detail = detail.strip()

        name = '-'
        if ': ' in detail:
            name = detail.rsplit(': ', 1)[1].strip() or '-'

        entries.append({
            'date': o.date, 'j_year': o.j_year, 'j_month': o.j_month, 'j_day': o.j_day,
            'currency': _currency_code_from(o.currency),
            'ref': ref, 'name': name, 'desc': detail or '-',
            'debit': amt if o.account_type == 'payable' else 0,
            'credit': amt if o.account_type != 'payable' else 0,
        })

    return entries


def bank_balances_by_currency(bank_id):
    """مانده این بانک را به‌ازای هر ارز فعال برمی‌گرداند: {currency_code: balance}
    بر اساس تمام تراکنش‌های واقعی مؤثر بر بانک (نه فقط حساب افتتاحیه)."""
    balances = {}
    active_currencies = Currency.query.filter_by(is_active=True).order_by(Currency.code).all()
    for c in active_currencies:
        balances[c.code] = 0.0

    for e in bank_ledger_entries(bank_id):
        code = e['currency']
        if not code:
            continue
        if code not in balances:
            balances[code] = 0.0
        balances[code] += (e['credit'] or 0) - (e['debit'] or 0)

    return balances


@main.route('/treasury/bank-search', methods=['GET'])
def bank_search():
    bank_list = Bank.query.order_by(Bank.name).all()
    return render_template('treasury/bank_search.html', bank_list=bank_list)


@main.route('/treasury/bank-account/<int:bank_id>')
def bank_account(bank_id):
    bank = Bank.query.get_or_404(bank_id)
    balances = bank_balances_by_currency(bank.id)
    return render_template('treasury/bank_account.html', bank=bank, balances=balances)


# ---- حساب جاری ----
@main.route('/treasury/bank-account/<int:bank_id>/current')
def bank_current_account(bank_id):
    bank = Bank.query.get_or_404(bank_id)

    entries = []
    for o in BankOpening.query.filter_by(bank_id=bank_id).all():
        amt = o.amount if o.account_type != 'payable' else -o.amount
        entries.append({
            'date': o.date, 'j_year': o.j_year, 'j_month': o.j_month, 'j_day': o.j_day,
            'desc': o.notes or 'حساب افتتاحیه', 'currency': o.currency.code if o.currency else '-',
            'debit': amt if amt > 0 else 0, 'credit': -amt if amt < 0 else 0
        })
    entries.sort(key=lambda e: e['date'])

    available_currencies = sorted({e['currency'] for e in entries if e['currency'] != '-'})
    currency_filter = request.args.get('currency', '').strip()
    if not currency_filter:
        currency_filter = available_currencies[0] if available_currencies else ''
    if currency_filter:
        entries = [e for e in entries if e['currency'] == currency_filter]

    running = 0
    for e in entries:
        running += e['debit'] - e['credit']
        e['balance'] = running

    return render_template('treasury/bank_current.html', bank=bank, entries=entries,
                            available_currencies=available_currencies, currency_filter=currency_filter)


# ---- جزئیات عملیاتی بانک (همان حساب جاری، جزئیات کامل‌تر هر رکورد) ----
@main.route('/treasury/bank-account/<int:bank_id>/operations')
def bank_operations(bank_id):
    bank = Bank.query.get_or_404(bank_id)
    records = BankOpening.query.filter_by(bank_id=bank_id).order_by(BankOpening.date).all()
    return render_template('treasury/bank_operations.html', bank=bank, records=records)


# ---- استتمنت بانکی (دفتر کامل تراکنش‌ها با مانده جاری) ----
@main.route('/treasury/bank-account/<int:bank_id>/statement')
def bank_statement(bank_id):
    bank = Bank.query.get_or_404(bank_id)
    all_entries = bank_ledger_entries(bank_id)

    available_currencies = sorted({e['currency'] for e in all_entries if e['currency']})
    currency_filter = request.args.get('currency', '').strip()
    if not currency_filter:
        default_code = bank.currency.code if bank.currency else None
        currency_filter = default_code if default_code in available_currencies else (available_currencies[0] if available_currencies else '')

    entries = [e for e in all_entries if e['currency'] == currency_filter]
    entries.sort(key=lambda e: e['date'])

    running = 0.0
    total_debit = 0.0
    total_credit = 0.0
    for idx, e in enumerate(entries, start=1):
        e['number'] = idx
        running += (e['credit'] or 0) - (e['debit'] or 0)
        e['balance'] = running
        total_debit += e['debit'] or 0
        total_credit += e['credit'] or 0

    return render_template('treasury/bank_statement.html',
        bank=bank, entries=entries, available_currencies=available_currencies,
        currency_filter=currency_filter, total_debit=total_debit, total_credit=total_credit,
        final_balance=running, record_count=len(entries))


# ---- استتمنت تاریخ‌وار ----
@main.route('/treasury/bank-account/<int:bank_id>/date-range')
def bank_date_range(bank_id):
    bank = Bank.query.get_or_404(bank_id)

    from_jy = request.args.get('from_year', type=int)
    from_jm = request.args.get('from_month', type=int)
    from_jd = request.args.get('from_day', type=int)
    to_jy = request.args.get('to_year', type=int)
    to_jm = request.args.get('to_month', type=int)
    to_jd = request.args.get('to_day', type=int)
    currency_id = request.args.get('currency_id', type=int)

    start_date = jalali_to_gregorian(from_jy, from_jm, from_jd) if (from_jy and from_jm and from_jd) else None
    end_date = jalali_to_gregorian(to_jy, to_jm, to_jd) if (to_jy and to_jm and to_jd) else None

    entries = []
    op_query = BankOpening.query.filter_by(bank_id=bank_id)
    if currency_id:
        op_query = op_query.filter_by(currency_id=currency_id)

    for o in op_query.all():
        amt = o.amount if o.account_type != 'payable' else -o.amount
        entries.append({
            'date': o.date, 'j_year': o.j_year, 'j_month': o.j_month, 'j_day': o.j_day,
            'desc': o.notes or 'حساب افتتاحیه', 'currency': o.currency.code if o.currency else '-',
            'debit': amt if amt > 0 else 0, 'credit': -amt if amt < 0 else 0
        })
    entries.sort(key=lambda e: e['date'])

    if start_date:
        entries = [e for e in entries if e['date'] >= start_date]
    if end_date:
        entries = [e for e in entries if e['date'] <= end_date]

    running = 0
    for e in entries:
        running += e['debit'] - e['credit']
        e['balance'] = running

    active_currencies = Currency.query.filter_by(is_active=True).order_by(Currency.code).all()
    today = jdatetime.date.today()
    searched = bool(request.args)
    return render_template('treasury/bank_date_range.html',
        bank=bank, entries=entries, today=today, active_currencies=active_currencies,
        from_year=from_jy, from_month=from_jm, from_day=from_jd,
        to_year=to_jy, to_month=to_jm, to_day=to_jd,
        selected_currency=currency_id, searched=searched)


# ==========================================
# مصارف — ثبت کتگوری مصارف
# ==========================================
@main.route('/treasury/expense-category', methods=['GET', 'POST'])
def expense_category():
    edit_id = request.args.get('edit', type=int)
    edit_ec = ExpenseCategory.query.get(edit_id) if edit_id else None

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        ec_id = request.form.get('ec_id', type=int)
        if not name:
            flash('نام کتگوری نمی‌تواند خالی باشد', 'danger')
        elif ec_id:
            ec = ExpenseCategory.query.get_or_404(ec_id)
            ec.name = name
            db.session.commit()
            flash('کتگوری ویرایش شد', 'success')
        else:
            db.session.add(ExpenseCategory(name=name))
            db.session.commit()
            flash('کتگوری ثبت شد', 'success')
        return redirect(url_for('main.expense_category'))

    search = request.args.get('q', '').strip()
    query = ExpenseCategory.query
    if search:
        query = query.filter(ExpenseCategory.name.contains(search))
    categories = query.order_by(ExpenseCategory.id).all()

    return render_template('expenses/expense_category.html', categories=categories, edit_ec=edit_ec, search=search)


@main.route('/treasury/expense-category/delete/<int:id>')
def expense_category_delete(id):
    ec = ExpenseCategory.query.get_or_404(id)
    db.session.delete(ec)
    db.session.commit()
    flash('کتگوری حذف شد', 'success')
    return redirect(url_for('main.expense_category'))


# ==========================================
# مصارف — ثبت مصارف
# ==========================================
@main.route('/treasury/expenses/new', methods=['GET', 'POST'])
def expense_new():
    edit_id = request.args.get('edit', type=int)
    edit_e = Expense.query.get(edit_id) if edit_id else None

    if request.method == 'POST':
        category_id = request.form.get('category_id', type=int)
        recipient = request.form.get('recipient', '').strip()
        notes = request.form.get('notes', '').strip()
        e_id = request.form.get('e_id', type=int)

        if not recipient:
            flash('گیرنده مصرف نمی‌تواند خالی باشد', 'danger')
        elif e_id:
            e = Expense.query.get_or_404(e_id)
            e.category_id, e.recipient, e.notes = category_id, recipient, notes
            db.session.commit()
            flash('مصرف ویرایش شد', 'success')
        else:
            db.session.add(Expense(category_id=category_id, recipient=recipient, notes=notes))
            db.session.commit()
            flash('مصرف ثبت شد', 'success')
        return redirect(url_for('main.expense_new'))

    search = request.args.get('q', '').strip()
    query = Expense.query
    if search:
        query = query.filter(Expense.recipient.contains(search))
    expense_list = query.order_by(Expense.id).all()
    category_list = ExpenseCategory.query.order_by(ExpenseCategory.name).all()

    return render_template('expenses/expense_new.html',
        expense_list=expense_list, edit_e=edit_e, category_list=category_list, search=search)


@main.route('/treasury/expenses/delete/<int:id>')
def expense_delete(id):
    e = Expense.query.get_or_404(id)
    db.session.delete(e)
    db.session.commit()
    flash('مصرف حذف شد', 'success')
    return redirect(url_for('main.expense_new'))


# ==========================================
# مصارف — شرح مصارف (ثبت واقعی هزینه با مبلغ)
# ==========================================
@main.route('/treasury/expenses/detail', methods=['GET', 'POST'])
def expense_detail():
    edit_id = request.args.get('edit', type=int)
    edit_ed = ExpenseDetail.query.get(edit_id) if edit_id else None

    if request.method == 'POST':
        jy = request.form.get('j_year', type=int)
        jm = request.form.get('j_month', type=int)
        jd = request.form.get('j_day', type=int)
        g_date = jalali_to_gregorian(jy, jm, jd)

        currency_id = request.form.get('currency_id', type=int)
        category_id = request.form.get('category_id', type=int)
        recipient = request.form.get('recipient', '').strip()
        amount = request.form.get('amount', type=float) or 0
        bank_id = request.form.get('bank_id', type=int)
        rate = request.form.get('rate', type=float) or 1
        notes = request.form.get('notes', '').strip()
        ed_id = request.form.get('ed_id', type=int)

        currency = Currency.query.get(currency_id) if currency_id else None
        if currency and currency.code == 'USD':
            total_usd = amount
        else:
            total_usd = (amount / rate) if rate else 0

        if not recipient or not g_date or not amount:
            flash('گیرنده مصرف، مقدار و تاریخ الزامی است', 'danger')
        else:
            if ed_id:
                ed = ExpenseDetail.query.get_or_404(ed_id)
                # برگرداندن اثر قبلی از موجودی بانک
                if ed.bank_id:
                    adjust_bank_balance(ed.bank_id, ed.currency_id, ed.amount or 0)  # برگشت = اضافه کردن دوباره

                ed.date, ed.j_year, ed.j_month, ed.j_day = g_date, jy, jm, jd
                ed.currency_id, ed.category_id, ed.recipient = currency_id, category_id, recipient
                ed.amount, ed.bank_id, ed.rate, ed.total_usd, ed.notes = amount, bank_id, rate, total_usd, notes

                if bank_id:
                    adjust_bank_balance(bank_id, currency_id, -amount, g_date=g_date,
                                        notes=f'مصرف — {recipient}')

                db.session.commit()
                flash('مصرف ویرایش شد', 'success')
            else:
                ed = ExpenseDetail(
                    date=g_date, j_year=jy, j_month=jm, j_day=jd,
                    currency_id=currency_id, category_id=category_id, recipient=recipient,
                    amount=amount, bank_id=bank_id, rate=rate, total_usd=total_usd, notes=notes,
                    created_by=session.get('username')
                )
                db.session.add(ed)

                if bank_id:
                    adjust_bank_balance(bank_id, currency_id, -amount, g_date=g_date,
                                        notes=f'مصرف — {recipient}')

                db.session.commit()
                flash('مصرف ثبت شد', 'success')
        return redirect(url_for('main.expense_detail'))

    search = request.args.get('q', '').strip()
    query = ExpenseDetail.query
    if search:
        query = query.filter(ExpenseDetail.recipient.contains(search))
    records = query.order_by(ExpenseDetail.id).all()

    category_list = ExpenseCategory.query.order_by(ExpenseCategory.name).all()
    active_currencies = Currency.query.filter_by(is_active=True).order_by(Currency.code).all()
    bank_list = Bank.query.filter_by(is_active=True).order_by(Bank.name).all()
    today = jdatetime.date.today()

    return render_template('expenses/expense_detail.html',
        records=records, edit_ed=edit_ed, category_list=category_list,
        active_currencies=active_currencies, bank_list=bank_list, today=today, search=search)


def adjust_bank_balance(bank_id, currency_id, delta_amount, g_date=None, notes='تعدیل خودکار از مصارف'):
    """موجودی یک بانک به یک ارز خاص را تغییر می‌دهد (با ساخت یک رکورد BankOpening تعدیلی)."""
    if not bank_id or not delta_amount:
        return
    account_type = 'receivable' if delta_amount > 0 else 'payable'
    today_j = jdatetime.date.today()
    db.session.add(BankOpening(
        date=g_date or today_j.togregorian(),
        j_year=today_j.year, j_month=today_j.month, j_day=today_j.day,
        bank_id=bank_id, currency_id=currency_id,
        amount=abs(delta_amount), account_type=account_type, notes=notes
    ))


@main.route('/treasury/expenses/detail/delete/<int:id>')
def expense_detail_delete(id):
    ed = ExpenseDetail.query.get_or_404(id)
    if ed.bank_id:
        adjust_bank_balance(ed.bank_id, ed.currency_id, ed.amount or 0)  # برگرداندن موجودی
    db.session.delete(ed)
    db.session.commit()
    flash('مصرف حذف شد', 'success')
    return redirect(url_for('main.expense_detail'))


# ==========================================
# سرمایه ثابت — کتگوری دارایی‌های ثابت
# ==========================================
@main.route('/assets/categories', methods=['GET', 'POST'])
def asset_category():
    edit_id = request.args.get('edit', type=int)
    edit_category = FixedAssetCategory.query.get(edit_id) if edit_id else None

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        cat_id = request.form.get('cat_id', type=int)
        if not name:
            flash('نام کتگوری نمی‌تواند خالی باشد', 'danger')
        elif cat_id:
            cat = FixedAssetCategory.query.get_or_404(cat_id)
            cat.name = name
            db.session.commit()
            flash('کتگوری ویرایش شد', 'success')
        else:
            db.session.add(FixedAssetCategory(name=name))
            db.session.commit()
            flash('کتگوری ثبت شد', 'success')
        return redirect(url_for('main.asset_category'))

    search = request.args.get('q', '').strip()
    query = FixedAssetCategory.query
    if search:
        query = query.filter(FixedAssetCategory.name.contains(search))
    categories = query.order_by(FixedAssetCategory.id).all()

    return render_template('assets/category.html',
        categories=categories, edit_category=edit_category, search=search)


@main.route('/assets/categories/delete/<int:id>')
def asset_category_delete(id):
    cat = FixedAssetCategory.query.get_or_404(id)
    db.session.delete(cat)
    db.session.commit()
    flash('کتگوری حذف شد', 'success')
    return redirect(url_for('main.asset_category'))


# ==========================================
# سرمایه ثابت — ثبت دارایی‌های ثابت
# ==========================================
@main.route('/assets/fixed', methods=['GET', 'POST'])
def fixed_assets():
    edit_id = request.args.get('edit', type=int)
    edit_asset = FixedAsset.query.get(edit_id) if edit_id else None

    if request.method == 'POST':
        jy = request.form.get('j_year', type=int)
        jm = request.form.get('j_month', type=int)
        jd = request.form.get('j_day', type=int)
        g_date = jalali_to_gregorian(jy, jm, jd)

        category_id = request.form.get('category_id', type=int)
        name = request.form.get('name', '').strip()
        asset_code = request.form.get('asset_code', '').strip()
        location = request.form.get('location', '').strip()
        currency_id = request.form.get('currency_id', type=int)
        purchase_price = request.form.get('purchase_price', type=float) or 0
        rate = request.form.get('rate', type=float) or 1
        quantity = request.form.get('quantity', type=float) or 1
        depreciation_rate = request.form.get('depreciation_rate', type=float) or 0
        bank_id = request.form.get('bank_id', type=int)
        status = request.form.get('status', 'active')
        notes = request.form.get('notes', '').strip()
        asset_id = request.form.get('asset_id', type=int)

        currency = Currency.query.get(currency_id) if currency_id else None
        if currency and currency.code == 'USD':
            purchase_price_usd = purchase_price
        else:
            purchase_price_usd = (purchase_price / rate) if rate else 0

        if not name or not g_date or not purchase_price:
            flash('نام دارایی، قیمت خرید و تاریخ الزامی است', 'danger')
        else:
            if asset_id:
                asset = FixedAsset.query.get_or_404(asset_id)
                # برگرداندن اثر قبلی از موجودی بانک قبل از اعمال تغییرات
                if asset.bank_id:
                    adjust_bank_balance(asset.bank_id, asset.currency_id, asset.purchase_price or 0)

                asset.date, asset.j_year, asset.j_month, asset.j_day = g_date, jy, jm, jd
                asset.category_id, asset.name = category_id, name
                asset.asset_code, asset.location = asset_code, location
                asset.currency_id, asset.purchase_price, asset.rate = currency_id, purchase_price, rate
                asset.purchase_price_usd, asset.quantity = purchase_price_usd, quantity
                asset.depreciation_rate, asset.bank_id, asset.status = depreciation_rate, bank_id, status
                asset.notes = notes

                if bank_id:
                    adjust_bank_balance(bank_id, currency_id, -purchase_price, g_date=g_date,
                                        notes=f'خرید دارایی ثابت — {name}')

                db.session.commit()
                flash('دارایی ویرایش شد', 'success')
            else:
                asset = FixedAsset(
                    date=g_date, j_year=jy, j_month=jm, j_day=jd,
                    category_id=category_id, name=name, asset_code=asset_code, location=location,
                    currency_id=currency_id, purchase_price=purchase_price, rate=rate,
                    purchase_price_usd=purchase_price_usd, quantity=quantity,
                    depreciation_rate=depreciation_rate, bank_id=bank_id, status=status, notes=notes,
                    created_by=session.get('username')
                )
                db.session.add(asset)

                if bank_id:
                    adjust_bank_balance(bank_id, currency_id, -purchase_price, g_date=g_date,
                                        notes=f'خرید دارایی ثابت — {name}')

                db.session.commit()
                flash('دارایی ثبت شد', 'success')
        return redirect(url_for('main.fixed_assets'))

    search = request.args.get('q', '').strip()
    query = FixedAsset.query
    if search:
        query = query.filter(FixedAsset.name.contains(search))
    records = query.order_by(FixedAsset.id).all()

    category_list = FixedAssetCategory.query.order_by(FixedAssetCategory.name).all()
    active_currencies = Currency.query.filter_by(is_active=True).order_by(Currency.code).all()
    bank_list = Bank.query.filter_by(is_active=True).order_by(Bank.name).all()
    today = jdatetime.date.today()

    return render_template('assets/fixed_assets.html',
        records=records, edit_asset=edit_asset, category_list=category_list,
        active_currencies=active_currencies, bank_list=bank_list, today=today, search=search)


@main.route('/assets/fixed/delete/<int:id>')
def fixed_asset_delete(id):
    asset = FixedAsset.query.get_or_404(id)
    if asset.bank_id:
        adjust_bank_balance(asset.bank_id, asset.currency_id, asset.purchase_price or 0)
    db.session.delete(asset)
    db.session.commit()
    flash('دارایی حذف شد', 'success')
    return redirect(url_for('main.fixed_assets'))


# ==========================================
# راپور مصارف — خلاصهٔ مصارف به تفکیک کتگوری/نام مصرف در یک بازه تاریخ
# ==========================================
@main.route('/reports/expenses/search')
def expense_report_search():
    today = jdatetime.date.today()

    from_jy = request.args.get('from_year', type=int) or today.year
    from_jm = request.args.get('from_month', type=int) or today.month
    from_jd = request.args.get('from_day', type=int) or today.day
    to_jy = request.args.get('to_year', type=int) or today.year
    to_jm = request.args.get('to_month', type=int) or today.month
    to_jd = request.args.get('to_day', type=int) or today.day
    category_id = request.args.get('category_id', type=int)
    recipient = request.args.get('recipient', '').strip()
    currency_id = request.args.get('currency_id', type=int)
    searched = request.args.get('searched') == '1'

    start_date = jalali_to_gregorian(from_jy, from_jm, from_jd)
    end_date = jalali_to_gregorian(to_jy, to_jm, to_jd)

    groups = []       # [{category, lines: [{recipient, total_usd}], sub_total}]
    grand_total = 0.0
    if searched:
        query = ExpenseDetail.query
        if start_date:
            query = query.filter(ExpenseDetail.date >= start_date)
        if end_date:
            query = query.filter(ExpenseDetail.date <= end_date)
        if category_id:
            query = query.filter(ExpenseDetail.category_id == category_id)
        if recipient:
            query = query.filter(ExpenseDetail.recipient == recipient)
        if currency_id:
            query = query.filter(ExpenseDetail.currency_id == currency_id)
        records = query.order_by(ExpenseDetail.id).all()

        by_cat = {}   # cat_name -> {recipient_name -> total_usd}
        for r in records:
            cat_name = r.category.name if r.category else 'سایر'
            rec_name = r.recipient or 'سایر'
            usd = r.total_usd or 0.0
            by_cat.setdefault(cat_name, {})
            by_cat[cat_name][rec_name] = by_cat[cat_name].get(rec_name, 0.0) + usd
            grand_total += usd

        for cat_name in sorted(by_cat.keys()):
            items = [{'recipient': rn, 'total_usd': tot} for rn, tot in sorted(by_cat[cat_name].items())]
            sub_total = sum(i['total_usd'] for i in items)
            groups.append({'category': cat_name, 'lines': items, 'sub_total': sub_total})

    category_list = ExpenseCategory.query.order_by(ExpenseCategory.name).all()
    active_currencies = Currency.query.filter_by(is_active=True).order_by(Currency.code).all()
    recipient_list = [r[0] for r in db.session.query(ExpenseDetail.recipient)
                       .filter(ExpenseDetail.recipient.isnot(None))
                       .distinct().order_by(ExpenseDetail.recipient).all() if r[0]]

    return render_template('reports/expense_search.html',
        today=today, category_list=category_list,
        active_currencies=active_currencies, recipient_list=recipient_list,
        groups=groups, grand_total=grand_total, searched=searched,
        from_year=from_jy, from_month=from_jm, from_day=from_jd,
        to_year=to_jy, to_month=to_jm, to_day=to_jd,
        selected_category=category_id, selected_recipient=recipient, selected_currency=currency_id)


# ==========================================
# راپور عواید متفرقه — خلاصهٔ عواید به تفکیک کتگوری/نام عاید در یک بازه تاریخ
# ==========================================
@main.route('/reports/revenue/search')
def revenue_report_search():
    today = jdatetime.date.today()

    from_jy = request.args.get('from_year', type=int) or today.year
    from_jm = request.args.get('from_month', type=int) or today.month
    from_jd = request.args.get('from_day', type=int) or today.day
    to_jy = request.args.get('to_year', type=int) or today.year
    to_jm = request.args.get('to_month', type=int) or today.month
    to_jd = request.args.get('to_day', type=int) or today.day
    category_id = request.args.get('category_id', type=int)
    recipient = request.args.get('recipient', '').strip()
    currency_id = request.args.get('currency_id', type=int)
    searched = request.args.get('searched') == '1'

    start_date = jalali_to_gregorian(from_jy, from_jm, from_jd)
    end_date = jalali_to_gregorian(to_jy, to_jm, to_jd)

    groups = []       # [{category, lines: [{recipient, total_usd}], sub_total}]
    grand_total = 0.0
    if searched:
        query = RevenueDetail.query
        if start_date:
            query = query.filter(RevenueDetail.date >= start_date)
        if end_date:
            query = query.filter(RevenueDetail.date <= end_date)
        if category_id:
            query = query.filter(RevenueDetail.category_id == category_id)
        if recipient:
            query = query.filter(RevenueDetail.recipient == recipient)
        if currency_id:
            query = query.filter(RevenueDetail.currency_id == currency_id)
        records = query.order_by(RevenueDetail.id).all()

        by_cat = {}   # cat_name -> {recipient_name -> total_usd}
        for r in records:
            cat_name = r.category.name if r.category else 'سایر'
            rec_name = r.recipient or 'سایر'
            usd = amount_to_usd(r.amount, r.currency_id)
            by_cat.setdefault(cat_name, {})
            by_cat[cat_name][rec_name] = by_cat[cat_name].get(rec_name, 0.0) + usd
            grand_total += usd

        for cat_name in sorted(by_cat.keys()):
            items = [{'recipient': rn, 'total_usd': tot} for rn, tot in sorted(by_cat[cat_name].items())]
            sub_total = sum(i['total_usd'] for i in items)
            groups.append({'category': cat_name, 'lines': items, 'sub_total': sub_total})

    category_list = RevenueCategory.query.order_by(RevenueCategory.name).all()
    active_currencies = Currency.query.filter_by(is_active=True).order_by(Currency.code).all()
    recipient_list = [r[0] for r in db.session.query(RevenueDetail.recipient)
                       .filter(RevenueDetail.recipient.isnot(None))
                       .distinct().order_by(RevenueDetail.recipient).all() if r[0]]

    return render_template('reports/revenue_search.html',
        today=today, category_list=category_list,
        active_currencies=active_currencies, recipient_list=recipient_list,
        groups=groups, grand_total=grand_total, searched=searched,
        from_year=from_jy, from_month=from_jm, from_day=from_jd,
        to_year=to_jy, to_month=to_jm, to_day=to_jd,
        selected_category=category_id, selected_recipient=recipient, selected_currency=currency_id)


# ==========================================
# برد و رسید — برد و رسید نقدی/بانکی (مشتری/فروشنده/کارمند/قرض‌گیرنده)
# ==========================================
PARTY_TYPE_LABELS = {
    'customer': 'مشتری',
    'vendor': 'فروشنده کالا',
    'employee': 'کارمند',
    'borrower': 'قرض‌گیرنده',
}


def get_party_list(party_type):
    """لیست طرف‌های قابل انتخاب برای یک نوع حسابدار را برمی‌گرداند (id, name)."""
    if party_type == 'customer':
        return [(c.id, c.name) for c in Customer.query.filter_by(is_active=True).order_by(Customer.name).all()]
    if party_type == 'vendor':
        return [(v.id, v.name) for v in Vendor.query.filter_by(is_active=True).order_by(Vendor.name).all()]
    if party_type == 'employee':
        return [(e.id, e.name) for e in Employee.query.order_by(Employee.name).all()]
    if party_type == 'borrower':
        return [(b.id, b.name) for b in Borrower.query.filter_by(is_active=True).order_by(Borrower.name).all()]
    return []


def get_party_name(party_type, party_id):
    if party_type == 'customer':
        c = Customer.query.get(party_id)
        return c.name if c else None
    if party_type == 'vendor':
        v = Vendor.query.get(party_id)
        return v.name if v else None
    if party_type == 'employee':
        e = Employee.query.get(party_id)
        return e.name if e else None
    if party_type == 'borrower':
        b = Borrower.query.get(party_id)
        return b.name if b else None
    return None


@main.route('/receipt/cash-transaction/parties/<party_type>')
def cash_transaction_parties(party_type):
    """برای پر کردن خودکار (AJAX) باکس دوم بعد از انتخاب نوع حسابدار."""
    from flask import jsonify
    parties = get_party_list(party_type)
    label = PARTY_TYPE_LABELS.get(party_type, '')
    return jsonify({
        'label': label,
        'parties': [{'id': pid, 'name': pname} for pid, pname in parties],
    })


@main.route('/receipt/cash-transaction/party-balance')
def cash_transaction_party_balance():
    """مانده تفکیکی-بر-اساس-ارز یک طرف را برمی‌گرداند (برای نمایش در باکس «حساب جاری»)."""
    from flask import jsonify
    party_type = request.args.get('party_type', '')
    party_id = request.args.get('party_id', type=int)
    if not party_type or not party_id:
        return jsonify({'balances': []})
    totals = party_balance_by_currency(party_type, party_id)
    return jsonify({'balances': format_balance_by_currency(totals)})


def _ct_contribution(party_type, transaction_type, amount):
    """جهت اثر یک رکورد برد/رسید روی مانده حساب طرف، بر اساس قرارداد هر نوع طرف‌حساب.
    از وقتی customer_balance هم‌قرارداد با vendor/borrower شده (منفی=بدهکار)، مشتری هم
    از همان فرمول عمومی پیروی می‌کند: برد کم می‌کند، رسید زیاد می‌کند."""
    amount = amount or 0
    return -amount if transaction_type == 'payment' else amount


def compute_cash_transaction_running_balances():
    """
    برای هر رکورد CashTransaction، مانده‌ی حساب جاری طرف (تا و شامل همان رکورد) را برمی‌گرداند.
    خروجی: دیکشنری {ct.id: مانده} — برای party_type == 'employee' مقدار None است (بدون حساب جاری).
    """
    result = {}
    all_ct = CashTransaction.query.order_by(CashTransaction.id).all()

    groups = {}
    for ct in all_ct:
        groups.setdefault((ct.party_type, ct.party_id), []).append(ct)

    for (ptype, pid), ct_list in groups.items():
        if ptype == 'vendor':
            full = vendor_balance(pid)
        elif ptype == 'customer':
            full = customer_balance(pid)
        elif ptype == 'borrower':
            full = borrower_balance(pid)
        else:
            for ct in ct_list:
                result[ct.id] = None
            continue

        total_contribution = sum(_ct_contribution(ptype, ct.transaction_type, ct.amount) for ct in ct_list)
        running = full - total_contribution   # مانده قبل از هر برد/رسیدی (پایه)
        for ct in ct_list:
            running += _ct_contribution(ptype, ct.transaction_type, ct.amount)
            result[ct.id] = running

    return result


@main.route('/receipt/cash-transaction', methods=['GET', 'POST'])
def cash_transaction():
    edit_id = request.args.get('edit', type=int)
    edit_ct = CashTransaction.query.get(edit_id) if edit_id else None

    if request.method == 'POST':
        jy = request.form.get('j_year', type=int)
        jm = request.form.get('j_month', type=int)
        jd = request.form.get('j_day', type=int)
        g_date = jalali_to_gregorian(jy, jm, jd)

        party_type = request.form.get('party_type', '').strip()
        party_id = request.form.get('party_id', type=int)
        currency_id = request.form.get('currency_id', type=int)
        transaction_type = request.form.get('transaction_type', '').strip()
        bank_id = request.form.get('bank_id', type=int)
        amount = request.form.get('amount', type=float) or 0
        check_no = request.form.get('check_no', '').strip()
        notes = request.form.get('notes', '').strip()
        ct_id = request.form.get('ct_id', type=int)

        party_name = get_party_name(party_type, party_id)

        if not (party_type and party_id and transaction_type and g_date and amount):
            flash('حسابدار، نوعیت حساب، تاریخ و مقدار الزامی است', 'danger')
        else:
            if ct_id:
                ct = CashTransaction.query.get_or_404(ct_id)
                # برگرداندن اثر قبلی از موجودی بانک قبل از اعمال مقدار جدید
                if ct.bank_id:
                    old_delta = ct.amount if ct.transaction_type == 'receipt' else -ct.amount
                    adjust_bank_balance(ct.bank_id, ct.currency_id, -old_delta, notes='برگشت تعدیل برد و رسید (ویرایش)')

                ct.date, ct.j_year, ct.j_month, ct.j_day = g_date, jy, jm, jd
                ct.party_type, ct.party_id, ct.party_name = party_type, party_id, party_name
                ct.currency_id, ct.transaction_type = currency_id, transaction_type
                ct.bank_id, ct.amount, ct.check_no, ct.notes = bank_id, amount, check_no, notes

                if bank_id:
                    new_delta = amount if transaction_type == 'receipt' else -amount
                    party_label = PARTY_TYPE_LABELS.get(party_type, 'طرف حساب')
                    adjust_bank_balance(bank_id, currency_id, new_delta, g_date=g_date,
                                         notes=f'برد و رسید نقدی — {party_label}: {party_name} (ویرایش)')

                db.session.commit()
                flash('رکورد ویرایش شد', 'success')
            else:
                ct = CashTransaction(
                    date=g_date, j_year=jy, j_month=jm, j_day=jd,
                    party_type=party_type, party_id=party_id, party_name=party_name,
                    currency_id=currency_id, transaction_type=transaction_type,
                    bank_id=bank_id, amount=amount, check_no=check_no, notes=notes,
                    created_by=session.get('username')
                )
                db.session.add(ct)

                if bank_id:
                    # رسید: پول به صندوق/بانک وارد می‌شود (+) — برد: پول از صندوق/بانک خارج می‌شود (-)
                    delta = amount if transaction_type == 'receipt' else -amount
                    party_label = PARTY_TYPE_LABELS.get(party_type, 'طرف حساب')
                    adjust_bank_balance(bank_id, currency_id, delta, g_date=g_date,
                                         notes=f'برد و رسید نقدی — {party_label}: {party_name}')

                db.session.commit()
                flash('رکورد ثبت شد', 'success')
        return redirect(url_for('main.cash_transaction'))

    search = request.args.get('q', '').strip()
    query = CashTransaction.query
    if search:
        query = query.filter(CashTransaction.party_name.contains(search))
    records = query.order_by(CashTransaction.id).all()

    active_currencies = Currency.query.filter_by(is_active=True).order_by(Currency.code).all()
    bank_list = Bank.query.filter_by(is_active=True).order_by(Bank.name).all()
    today = jdatetime.date.today()

    prefill_party_type = request.args.get('party_type', '').strip()
    prefill_party_id = request.args.get('party_id', type=int)

    edit_party_list = get_party_list(edit_ct.party_type) if edit_ct else (
        get_party_list(prefill_party_type) if prefill_party_type else [])
    running_balances = compute_cash_transaction_running_balances()

    return render_template('receipt/cash_transaction.html',
        records=records, edit_ct=edit_ct, active_currencies=active_currencies,
        bank_list=bank_list, today=today, search=search,
        party_type_labels=PARTY_TYPE_LABELS, edit_party_list=edit_party_list,
        running_balances=running_balances,
        prefill_party_type=prefill_party_type, prefill_party_id=prefill_party_id)


# ---- سند چاپی برد و رسید نقدی (برای هر چهار نوع طرف‌حساب: مشتری/فروشنده/کارمند/قرض‌گیرنده) ----
@main.route('/receipt/cash-transaction/<int:id>/print')
def cash_transaction_print(id):
    ct = CashTransaction.query.get_or_404(id)
    party_label = PARTY_TYPE_LABELS.get(ct.party_type, 'طرف حساب')

    is_payment = (ct.transaction_type == 'payment')
    transaction_type_label = 'برد (پرداخت به طرف)' if is_payment else 'رسید (دریافت از طرف)'
    doc_title = ('سند پرداختی ' if is_payment else 'سند دریافتی ') + party_label

    # قرمز برای برد (خروج پول)، سبز برای رسید (ورود پول) — هماهنگ با رنگ‌بندی جدول برد و رسید
    if is_payment:
        theme_color, theme_light, theme_bg = '#b71c1c', '#f5cdcd', '#fdecea'
    else:
        theme_color, theme_light, theme_bg = '#1b5e20', '#cde5cf', '#e8f5e9'

    running_balances = compute_cash_transaction_running_balances()
    balance = running_balances.get(ct.id)

    return render_template('receipt/cash_transaction_print.html',
        ct=ct, party_label=party_label, transaction_type_label=transaction_type_label,
        doc_title=doc_title, theme_color=theme_color, theme_light=theme_light, theme_bg=theme_bg,
        balance=balance)


@main.route('/receipt/cash-transaction/delete/<int:id>')
def cash_transaction_delete(id):
    ct = CashTransaction.query.get_or_404(id)
    if ct.bank_id:
        old_delta = ct.amount if ct.transaction_type == 'receipt' else -ct.amount
        adjust_bank_balance(ct.bank_id, ct.currency_id, -old_delta, notes='برگشت تعدیل برد و رسید (حذف)')
    db.session.delete(ct)
    db.session.commit()
    flash('رکورد حذف شد', 'success')
    return redirect(url_for('main.cash_transaction'))


# ==========================================
# انتقال حساب بین مشتریان — برد و رسید نقدی بین مشتریان
# ==========================================
@main.route('/receipt/customer-transfer/balance')
def customer_transfer_balance():
    """مانده تفکیکی-بر-اساس-ارز مشتری مبدا را برمی‌گرداند (برای نمایش در باکس «حساب جاری»)."""
    from flask import jsonify
    customer_id = request.args.get('customer_id', type=int)
    if not customer_id:
        return jsonify({'balances': []})
    totals = customer_balance_by_currency(customer_id)
    return jsonify({'balances': format_balance_by_currency(totals)})


@main.route('/receipt/customer-transfer', methods=['GET', 'POST'])
def customer_transfer():
    edit_id = request.args.get('edit', type=int)
    edit_tr = CustomerTransfer.query.get(edit_id) if edit_id else None

    if request.method == 'POST':
        jy = request.form.get('j_year', type=int)
        jm = request.form.get('j_month', type=int)
        jd = request.form.get('j_day', type=int)
        g_date = jalali_to_gregorian(jy, jm, jd)

        from_customer_id = request.form.get('from_customer_id', type=int)
        to_customer_id = request.form.get('to_customer_id', type=int)
        currency_id = request.form.get('currency_id', type=int)
        transaction_type = request.form.get('transaction_type', '').strip()
        amount = request.form.get('amount', type=float) or 0
        notes = request.form.get('notes', '').strip()
        tr_id = request.form.get('tr_id', type=int)

        if not (from_customer_id and to_customer_id and transaction_type and g_date and amount):
            flash('انتقال از/به مشتری، نوعیت حساب، تاریخ و مقدار الزامی است', 'danger')
        elif from_customer_id == to_customer_id:
            flash('مشتری مبدا و مقصد نمی‌توانند یکسان باشند', 'danger')
        else:
            if tr_id:
                tr = CustomerTransfer.query.get_or_404(tr_id)
                tr.date, tr.j_year, tr.j_month, tr.j_day = g_date, jy, jm, jd
                tr.from_customer_id, tr.to_customer_id = from_customer_id, to_customer_id
                tr.currency_id, tr.transaction_type = currency_id, transaction_type
                tr.amount, tr.notes = amount, notes
                db.session.commit()
                flash('رکورد ویرایش شد', 'success')
            else:
                tr = CustomerTransfer(
                    date=g_date, j_year=jy, j_month=jm, j_day=jd,
                    from_customer_id=from_customer_id, to_customer_id=to_customer_id,
                    currency_id=currency_id, transaction_type=transaction_type,
                    amount=amount, notes=notes
                )
                db.session.add(tr)
                db.session.commit()
                flash('رکورد ثبت شد', 'success')
        return redirect(url_for('main.customer_transfer'))

    search = request.args.get('q', '').strip()
    query = CustomerTransfer.query
    if search:
        query = query.join(Customer, CustomerTransfer.from_customer_id == Customer.id).filter(Customer.name.contains(search))
    records = query.order_by(CustomerTransfer.id).all()

    customer_list = Customer.query.filter_by(is_active=True).order_by(Customer.name).all()
    active_currencies = Currency.query.filter_by(is_active=True).order_by(Currency.code).all()
    today = jdatetime.date.today()

    return render_template('receipt/customer_transfer.html',
        records=records, edit_tr=edit_tr, customer_list=customer_list,
        active_currencies=active_currencies, today=today, search=search)


@main.route('/receipt/customer-transfer/delete/<int:id>')
def customer_transfer_delete(id):
    tr = CustomerTransfer.query.get_or_404(id)
    db.session.delete(tr)
    db.session.commit()
    flash('رکورد حذف شد', 'success')
    return redirect(url_for('main.customer_transfer'))


# ==========================================
# پرداختی مشتری — برد/رسید با تبدیل ارز (مثلاً دالر <-> افغانی)
# ==========================================
def _set_party_fk(payment, party_type, party_id):
    """ستون‌های راحتی customer_id/vendor_id/employee_id را بر اساس party_type پر می‌کند."""
    payment.customer_id = party_id if party_type == 'customer' else None
    payment.vendor_id = party_id if party_type == 'vendor' else None
    payment.employee_id = party_id if party_type == 'employee' else None


@main.route('/receipt/customer-payment/balance')
def customer_payment_balance():
    """مانده تفکیکی-بر-اساس-ارز یک طرف را برمی‌گرداند (برای باکس «حساب جاری»)."""
    from flask import jsonify
    party_type = request.args.get('party_type', '')
    party_id = request.args.get('party_id', type=int)
    if not party_type or not party_id:
        return jsonify({'balances': []})
    totals = party_balance_by_currency(party_type, party_id)
    return jsonify({'balances': format_balance_by_currency(totals)})


@main.route('/receipt/customer-payment', methods=['GET', 'POST'])
def customer_payment():
    edit_id = request.args.get('edit', type=int)
    edit_cp = CustomerPayment.query.get(edit_id) if edit_id else None

    if request.method == 'POST':
        jy = request.form.get('j_year', type=int)
        jm = request.form.get('j_month', type=int)
        jd = request.form.get('j_day', type=int)
        g_date = jalali_to_gregorian(jy, jm, jd)

        party_type = request.form.get('party_type', '').strip()
        party_id = request.form.get('party_id', type=int)
        payment_type = request.form.get('payment_type', '').strip()
        pay_currency_id = request.form.get('pay_currency_id', type=int)
        amount = request.form.get('amount', type=float) or 0
        account_currency_id = request.form.get('account_currency_id', type=int)
        bank_id = request.form.get('bank_id', type=int)
        exchange_rate = request.form.get('exchange_rate', type=float) or 1
        converted_amount = request.form.get('converted_amount', type=float) or 0
        notes = request.form.get('notes', '').strip()
        cp_id = request.form.get('cp_id', type=int)

        party_name = get_party_name(party_type, party_id)

        if not (party_type and party_id and payment_type and g_date and amount and pay_currency_id and account_currency_id):
            flash('حسابدار، نوعیت پرداخت، نوعیت پول‌ها، تاریخ و مقدار الزامی است', 'danger')
        else:
            if not converted_amount:
                converted_amount = amount * exchange_rate

            if cp_id:
                cp = CustomerPayment.query.get_or_404(cp_id)
                # برگرداندن اثر قبلی از موجودی بانک
                if cp.bank_id:
                    old_delta = cp.converted_amount if cp.payment_type == 'receipt' else -cp.converted_amount
                    adjust_bank_balance(cp.bank_id, cp.account_currency_id, -old_delta, notes='برگشت تعدیل پرداختی مشتری (ویرایش)')

                cp.date, cp.j_year, cp.j_month, cp.j_day = g_date, jy, jm, jd
                cp.party_type, cp.party_id, cp.party_name = party_type, party_id, party_name
                _set_party_fk(cp, party_type, party_id)
                cp.payment_type = payment_type
                cp.pay_currency_id, cp.amount = pay_currency_id, amount
                cp.account_currency_id, cp.bank_id = account_currency_id, bank_id
                cp.exchange_rate, cp.converted_amount = exchange_rate, converted_amount
                cp.notes = notes

                if bank_id:
                    new_delta = converted_amount if payment_type == 'receipt' else -converted_amount
                    party_label = PARTY_TYPE_LABELS.get(party_type, 'طرف حساب')
                    adjust_bank_balance(bank_id, account_currency_id, new_delta, g_date=g_date,
                                         notes=f'برد و رسید (تبدیل ارزی) — {party_label}: {party_name} (ویرایش)')

                db.session.commit()
                flash('رکورد ویرایش شد', 'success')
            else:
                cp = CustomerPayment(
                    date=g_date, j_year=jy, j_month=jm, j_day=jd,
                    party_type=party_type, party_id=party_id, party_name=party_name,
                    payment_type=payment_type,
                    pay_currency_id=pay_currency_id, amount=amount,
                    account_currency_id=account_currency_id, bank_id=bank_id,
                    exchange_rate=exchange_rate, converted_amount=converted_amount,
                    notes=notes, created_by=session.get('username')
                )
                _set_party_fk(cp, party_type, party_id)
                db.session.add(cp)

                if bank_id:
                    # رسید: پول (به ارز حساب) به صندوق وارد می‌شود — برد: خارج می‌شود
                    delta = converted_amount if payment_type == 'receipt' else -converted_amount
                    adjust_bank_balance(bank_id, account_currency_id, delta, g_date=g_date,
                                         notes=f'برد و رسید (تبدیل ارزی) — {PARTY_TYPE_LABELS.get(party_type, "طرف حساب")}: {party_name}')

                db.session.commit()
                flash('رکورد ثبت شد', 'success')
        return redirect(url_for('main.customer_payment'))

    search = request.args.get('q', '').strip()
    query = CustomerPayment.query
    if search:
        query = query.filter(CustomerPayment.party_name.contains(search))
    records = query.order_by(CustomerPayment.id).all()

    active_currencies = Currency.query.filter_by(is_active=True).order_by(Currency.code).all()
    bank_list = Bank.query.filter_by(is_active=True).order_by(Bank.name).all()
    today = jdatetime.date.today()
    edit_party_list = get_party_list(edit_cp.party_type) if edit_cp else []

    return render_template('receipt/customer_payment.html',
        records=records, edit_cp=edit_cp, active_currencies=active_currencies,
        bank_list=bank_list, today=today, search=search,
        party_type_labels=PARTY_TYPE_LABELS, edit_party_list=edit_party_list)


@main.route('/receipt/customer-payment/delete/<int:id>')
def customer_payment_delete(id):
    cp = CustomerPayment.query.get_or_404(id)
    if cp.bank_id:
        old_delta = cp.converted_amount if cp.payment_type == 'receipt' else -cp.converted_amount
        adjust_bank_balance(cp.bank_id, cp.account_currency_id, -old_delta, notes='برگشت تعدیل پرداختی مشتری (حذف)')
    db.session.delete(cp)
    db.session.commit()
    flash('رکورد حذف شد', 'success')
    return redirect(url_for('main.customer_payment'))


# ==========================================
# تبادله پولی بین حساب مشتری — تبدیل مانده مشتری از یک ارز به ارز دیگر (بدون اثر بانکی)
# ==========================================
def _detect_exchange_sign(customer_id, from_currency_id, exclude_id=None):
    """جهت تبادله را بر اساس مانده فعلی مشتری به ارز مبدا تشخیص می‌دهد.
    اگر مانده فعلی صفر یا نامشخص باشد، پیش‌فرض +1 (مشتری بدهکار فرض می‌شود).
    توجه: چون customer_balance_by_currency اکنون علامت معکوس برمی‌گرداند (منفی = بدهکار)،
    شرط زیر برای حفظ همان نتیجهٔ قبلی (سازگار با ستون sign ذخیره‌شده‌ی رکوردهای قبلی) برعکس شده است."""
    totals = customer_balance_by_currency(customer_id, exclude_exchange_id=exclude_id)
    current = totals.get(from_currency_id, 0.0)
    if current > 0:
        return -1
    return 1


@main.route('/receipt/customer-exchange/balance')
def customer_exchange_balance():
    """مانده تفکیکی-بر-اساس-ارز یک مشتری را برمی‌گرداند (برای باکس «حساب جاری»، اگر بعداً افزوده شود)."""
    from flask import jsonify
    customer_id = request.args.get('customer_id', type=int)
    if not customer_id:
        return jsonify({'balances': []})
    totals = customer_balance_by_currency(customer_id)
    return jsonify({'balances': format_balance_by_currency(totals)})


@main.route('/receipt/customer-exchange', methods=['GET', 'POST'])
def customer_exchange():
    edit_id = request.args.get('edit', type=int)
    edit_ex = CustomerCurrencyExchange.query.get(edit_id) if edit_id else None

    if request.method == 'POST':
        jy = request.form.get('j_year', type=int)
        jm = request.form.get('j_month', type=int)
        jd = request.form.get('j_day', type=int)
        g_date = jalali_to_gregorian(jy, jm, jd)

        customer_id = request.form.get('customer_id', type=int)
        from_currency_id = request.form.get('from_currency_id', type=int)
        amount = request.form.get('amount', type=float) or 0
        to_currency_id = request.form.get('to_currency_id', type=int)
        exchange_rate = request.form.get('exchange_rate', type=float) or 1
        converted_amount = request.form.get('converted_amount', type=float) or 0
        notes = request.form.get('notes', '').strip()
        ex_id = request.form.get('ex_id', type=int)

        if not (customer_id and from_currency_id and to_currency_id and g_date and amount):
            flash('نام مشتری، نوعیت پول‌ها، تاریخ و مقدار الزامی است', 'danger')
        elif from_currency_id == to_currency_id:
            flash('ارز مبدا و مقصد نمی‌توانند یکسان باشند', 'danger')
        else:
            if not converted_amount:
                converted_amount = amount * exchange_rate

            if ex_id:
                ex = CustomerCurrencyExchange.query.get_or_404(ex_id)
                sign = _detect_exchange_sign(customer_id, from_currency_id, exclude_id=ex_id)
                ex.date, ex.j_year, ex.j_month, ex.j_day = g_date, jy, jm, jd
                ex.customer_id = customer_id
                ex.from_currency_id, ex.amount = from_currency_id, amount
                ex.to_currency_id = to_currency_id
                ex.exchange_rate, ex.converted_amount = exchange_rate, converted_amount
                ex.sign = sign
                ex.notes = notes
                db.session.commit()
                flash('رکورد ویرایش شد', 'success')
            else:
                sign = _detect_exchange_sign(customer_id, from_currency_id)
                ex = CustomerCurrencyExchange(
                    date=g_date, j_year=jy, j_month=jm, j_day=jd,
                    customer_id=customer_id,
                    from_currency_id=from_currency_id, amount=amount,
                    to_currency_id=to_currency_id, exchange_rate=exchange_rate,
                    converted_amount=converted_amount, sign=sign, notes=notes
                )
                db.session.add(ex)
                db.session.commit()
                flash('رکورد ثبت شد', 'success')
        return redirect(url_for('main.customer_exchange'))

    search = request.args.get('q', '').strip()
    query = CustomerCurrencyExchange.query
    if search:
        query = query.join(Customer, CustomerCurrencyExchange.customer_id == Customer.id).filter(Customer.name.contains(search))
    records = query.order_by(CustomerCurrencyExchange.id).all()

    customer_list = Customer.query.filter_by(is_active=True).order_by(Customer.name).all()
    active_currencies = Currency.query.filter_by(is_active=True).order_by(Currency.code).all()
    today = jdatetime.date.today()

    return render_template('receipt/customer_exchange.html',
        records=records, edit_ex=edit_ex, customer_list=customer_list,
        active_currencies=active_currencies, today=today, search=search)


@main.route('/receipt/customer-exchange/delete/<int:id>')
def customer_exchange_delete(id):
    ex = CustomerCurrencyExchange.query.get_or_404(id)
    db.session.delete(ex)
    db.session.commit()
    flash('رکورد حذف شد', 'success')
    return redirect(url_for('main.customer_exchange'))

# ==========================================
# انتقال بین بانک‌ها — جابجایی پول بین دو بانک/صندوق (با امکان تبدیل ارز هم‌زمان)
# ==========================================
@main.route('/receipt/bank-transfer', methods=['GET', 'POST'])
def bank_transfer():
    edit_id = request.args.get('edit', type=int)
    edit_bt = BankTransfer.query.get(edit_id) if edit_id else None

    if request.method == 'POST':
        jy = request.form.get('j_year', type=int)
        jm = request.form.get('j_month', type=int)
        jd = request.form.get('j_day', type=int)
        g_date = jalali_to_gregorian(jy, jm, jd)

        from_bank_id = request.form.get('from_bank_id', type=int)
        from_currency_id = request.form.get('from_currency_id', type=int)
        amount = request.form.get('amount', type=float) or 0
        to_bank_id = request.form.get('to_bank_id', type=int)
        to_currency_id = request.form.get('to_currency_id', type=int)
        exchange_rate = request.form.get('exchange_rate', type=float) or 1
        converted_amount = request.form.get('converted_amount', type=float) or 0
        notes = request.form.get('notes', '').strip()
        bt_id = request.form.get('bt_id', type=int)

        if not (from_bank_id and to_bank_id and from_currency_id and to_currency_id and g_date and amount):
            flash('بانک مبدا/مقصد، واحد پولی مبدا/مقصد، تاریخ و مقدار الزامی است', 'danger')
        else:
            if not converted_amount:
                converted_amount = amount * exchange_rate

            if bt_id:
                bt = BankTransfer.query.get_or_404(bt_id)
                # برگرداندن اثر قبلی
                adjust_bank_balance(bt.from_bank_id, bt.from_currency_id, bt.amount, notes='برگشت تعدیل انتقال بین بانک‌ها (ویرایش)')
                adjust_bank_balance(bt.to_bank_id, bt.to_currency_id, -bt.converted_amount, notes='برگشت تعدیل انتقال بین بانک‌ها (ویرایش)')

                bt.date, bt.j_year, bt.j_month, bt.j_day = g_date, jy, jm, jd
                bt.from_bank_id, bt.from_currency_id, bt.amount = from_bank_id, from_currency_id, amount
                bt.to_bank_id, bt.to_currency_id = to_bank_id, to_currency_id
                bt.exchange_rate, bt.converted_amount = exchange_rate, converted_amount
                bt.notes = notes

                adjust_bank_balance(from_bank_id, from_currency_id, -amount, g_date=g_date,
                                     notes=f'انتقال به بانک {Bank.query.get(to_bank_id).name if Bank.query.get(to_bank_id) else ""} (ویرایش)')
                adjust_bank_balance(to_bank_id, to_currency_id, converted_amount, g_date=g_date,
                                     notes=f'انتقال از بانک {Bank.query.get(from_bank_id).name if Bank.query.get(from_bank_id) else ""} (ویرایش)')

                db.session.commit()
                flash('رکورد ویرایش شد', 'success')
            else:
                bt = BankTransfer(
                    date=g_date, j_year=jy, j_month=jm, j_day=jd,
                    from_bank_id=from_bank_id, from_currency_id=from_currency_id, amount=amount,
                    to_bank_id=to_bank_id, to_currency_id=to_currency_id,
                    exchange_rate=exchange_rate, converted_amount=converted_amount, notes=notes,
                    created_by=session.get('username')
                )
                db.session.add(bt)

                to_bank_obj = Bank.query.get(to_bank_id)
                from_bank_obj = Bank.query.get(from_bank_id)
                adjust_bank_balance(from_bank_id, from_currency_id, -amount, g_date=g_date,
                                     notes=f'انتقال به بانک {to_bank_obj.name if to_bank_obj else ""}')
                adjust_bank_balance(to_bank_id, to_currency_id, converted_amount, g_date=g_date,
                                     notes=f'انتقال از بانک {from_bank_obj.name if from_bank_obj else ""}')

                db.session.commit()
                flash('رکورد ثبت شد', 'success')
        return redirect(url_for('main.bank_transfer'))

    search = request.args.get('q', '').strip()
    query = BankTransfer.query
    if search:
        query = query.join(Bank, BankTransfer.from_bank_id == Bank.id).filter(Bank.name.contains(search))
    records = query.order_by(BankTransfer.id).all()

    bank_list = Bank.query.filter_by(is_active=True).order_by(Bank.name).all()
    active_currencies = Currency.query.filter_by(is_active=True).order_by(Currency.code).all()
    today = jdatetime.date.today()

    return render_template('receipt/bank_transfer.html',
        records=records, edit_bt=edit_bt, bank_list=bank_list,
        active_currencies=active_currencies, today=today, search=search)


@main.route('/receipt/bank-transfer/delete/<int:id>')
def bank_transfer_delete(id):
    bt = BankTransfer.query.get_or_404(id)
    adjust_bank_balance(bt.from_bank_id, bt.from_currency_id, bt.amount, notes='برگشت تعدیل انتقال بین بانک‌ها (حذف)')
    adjust_bank_balance(bt.to_bank_id, bt.to_currency_id, -bt.converted_amount, notes='برگشت تعدیل انتقال بین بانک‌ها (حذف)')
    db.session.delete(bt)
    db.session.commit()
    flash('رکورد حذف شد', 'success')
    return redirect(url_for('main.bank_transfer'))


# ---- سند چاپی انتقال بین بانک‌ها ----
@main.route('/receipt/bank-transfer/<int:id>/print')
def bank_transfer_print(id):
    bt = BankTransfer.query.get_or_404(id)
    return render_template('receipt/bank_transfer_print.html', bt=bt)


# ==========================================
# حسابات شخصی — کتگوری عواید متفرقه
# ==========================================
@main.route('/personal/revenue-category', methods=['GET', 'POST'])
def revenue_category():
    edit_id = request.args.get('edit', type=int)
    edit_rc = RevenueCategory.query.get(edit_id) if edit_id else None

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        rc_id = request.form.get('rc_id', type=int)
        if not name:
            flash('نام کتگوری نمی‌تواند خالی باشد', 'danger')
        elif rc_id:
            rc = RevenueCategory.query.get_or_404(rc_id)
            rc.name = name
            db.session.commit()
            flash('کتگوری ویرایش شد', 'success')
        else:
            db.session.add(RevenueCategory(name=name))
            db.session.commit()
            flash('کتگوری ثبت شد', 'success')
        return redirect(url_for('main.revenue_category'))

    search = request.args.get('q', '').strip()
    query = RevenueCategory.query
    if search:
        query = query.filter(RevenueCategory.name.contains(search))
    categories = query.order_by(RevenueCategory.id).all()

    return render_template('personal/revenue_category.html', categories=categories, edit_rc=edit_rc, search=search)


@main.route('/personal/revenue-category/delete/<int:id>')
def revenue_category_delete(id):
    rc = RevenueCategory.query.get_or_404(id)
    db.session.delete(rc)
    db.session.commit()
    flash('کتگوری حذف شد', 'success')
    return redirect(url_for('main.revenue_category'))


# ==========================================
# حسابات شخصی — ثبت عواید متفرقه (تعریف نام عاید ذیل یک کتگوری)
# ==========================================
@main.route('/personal/revenue', methods=['GET', 'POST'])
def revenue():
    edit_id = request.args.get('edit', type=int)
    edit_rv = Revenue.query.get(edit_id) if edit_id else None

    if request.method == 'POST':
        category_id = request.form.get('category_id', type=int)
        name = request.form.get('name', '').strip()
        rv_id = request.form.get('rv_id', type=int)

        if not (category_id and name):
            flash('کتگوری و نام عاید الزامی است', 'danger')
        elif rv_id:
            rv = Revenue.query.get_or_404(rv_id)
            rv.category_id, rv.name = category_id, name
            db.session.commit()
            flash('رکورد ویرایش شد', 'success')
        else:
            db.session.add(Revenue(category_id=category_id, name=name))
            db.session.commit()
            flash('رکورد ثبت شد', 'success')
        return redirect(url_for('main.revenue'))

    search = request.args.get('q', '').strip()
    query = Revenue.query
    if search:
        query = query.filter(Revenue.name.contains(search))
    records = query.order_by(Revenue.id).all()

    revenue_categories = RevenueCategory.query.order_by(RevenueCategory.name).all()

    return render_template('personal/revenue.html',
        records=records, edit_rv=edit_rv, revenue_categories=revenue_categories, search=search)


@main.route('/personal/revenue/delete/<int:id>')
def revenue_delete(id):
    rv = Revenue.query.get_or_404(id)
    db.session.delete(rv)
    db.session.commit()
    flash('رکورد حذف شد', 'success')
    return redirect(url_for('main.revenue'))


# ==========================================
# حسابات شخصی — عواید متفرقه (ثبت واقعی دریافتی با تاریخ/مقدار/ارز/بانک)
# ==========================================
@main.route('/personal/revenue-detail', methods=['GET', 'POST'])
def revenue_detail():
    edit_id = request.args.get('edit', type=int)
    edit_rd = RevenueDetail.query.get(edit_id) if edit_id else None

    if request.method == 'POST':
        jy = request.form.get('j_year', type=int)
        jm = request.form.get('j_month', type=int)
        jd = request.form.get('j_day', type=int)
        g_date = jalali_to_gregorian(jy, jm, jd)

        category_id = request.form.get('category_id', type=int)
        recipient = request.form.get('recipient', '').strip()
        currency_id = request.form.get('currency_id', type=int)
        amount = request.form.get('amount', type=float) or 0
        bank_id = request.form.get('bank_id', type=int)
        notes = request.form.get('notes', '').strip()
        rd_id = request.form.get('rd_id', type=int)

        if not (category_id and currency_id and g_date and amount):
            flash('کتگوری، نوعیت پول، تاریخ و مقدار الزامی است', 'danger')
        else:
            if rd_id:
                rd = RevenueDetail.query.get_or_404(rd_id)
                # برگرداندن اثر قبلی از موجودی بانک
                if rd.bank_id:
                    adjust_bank_balance(rd.bank_id, rd.currency_id, -rd.amount, notes='برگشت تعدیل عواید متفرقه (ویرایش)')

                rd.date, rd.j_year, rd.j_month, rd.j_day = g_date, jy, jm, jd
                rd.category_id, rd.recipient = category_id, recipient
                rd.currency_id, rd.amount = currency_id, amount
                rd.bank_id, rd.notes = bank_id, notes

                if bank_id:
                    adjust_bank_balance(bank_id, currency_id, amount, g_date=g_date,
                                         notes=f'عواید متفرقه — {recipient}' if recipient else 'عواید متفرقه (ویرایش)')

                db.session.commit()
                flash('رکورد ویرایش شد', 'success')
            else:
                rd = RevenueDetail(
                    date=g_date, j_year=jy, j_month=jm, j_day=jd,
                    category_id=category_id, recipient=recipient,
                    currency_id=currency_id, amount=amount,
                    bank_id=bank_id, notes=notes, created_by=session.get('username')
                )
                db.session.add(rd)

                if bank_id:
                    adjust_bank_balance(bank_id, currency_id, amount, g_date=g_date,
                                         notes=f'عواید متفرقه — {recipient}' if recipient else 'عواید متفرقه')

                db.session.commit()
                flash('رکورد ثبت شد', 'success')
        return redirect(url_for('main.revenue_detail'))

    search = request.args.get('q', '').strip()
    query = RevenueDetail.query
    if search:
        query = query.filter(RevenueDetail.recipient.contains(search))
    records = query.order_by(RevenueDetail.id).all()

    revenue_categories = RevenueCategory.query.order_by(RevenueCategory.name).all()
    revenue_names = Revenue.query.order_by(Revenue.name).all()
    active_currencies = Currency.query.filter_by(is_active=True).order_by(Currency.code).all()
    bank_list = Bank.query.filter_by(is_active=True).order_by(Bank.name).all()
    today = jdatetime.date.today()

    return render_template('personal/revenue_detail.html',
        records=records, edit_rd=edit_rd, revenue_categories=revenue_categories,
        revenue_names=revenue_names, active_currencies=active_currencies,
        bank_list=bank_list, today=today, search=search)


@main.route('/personal/revenue-detail/delete/<int:id>')
def revenue_detail_delete(id):
    rd = RevenueDetail.query.get_or_404(id)
    if rd.bank_id:
        adjust_bank_balance(rd.bank_id, rd.currency_id, -rd.amount, notes='برگشت تعدیل عواید متفرقه (حذف)')
    db.session.delete(rd)
    db.session.commit()
    flash('رکورد حذف شد', 'success')
    return redirect(url_for('main.revenue_detail'))


# ==========================================
# قرض‌ها — تعریف قرض‌دهنده/قرض‌گیرنده
# ==========================================
@main.route('/personal/borrowers', methods=['GET', 'POST'])
def borrowers():
    edit_id = request.args.get('edit', type=int)
    edit_b = Borrower.query.get(edit_id) if edit_id else None

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        address = request.form.get('address', '').strip()
        book_no = request.form.get('book_no', '').strip()
        phone = request.form.get('phone', '').strip()
        notes = request.form.get('notes', '').strip()
        b_id = request.form.get('b_id', type=int)

        if not name:
            flash('نام قرض دهنده/گیرنده نمی‌تواند خالی باشد', 'danger')
        elif b_id:
            b = Borrower.query.get_or_404(b_id)
            b.name, b.address, b.book_no, b.phone, b.notes = name, address, book_no, phone, notes
            db.session.commit()
            flash('رکورد ویرایش شد', 'success')
        else:
            db.session.add(Borrower(name=name, address=address, book_no=book_no,
                                     phone=phone, notes=notes))
            db.session.commit()
            flash('قرض ثبت شد', 'success')
        return redirect(url_for('main.borrowers'))

    search = request.args.get('q', '').strip()
    query = Borrower.query
    if search:
        query = query.filter(Borrower.name.contains(search))
    borrowers_list = query.order_by(Borrower.id.desc()).all()

    return render_template('personal/borrowers.html',
        borrowers=borrowers_list, edit_b=edit_b, search=search)


@main.route('/personal/borrowers/delete/<int:id>')
def borrower_delete(id):
    b = Borrower.query.get_or_404(id)

    # ===== بررسی وابستگی‌ها قبل از حذف =====
    has_transactions = CashTransaction.query.filter_by(
        party_type='borrower', party_id=id).first() is not None
    has_payments = CustomerPayment.query.filter_by(
        party_type='borrower', party_id=id).first() is not None

    if has_transactions or has_payments:
        flash('این قرض دارای تراکنش نقدی یا پرداخت ثبت‌شده است — ابتدا آن‌ها را حذف کنید', 'danger')
        return redirect(url_for('main.borrowers'))

    db.session.delete(b)
    db.session.commit()
    flash('رکورد حذف شد', 'success')
    return redirect(url_for('main.borrowers'))


# ==========================================
# قرض‌ها — ثبت حساب افتتاحیه قرضه
# ==========================================
@main.route('/personal/borrower-opening', methods=['GET', 'POST'])
def borrower_opening():
    edit_id = request.args.get('edit', type=int)
    edit_bo = BorrowerOpening.query.get(edit_id) if edit_id else None

    if request.method == 'POST':
        jy = request.form.get('j_year', type=int)
        jm = request.form.get('j_month', type=int)
        jd = request.form.get('j_day', type=int)
        g_date = jalali_to_gregorian(jy, jm, jd)

        borrower_name = request.form.get('borrower_name', '').strip()
        borrower = Borrower.query.filter_by(name=borrower_name).first()
        currency = request.form.get('currency', '').strip()
        amount = request.form.get('amount', type=float) or 0
        account_type = request.form.get('account_type', '').strip()
        bo_id = request.form.get('bo_id', type=int)

        if not borrower or not g_date:
            flash('نام قرضه (از لیست) و تاریخ الزامی است', 'danger')
        elif bo_id:
            bo = BorrowerOpening.query.get_or_404(bo_id)
            bo.date, bo.j_year, bo.j_month, bo.j_day = g_date, jy, jm, jd
            bo.borrower_id, bo.currency = borrower.id, currency
            bo.amount, bo.account_type = amount, account_type
            db.session.commit()
            flash('حساب افتتاحیه ویرایش شد', 'success')
        else:
            db.session.add(BorrowerOpening(
                date=g_date, j_year=jy, j_month=jm, j_day=jd,
                borrower_id=borrower.id, currency=currency,
                amount=amount, account_type=account_type
            ))
            db.session.commit()
            flash('حساب افتتاحیه ثبت شد', 'success')
        return redirect(url_for('main.borrower_opening'))

    search = request.args.get('q', '').strip()
    query = BorrowerOpening.query
    if search:
        query = query.join(Borrower).filter(Borrower.name.contains(search))
    records = query.order_by(BorrowerOpening.id).all()

    borrower_list = Borrower.query.order_by(Borrower.name).all()
    today = jdatetime.date.today()

    return render_template('personal/borrower_opening.html',
        records=records, edit_bo=edit_bo, borrower_list=borrower_list, today=today, search=search)


@main.route('/personal/borrower-opening/delete/<int:id>')
def borrower_opening_delete(id):
    bo = BorrowerOpening.query.get_or_404(id)
    db.session.delete(bo)
    db.session.commit()
    flash('رکورد حذف شد', 'success')
    return redirect(url_for('main.borrower_opening'))


# ==========================================
# قرض‌ها — حسابات قرضه (جستجو)
# ==========================================
@main.route('/personal/borrower-search', methods=['GET'])
def borrower_search():
    borrower_list = Borrower.query.order_by(Borrower.name).all()
    return render_template('personal/borrower_search.html', borrower_list=borrower_list)


@main.route('/personal/borrower-account/<int:borrower_id>')
def borrower_account(borrower_id):
    borrower = Borrower.query.get_or_404(borrower_id)
    balance = borrower_balance(borrower.id)
    return render_template('personal/borrower_account.html', borrower=borrower, balance=balance)


# ---- صورت حساب کلی قرضه (ریز تراکنش‌های قرض‌گرفتگی/قرض‌دادگی با مانده جاری) ----
@main.route('/personal/borrower-account/<int:borrower_id>/summary')
def borrower_summary(borrower_id):
    borrower = Borrower.query.get_or_404(borrower_id)

    entries = []
    for o in BorrowerOpening.query.filter_by(borrower_id=borrower_id).all():
        amt = -(o.amount or 0) if o.account_type == 'receivable' else (o.amount or 0)
        entries.append({'date': o.date, 'j_year': o.j_year, 'j_month': o.j_month, 'j_day': o.j_day,
                         'currency': o.currency or '-', 'ref': 'حساب افتتاحیه', 'desc': '',
                         'debit': amt if amt > 0 else 0, 'credit': -amt if amt < 0 else 0})
    for ct in CashTransaction.query.filter_by(party_type='borrower', party_id=borrower_id).all():
        amt = ct.amount or 0
        entries.append({'date': ct.date, 'j_year': ct.j_year, 'j_month': ct.j_month, 'j_day': ct.j_day,
                         'currency': (ct.currency.code if ct.currency else '-'), 'ref': 'برد و رسید',
                         'desc': ct.notes or '',
                         'debit': 0 if ct.transaction_type == 'payment' else amt,
                         'credit': amt if ct.transaction_type == 'payment' else 0})
    for cp in CustomerPayment.query.filter_by(party_type='borrower', party_id=borrower_id).all():
        amt = cp.amount or 0
        entries.append({'date': cp.date, 'j_year': cp.j_year, 'j_month': cp.j_month, 'j_day': cp.j_day,
                         'currency': (cp.pay_currency.code if cp.pay_currency else '-'),
                         'ref': 'برد و رسید (تبدیل ارزی)', 'desc': cp.notes or '',
                         'debit': 0 if cp.payment_type == 'payment' else amt,
                         'credit': amt if cp.payment_type == 'payment' else 0})

    entries.sort(key=lambda e: e['date'])

    currency_filter = request.args.get('currency', '').strip()
    if currency_filter:
        entries = [e for e in entries if e['currency'] == currency_filter]

    running = 0
    for e in entries:
        running += e['debit'] - e['credit']
        e['balance'] = running

    active_currencies = Currency.query.filter_by(is_active=True).order_by(Currency.code).all()
    balance = borrower_balance(borrower.id)

    return render_template('personal/borrower_summary.html',
        borrower=borrower, entries=entries, active_currencies=active_currencies,
        currency_filter=currency_filter, balance=balance)
