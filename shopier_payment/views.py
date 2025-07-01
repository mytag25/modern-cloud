# shopier_payment/views.py
from django.conf import settings
from django.shortcuts import render
import hmac
import hashlib
import base64
import time


def payment_view(request):
    # Bu mantık, bize gönderdiğiniz son Django örneğinden alınmıştır.
    # Bu, en doğru ve en güvenilir imza algoritmasıdır.
    params_for_signature = {
        'api_key': settings.SHOPIER_API_KEY,
        'website_index': '1',
        'platform_order_id': f"DJANGO-TEST-{int(time.time())}",
        'product_name': 'Django Test Siparis',
        'total_order_value': '1.00',
        'currency': 'TRY',
        'user_email': 'test@example.com',
        'user_name': 'Ali',
        'user_surname': 'Veli',
        'user_address': 'Test Adres',
        'user_phone': '5551234567',
        'billing_address': 'Test Adres',
        'billing_city': 'Istanbul',
        'billing_country': 'TR',
        'billing_postcode': '34000',
        'shipping_address': 'Test Adres',
        'shipping_city': 'Istanbul',
        'shipping_country': 'TR',
        'shipping_postcode': '34000',
        'buyer_account_age': '0',
        'client_ip': '127.0.0.1',
        'redirect_url': 'https://www.google.com/search?q=basarili',
        'cancel_url': 'https://www.google.com/search?q=iptal',
        'module': 'Django'
    }

    message = "".join(
        str(params_for_signature[k])
        for k in sorted(params_for_signature.keys()))

    signature = base64.b64encode(
        hmac.new(settings.SHOPIER_API_SECRET.encode(), message.encode(),
                 hashlib.sha256).digest()).decode()

    shopier_params = params_for_signature.copy()
    shopier_params['signature'] = signature

    return render(request, 'shopier_form.html', {'params': shopier_params})
