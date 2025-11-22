from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum
from .forms import RegistrationForm, LoginForm, ProfileUpdateForm
from .models import User, Profile
from core.models import Investment, Deposit, Withdrawal
import uuid

def register(request):
    if request.user.is_authenticated:
        return redirect('account:dashboard')
    
    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)

            # Store referral code without validation (will be handled manually)
            user.refferal_code = form.cleaned_data.get('referral_code', '')
            
            user.save()
            Profile.objects.create(user=user)
            login(request, user)
            messages.success(request, 'Registration successful!')
            return redirect('account:dashboard')
    else:
        form = RegistrationForm()
    
    return render(request, 'account/register.html', {'form': form})

def user_login(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            password = form.cleaned_data['password']
            
            user = authenticate(request, email=email, password=password)
            if user is not None:
                login(request, user)
                
                messages.success(request, 'Login successful!')
                return redirect('dashboard')
            else:
                messages.error(request, 'Invalid email or password.')
    else:
        form = LoginForm()
    
    return render(request, 'account/login.html', {'form': form})

@login_required
def user_logout(request):
    logout(request)
    messages.success(request, 'You have been logged out successfully.')
    return redirect('account:login')

@login_required
def profile(request):
    if request.method == 'POST':
        form = ProfileUpdateForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Your profile has been updated successfully!')
            return redirect('profile')
    else:
        form = ProfileUpdateForm(instance=request.user)
    
    context = {
        'form': form,
        'user': request.user,
        'profile': request.user.profile
    }
    return render(request, 'account/profile.html', context)

@login_required
def dashboard(request):
    # Get user's investment summary
    investments = Investment.objects.filter(user=request.user)
    active_investments = investments.filter(is_active=True)
    account_balance = request.user.profile.account_balance
    
    investment_summary = investments.aggregate(
        total_invested=Sum('amount_invested'),
        total_expected=Sum('expected_return')
    )
    # Calculate total_profit from completed investments' expected_return
    completed_investments = investments.filter(is_active=False)
    total_profit = completed_investments.aggregate(total_profit=Sum('expected_return')).get('total_profit') or 0
    active_investments_count = active_investments.count()
    completed_investments_count = investments.filter(is_active=False).count()

    # Deposits and withdrawals totals
    total_deposits = Deposit.objects.filter(user=request.user, status='COMPLETED').aggregate(total=Sum('amount')).get('total') or 0
    total_withdrawals = Withdrawal.objects.filter(user=request.user, status='COMPLETED').aggregate(total=Sum('amount')).get('total') or 0
    
    # Get latest deposits and withdrawals
    latest_deposits = Deposit.objects.filter(
        user=request.user
    ).order_by('-created_at')[:3]
    
    latest_withdrawals = Withdrawal.objects.filter(
        user=request.user
    ).order_by('-created_at')[:3]
        
    context = {
        'profile': request.user.profile,
        'account_balance': account_balance,
        'active_investments': active_investments,
        'investment_summary': investment_summary,
        'total_invested': investment_summary.get('total_invested') or 0,
        'total_expected': investment_summary.get('total_expected') or 0,
        'total_profit': total_profit,
        'active_investments_count': active_investments_count,
        'completed_investments_count': completed_investments_count,
        'total_deposits': total_deposits,
        'total_withdrawals': total_withdrawals,
        'latest_deposits': latest_deposits,
        'latest_withdrawals': latest_withdrawals,
    }
    return render(request, 'account/dashboard.html', context)

