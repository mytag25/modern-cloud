from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, BooleanField, TextAreaField, FloatField, SelectField, IntegerField
# forms.py en üstteki import satırı
from wtforms.validators import DataRequired, Length, Email, EqualTo, ValidationError, Optional, URL
from models import User, Product, Coupon
from wtforms import IntegerField
from wtforms_sqlalchemy.fields import QuerySelectField


class RegistrationForm(FlaskForm):
    # --- YENİ EKLENEN ALANLAR ---
    first_name = StringField(
        'Adınız', validators=[DataRequired(),
                              Length(min=2, max=50)])
    last_name = StringField('Soyadınız',
                            validators=[DataRequired(),
                                        Length(min=2, max=50)])
    # --------------------------

    username = StringField('Kullanıcı Adı',
                           validators=[DataRequired(),
                                       Length(min=2, max=20)])
    email = StringField('E-posta', validators=[DataRequired(), Email()])
    password = PasswordField('Şifre',
                             validators=[DataRequired(),
                                         Length(min=6)])
    confirm_password = PasswordField(
        'Şifreyi Doğrula', validators=[DataRequired(),
                                       EqualTo('password')])
    submit = SubmitField('Kayıt Ol')

    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('Bu kullanıcı adı zaten alınmış.')

    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('Bu e-posta adresi zaten kullanımda.')


class LoginForm(FlaskForm):
    email = StringField('E-posta', validators=[DataRequired(), Email()])
    password = PasswordField('Şifre', validators=[DataRequired()])
    remember = BooleanField('Beni Hatırla')
    submit = SubmitField('Giriş Yap')


class CouponForm(FlaskForm):
    code = StringField('Kupon Kodu',
                       validators=[DataRequired(),
                                   Length(min=3, max=50)])
    discount_percentage = IntegerField('İndirim Yüzdesi (%)',
                                       validators=[DataRequired()])
    submit = SubmitField('Kupon Oluştur')

    def validate_code(self, code):
        coupon = Coupon.query.filter_by(code=code.data).first()
        if coupon:
            raise ValidationError(
                'Bu kupon kodu zaten mevcut. Lütfen başka bir kod seçin.')


class ProductForm(FlaskForm):
    name = StringField('Paket Adı', validators=[DataRequired()])
    description = TextAreaField('Açıklama', validators=[DataRequired()])
    price = FloatField('Fiyat', validators=[DataRequired()])
    billing_cycle = SelectField('Fatura Döngüsü',
                                choices=[('Aylık', 'Aylık'),
                                         ('Yıllık', 'Yıllık')],
                                validators=[DataRequired()])
    image_url = StringField(
        'Görsel URL (İsteğe Bağlı)',
        validators=[Optional(),
                    URL(message="Lütfen geçerli bir URL girin.")])
    submit = SubmitField('Paketi Kaydet')


class CredentialForm(FlaskForm):
    content = TextAreaField('Hizmet Bilgileri', validators=[DataRequired()])
    submit = SubmitField('Bilgileri Gönder')


def user_choices():
    return User.query.filter_by(role='customer')


def product_choices():
    return Product.query.all()


class ManualServiceForm(FlaskForm):
    customer = QuerySelectField('Müşteri',
                                query_factory=user_choices,
                                get_label='username',
                                allow_blank=False)
    product = QuerySelectField('Paket',
                               query_factory=product_choices,
                               get_label='name',
                               allow_blank=False)
    credentials = TextAreaField('Hizmet Bilgileri',
                                validators=[DataRequired()])
    submit = SubmitField('Hizmeti Ekle')


def all_users_choice():
    return User.query.order_by(User.username).all()


class NotificationForm(FlaskForm):
    recipient = QuerySelectField('Alıcı',
                                 query_factory=all_users_choice,
                                 get_label='username',
                                 allow_blank=True,
                                 blank_text='-- Tüm Kullanıcılar --')
    title = StringField('Başlık',
                        validators=[DataRequired(),
                                    Length(min=3, max=100)])
    message = TextAreaField('Mesaj', validators=[DataRequired()])
    submit = SubmitField('Gönder')


class SupportTicketForm(FlaskForm):
    name = StringField('Adınız',
                       validators=[DataRequired(),
                                   Length(min=2, max=100)])
    email = StringField('E-posta Adresiniz',
                        validators=[DataRequired(), Email()])
    subject = TextAreaField('Sorununuz',
                            validators=[DataRequired(),
                                        Length(min=10)])
    submit = SubmitField('Destek Talebi Gönder')


# forms.py sif degis


class ChangePasswordForm(FlaskForm):
    current_password = PasswordField('Mevcut Şifre',
                                     validators=[DataRequired()])
    new_password = PasswordField(
        'Yeni Şifre', validators=[DataRequired(),
                                  Length(min=6, max=20)])
    confirm_password = PasswordField('Yeni Şifreyi Onayla',
                                     validators=[
                                         DataRequired(),
                                         EqualTo('new_password',
                                                 message='Şifreler uyuşmalı.')
                                     ])
    submit = SubmitField('Şifreyi Değiştir')


# forms.py duyuru


class AnnouncementForm(FlaskForm):
    title = StringField('Duyuru Başlığı',
                        validators=[DataRequired(),
                                    Length(min=5, max=150)])
    content = TextAreaField('Duyuru İçeriği', validators=[DataRequired()])
    category = SelectField('Duyuru Tipi (Renk)',
                           choices=[('info', 'Bilgi (Mavi)'),
                                    ('success', 'Başarı (Yeşil)'),
                                    ('warning', 'Uyarı (Sarı)'),
                                    ('danger', 'Tehlike (Kırmızı)')],
                           validators=[DataRequired()])
    submit = SubmitField('Duyuruyu Yayınla')
