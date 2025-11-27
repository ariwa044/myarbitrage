from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse, HttpResponseServerError
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_POST
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.conf import settings
from .models import Deposit, Withdrawal, Type_plans, Investment, Cryptocurrency
from decimal import Decimal
import json
import logging
from .forms import WithdrawalForm, InvestmentForm, DepositForm
from django.core.paginator import Paginator
from django.db.models import Sum, Count
from django.db import transaction

logger = logging.getLogger(__name__)


def index(request):
    """Professional landing page for the investment platform"""
    plans = Type_plans.objects.all()
    return render(request, 'core/index.html', {'plans': plans})


@login_required
def deposit_page(request):
    """
    Display deposit form (GET) and handle deposit creation (POST).
    """
    if request.method == 'POST':
        form = DepositForm(request.POST)
        if form.is_valid():
            try:
                amount = form.cleaned_data['amount']
                crypto_code = form.cleaned_data['pay_currency']

                # Fetch the selected cryptocurrency by ID
                crypto = Cryptocurrency.objects.get(id=crypto_code)

                # Create the deposit
                deposit = Deposit.objects.create(
                    user=request.user,
                    amount=amount,
                    crypto=crypto,
                    status='PENDING'
                )

                return JsonResponse({
                    'success': True,
                    'deposit_id': deposit.deposit_id,
                    'pay_address': crypto.deposit_address,
                    'currency_name': crypto.name
                })

            except Cryptocurrency.DoesNotExist:
                return JsonResponse({'success': False, 'error': 'Selected cryptocurrency not available'}, status=400)
            except Exception as e:
                return JsonResponse({'success': False, 'error': str(e)}, status=500)
        else:
            return JsonResponse({'success': False, 'error': 'Invalid form submission'}, status=400)

    # GET request: Display the deposit form
    form = DepositForm()
    supported_currencies = Cryptocurrency.objects.all()
    min_deposit = getattr(settings, 'MIN_DEPOSIT_AMOUNT', 10.00)
    return render(request, 'core/deposit.html', {
        'form': form,
        'supported_currencies': supported_currencies,
        'min_deposit': min_deposit
    })

@login_required
def check_payment_status(request, deposit_id):
    """Check status of a specific deposit"""
    try:
        deposit = Deposit.objects.get(deposit_id=deposit_id, user=request.user)
        
        return JsonResponse({
            'success': True,
            'status': deposit.status,
            'deposit_data': {
                'pay_address': deposit.crypto.deposit_address if deposit.crypto else '',
                'pay_amount': str(deposit.pay_amount) if deposit.pay_amount else '',
                'created_at': deposit.created_at.isoformat(),
                'status': deposit.status,
            }
        })

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
def deposit_pending(request, deposit_id):
    """Display pending deposit review page"""
    try:
        deposit = Deposit.objects.get(deposit_id=deposit_id, user=request.user)
        return render(request, 'core/deposit_pending.html', {
            'deposit': deposit
        })
    except Deposit.DoesNotExist:
        messages.error(request, 'Deposit not found')
        return redirect('core:deposit')

@login_required
def get_supported_currencies(request):
    """Get list of supported cryptocurrencies"""
    try:
        cryptos = Cryptocurrency.objects.all().values('id', 'name', 'symbol', 'deposit_address')
        return JsonResponse({
            'success': True,
            'currencies': list(cryptos)
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
        
        try:
            crypto_obj = Cryptocurrency.objects.get(id=currency_to)
        except Cryptocurrency.DoesNotExist:
            return JsonResponse({
                'error': 'Please select a valid cryptocurrency'
            }, status=400)

        # Simple estimate: just return the amount (no exchange rate conversion)
        return JsonResponse({
            'success': True,
            'estimated_amount': str(amount),
            'currency_from': currency_from,
            'currency_to': currency_to
        })
            
    except ValueError as e:
        logger.warning(f"Invalid estimate request: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=400)
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
