# models.py

from flask_login import UserMixin
from datetime import datetime
from extensions import db, bcrypt


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)

    # --- YENİ EKLENEN ALANLAR ---
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    # --------------------------

    password_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='customer')
    last_notification_read_time = db.Column(db.DateTime,
                                            default=datetime.utcnow)

    orders = db.relationship('Order', backref='customer', lazy=True)
    notifications = db.relationship('Notification',
                                    foreign_keys='Notification.recipient_id',
                                    backref='recipient',
                                    lazy=True)
    chat_messages_authored = db.relationship(
        'ChatMessage',
        foreign_keys='ChatMessage.author_id',
        backref='author',
        lazy=True)

    def set_password(self, password):
        self.password_hash = bcrypt.generate_password_hash(password).decode(
            'utf-8')

    def check_password(self, password):
        return bcrypt.check_password_hash(self.password_hash, password)


class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    price = db.Column(db.Float, nullable=False)
    billing_cycle = db.Column(db.String(50), nullable=False)
    image_url = db.Column(db.String(255), nullable=True)

    orders = db.relationship('Order', backref='product', lazy=True)


class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    product_id = db.Column(db.Integer,
                           db.ForeignKey('product.id'),
                           nullable=False)
    order_date = db.Column(db.DateTime,
                           nullable=False,
                           default=datetime.utcnow)

    expiry_date = db.Column(db.DateTime, nullable=True)  # Son kullanma tarihi

    status = db.Column(db.String(50),
                       nullable=False,
                       default='Ödeme Bekleniyor')
    notes = db.Column(db.Text, nullable=True)

    # Shopier işlemlerini gruplamak için eklenen alan
    platform_order_id = db.Column(db.String(40), nullable=True, index=True)

    credential = db.relationship('ServiceCredential',
                                 backref='order',
                                 uselist=False,
                                 cascade="all, delete-orphan")


class ServiceCredential(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer,
                         db.ForeignKey('order.id'),
                         nullable=False,
                         unique=True)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime,
                           nullable=False,
                           default=datetime.utcnow)


class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    recipient_id = db.Column(db.Integer,
                             db.ForeignKey('user.id'),
                             nullable=True)
    title = db.Column(db.String(100), nullable=False)
    message = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)


class SupportTicket(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_sid = db.Column(db.String(128), nullable=False, index=True)
    customer_name = db.Column(db.String(100), nullable=False)
    customer_email = db.Column(db.String(120), nullable=False)
    subject = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(30), default='Pending', index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    customer_token = db.Column(db.String(64), unique=True, nullable=False)

    messages = db.relationship('ChatMessage',
                               backref='ticket',
                               lazy='dynamic',
                               cascade="all, delete-orphan")


class Coupon(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), unique=True, nullable=False)
    discount_percentage = db.Column(db.Integer, nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"Coupon('{self.code}', '{self.discount_percentage}%')"


class ChatMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer,
                          db.ForeignKey('support_ticket.id'),
                          nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    author_role = db.Column(db.String(20), nullable=False)
    author_name = db.Column(db.String(100), nullable=False)
    body = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)


# models.py duyuru


class Announcement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    content = db.Column(db.Text, nullable=False)
    # Duyuru tipi, Bootstrap alert renkleriyle eşleşecek: 'primary', 'success', 'warning', 'danger', 'info'
    category = db.Column(db.String(20), nullable=False, default='info')
    is_active = db.Column(db.Boolean, default=True)
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)

    def __repr__(self):
        return f"Announcement('{self.title}', '{self.timestamp}')"
