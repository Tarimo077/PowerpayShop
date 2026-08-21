from django.contrib import admin
from .models import Product, Sale, Cart, CartItem, CheckoutOrder, ProductRating

# Product Admin
@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'vendor', 'price', 'stock', 'created_at')
    list_filter = ('vendor',)
    search_fields = ('name', 'description', 'vendor__username')
    ordering = ('-created_at',)


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
