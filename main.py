# main.py (Yeni Python Sistemi - Tam ve Eksiksiz Sürüm)

import os
import logging
from logging.handlers import RotatingFileHandler
from flask import Flask, render_template, url_for, flash, redirect, request, abort, session
from functools import wraps
from flask_login import login_user, current_user, logout_user, login_required
from flask_socketio import SocketIO, emit, join_room, leave_room
from sqlalchemy import or_
from datetime import datetime
from dateutil.relativedelta import relativedelta
import secrets
import json

# Yeni servis dosyamızı import ediyoruz
from shopier_service import ShopierService, Buyer, Address
from sqlalchemy import func, extract
from extensions import db, bcrypt, login_manager
from models import User, Product, Order, ServiceCredential, Notification, SupportTicket, ChatMessage, Coupon, Announcement
from forms import (RegistrationForm, LoginForm, ProductForm, CredentialForm,
                   ManualServiceForm, NotificationForm, SupportTicketForm,
                   ChangePasswordForm, SupportTicketForm, CouponForm,
                   AnnouncementForm)

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get(
    'SECRET_KEY', 'default_secret_key_for_development')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# --- SHOPIER API YAPILANDIRMASI ---
# Bu bilgileri Replit'in Secrets (ortam değişkenleri) bölümüne girin.
app.config['SHOPIER_API_KEY'] = os.environ.get('SHOPIER_API_KEY')
app.config['SHOPIER_API_SECRET'] = os.environ.get('SHOPIER_API_SECRET')

# Hata kontrolü
if not app.config['SHOPIER_API_KEY'] or not app.config['SHOPIER_API_SECRET']:
    raise ValueError(
        "Lütfen Replit Secrets'a SHOPIER_API_KEY ve SHOPIER_API_SECRET ekleyin."
    )

# Shopier servisini başlat
shopier = ShopierService(app.config['SHOPIER_API_KEY'],
                         app.config['SHOPIER_API_SECRET'])

# --- LOGLAMA, EXTENSIONS, DECORATORS... (Tüm yardımcı kodlar) ---
log_formatter = logging.Formatter(
    '%(asctime)s %(levelname)s %(funcName)s(%(lineno)d) %(message)s')
log_file = 'app.log'
file_handler = RotatingFileHandler(log_file,
                                   maxBytes=5 * 1024 * 1024,
                                   backupCount=2)
file_handler.setFormatter(log_formatter)
file_handler.setLevel(logging.INFO)
app.logger.addHandler(file_handler)
app.logger.setLevel(logging.INFO)
socketio = SocketIO(app)
db.init_app(app)
bcrypt.init_app(app)
login_manager.init_app(app)
user_sids = {}


def admin_required(f):

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            flash('Bu sayfaya erişim için admin yetkisi gereklidir.', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)

    return decorated_function


def support_required(f):

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role not in [
                'support', 'admin'
        ]:
            flash('Bu sayfaya erişim yetkiniz yok.', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)

    return decorated_function


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


@app.context_processor
def inject_global_variables():
    cart_item_count = len(session.get('cart', {}))
    has_unread = False
    if current_user.is_authenticated:
        unread_direct_count = db.session.query(Notification.id).filter_by(
            recipient_id=current_user.id, is_read=False).count()
        last_read_time = current_user.last_notification_read_time or datetime.min
        unread_broadcast_count = db.session.query(Notification.id).filter(
            Notification.recipient_id == None, Notification.timestamp
            > last_read_time).count()
        if unread_direct_count > 0 or unread_broadcast_count > 0:
            has_unread = True
    is_admin = current_user.is_authenticated and current_user.role == 'admin'
    is_support = current_user.is_authenticated and current_user.role in [
        'support', 'admin'
    ]
    # --- EKSİK OLAN VE ŞİMDİ EKLENEN BÖLÜM ---
    # Aktif olan son duyuruyu bul
    active_announcement = Announcement.query.filter_by(
        is_active=True).order_by(Announcement.timestamp.desc()).first()
    # -------------------------------------------
    return dict(is_admin=is_admin,
                is_support=is_support,
                has_unread_notifications=has_unread,
                cart_item_count=cart_item_count,
                active_announcement=active_announcement)


# --- GENEL VE KULLANICI ROTALARI ---
@app.route("/")
@app.route("/index")
def index():
    products = Product.query.limit(3).all()
    return render_template('index.html', title='Ana Sayfa', products=products)


@app.route("/paketler")
def paketler():
    products = Product.query.all()
    return render_template('paketler.html',
                           title='Hosting Paketleri',
                           products=products)


@app.route("/paket/<int:product_id>")
def product_detail(product_id):
    product = db.session.get(Product, product_id) or abort(404)
    return render_template("product_detail.html",
                           title=product.name,
                           product=product)


@app.route("/kayit", methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated: return redirect(url_for('index'))
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(
            username=form.username.data,
            email=form.email.data,
            first_name=form.first_name.data,  # <-- YENİ
            last_name=form.last_name.data,  # <-- YENİ
            role='customer')
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash('Hesabınız başarıyla oluşturuldu! Şimdi giriş yapabilirsiniz.',
              'success')
        return redirect(url_for('login'))
    return render_template('register.html', title='Kayıt Ol', form=form)


@app.route("/giris", methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated: return redirect(url_for('index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and user.check_password(form.password.data):
            login_user(user, remember=form.remember.data)
            next_page = request.args.get('next')
            flash('Giriş başarılı!', 'success')
            if user.role == 'admin':
                return redirect(url_for('admin_dashboard'))
            if user.role == 'support':
                return redirect(url_for('support_live_chat'))
            return redirect(next_page) if next_page else redirect(
                url_for('customer_dashboard'))
        else:
            flash('Giriş başarısız. Lütfen e-posta ve şifrenizi kontrol edin.',
                  'danger')
    return render_template('login.html', title='Giriş Yap', form=form)


@app.route("/cikis")
@login_required
def logout():
    logout_user()
    session.pop('cart', None)
    return redirect(url_for('index'))


# --- SEPET ROTALARI ---
@app.route('/sepete_ekle/<int:product_id>', methods=['POST'])
@login_required
def add_to_cart(product_id):
    cart = session.get('cart', {})
    cart[str(product_id)] = 1
    session['cart'] = cart
    product = db.session.get(Product, product_id)
    flash(f'"{product.name}" sepetinize eklendi.', 'success')
    return redirect(request.referrer or url_for('paketler'))


@app.route('/sepetim')
@login_required
def cart():
    cart_items = []
    subtotal = 0
    cart_data = session.get('cart', {})

    if cart_data:
        product_ids = [int(id) for id in cart_data.keys()]
        cart_products = db.session.query(Product).filter(
            Product.id.in_(product_ids)).all()
        for product in cart_products:
            quantity = cart_data.get(str(product.id), 0)
            cart_items.append({'product': product, 'quantity': quantity})
            subtotal += product.price * quantity

    # Kupon indirimini hesapla
    discount = 0
    applied_coupon = None
    coupon_id = session.get('coupon_id')
    if coupon_id:
        applied_coupon = db.session.get(Coupon, coupon_id)
        if applied_coupon and applied_coupon.is_active:
            discount = (subtotal * applied_coupon.discount_percentage) / 100
        else:
            # Kupon artık geçerli değilse session'dan kaldır
            session.pop('coupon_id', None)
            applied_coupon = None

    total_price = subtotal - discount

    return render_template('cart.html',
                           title='Sepetim',
                           cart_items=cart_items,
                           subtotal=subtotal,
                           discount=discount,
                           total_price=total_price,
                           applied_coupon=applied_coupon)


@app.route('/sepeti_guncelle', methods=['POST'])
@login_required
def update_cart():
    flash('Sepetiniz güncellendi.', 'info')
    return redirect(url_for('cart'))


@app.route('/sepetten_cikar/<int:product_id>', methods=['POST'])
@login_required
def remove_from_cart(product_id):
    cart = session.get('cart', {})
    if str(product_id) in cart:
        cart.pop(str(product_id))
        session['cart'] = cart
        flash('Ürün sepetten çıkarıldı.', 'info')
    return redirect(url_for('cart'))


@app.route('/onayla', methods=['GET', 'POST'])
@login_required
def checkout():
    cart_data = session.get('cart', {})
    if not cart_data:
        flash('Sepetiniz boş.', 'warning')
        return redirect(url_for('cart'))

    items_in_cart = []
    subtotal = 0  # Ara toplam için yeni değişken
    product_ids = [int(id) for id in cart_data.keys()]
    products = db.session.query(Product).filter(
        Product.id.in_(product_ids)).all()

    if not products:
        session.pop('cart', None)
        return redirect(url_for('paketler'))

    for product in products:
        quantity = cart_data.get(str(product.id), 0)
        items_in_cart.append({'product': product, 'quantity': quantity})
        subtotal += product.price * quantity

    # --- YENİ EKLENEN BÖLÜM ---
    # Kupon indirimini burada da hesapla
    discount = 0
    applied_coupon = None
    coupon_id = session.get('coupon_id')
    if coupon_id:
        applied_coupon = db.session.get(Coupon, coupon_id)
        if applied_coupon and applied_coupon.is_active:
            discount = (subtotal * applied_coupon.discount_percentage) / 100
        else:
            session.pop('coupon_id', None)
            applied_coupon = None

    total_price = subtotal - discount  # İndirimli son fiyat
    # --------------------------

    formatted_total_price = "{:.2f}".format(total_price)

    if request.method == 'POST':
        # Ödeme başlatma kısmının geri kalanı aynı
        platform_order_id = f"MH-{secrets.token_hex(8).upper()}"
        notes = request.form.get('notes')
        for item in items_in_cart:
            order = Order(user_id=current_user.id,
                          product_id=item['product'].id,
                          status='Ödeme Bekleniyor',
                          notes=notes,
                          platform_order_id=platform_order_id)
            db.session.add(order)
        db.session.commit()

        buyer_name_parts = current_user.username.split(' ', 1)
        buyer = Buyer(
            id=str(current_user.id),
            name=buyer_name_parts[0],
            surname=buyer_name_parts[1] if len(buyer_name_parts) > 1 else '.',
            email=current_user.email,
            phone='5555555555')
        address = Address(address='Adres gerekli değil',
                          city='Istanbul',
                          country='Turkey',
                          postcode='34000')

        callback_url = url_for('payment_callback', _external=True)

        try:
            params = shopier.get_params(
                platform_order_id=platform_order_id,
                total_order_value=
                formatted_total_price,  # Buraya indirimli fiyat gidiyor
                buyer=buyer,
                billing_address=address,
                shipping_address=address,
                callback_url=callback_url)
            return render_template('shopier_redirect.html',
                                   shopier_params=params,
                                   payment_url=shopier.payment_url)
        except Exception as e:
            app.logger.error(f"Shopier ödeme başlatma hatası: {e}")
            flash(
                "Ödeme başlatılırken bir sorun oluştu. Lütfen tekrar deneyin.",
                "danger")
            return redirect(url_for('cart'))

    # GET isteği için, indirimli fiyatları template'e gönder
    return render_template('checkout.html',
                           title='Siparişi Onayla',
                           items=items_in_cart,
                           subtotal=subtotal,
                           discount=discount,
                           total_price=total_price,
                           applied_coupon=applied_coupon)


@app.route('/payment/callback', methods=['POST'])
def payment_callback():
    # Bu fonksiyon artık sadece Shopier'dan gelen POST isteklerini kabul eder.
    # Hem sunucu bildirimi hem de kullanıcı yönlendirmesi bu adrese POST ile gelir.

    post_data = request.form.to_dict()
    app.logger.info(f"Callback (POST) isteği alındı: {post_data}")

    is_valid = shopier.verify_callback(post_data)

    if is_valid:
        platform_order_id = post_data.get('platform_order_id')
        status = post_data.get('status')

        if status == 'success':
            # Ödeme başarılıysa, siparişi veritabanında bul ve onayla.
            orders_to_update = Order.query.filter_by(
                platform_order_id=platform_order_id,
                status='Ödeme Bekleniyor').all()
            if orders_to_update:
                for order in orders_to_update:
                    # --- İSTEDİĞİN TEK DEĞİŞİKLİK BURADA ---
                    order.status = 'Onay Bekliyor'
                    # Otomatik hizmet bilgisi oluşturma satırları kaldırıldı.
                # --- Yenileme ---
                if order.product.billing_cycle == 'Aylık':
                    order.expiry_date = datetime.utcnow() + relativedelta(
                        months=1)
                elif order.product.billing_cycle == 'Yıllık':
                    order.expiry_date = datetime.utcnow() + relativedelta(
                        years=1)
                    # --- Yenileme 2 ---
                db.session.commit()
                app.logger.info(
                    f"Sipariş {platform_order_id} başarıyla 'Onay Bekliyor' durumuna getirildi."
                )
            else:
                app.logger.warning(
                    f"Callback: Veritabanında bekleyen sipariş bulunamadı veya zaten işlenmiş: {platform_order_id}"
                )

            # Sepeti temizle ve kullanıcıya başarı sayfasını göster.
            session.pop('cart', None)
            return render_template('payment_success.html',
                                   title="Ödeme Başarılı")

        else:
            # Ödeme başarısız olduysa, kullanıcıyı bir hata mesajıyla sepete geri gönder.
            flash('Ödeme işlemi başarısız oldu veya iptal edildi.', 'danger')
            return redirect(url_for('cart'))
    else:
        # İmza geçersizse, bu şüpheli bir istektir. Ana sayfaya yönlendir.
        app.logger.error("GEÇERSİZ İMZA! Callback isteği reddedildi.")
        flash('Geçersiz bir ödeme dönüşü tespit edildi.', 'warning')
        return redirect(url_for('index'))


# --- DİĞER TÜM ROTALAR ---
@app.route("/hesabim/dashboard")
@login_required
def customer_dashboard():
    active_services_count = Order.query.filter_by(user_id=current_user.id,
                                                  status='Aktif').count()
    pending_orders_count = Order.query.filter_by(
        user_id=current_user.id, status='Onay Bekliyor').count()
    return render_template('musteri/dashboard.html',
                           title='Müşteri Paneli',
                           active_services_count=active_services_count,
                           pending_orders_count=pending_orders_count)


@app.route("/hesabim/siparisler")
@login_required
def customer_orders():
    orders = Order.query.filter_by(user_id=current_user.id).order_by(
        Order.order_date.desc()).all()
    return render_template('musteri/siparisler.html',
                           title='Siparişlerim',
                           orders=orders)


# main.py - customer_services fonksiyonu


@app.route("/hesabim/hizmetlerim")
@login_required
def customer_services():
    active_orders_query = Order.query.filter_by(
        user_id=current_user.id,
        status='Aktif').order_by(Order.order_date.desc()).all()

    services = []
    for order in active_orders_query:
        days_left = 0
        if order.expiry_date:
            days_left = (order.expiry_date - datetime.utcnow()).days
        services.append({'order': order, 'days_left': days_left})

    return render_template('musteri/hizmetlerim.html',
                           title='Aktif Hizmetlerim',
                           services=services)


@app.route("/hesabim/hizmet/<int:order_id>")
@login_required
def service_detail(order_id):
    order = db.session.get(Order, order_id) or abort(404)
    if order.customer != current_user: abort(403)
    if order.status != 'Aktif':
        flash('Bu hizmet henüz aktif edilmemiş.', 'warning')
        return redirect(url_for('customer_services'))
    return render_template('musteri/hizmet_detay.html',
                           title=f'{order.product.name} Detayları',
                           order=order)


# main.py dosyasına eklenecek yeni rota


@app.route("/hesabim/sifre-degistir", methods=['GET', 'POST'])
@login_required
def change_password():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        # Mevcut şifrenin doğru olup olmadığını kontrol et
        if current_user.check_password(form.current_password.data):
            # Yeni şifreyi ayarla
            current_user.set_password(form.new_password.data)
            db.session.commit()
            flash('Şifreniz başarıyla güncellendi!', 'success')
            return redirect(url_for('customer_dashboard'))
        else:
            flash('Mevcut şifreniz yanlış. Lütfen tekrar deneyin.', 'danger')
    return render_template('musteri/sifre_degistir.html',
                           title='Şifre Değiştir',
                           form=form)


@app.route("/bildirimlerim")
@login_required
def notifications():
    Notification.query.filter_by(recipient_id=current_user.id,
                                 is_read=False).update({'is_read': True})
    current_user.last_notification_read_time = datetime.utcnow()
    db.session.commit()
    all_visible_notifications = Notification.query.filter(
        or_(Notification.recipient_id == current_user.id,
            Notification.recipient_id == None)).order_by(
                Notification.timestamp.desc()).all()
    return render_template('bildirimlerim.html',
                           title="Bildirimlerim",
                           notifications=all_visible_notifications)


@app.route("/admin/dashboard")
@admin_required
def admin_dashboard():
    stats = {
        'user_count': User.query.count(),
        'pending_orders':
        Order.query.filter_by(status='Onay Bekliyor').count(),
        'active_services': Order.query.filter_by(status='Aktif').count(),
        'total_products': Product.query.count()
    }
    return render_template('admin/dashboard.html',
                           title='Admin Paneli',
                           stats=stats)


@app.route("/admin/siparisler")
@admin_required
def admin_orders():
    status_filter = request.args.get('status')
    valid_statuses = [
        'Onay Bekliyor', 'Aktif', 'İptal Edildi', 'Ödeme Bekleniyor',
        'Ödeme Başarısız'
    ]
    if status_filter in valid_statuses:
        orders = Order.query.filter_by(status=status_filter).order_by(
            Order.order_date.desc()).all()
    else:
        orders = Order.query.order_by(Order.order_date.desc()).all()
    return render_template('admin/siparisler.html',
                           title='Sipariş Yönetimi',
                           orders=orders)


@app.route("/admin/siparis/onayla/<int:order_id>", methods=['GET', 'POST'])
@admin_required
def approve_order(order_id):
    order = db.session.get(Order, order_id) or abort(404)
    form = CredentialForm()
    if form.validate_on_submit():
        order.status = 'Aktif'
        #yenileme tarih
        if order.product.billing_cycle == 'Aylık':
            order.expiry_date = datetime.utcnow() + relativedelta(months=1)
        elif order.product.billing_cycle == 'Yıllık':
            order.expiry_date = datetime.utcnow() + relativedelta(years=1)

        credential = ServiceCredential(order_id=order.id,
                                       content=form.content.data)
        db.session.add(credential)
        db.session.commit()
        flash(f'Sipariş #{order.id} onaylandı.', 'success')
        return redirect(url_for('admin_orders'))
    return render_template('admin/siparis_onayla.html',
                           title='Sipariş Onayla',
                           form=form,
                           order=order)


@app.route('/admin/siparis/iptal/<int:order_id>', methods=['POST'])
@admin_required
def cancel_order(order_id):
    order = db.session.get(Order, order_id) or abort(404)
    order.status = 'İptal Edildi'
    db.session.commit()
    flash(f'Sipariş #{order.id} iptal edildi.', 'warning')
    return redirect(url_for('admin_orders'))


@app.route('/admin/orders/delete_canceled', methods=['POST'])
@admin_required
def delete_canceled_orders():
    try:
        num_deleted = db.session.query(Order).filter(
            Order.status.in_(['İptal Edildi', 'Ödeme Başarısız'])).delete()
        db.session.commit()
        if num_deleted > 0:
            flash(f'{num_deleted} adet sipariş kalıcı olarak silindi.',
                  'success')
        else:
            flash('Silinecek sipariş bulunamadı.', 'info')
    except Exception as e:
        db.session.rollback()
        flash(f'Siparişler silinirken bir hata oluştu: {e}', 'danger')
        app.logger.error(f'İptal edilen siparişler silinemedi: {e}')
    return redirect(url_for('admin_orders'))


@app.route('/admin/hizmet/ekle', methods=['GET', 'POST'])
@admin_required
def add_manual_service():
    form = ManualServiceForm()
    if form.validate_on_submit():
        customer = form.customer.data
        product = form.product.data
        order = Order(customer=customer, product=product, status='Aktif')

        # --- YENİ EKLENEN BÖLÜM ---
        # Son kullanma tarihini ürünün döngüsüne göre hesapla
        if product.billing_cycle == 'Aylık':
            order.expiry_date = datetime.utcnow() + relativedelta(months=1)
        elif product.billing_cycle == 'Yıllık':
            order.expiry_date = datetime.utcnow() + relativedelta(years=1)
        # Not: Gelecekte başka fatura döngüleri (3 aylık, 6 aylık vb.) eklersen,
        # buraya yeni 'elif' koşulları eklemen gerekir.
        # --------------------------

        db.session.add(order)
        db.session.commit()
        credential = ServiceCredential(order_id=order.id,
                                       content=form.credentials.data)
        db.session.add(credential)
        db.session.commit()
        flash(
            f"'{customer.username}' için '{product.name}' hizmeti başarıyla manuel olarak oluşturuldu.",
            "success")
        return redirect(url_for('admin_orders', status='Aktif'))
    return render_template('admin/hizmet_ekle.html',
                           title="Manuel Hizmet Ekle",
                           form=form)


@app.route("/admin/paketler")
@admin_required
def admin_products():
    products = Product.query.all()
    return render_template('admin/paketler.html',
                           title='Paket Yönetimi',
                           products=products)


@app.route("/admin/paket/yeni", methods=['GET', 'POST'])
@admin_required
def new_product():
    form = ProductForm()
    if form.validate_on_submit():
        product = Product(name=form.name.data,
                          description=form.description.data,
                          price=form.price.data,
                          billing_cycle=form.billing_cycle.data,
                          image_url=form.image_url.data)
        db.session.add(product)
        db.session.commit()
        flash('Yeni hosting paketi başarıyla eklendi!', 'success')
        return redirect(url_for('admin_products'))
    return render_template('admin/paket_form.html',
                           title='Yeni Paket Ekle',
                           form=form,
                           legend='Yeni Paket Ekle')


@app.route("/admin/paket/duzenle/<int:product_id>", methods=['GET', 'POST'])
@admin_required
def edit_product(product_id):
    product = db.session.get(Product, product_id) or abort(404)
    form = ProductForm(obj=product)
    if form.validate_on_submit():
        form.populate_obj(product)
        db.session.commit()
        flash('Paket bilgileri güncellendi!', 'success')
        return redirect(url_for('admin_products'))
    return render_template('admin/paket_form.html',
                           title='Paketi Düzenle',
                           form=form,
                           legend='Paketi Düzenle')


@app.route('/admin/paket/sil/<int:product_id>', methods=['POST'])
@admin_required
def delete_product(product_id):
    product = db.session.get(Product, product_id) or abort(404)
    if product.orders:
        flash('Bu paketle ilişkili siparişler olduğu için silinemez.',
              'danger')
        return redirect(url_for('admin_products'))
    db.session.delete(product)
    db.session.commit()
    flash('Paket silindi!', 'success')
    return redirect(url_for('admin_products'))


@app.route("/admin/musteriler")
@admin_required
def admin_customers():
    users = User.query.order_by(User.id).all()
    return render_template('admin/musteriler.html',
                           title='Müşteri Yönetimi',
                           users=users)


@app.route("/admin/bildirim/gonder", methods=['GET', 'POST'])
@admin_required
def send_notification():
    form = NotificationForm()
    if form.validate_on_submit():
        recipient_user = form.recipient.data
        title = form.title.data
        message = form.message.data
        notification = Notification(
            recipient_id=recipient_user.id if recipient_user else None,
            title=title,
            message=message)
        db.session.add(notification)
        db.session.commit()
        notification_data = {'title': title, 'message': message}
        if recipient_user:
            if recipient_user.id in user_sids:
                for sid in user_sids[recipient_user.id]:
                    socketio.emit('new_notification',
                                  notification_data,
                                  to=sid)
                flash(
                    f"'{recipient_user.username}' kullanıcısına bildirim gönderildi.",
                    "success")
            else:
                flash(
                    f"'{recipient_user.username}' şu an aktif değil, ancak giriş yaptığında bildirimi görecek.",
                    "info")
        else:
            socketio.emit('new_notification', notification_data, namespace='/')
            flash("Tüm aktif kullanıcılara bildirim gönderildi.", "success")
        return redirect(url_for('send_notification'))
    return render_template("admin/gonder_bildirim.html",
                           title="Bildirim Gönder",
                           form=form)


@app.route("/support/live-chat")
@support_required
def support_live_chat():
    pending_tickets = SupportTicket.query.filter_by(status='Pending').order_by(
        SupportTicket.created_at.asc()).all()
    active_tickets = SupportTicket.query.filter_by(status='Active').order_by(
        SupportTicket.created_at.desc()).all()
    return render_template('support/live_chat.html',
                           title='Destek Paneli',
                           pending_tickets=pending_tickets,
                           active_tickets=active_tickets)


@app.route('/support/start_chat/<int:ticket_id>', methods=['POST'])
@support_required
def start_chat(ticket_id):
    ticket = db.session.get(SupportTicket, ticket_id)
    if not ticket or ticket.status != 'Pending':
        flash('Geçersiz veya zaten işlem yapılmış destek talebi.', 'danger')
        return redirect(url_for('support_live_chat'))
    ticket.status = 'Active'
    db.session.commit()
    socketio.emit('chat_approved', {'ticket_id': ticket.id},
                  to=ticket.id,
                  namespace='/chat')
    socketio.emit(
        'ticket_approved',
        {'ticket': {
            'id': ticket.id,
            'customer_name': ticket.customer_name
        }},
        to='support_team',
        namespace='/chat')
    flash(f'Talep #{ticket.id} için sohbet başlatıldı.', 'success')
    return redirect(url_for('support_live_chat'))


@app.route('/hizmet/yenile/<int:order_id>', methods=['POST'])
@login_required
def renew_service(order_id):
    """ Mevcut bir hizmeti yenilemek için ürünü sepete ekler. """
    order = db.session.get(Order, order_id)
    if not order or order.customer != current_user:
        flash('Geçersiz işlem.', 'danger')
        return redirect(url_for('customer_services'))

    # Ürünü sepete ekle
    cart = session.get('cart', {})
    cart[str(order.product_id)] = 1
    session['cart'] = cart

    flash(
        f'"{order.product.name}" hizmetini yenilemek için sepetinize eklendi. Ödemeyi tamamlayarak hizmet sürenizi uzatabilirsiniz.',
        'success')
    return redirect(url_for('cart'))


@app.route('/hizmet/iptal-et/<int:order_id>', methods=['POST'])
@login_required
def request_cancellation(order_id):
    """ Bir hizmet için iptal talebi oluşturur. """
    order = db.session.get(Order, order_id)
    if not order or order.customer != current_user:
        flash('Geçersiz işlem.', 'danger')
        return redirect(url_for('customer_services'))

    # Siparişin durumunu 'İptal Talep Edildi' olarak güncelle
    order.status = 'İptal Talep Edildi'
    db.session.commit()

    flash(
        f'"{order.product.name}" hizmeti için iptal talebiniz alındı. Yetkililerimiz en kısa sürede sizinle iletişime geçecektir.',
        'info')
    return redirect(url_for('customer_services'))


# main.py dosyasına eklenecek yeni admin rotaları kupon


@app.route("/admin/kuponlar", methods=['GET', 'POST'])
@admin_required
def admin_coupons():
    form = CouponForm()
    if form.validate_on_submit():
        coupon = Coupon(code=form.code.data.upper(),
                        discount_percentage=form.discount_percentage.data)
        db.session.add(coupon)
        db.session.commit()
        flash('Yeni kupon başarıyla oluşturuldu!', 'success')
        return redirect(url_for('admin_coupons'))

    coupons = Coupon.query.order_by(Coupon.created_at.desc()).all()
    return render_template('admin/kuponlar.html',
                           title='Kupon Yönetimi',
                           coupons=coupons,
                           form=form)


@app.route('/admin/kupon/sil/<int:coupon_id>', methods=['POST'])
@admin_required
def delete_coupon(coupon_id):
    coupon = db.session.get(Coupon, coupon_id) or abort(404)
    db.session.delete(coupon)
    db.session.commit()
    flash('Kupon başarıyla silindi.', 'success')
    return redirect(url_for('admin_coupons'))


@app.route('/kupon-uygula', methods=['POST'])
@login_required
def apply_coupon():
    code = request.form.get('coupon_code').upper()
    coupon = Coupon.query.filter_by(code=code, is_active=True).first()

    if coupon:
        session['coupon_id'] = coupon.id
        flash(f'"{coupon.code}" kuponu başarıyla uygulandı!', 'success')
    else:
        flash('Geçersiz veya pasif kupon kodu.', 'danger')

    return redirect(url_for('cart'))


@app.route('/kupon-kaldir', methods=['POST'])
@login_required
def remove_coupon():
    if 'coupon_id' in session:
        session.pop('coupon_id', None)
        flash('Kupon kaldırıldı.', 'info')
    return redirect(url_for('cart'))


# main.py duyuru


@app.route("/admin/duyurular", methods=['GET', 'POST'])
@admin_required
def admin_announcements():
    form = AnnouncementForm()
    if form.validate_on_submit():
        # Yeni duyuru oluştur
        announcement = Announcement(title=form.title.data,
                                    content=form.content.data,
                                    category=form.category.data,
                                    is_active=True)
        # Aktif olan diğer tüm duyuruları pasif yap
        Announcement.query.filter_by(is_active=True).update(
            {"is_active": False})
        db.session.add(announcement)
        db.session.commit()
        flash(
            'Yeni duyuru başarıyla yayınlandı ve diğerleri pasif hale getirildi.',
            'success')
        return redirect(url_for('admin_announcements'))

    announcements = Announcement.query.order_by(
        Announcement.timestamp.desc()).all()
    return render_template('admin/duyurular.html',
                           title='Duyuru Yönetimi',
                           announcements=announcements,
                           form=form)


@app.route('/admin/duyuru/sil/<int:announcement_id>', methods=['POST'])
@admin_required
def delete_announcement(announcement_id):
    announcement = db.session.get(Announcement, announcement_id) or abort(404)
    db.session.delete(announcement)
    db.session.commit()
    flash('Duyuru başarıyla silindi.', 'success')
    return redirect(url_for('admin_announcements'))


@app.route('/admin/duyuru/aktiflestir/<int:announcement_id>', methods=['POST'])
@admin_required
def activate_announcement(announcement_id):
    # Önce tüm duyuruları pasif yap
    Announcement.query.filter_by(is_active=True).update({"is_active": False})
    # Sonra seçileni aktif yap
    announcement = db.session.get(Announcement, announcement_id) or abort(404)
    announcement.is_active = True
    db.session.commit()
    flash('Duyuru başarıyla aktif edildi.', 'success')
    return redirect(url_for('admin_announcements'))


@app.route("/admin/raporlar")
@admin_required
def admin_reports():
    # 1. Aylık Gelir Raporu
    monthly_revenue = db.session.query(
        func.strftime('%Y-%m', Order.order_date).label('month'),
        func.sum(Product.price)).join(Product).filter(
            Order.status == 'Aktif').group_by('month').order_by('month').all()

    # Grafik için verileri hazırla
    chart_labels = [row[0] for row in monthly_revenue]
    chart_data = [float(row[1]) for row in monthly_revenue]

    # 2. En Çok Satan Paketler Raporu
    best_selling_products = db.session.query(
        Product.name,
        func.count(Order.id).label('sales_count')).join(Order).group_by(
            Product.name).order_by(func.count(Order.id).desc()).limit(5).all()

    # 3. Son Kaydolan Müşteriler
    recent_customers = User.query.filter_by(role='customer').order_by(
        User.id.desc()).limit(10).all()

    return render_template('admin/raporlar.html',
                           title='Raporlar ve İstatistikler',
                           chart_labels=chart_labels,
                           chart_data=chart_data,
                           best_selling_products=best_selling_products,
                           recent_customers=recent_customers)


# --- SOCKET.IO OLAY YÖNETİCİLERİ ---
@socketio.on('connect')
def handle_connect(auth=None):
    global user_sids
    if current_user.is_authenticated:
        if current_user.id not in user_sids: user_sids[current_user.id] = set()
        user_sids[current_user.id].add(request.sid)


@socketio.on('disconnect')
def handle_disconnect():
    global user_sids
    if current_user.is_authenticated:
        if current_user.id in user_sids and request.sid in user_sids[
                current_user.id]:
            user_sids[current_user.id].remove(request.sid)
            if not user_sids[current_user.id]: del user_sids[current_user.id]


@socketio.on('connect', namespace='/chat')
def chat_connect():
    if current_user.is_authenticated and current_user.role in [
            'support', 'admin'
    ]:
        join_room('support_team')
        app.logger.info(
            f"Yetkili {current_user.username}, support_team odasına katıldı.")


@socketio.on('disconnect', namespace='/chat')
def chat_disconnect():
    ticket = SupportTicket.query.filter_by(customer_sid=request.sid,
                                           status='Active').first()
    if ticket:
        socketio.emit('customer_left', {'ticket_id': ticket.id},
                      to='support_team',
                      namespace='/chat')
        app.logger.info(
            f"Müşteri {ticket.customer_name}, #{ticket.id} nolu sohbetten ayrıldı."
        )


@socketio.on('new_support_ticket', namespace='/chat')
def handle_new_ticket(data):
    form = SupportTicketForm(data=data, meta={'csrf': False})
    if form.validate():
        ticket = SupportTicket(customer_sid=request.sid,
                               customer_name=form.name.data,
                               customer_email=form.email.data,
                               subject=form.subject.data,
                               customer_token=secrets.token_hex(16))
        db.session.add(ticket)
        db.session.commit()
        join_room(ticket.id)
        emit('ticket_received', {
            'ticket_id': ticket.id,
            'token': ticket.customer_token
        })
        socketio.emit('new_ticket_arrived', {
            'id': ticket.id,
            'customer_name': ticket.customer_name,
            'subject': ticket.subject,
            'time': ticket.created_at.strftime('%H:%M')
        },
                      to='support_team',
                      namespace='/chat')
    else:
        emit('form_error', {'errors': form.errors})


@socketio.on('join_chat_room', namespace='/chat')
def join_chat_room(data):
    ticket_id = data.get('ticket_id')
    ticket = db.session.get(SupportTicket, ticket_id)
    if not ticket: return
    join_room(ticket_id)
    if not (current_user.is_authenticated
            and current_user.role in ['support', 'admin']):
        ticket.customer_sid = request.sid
        db.session.commit()
    messages = ticket.messages.order_by(ChatMessage.timestamp.asc()).all()
    message_history = [{
        'sender': m.author_name,
        'message': m.body,
        'role': m.author_role
    } for m in messages]
    emit('load_history', {'messages': message_history})
    if current_user.is_authenticated and current_user.role in [
            'support', 'admin'
    ]:
        socketio.emit('status',
                      {'msg': f'{current_user.username} sohbete katıldı.'},
                      to=ticket_id,
                      namespace='/chat')


@socketio.on('send_message', namespace='/chat')
def send_message(data):
    ticket_id = data.get('ticket_id')
    message_body = data.get('message')
    ticket = db.session.get(SupportTicket, ticket_id)
    if not ticket or ticket.status != 'Active' or not message_body: return
    is_auth = current_user.is_authenticated
    author_id = current_user.id if is_auth and current_user.role != 'customer' else None
    author_role = current_user.role if is_auth else 'customer'
    author_name = current_user.username if author_id else ticket.customer_name
    msg = ChatMessage(ticket_id=ticket.id,
                      author_id=author_id,
                      author_role=author_role,
                      author_name=author_name,
                      body=message_body)
    db.session.add(msg)
    db.session.commit()
    message_data = {
        'sender': author_name,
        'message': message_body,
        'role': author_role,
        'ticket_id': ticket.id
    }
    emit('new_message',
         message_data,
         to=ticket_id,
         namespace='/chat',
         include_self=False)


@socketio.on('close_chat', namespace='/chat')
def close_chat(data):
    ticket_id = data.get('ticket_id')
    token = data.get('token')
    ticket = db.session.get(SupportTicket, ticket_id)
    if not ticket: return
    can_close = False
    if current_user.is_authenticated and current_user.role in [
            'support', 'admin'
    ]:
        can_close = True
    elif token and ticket.customer_token == token:
        can_close = True
    if can_close and ticket.status == 'Active':
        ticket.status = 'Closed'
        db.session.commit()
        emit('chat_closed', {'ticket_id': ticket.id},
             to=ticket_id,
             broadcast=True,
             namespace='/chat')
        socketio.emit('ticket_closed_for_admin', {'ticket_id': ticket.id},
                      to='support_team',
                      namespace='/chat')


# --- İLK KURULUM VE UYGULAMAYI BAŞLATMA ---
def create_initial_data():
    with app.app_context():
        if not User.query.filter_by(email='admin@example.com').first():
            admin_user = User(username='admin',
                              email='admin@example.com',
                              role='admin',
                              first_name='Yönetici',
                              last_name='Hesap')
            admin_user.set_password('password123')
            db.session.add(admin_user)
            print("Varsayılan admin kullanıcısı oluşturuldu.")
        if Product.query.count() == 0:
            p1 = Product(
                name='Başlangıç SSD Hosting',
                description=
                '1 GB SSD Disk Alanı\n10 GB Aylık Trafik\n1 Adet Web Sitesi',
                price=29.99,
                billing_cycle='Aylık')
            db.session.add(p1)
            print("Örnek ürün oluşturuldu.")
        db.session.commit()


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        create_initial_data()
    socketio.run(app, debug=True, port=8080)
