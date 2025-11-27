from django import forms
from decimal import Decimal
from django.conf import settings
from .models import Deposit, Cryptocurrency

class WithdrawalForm(forms.Form):
    amount = forms.DecimalField(
        max_digits=10, 
        decimal_places=2,
        min_value=Decimal('0.01'),
        widget=forms.NumberInput(attrs={
            'class': 'form-control-custom',
            'placeholder': 'Enter withdrawal amount',
            'step': '0.01',
            'min': '0.01'
        }),
        help_text='Enter amount to withdraw'
    )
    crypto_currency = forms.ModelChoiceField(
        queryset=Cryptocurrency.objects.all(),
        widget=forms.Select(attrs={
            'class': 'form-control-custom'
        }),
        help_text='Select cryptocurrency for withdrawal'
    )
    wallet_address = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control-custom',
            'placeholder': 'Enter your wallet address'
        }),
        help_text='Enter your wallet address'
    )

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        # Update queryset to show name and symbol
        self.fields['crypto_currency'].queryset = Cryptocurrency.objects.all()

    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        
        if not amount:
            raise forms.ValidationError('Amount is required')
            
        if amount <= 0:
            raise forms.ValidationError('Amount must be greater than zero')
        
        if amount < Decimal('10.00'):
            raise forms.ValidationError('Minimum withdrawal amount is $10.00')
            
        if amount > self.user.profile.account_balance:
            raise forms.ValidationError(f'Insufficient balance. Available: ${self.user.profile.account_balance:.2f}')
            
        return amount

    def clean_crypto_currency(self):
        crypto = self.cleaned_data.get('crypto_currency')
        
        if not crypto:
            raise forms.ValidationError('Please select a cryptocurrency')
        
        # Ensure the cryptocurrency object is valid
        if not isinstance(crypto, Cryptocurrency):
            raise forms.ValidationError('Invalid cryptocurrency selected')
            
        return crypto

    def clean_wallet_address(self):
        address = self.cleaned_data.get('wallet_address')
        
        if not address or not address.strip():
            raise forms.ValidationError('Wallet address is required')
        
        if len(address) < 26:
            raise forms.ValidationError('Wallet address appears to be invalid')
            
        return address.strip()

class InvestmentForm(forms.Form):
    amount = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=Decimal('0.01'),
        help_text='Enter amount to invest'
    )

    def __init__(self, user, plan, *args, **kwargs):
        self.user = user
        self.plan = plan
        super().__init__(*args, **kwargs)

    def clean_amount(self):
        amount = self.cleaned_data['amount']
        
        # Check plan limits
        if amount < self.plan.min_amount:
            raise forms.ValidationError(f'Minimum investment amount is {self.plan.min_amount}')
        if amount > self.plan.max_amount:
            raise forms.ValidationError(f'Maximum investment amount is {self.plan.max_amount}')
            
        # Check user balance
        if amount > self.user.profile.account_balance:
            raise forms.ValidationError('Insufficient balance')
            
        return amount

class DepositForm(forms.ModelForm):
    amount = forms.DecimalField(
        min_value=Decimal('10.00'),
        max_digits=10,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter amount',
            'min': '10'
        })
    )
    pay_currency = forms.ChoiceField(
        widget=forms.Select(attrs={
            'class': 'form-control'
        })
    )

    class Meta:
        model = Deposit
        fields = ['amount', 'pay_currency']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['amount'].label = 'Amount (USD)'
        self.fields['pay_currency'].label = 'Select Cryptocurrency'
        
        # Populate choices from Cryptocurrency model
        cryptos = Cryptocurrency.objects.all()
        choices = [('', 'Select cryptocurrency...')]
        for crypto in cryptos:
            choices.append((str(crypto.id), f"{crypto.name} ({crypto.symbol})"))
        
        self.fields['pay_currency'].choices = choices

    def clean_amount(self):
        amount = self.cleaned_data['amount']
        if amount < Decimal('10.00'):
            raise forms.ValidationError('Minimum deposit amount is $10.00')
        return amount
