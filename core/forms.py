from django import forms
from decimal import Decimal
from django.conf import settings
from .models import CRYPTO_CHOICES, Deposit

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
    crypto_currency = forms.ChoiceField(
        choices=[
            ('', 'Select cryptocurrency...'),
            ('btc', 'Bitcoin (BTC)'),
            ('eth', 'Ethereum (ETH)'),
            ('sol', 'Solana (SOL)'),
            ('usdterc20', 'USDT ERC20'),
            ('usdttrc20', 'USDT TRC20')
        ],
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
        # Populate choices from settings.NOWPAYMENTS['SUPPORTED_NETWORKS'] when available
        try:
            supported = getattr(settings, 'NOWPAYMENTS', {}).get('SUPPORTED_NETWORKS')
        except Exception:
            supported = None

        if supported and isinstance(supported, dict):
            choices = [('', 'Select cryptocurrency...')]
            for currency_key, details in supported.items():
                # details may be a dict with name/network keys
                name = details.get('name') if isinstance(details, dict) else None
                network = details.get('network') if isinstance(details, dict) else None
                # Only display the main name (uppercase). Do not append symbol or network.
                label = (name or currency_key).upper()
                choices.append((currency_key.lower(), label))
            self.fields['pay_currency'].choices = choices
        else:
            # Fallback: provide basic cryptocurrency choices
            import logging
            logger = logging.getLogger(__name__)
            logger.warning("NOWPAYMENTS['SUPPORTED_NETWORKS'] not configured; using fallback choices")
            self.fields['pay_currency'].choices = [
                ('', 'Select cryptocurrency...'),
                ('btc', 'BITCOIN'),
                ('eth', 'ETHEREUM'),
                ('sol', 'SOLANA'),
                ('usdttrc20', 'USDT TRC20'),
                ('usdterc20', 'USDT ERC20'),
            ]

    def clean_amount(self):
        amount = self.cleaned_data['amount']
        if amount < Decimal('10.00'):
            raise forms.ValidationError('Minimum deposit amount is $10.00')
        return amount
