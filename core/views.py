from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse, HttpResponseServerError
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_POST
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from .models import Deposit, Withdrawal, Type_plans, Investment
from decimal import Decimal
import json
from .nowpayment import NOWPaymentsAPI
import logging
from .forms import WithdrawalForm, InvestmentForm, DepositForm
from django.core.paginator import Paginator
from django.db.models import Sum, Count
from django.db import transaction

logger = logging.getLogger(__name__)

# Initialize NOWPayments API
nowpayments = NOWPaymentsAPI()


@staff_member_required
def test_nowpayments_view(request):
    """Display the NOWPayments API test interface"""
    return render(request, 'core/api_test.html')

@staff_member_required
def test_nowpayments_api(request):
    """
    Test NOWPayments API connection and show detailed diagnostic information
    Only accessible by staff users
    """
    try:
        # Test API Configuration
        config_status = {
            'api_key': bool(nowpayments.api_key),
            'ipn_secret': bool(nowpayments.ipn_secret),
            'sandbox_mode': nowpayments.sandbox,
            'base_url': nowpayments.base_url
        }

        # Test API Connection
        try:
            currencies = nowpayments.get_currencies()
            currencies_test = {
                'status': 'success',
                'count': len(currencies) if isinstance(currencies, dict) else 0
            }
        except Exception as e:
            currencies_test = {
                'status': 'failed',
                'error': str(e)
            }

        # Test Price Estimation
        try:
            estimate = nowpayments.estimate_exchange_rate(
                amount=100,
                currency_from='usd',
                currency_to='btc'
            )
            estimate_test = {
                'status': 'success',
                'data': estimate
            }
        except Exception as e:
            estimate_test = {
                'status': 'failed',
                'error': str(e)
            }

        # Get supported networks
        networks = nowpayments.supported_networks

        # Check recent transactions
        recent_deposits = Deposit.objects.all().order_by('-created_at')[:5]
        transactions_status = [{
            'deposit_id': deposit.deposit_id,
            'payment_id': deposit.payment_id,
            'status': deposit.payment_status,
            'created_at': deposit.created_at,
            'currency': deposit.pay_currency,
            'amount': float(deposit.amount)
        } for deposit in recent_deposits]

        return JsonResponse({
            'success': True,
            'api_configuration': config_status,
            'currencies_test': currencies_test,
            'estimate_test': estimate_test,
            'supported_networks': networks,
            'recent_transactions': transactions_status,
            'minimum_deposit': float(nowpayments.min_amount),
            'maximum_deposit': float(nowpayments.max_amount)
        })

    except Exception as e:
        logger.error(f"API test failed: {e}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)



def index(request):
    """Professional landing page for the investment platform"""
    plans = Type_plans.objects.all()
    return render(request, 'core/index.html', {'plans': plans})


@login_required
def deposit_page(request):
    """Display deposit form and handle submissions"""
    if request.method == 'POST':
        form = DepositForm(request.POST)
        if form.is_valid():
            try:
                amount = form.cleaned_data['amount']
                crypto = form.cleaned_data['pay_currency']
                
                # Create payment through NOWPayments
                result = nowpayments.create_payment(
                    amount=amount,
                    user=request.user,
                    currency_from="usd",
                    currency_to=crypto.lower()
                )
                
                # Create local deposit record
                deposit, created = Deposit.objects.get_or_create(
                    payment_id=result['payment_id'],
                    defaults={
                        'user': request.user,
                        'amount': amount,
                        'pay_currency': crypto.lower(),
                        'pay_address': result['pay_address'],
                        'pay_amount': result['pay_amount'],
                        'status': 'PENDING'
                    }
                )
                
                messages.success(request, 'Deposit initiated successfully')
                return JsonResponse({
                    'success': True,
                    'deposit_id': deposit.deposit_id,
                    'payment_data': result
                })
                
            except Exception as e:
                logger.error(f"Deposit creation failed: {e}")
                messages.error(request, 'Failed to process deposit')
                return JsonResponse({'error': str(e)}, status=500)
    else:
        form = DepositForm()

    return render(request, 'core/deposit.html', {
        'form': form,
        'min_deposit': 10.00,
        'supported_currencies': nowpayments.get_supported_currencies()
    })

@login_required
def create_deposit(request):
    """Handle AJAX deposit creation"""
    if not request.user.is_authenticated:
        logger.warning("Unauthenticated deposit creation attempt")
        return JsonResponse({'success': False, 'error': 'Authentication required'}, status=401)
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)

    logger.debug(f"POST data received: {dict(request.POST)}")
    form = DepositForm(request.POST)
    if not form.is_valid():
        logger.error(f"Deposit form validation failed: {form.errors}")
        # Return the first error message
        error_msg = str(list(form.errors.values())[0][0]) if form.errors else "Form validation failed"
        return JsonResponse({'success': False, 'error': error_msg}, status=400)

    try:
        amount = form.cleaned_data['amount']
        crypto = form.cleaned_data['pay_currency']
        
        logger.info(f"Creating payment: amount={amount}, crypto={crypto}, user={request.user.email}")
        
        # Create payment (this also creates the deposit record)
        result = nowpayments.create_payment(
            amount=amount,
            user=request.user,
            currency_from="usd",
            currency_to=crypto.lower()
        )
        
        logger.info(f"Payment created successfully with keys: {result.keys()}")
        
        # The deposit is already created in nowpayments.create_payment()
        # Just retrieve it using the deposit_id returned from create_payment
        if 'deposit_id' not in result:
            logger.error(f"No deposit_id in payment result: {result}")
            return JsonResponse({'success': False, 'error': 'Failed to create deposit record'}, status=500)
        
        # Convert Decimal to string for JSON serialization
        pay_amount = str(result['pay_amount']) if result.get('pay_amount') else '0'
        
        response_data = {
            'success': True,
            'payment_id': str(result.get('payment_id', '')),
            'pay_address': str(result.get('pay_address', '')),
            'pay_amount': pay_amount,
            'deposit_id': str(result.get('deposit_id', ''))
        }
        # Add network/display info based on supported_networks mapping
        try:
            networks = nowpayments.supported_networks
            details = networks.get(crypto.lower()) if isinstance(networks, dict) else None
            network_name = None
            display_name = None
            if isinstance(details, dict):
                network_name = details.get('network') or details.get('symbol') or None
                display_name = details.get('name') or crypto.upper()
            else:
                display_name = crypto.upper()

            response_data.update({
                'network': network_name or '',
                'currency_name': display_name
            })
        except Exception:
            response_data.update({'network': '', 'currency_name': crypto.upper()})
        
        logger.info(f"Returning successful deposit response: {response_data}")
        return JsonResponse(response_data, status=200)
        
    except ValueError as e:
        logger.warning(f"Validation error in deposit creation: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=400)
    except Exception as e:
        logger.error(f"Payment creation failed: {e}", exc_info=True)
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["POST"])
def nowpayments_ipn(request):
    """Handle NOWPayments IPN (Instant Payment Notifications)"""
    try:
        ipn_data = json.loads(request.body)
        nowpayments_sig = request.headers.get('x-nowpayments-sig')
        
        if not nowpayments_sig:
            logger.warning("IPN request missing signature")
            return HttpResponse(status=400)
            
        if not nowpayments.verify_ipn_request(ipn_data, nowpayments_sig):
            logger.warning("Invalid IPN signature")
            return HttpResponse(status=400)
        
        payment_status = ipn_data.get('payment_status')
        payment_id = ipn_data.get('payment_id')
        
        try:
            deposit = Deposit.objects.get(payment_id=payment_id)

            # Use model helper to apply payment status mapping and persist changes
            actually_paid = ipn_data.get('actually_paid')
            try:
                deposit.apply_payment_status(payment_status, actually_paid)
            except Exception as e:
                logger.error(f"Failed to apply payment status for deposit {deposit.deposit_id}: {e}", exc_info=True)
                return HttpResponse(status=500)

            logger.info(f"Successfully processed IPN for deposit {deposit.deposit_id}")
            return HttpResponse(status=200)
            
        except Deposit.DoesNotExist:
            logger.error(f"No deposit found for payment_id: {payment_id}")
            return HttpResponse(status=404)

    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in IPN request: {e}")
        return HttpResponse(status=400)
    except Exception as e:
        logger.error(f"Error processing IPN: {e}")
        return HttpResponse(status=500)

@login_required
def check_payment_status(request, deposit_id):
    """Check status of a specific payment"""
    try:
        deposit = Deposit.objects.get(deposit_id=deposit_id, user=request.user)
        
        try:
            payment_data = nowpayments.get_payment_status(deposit.payment_id)
            payment_status = payment_data.get('payment_status')
            
            if payment_status != deposit.payment_status:
                # Use model helper to update deposit based on payment status
                try:
                    deposit.apply_payment_status(payment_status, payment_data.get('actually_paid'))
                    logger.info(f"Updated status for deposit {deposit.deposit_id} to {payment_status}")
                except Exception as e:
                    logger.error(f"Failed to apply payment status for deposit {deposit.deposit_id}: {e}", exc_info=True)
                    return JsonResponse({'success': False, 'error': 'Failed to update deposit status'}, status=500)
            
            return JsonResponse({
                'success': True,
                'status': deposit.status,
                'payment_status': payment_status,
                'payment_data': {
                    'pay_address': payment_data.get('pay_address'),
                    'pay_amount': payment_data.get('pay_amount'),
                    'actually_paid': payment_data.get('actually_paid'),
                    'payment_status': payment_status,
                }
            })
            
        except Exception as e:
            logger.error(f"Failed to get payment status: {e}")
            return JsonResponse({
                'success': False, 
                'error': "Failed to fetch payment status"
            }, status=500)

    except Deposit.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Deposit not found'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)

@login_required
def get_supported_currencies(request):
    """Get list of supported cryptocurrencies"""
    try:
        currencies = nowpayments.get_supported_currencies()
        return JsonResponse({
            'success': True,
            'currencies': currencies
        })
    except Exception as e:
        logger.error(f"Failed to get supported currencies: {e}")
        return JsonResponse({
            'success': False,
            'error': "Failed to fetch supported currencies"
        }, status=500)

@login_required
def estimate_price(request):
    """Get estimated crypto amount for fiat payment"""
    if request.method != 'GET':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
        
    try:
        try:
            amount = Decimal(request.GET.get('amount', '0'))
            if amount <= 0:
                return JsonResponse({'error': 'Invalid amount'}, status=400)
        except (TypeError, ValueError):
            return JsonResponse({'error': 'Invalid amount format'}, status=400)

        currency_from = request.GET.get('currency_from', 'usd')
        currency_to = request.GET.get('currency_to', 'btc')
        
        logger.debug(f"Estimate request: {amount} {currency_from} -> {currency_to}")
        
        if not currency_to or currency_to.lower() not in nowpayments.supported_networks:
            return JsonResponse({
                'error': 'Please select a valid cryptocurrency',
                'supported_currencies': nowpayments.get_supported_currencies()
            }, status=400)
            
        try:
            result = nowpayments.estimate_price(
                amount=amount,
                currency_from=currency_from.lower(),
                currency_to=currency_to.lower()
            )
            
            logger.debug(f"Estimate result: {result}")
            
            return JsonResponse({
                'success': True,
                'estimated_amount': str(result.get('estimated_amount', 0)),
                'currency_from': currency_from,
                'currency_to': currency_to
            })
            
        except ValueError as e:
            logger.warning(f"Invalid estimate request: {e}")
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
        except Exception as e:
            logger.error(f"Estimate price API error: {e}", exc_info=True)
            return JsonResponse({'success': False, 'error': f"API error: {str(e)}"}, status=500)
            
    except Exception as e:
        logger.error(f"Price estimation failed: {e}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': "Failed to get price estimate"
        }, status=500)



@login_required
def withdrawal(request):
    """Handle withdrawal page and form submission"""
    if request.method == 'POST':
        form = WithdrawalForm(request.user, request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    withdrawal = Withdrawal.objects.create(
                        user=request.user,
                        amount=form.cleaned_data['amount'],
                        crypto_currency=form.cleaned_data['crypto_currency'],
                        wallet_address=form.cleaned_data['wallet_address'],
                        status='PENDING'  # Start with PENDING status
                    )
                    
                    messages.success(
                        request, 
                        f'Withdrawal request submitted successfully. Your withdrawal is PENDING and will be processed within 24-48 hours.'
                    )
                    return redirect('account:dashboard')

            except Exception as e:
                logger.error(f"Withdrawal creation failed: {e}", exc_info=True)
                messages.error(request, 'Failed to process withdrawal request. Please try again.')
        else:
            # Form has errors - they will be displayed below fields in template
            pass
    else:
        form = WithdrawalForm(request.user)

    context = {
        'form': form,
        'available_balance': request.user.profile.account_balance,
        'min_withdrawal': 10.00,
    }
    return render(request, 'core/withdrawal.html', context)

@login_required
def investment_plans(request):
    """Display available investment plans"""
    plans = Type_plans.objects.all()
    return render(request, 'core/investment_plans.html', {
        'plans': plans
    })

@login_required
def create_investment(request, plan_id):
    """Create new investment with proper form handling"""
    try:
        plan = get_object_or_404(Type_plans, id=plan_id)

        if request.method == 'POST':
            form = InvestmentForm(request.user, plan, request.POST)
            if form.is_valid():
                try:
                    with transaction.atomic():
                        amount = form.cleaned_data['amount']

                        # Create investment (post_save signal will deduct balance)
                        investment = Investment.objects.create(
                            user=request.user,
                            type_plan=plan,
                            amount_invested=amount
                        )

                        logger.info(
                            f"Investment created: {investment.plan_id} by {request.user.email} "
                            f"for {amount} in plan {plan.name}"
                        )

                        messages.success(
                            request,
                            f'Investment of ${amount:.2f} created successfully.'
                        )
                        # Redirect to the investment detail page which will show the summary
                        return redirect('core:investment_detail', plan_id=investment.plan_id)

                except Exception as e:
                    logger.error(f"Error creating investment: {e}", exc_info=True)
                    messages.error(request, 'Failed to create investment. Please try again.')
                    # fall through to render form with errors/message
            else:
                # Form invalid: render the form with bound errors
                context = {
                    'plan': plan,
                    'form': form,
                    'available_balance': request.user.profile.account_balance,
                }
                return render(request, 'core/invest.html', context)

        # GET request — render the investment form
        context = {
            'plan': plan,
            'form': InvestmentForm(request.user, plan),
            'available_balance': request.user.profile.account_balance,
        }
        return render(request, 'core/invest.html', context)

    except Type_plans.DoesNotExist:
        logger.warning(f"Investment plan {plan_id} not found")
        messages.error(request, 'Investment plan not found')
        return redirect('core:investment_plans')

    except Exception as e:
        logger.error(f"Unexpected error in create_investment: {e}", exc_info=True)
        messages.error(request, 'An unexpected error occurred. Please try again.')
        return redirect('core:investment_plans')

@login_required
def investment_detail(request, plan_id):
    """View investment details"""
    investment = get_object_or_404(
        Investment.objects.select_related('type_plan'),
        plan_id=plan_id,
        user=request.user
    )

    # Calculate net profit and profit percentage for display
    try:
        net_profit = (investment.expected_return - investment.amount_invested)
    except Exception:
        net_profit = 0
    try:
        profit_percentage = (net_profit / investment.amount_invested) * 100 if investment.amount_invested else 0
    except Exception:
        profit_percentage = 0

    return render(request, 'core/investment_detail.html', {
        'investment': investment,
        'net_profit': net_profit,
        'profit_percentage': profit_percentage,
        'countdown_seconds': 6,  # seconds before redirect in template
    })

@login_required
def transaction_history(request):
    """View all transactions"""
    page = request.GET.get('page', 1)
    
    deposits = Deposit.objects.filter(user=request.user)
    withdrawals = Withdrawal.objects.filter(user=request.user)
    investments = Investment.objects.filter(user=request.user)

    # Combine all transactions and sort by their respective date fields
    transactions = []
    for d in deposits:
        d.txn_type = 'Deposit'
        d.txn_date = d.created_at
        transactions.append(d)
    for w in withdrawals:
        w.txn_type = 'Withdrawal'
        w.txn_date = w.created_at
        transactions.append(w)
    for i in investments:
        i.txn_type = 'Investment'
        i.txn_date = i.start_date
        transactions.append(i)

    # Sort by date descending
    transactions.sort(key=lambda x: x.txn_date, reverse=True)

    paginator = Paginator(transactions, 10)
    transactions_page = paginator.get_page(page)

    return render(request, 'core/transactions.html', {
        'transactions': transactions_page
    })

@login_required
@require_POST
def update_investment_profit(request, plan_id):
    """Update profit for a specific investment via AJAX"""
    try:
        with transaction.atomic():
            investment = get_object_or_404(
                Investment.objects.select_related('type_plan'),
                plan_id=plan_id,
                user=request.user,
                is_active=True
            )
            
            daily_profit = investment.calculate_daily_profit()
            investment.profit_made += daily_profit
            investment.save()
            
            # Update user's balance
            profile = request.user.profile
            profile.account_balance += daily_profit
            profile.total_profit += daily_profit
            profile.save()
            
            return JsonResponse({
                'success': True,
                'new_profit': float(investment.profit_made),
                'daily_profit': float(daily_profit)
            })
            
    except Investment.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Investment not found'
        }, status=404)
    except Exception as e:
        logger.error(f"Failed to update investment profit: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

def custom_404_view(request, exception):
    return render(request, '404.html', status=404)

def custom_500_view(request):
    return render(request, '500.html', status=500)
