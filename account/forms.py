from django import forms
from django.contrib.auth.forms import UserCreationForm, PasswordChangeForm
from django.contrib.auth import get_user_model
from .models import User, Profile

User = get_user_model()

class RegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    full_name = forms.CharField(
        max_length=50,
        help_text='Enter your full name'
    )
    country = forms.CharField(
        max_length=100,
        help_text='Enter your country'
    )
    phone_number = forms.CharField(
        max_length=30,
        help_text='Enter your phone number with country code (e.g., +1234567890)'
    )
    birth_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'}),
        help_text='Select your date of birth'
    )
    referral_code = forms.CharField(
        max_length=30,
        required=False,
        help_text='Enter referral code if you have one'
    )

    class Meta:
        model = User
        fields = [
            'full_name',
            'email',
            'username',
            'country',
            'phone_number',
            'birth_date',
            'referral_code',
            'password1',
            'password2'
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make all fields except referral_code required
        for field_name, field in self.fields.items():
            if field_name != 'referral_code':
                field.required = True
            
            # Add custom CSS classes to all fields
            if field_name == 'password1':
                field.help_text = 'Your password must contain at least 8 characters and cannot be entirely numeric.'
            elif field_name == 'password2':
                field.help_text = 'Enter the same password as before, for verification.'
            
            # Add class to fields for styling
            self.fields[field_name].widget.attrs.update({
                'class': 'form-input'
            })

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError('This email address is already registered.')
        return email

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError('This username is already taken.')
        return username


class LoginForm(forms.Form):
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'placeholder': 'Enter your email address',
            'class': 'form-input'
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Enter your password',
            'class': 'form-input'
        })
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['email'].label = 'Email Address'
        self.fields['password'].label = 'Password'


class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['full_name', 'phone_number', 'birth_date', 'address']
        widgets = {
            'full_name': forms.TextInput(attrs={
                'placeholder': 'Enter your full name',
                'class': 'form-input'
            }),
            'phone_number': forms.TextInput(attrs={
                'placeholder': 'Enter your phone number with country code',
                'class': 'form-input'
            }),
            'birth_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-input'
            }),
            'address': forms.Textarea(attrs={
                'placeholder': 'Enter your address',
                'class': 'form-input',
                'rows': 3
            })
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['full_name'].label = 'Full Name'
        self.fields['phone_number'].label = 'Phone Number'
        self.fields['birth_date'].label = 'Date of Birth'
        self.fields['address'].label = 'Address'


class CustomPasswordChangeForm(PasswordChangeForm):
    """
    Extended PasswordChangeForm with custom styling and validation
    """
    old_password = forms.CharField(
        label='Current Password',
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Enter your current password',
            'class': 'form-input',
            'autocomplete': 'current-password'
        })
    )
    new_password1 = forms.CharField(
        label='New Password',
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Enter your new password',
            'class': 'form-input',
            'autocomplete': 'new-password'
        }),
        help_text='Your new password must be at least 8 characters long and cannot be entirely numeric.'
    )
    new_password2 = forms.CharField(
        label='Confirm New Password',
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Confirm your new password',
            'class': 'form-input',
            'autocomplete': 'new-password'
        }),
        help_text='Enter the same password as above for verification.'
    )

    def __init__(self, user, *args, **kwargs):
        super().__init__(user, *args, **kwargs)
        
        # Add additional help text
        self.fields['old_password'].help_text = 'For your security, we need your current password to verify your identity.'
        
        # Update field labels for clarity
        self.fields['new_password1'].label = 'New Password'
        self.fields['new_password2'].label = 'Confirm New Password'

    def clean_old_password(self):
        """
        Validate that the old password is correct
        """
        old_password = self.cleaned_data.get('old_password')
        if not self.user.check_password(old_password):
            raise forms.ValidationError(
                'Your old password was entered incorrectly. Please try again.'
            )
        return old_password

    def clean_new_password2(self):
        """
        Validate that new passwords match
        """
        new_password1 = self.cleaned_data.get('new_password1')
        new_password2 = self.cleaned_data.get('new_password2')
        
        if new_password1 and new_password2:
            if new_password1 != new_password2:
                raise forms.ValidationError(
                    'The two password fields did not match.'
                )
        
        return new_password2

    def clean(self):
        """
        Additional validation for the entire form
        """
        cleaned_data = super().clean()
        old_password = cleaned_data.get('old_password')
        new_password1 = cleaned_data.get('new_password1')
        
        # Check if new password is same as old password
        if old_password and new_password1:
            if old_password == new_password1:
                raise forms.ValidationError(
                    'Your new password must be different from your current password.'
                )
        
        return cleaned_data