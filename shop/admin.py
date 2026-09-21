from django.contrib import admin
from .models import (
    Cart,
    CartItem,
    CheckoutOrder,
    Product,
    ProductGallery,
    ProductRating,
    PromoCode,
    Sale,
)

# Product Admin
@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'vendor', 'price', 'stock', 'created_at')
    list_filter = ('vendor',)
    search_fields = ('name', 'description', 'vendor__username')
    ordering = ('-created_at',)


@admin.register(ProductGallery)
class ProductGalleryAdmin(admin.ModelAdmin):
    list_display = ('product', 'alt_text')
    search_fields = ('product__name', 'alt_text')
    autocomplete_fields = ('product',)


@admin.register(PromoCode)
class PromoCodeAdmin(admin.ModelAdmin):
    list_display = (
        'code',
        'vendor',
        'discount_display',
        'visibility',
        'currently_valid',
        'used_count',
        'usage_limit',
        'valid_from',
        'valid_to',
    )
    list_filter = ('visibility', 'discount_type', 'is_active', 'vendor')
    search_fields = ('code', 'vendor__shop_name', 'vendor__user__username')
    filter_horizontal = ('products',)
    readonly_fields = ('used_count', 'created_at')
    ordering = ('-created_at',)
    date_hierarchy = 'created_at'

    @admin.display(description='Discount')
    def discount_display(self, promo):
        if promo.discount_type == 'percentage':
            return f'{promo.discount_value:g}%'
        return f'Ksh. {promo.discount_value:,.2f}'

    @admin.display(boolean=True, description='Valid now')
    def currently_valid(self, promo):
        return promo.is_valid()


# Sale/Admin
@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ('product', 'customer', 'vendor', 'quantity', 'total_price', 'status', 'created_at')
    list_filter = ('status', 'vendor')
    search_fields = ('product__name', 'customer__username', 'vendor__username')
    ordering = ('-created_at',)
    list_editable = ('status',)  # Allows changing status directly in list view


# Cart Admin
@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ('user', 'created_at')
    search_fields = ('user__username',)
    ordering = ('-created_at',)


# CartItem Admin
@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ('cart', 'product', 'quantity', 'total_price')
    search_fields = ('cart__user__username', 'product__name')

@admin.register(CheckoutOrder)
class CheckoutOrderAdmin(admin.ModelAdmin):
    list_display = ('user', 'email', 'phone', 'warranty_selected', 'payment_status', 'payment_ref', 'submitted_at')
    list_filter = ('warranty_selected', 'payment_status', 'buying_method')
    ordering = ('-submitted_at',)

@admin.register(ProductRating)
class ProductRatingAdmin(admin.ModelAdmin):
    list_display = ('product', 'user', 'rating', 'review', 'created_at')
    ordering = ('-created_at',)
    list_filter = ('rating', 'created_at', 'product')  # optional, for easier filtering
    search_fields = ('product__name', 'user__username', 'review')  # optional, for easier search
