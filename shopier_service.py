# shopier_service.py
import hmac
import hashlib
import base64
import random
from dataclasses import dataclass


# Veri yapılarını daha temiz tutmak için dataclass'lar kullanıyoruz.
@dataclass
class Buyer:
    id: str
    name: str
    surname: str
    email: str
    phone: str
    account_age: int = 0


@dataclass
class Address:
    address: str
    city: str
    country: str
    postcode: str


class ShopierService:
    """
    Shopier ödeme entegrasyonu için tüm işlemleri yöneten servis sınıfı.
    Bu kod, çalışan referans Python örneğine göre yazılmıştır.
    """

    def __init__(self, api_key: str, api_secret: str):
        if not api_key or not api_secret:
            raise ValueError("API anahtarı ve sırrı boş olamaz.")
        self.api_key = api_key
        self.api_secret = api_secret
        self.payment_url = 'https://www.shopier.com/ShowProduct/api_pay4.php'
        self.modul_version = '1.0.5'

    def get_params(self, platform_order_id: str, total_order_value: str,
                   buyer: Buyer, billing_address: Address,
                   shipping_address: Address, callback_url: str) -> dict:
        """
        Shopier'e gönderilecek tüm parametreleri bir sözlük olarak hazırlar.
        İmzayı hesaplar ve son parametre listesini döner.
        """
        params = {
            'API_key': self.api_key,
            'website_index': '1',
            'platform_order_id': platform_order_id,
            'product_name': f"Siparis #{platform_order_id}",
            'product_type': '1',  # 0: Fiziksel, 1: Dijital
            'buyer_name': buyer.name,
            'buyer_surname': buyer.surname,
            'buyer_email': buyer.email,
            'buyer_account_age': str(buyer.account_age),
            'buyer_id_nr': buyer.id,
            'buyer_phone': buyer.phone,
            'billing_address': billing_address.address,
            'billing_city': billing_address.city,
            'billing_country': billing_address.country,
            'billing_postcode': billing_address.postcode,
            'shipping_address': shipping_address.address,
            'shipping_city': shipping_address.city,
            'shipping_country': shipping_address.country,
            'shipping_postcode': shipping_address.postcode,
            'total_order_value': total_order_value,
            'currency': '0',  # 0: TL
            'platform': 0,
            'is_in_frame': 0,
            'current_language': 0,  # 0: TR
            'modul_version': self.modul_version,
            'random_nr': str(random.randint(100000, 999999)),
            'callback': callback_url
        }
        params['signature'] = self._calculate_payment_signature(params)
        return params

    def _calculate_payment_signature(self, params: dict) -> str:
        """
        Çalışan PHP örneğindeki mantığa göre imzayı hesaplar.
        """
        data_to_be_hashed = (str(params['random_nr']) +
                             str(params['platform_order_id']) +
                             str(params['total_order_value']) +
                             str(params['currency']))

        hmac_obj = hmac.new(self.api_secret.encode('utf-8'),
                            data_to_be_hashed.encode('utf-8'), hashlib.sha256)
        raw_signature = hmac_obj.digest()
        signature = base64.b64encode(raw_signature)
        return signature.decode('utf-8')

    def verify_callback(self, post_data: dict) -> bool:
        """
        Shopier'den gelen callback isteğinin geçerliliğini doğrular.
        """
        try:
            received_signature_b64 = post_data.get('signature')
            if not received_signature_b64:
                return False

            received_signature_raw = base64.b64decode(received_signature_b64)

            random_nr = post_data.get('random_nr')
            platform_order_id = post_data.get('platform_order_id')
            data_to_be_hashed = str(random_nr) + str(platform_order_id)

            expected_signature_raw = hmac.new(
                self.api_secret.encode('utf-8'),
                data_to_be_hashed.encode('utf-8'), hashlib.sha256).digest()

            return hmac.compare_digest(received_signature_raw,
                                       expected_signature_raw)
        except Exception as e:
            print(f"Callback doğrulama hatası: {e}")
            return False
