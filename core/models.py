from django.db import models
from django.conf import settings
from django.utils import timezone
from decimal import Decimal
from shortuuid.django_fields import ShortUUIDField
from django.db.models.signals import pre_save, post_save
from django.db.models.signals import post_save, pre_save
from account.models import User, Profile
from django.dispatch import receiver
from django.db.models import F
from django.core.exceptions import FieldDoesNotExist


User = settings.AUTH_USER_MODEL
# Create your models here.
DEPOSIT_STATUS = [
    ('PENDING', 'Pending'),
    ('COMPLETED', 'Completed'),
    ('FAILED', 'Failed'),
    ('EXPIRED', 'Expired'),
    ('CANCELLED', 'Cancelled'),
]

WITHDRAWAL_STATUS = [
    ('PENDING', 'Pending'),
    ('COMPLETED', 'Completed'),
    ('FAILED', 'Failed'),
    ]


CRYPTO_CHOICES = [
    ('btc', 'Bitcoin (BTC)'),
    ('sol', 'Solana (SOL)'),
    ('usdterc20', 'USDT ERC20'),
    ('usdttrc20', 'USDT TRC20'),
    ('usdtbep20', 'USDT BEP20'),
    ('eth', 'Ethereum (ETH)')
]

class Deposit(models.Model):
    """
    Model for tracking cryptocurrency deposits through NOWPayments
    """
    # Payment Status Choices
    PAYMENT_STATUS_CHOICES = [
        ('waiting', 'Waiting for Payment'),
        ('partially_paid', 'Partially Paid'),
        ('finished', 'Payment Complete'),
        ('failed', 'Payment Failed'),
        ('refunded', 'Payment Refunded'),
        ('expired', 'Payment Expired'),
        ('cancelled', 'Payment Cancelled'),
    ]
    
    # Core fields
    deposit_id = ShortUUIDField(
        primary_key=True,
        unique=True,
        length=12,
        # length=10 generates 10 chars + the prefix 'dep_' (4 chars) -> total 14
        max_length=45,
        prefix="dep_",
        alphabet='abcdesqp1234567890'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='deposits'
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Deposit amount in USD"
    )
    status = models.CharField(
        max_length=10,
        choices=DEPOSIT_STATUS,
        default='PENDING'
    )
    # Make created_at editable by using a default rather than auto_now_add
    # auto_now_add sets editable=False which prevents editing in admin.
    created_at = models.DateTimeField(default=timezone.now)
    
    # NOWPayments fields
    payment_id = models.CharField(
        max_length=100,
        unique=True,
        help_text="NOWPayments payment ID",
        null=True, blank=True
    )
    pay_address = models.CharField(
        max_length=100,
        help_text="Cryptocurrency address for payment",
        null=True, blank=True
    )
    pay_amount = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        help_text="Amount in cryptocurrency to pay",
        null=True, blank=True
    )
    pay_currency = models.CharField(
        max_length=20,
        choices=CRYPTO_CHOICES,
        help_text="Selected cryptocurrency for payment"
    )
    payment_status = models.CharField(
        max_length=20,
        choices=PAYMENT_STATUS_CHOICES,
        default='waiting',
        help_text="Current payment status from NOWPayments"
    )
    # Processing flags
    ipn_processed = models.BooleanField(
        default=False,
        help_text="Whether the IPN webhook has been processed"
    )
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the deposit was completed"
    )
    
    
    class Meta:
        verbose_name = 'Deposit'
        verbose_name_plural = 'Deposits'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['payment_id']),
            models.Index(fields=['user', 'status']),
            models.Index(fields=['created_at']),
        ]
        
    def __str__(self):
        return f"Deposit {self.deposit_id} by {self.user.email}"
        
    @property
    def is_completed(self):
        """Check if deposit is completed"""
        return self.status == 'COMPLETED'
        
    @property
    def is_failed(self):
        """Check if deposit has failed"""
        return self.status == 'FAILED'
        
    @property
    def is_pending(self):
        """Check if deposit is still pending"""
        return self.status == 'PENDING'
        
    @property
    def formatted_amount(self):
        """Get formatted deposit amount"""
        return f"${self.amount:,.2f}"
        
    @property
    def formatted_crypto_amount(self):
        """Get formatted cryptocurrency amount"""
        return f"{self.pay_amount:,.8f} {self.pay_currency.upper()}"

    def apply_payment_status(self, payment_status: str, actually_paid: Decimal = None, save: bool = True):
        """
        Apply a NOWPayments payment_status to this Deposit and map it to the
        integration-level `status` field. This centralizes the mapping logic so
        other code paths (IPN webhook, polling sync) can call a single method.

        Args:
            payment_status: The NOWPayments payment_status string (e.g. 'finished')
            actually_paid: Optional amount actually paid in crypto (Decimal or numeric)
        """
        # Normalize
        payment_status = str(payment_status) if payment_status is not None else None
        if payment_status is None:
            return

        self.payment_status = payment_status

        # Map payment_status -> deposit.status and update amounts/timestamps
        if payment_status == 'finished':
            self.status = 'COMPLETED'
            # mark completion time
            self.completed_at = timezone.now()
        elif payment_status in ('failed', 'expired', 'cancelled'):
            self.status = 'FAILED'
            self.completed_at = timezone.now()
        elif payment_status == 'partially_paid':
            # keep deposit pending but record actual amount
            self.status = 'PENDING'
            # do not persist actual paid amount; only keep status pending

        # Mark that IPN has been processed when mapping is applied
        self.ipn_processed = True
        # If save=True, persist changes now. When called from signals (pre_save)
        # we pass save=False so the surrounding save() call will persist.
        if save:
            try:
                # mark we are saving via this helper to avoid re-entrant signal handling
                self._apply_payment_status_in_progress = True
                self.save()
            finally:
                # Clear the flag after save completes
                try:
                    del self._apply_payment_status_in_progress
                except Exception:
                    pass

    class Meta:
        verbose_name = 'Deposit'
        verbose_name_plural = 'Deposits'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['payment_id']),
            models.Index(fields=['user', 'status']),
            models.Index(fields=['created_at']),
        ]

class Withdrawal(models.Model):
    """
    Model for tracking cryptocurrency withdrawals
    """
    withdrawal_id = ShortUUIDField(
        primary_key=True,
        unique=True,
        length=10,
        # length=10 generates 10 chars + the prefix 'wit_' (4 chars) -> total 14
        max_length=32,
        prefix="wit_",
        alphabet='abcdesqp1234567890'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='withdrawals'
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Withdrawal amount in USD"
    )
    crypto_currency = models.CharField(
        max_length=20,
        choices=CRYPTO_CHOICES,
        help_text="Cryptocurrency for withdrawal"
    )
    wallet_address = models.CharField(
        max_length=100,
        help_text="Destination wallet address",
        null=True, blank=True
    )

    status = models.CharField(
        max_length=10,
        choices=WITHDRAWAL_STATUS,
        default='PENDING'
    )
    tx_hash = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Blockchain transaction hash"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the withdrawal was completed"
    )
    crypto_amount = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        null=True,
        blank=True,
        help_text="Amount in cryptocurrency"
    )

    class Meta:
        verbose_name = 'Withdrawal'
        verbose_name_plural = 'Withdrawals'
        ordering = ['-created_at']

    def __str__(self):
        return f"Withdrawal {self.withdrawal_id} by {self.user.email}"


class Type_plans(models.Model):
    name = models.CharField(max_length=100)
    min_amount = models.DecimalField(max_digits=10, decimal_places=2)
    max_amount = models.DecimalField(max_digits=10, decimal_places=2)
    percent_return = models.DecimalField(max_digits=5, decimal_places=2, help_text="Enter percentage as a whole number, e.g., 5 for 5%")
    duration_days = models.IntegerField()

    class Meta:
        verbose_name = 'Type Plan'
        verbose_name_plural = 'Type Plans'

    def __str__(self):
        return self.name


class Investment(models.Model):
    INVESTMENT_STATUS = [
        ('ACTIVE', 'Active'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled')
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    plan_id = ShortUUIDField(unique=True, length=10, max_length=20, prefix="PPD", alphabet='abcdesqp1234567890')
    type_plan = models.ForeignKey(Type_plans, on_delete=models.CASCADE)
    amount_invested = models.DecimalField(max_digits=10, decimal_places=2)
    expected_return = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    start_date = models.DateTimeField(default=timezone.now)
    end_date = models.DateTimeField(null=True, blank=True)  # Made optional since it's calculated
    profit_made = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)
    status = models.CharField(max_length=10, choices=INVESTMENT_STATUS, default='ACTIVE')
    last_profit_update = models.DateTimeField(auto_now_add=True, null=True, blank=True)  # Track last profit update

    class Meta:
        verbose_name = 'Investment'
        verbose_name_plural = 'Investments'
        ordering = ['-start_date']

    def __str__(self):
        return f"{self.type_plan.name} plan for {self.user.email}"

    def clean(self):
        from django.core.exceptions import ValidationError
        from django.db.models import Sum

        # Always enforce plan min/max limits
        if self.amount_invested < self.type_plan.min_amount:
            raise ValidationError(f"Amount must be at least {self.type_plan.min_amount}")
        if self.amount_invested > self.type_plan.max_amount:
            raise ValidationError(f"Amount cannot exceed {self.type_plan.max_amount}")

        # Only enforce the user's balance check when creating a new investment.
        # This avoids preventing admin edits (status changes, etc.) on already-purchased investments.
        if not self.pk:
            profile = Profile.objects.get(user=self.user)
            if profile.account_balance < self.amount_invested:
                raise ValidationError("Insufficient balance to purchase this plan")

    def calculate_end_date(self):
        """Calculate the end date based on type_plan duration"""
        # Use start_date if set, otherwise use now()
        base = self.start_date or timezone.now()
        return base + timezone.timedelta(days=self.type_plan.duration_days)

    def calculate_expected_return(self):
        """Calculate the expected return based on investment amount and plan percentage
        Uses simple interest: expected = principal * (1 + daily_percent * duration_days)
        """
        try:
            daily_rate = float(self.type_plan.percent_return) / 100.0
            days = int(self.type_plan.duration_days)
            total_multiplier = 1 + (daily_rate * days)
            return (Decimal(self.amount_invested) * Decimal(str(total_multiplier))).quantize(Decimal('0.01'))
        except Exception:
            # Fallback: single-period return
            roi_multiplier = self.type_plan.percent_return / 100
            return self.amount_invested + (self.amount_invested * roi_multiplier)

    def calculate_daily_profit(self):
        """Calculate daily profit based on investment amount and plan percentage"""
        daily_roi = self.type_plan.percent_return / 100
        return self.amount_invested * daily_roi

    def update_profit(self):
        """Update profit for days since last update"""
        from django.db import transaction
        now = timezone.now()
        
        # Only process if investment is active
        if not self.is_active or now >= self.end_date:
            return
            
        days_passed = (now - self.last_profit_update).days
        if days_passed < 1:
            return
            
        daily_profit = self.calculate_daily_profit()
        profit_to_add = daily_profit * days_passed
        
        with transaction.atomic():
            # Update investment profit
            self.profit_made += profit_to_add
            self.last_profit_update = now
            self.save()
            
            # Update user's balance with new profit
            Profile.objects.filter(user=self.user).update(
                account_balance=F('account_balance') + profit_to_add
            )
            
        return profit_to_add

    def save(self, *args, **kwargs):
        # Ensure start_date exists before calculating end_date/expected_return for new instances
        if not self.pk:
            if not self.start_date:
                self.start_date = timezone.now()
            self.end_date = self.calculate_end_date()
            self.expected_return = self.calculate_expected_return()

        # Run model validation but skip plan_id to avoid false failures when the DB/migrations
        # or ShortUUID generation produce values longer than the previous field constraint.
        # This avoids raising ValidationError on auto-generated plan_id.
        exclude = ['plan_id']
        self.full_clean(exclude=exclude)
        super().save(*args, **kwargs)

@receiver(post_save, sender=Deposit)
def update_profile_balance_on_deposit(sender, instance, created, **kwargs):
    # Only credit profile balance when deposit transitions to COMPLETED.
    # Use the _previous_status set in pre_save to determine if this is a transition.
    previous_status = getattr(instance, '_previous_status', None)
    if instance.status == 'COMPLETED' and previous_status != 'COMPLETED':
        Profile.objects.filter(user=instance.user).update(
            account_balance=F('account_balance') + instance.amount
        )


@receiver(pre_save, sender=Deposit)
def deposit_payment_status_pre_save(sender, instance, **kwargs):
    """Pre-save signal: if payment_status changed, apply mapping to other fields
    so a single save persists both payment_status and the mapped fields.
    """
    # Avoid re-entrant handling when apply_payment_status itself triggers save()
    if getattr(instance, '_apply_payment_status_in_progress', False):
        return

    # If this is a new instance there's no previous status to compare
    if not instance.pk:
        # New instance — record that there was no previous status
        instance._previous_status = None
        return

    try:
        previous = Deposit.objects.get(pk=instance.pk)
    except Deposit.DoesNotExist:
        instance._previous_status = None
        return

    # Store previous status on the instance so post_save handlers can detect transitions
    instance._previous_status = previous.status

    # If the payment_status changed, apply mapping to other fields *without* saving here;
    # the outer save() call (that triggered this pre_save) will persist the changes.
    if previous.payment_status != instance.payment_status:
        try:
            instance.apply_payment_status(instance.payment_status, actually_paid=None, save=False)
        except Exception:
            # Keep pre-save lightweight; let views/logging handle failures
            pass

@receiver(pre_save, sender=Withdrawal)
def track_withdrawal_status_change(sender, instance, **kwargs):
    """Track previous status before save"""
    if instance.pk:
        try:
            previous = Withdrawal.objects.get(pk=instance.pk)
            instance._previous_status = previous.status
        except Withdrawal.DoesNotExist:
            instance._previous_status = None
    else:
        instance._previous_status = None

@receiver(post_save, sender=Withdrawal)
def update_profile_balance_on_withdrawal(sender, instance, created, **kwargs):
    """Only debit profile balance when withdrawal transitions to COMPLETED"""
    previous_status = getattr(instance, '_previous_status', None)
    
    # Only debit if status changed to COMPLETED (not on creation)
    if instance.status == 'COMPLETED' and previous_status != 'COMPLETED':
        Profile.objects.filter(user=instance.user).update(
            account_balance=F('account_balance') - instance.amount
        )
        # Set completed timestamp if not already set
        if not instance.completed_at:
            instance.completed_at = timezone.now()
            instance.save(update_fields=['completed_at'])

@receiver(post_save, sender=Investment)
def update_profile_balance_on_investment(sender, instance, created, **kwargs):
	if created:
		# Safely update account_balance and optionally total_invested if it exists on Profile.
		updates = {
			'account_balance': F('account_balance') - instance.amount_invested
		}
		try:
			# Check whether Profile model defines 'total_invested'
			Profile._meta.get_field('total_invested')
		except FieldDoesNotExist:
			# Only update account_balance
			Profile.objects.filter(user=instance.user).update(**updates)
		else:
			# Update both account_balance and total_invested
			updates['total_invested'] = F('total_invested') + instance.amount_invested
			Profile.objects.filter(user=instance.user).update(**updates)

# Investment completion is now automated via context processor (see core/context_processors.py)
# This runs on every template render for authenticated users and completes expired investments.
