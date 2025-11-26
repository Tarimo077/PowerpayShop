from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, Vendor

# Inline for vendor info in User admin
class VendorInline(admin.StackedInline):
    model = Vendor
    can_delete = False
    verbose_name_plural = 'Vendor Info'
    fk_name = 'user'

class CustomUserAdmin(BaseUserAdmin):
    model = User
    list_display = ('username', 'email', 'is_vendor', 'is_staff', 'is_active')
    list_filter = ('is_vendor', 'is_staff', 'is_active')
    
    fieldsets = (
        (None, {'fields': ('username', 'email', 'password')}),
        ('Permissions', {'fields': ('is_vendor', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'password1', 'password2', 'is_vendor', 'is_staff', 'is_active')}
        ),
    )
    search_fields = ('username', 'email')
    ordering = ('username',)
    inlines = (VendorInline,)  # ← Add this line to include vendor info inline

# Register User with the updated admin
admin.site.register(User, CustomUserAdmin)

# Optionally register Vendor separately for admin-only access
@admin.register(Vendor)
class VendorAdmin(admin.ModelAdmin):
    list_display = ('shop_name', 'user', 'created_at')
    search_fields = ('shop_name', 'user__username', 'user__email')
