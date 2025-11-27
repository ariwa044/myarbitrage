from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    # Base URLs
    path('', views.index, name='index'),

    # Deposit URLs
    path('deposit/', views.deposit_page, name='deposit'),
    path('deposit/status/<str:deposit_id>/', views.check_payment_status, name='check_deposit_status'),
    path('deposit/pending/<str:deposit_id>/', views.deposit_pending, name='deposit_pending'),
    
    # Crypto Payment URLs
    path('api/crypto/currencies/', views.get_supported_currencies, name='supported_currencies'),
    path('api/crypto/estimate/', views.estimate_price, name='estimate_price'),

    # Investment URLs
    path('plans/', views.investment_plans, name='investment_plans'),
    path('invest/<int:plan_id>/', views.create_investment, name='create_investment'),
    path('investment/<str:plan_id>/', views.investment_detail, name='investment_detail'),
    path('transactions/', views.transaction_history, name='transactions'),

    # Profit Update URL
    path('investment/<str:plan_id>/update-profit/', views.update_investment_profit, name='update_investment_profit'),

    # Withdrawal URL
    path('withdraw/', views.withdrawal, name='withdrawal'),
]