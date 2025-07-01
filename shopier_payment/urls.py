# shopier_payment/urls.py
from django.urls import path
from . import views

urlpatterns = [
    # Ana sayfa direkt ödeme formunu göstersin
    path('', views.payment_view, name='shopier_payment'),
]
