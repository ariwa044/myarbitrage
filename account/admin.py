from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html
from .models import User, Profile
from django.urls import reverse
from django.db.models import Sum, Count
from django.utils.translation import gettext_lazy as _

class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    verbose_name_plural = 'Financial Profile'
    fk_name = 'user'
    fields = ('account_balance',)

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ('email', 'username', 'full_name', 'phone_number', 'country',
                   'account_balance', 'birth_date', 'date_joined', 'is_active', 'actions_buttons')
    list_filter = ('is_active', 'is_staff', 'date_joined', 'country')
    search_fields = ('email', 'username', 'full_name', 'phone_number')
    ordering = ('-date_joined',)
    inlines = (ProfileInline,)

    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        (_('Personal info'), {'fields': (
            'username', 'full_name', 'phone_number', 'birth_date', 'address', 'refferal_code'
        )}),
        (_('Permissions'), {'fields': (
            'is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'
        )}),
        (_('Important dates'), {'fields': ('last_login', 'date_joined')}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'username', 'password1', 'password2'),
        }),
    )

    def get_full_name(self, obj):
        return obj.full_name or "-"
    get_full_name.short_description = 'Full Name'

    def account_balance(self, obj):
        try:
            # Ensure we format the numeric value before passing it to
            # format_html. If a value is already a SafeString, using a
            # format spec like ':,.2f' inside the template string will
            # attempt to apply numeric formatting to the SafeString and
            # raise ValueError: "Unknown format code 'f' for object of
            # type 'SafeString'". Pre-formatting avoids that.
            color = 'green' if obj.profile.account_balance > 0 else 'red'
            # Convert Decimal to a localized string with two decimals
            # and thousand separators.
            formatted_amount = f"{obj.profile.account_balance:,.2f}"
            return format_html(
                '<span style="color: {}">${}</span>',
                color,
                formatted_amount,
            )
        except Profile.DoesNotExist:
            return "-"
    account_balance.short_description = 'Balance'

    def actions_buttons(self, obj):
        profile_url = reverse('admin:account_profile_change', args=[obj.profile.id])
        return format_html(
            '<a class="button" href="{}">View Profile</a>&nbsp;',
            profile_url
        )
    actions_buttons.short_description = 'Actions'

    def get_inline_instances(self, request, obj=None):
        if not obj:
            return []
        return super().get_inline_instances(request, obj)

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user_email', 'user_full_name', 'account_balance', 'date_joined')
    list_filter = ('user__is_active',)
    search_fields = ('user__email', 'user__username', 'user__full_name')
    ordering = ('-user__date_joined',)

    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = 'Email'

    def user_full_name(self, obj):
        return obj.user.full_name or obj.user.username
    user_full_name.short_description = 'Full Name'

    def date_joined(self, obj):
        return obj.user.date_joined
    date_joined.short_description = 'Date Joined'

    def has_delete_permission(self, request, obj=None):
        return False  # Prevent profile deletion

    class Media:
        css = {
            'all': ('admin/css/custom_admin.css',)
        }

# Admin site customization
admin.site.site_header = 'Investment Platform Administration'
admin.site.site_title = 'Investment Admin Portal'
admin.site.index_title = 'Welcome to Investment Platform Admin'
