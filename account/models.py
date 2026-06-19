from django.contrib.auth.models import AbstractUser
from django.db import models
from django.conf import settings
from django.utils import timezone
from shortuuid.django_fields import ShortUUIDField

class User(AbstractUser):
    email = models.EmailField(unique=True)
    username = models.CharField(max_length=30, unique=True)
    full_name = models.CharField(max_length=50, blank=True)
    phone_number = models.CharField(max_length=30, blank=True)
    birth_date = models.DateField(null=True, blank=True)
    address = models.CharField(max_length=255, blank=True)
    country = models.CharField(max_length=100, null=True, blank=True)
    refferal_code = ShortUUIDField(
        unique=True,
        length=6,
        max_length=30,
        prefix="AB",
        alphabet='1234567890',
        help_text="Unique referral code for this user"
    )
    signup_referral_code = models.CharField(
        max_length=30,
        null=True,
        blank=True,
        help_text="Referral code used during signup"
    )
    date_joined = models.DateTimeField(default=timezone.now)

#    is_active = models.BooleanField(default=False)
 #   is_staff = models.BooleanField(default=False)
  #  is_superuser = models.BooleanField(default=False)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    def __str__(self):
        return self.username

    class Meta:
      verbose_name = 'User'
      verbose_name_plural = 'Users'

class Profile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    account_balance = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    def __str__(self):
        return f"{self.user.username}'s profile"

    class Meta:
        verbose_name = 'Profile'
        verbose_name_plural = 'Profiles'