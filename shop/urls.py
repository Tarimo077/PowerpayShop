from django.urls import path
from . import views

urlpatterns = [
    path('', views.index_page, name='index'),
    path('vendor/', views.vendor_dashboard, name='vendor_dashboard'),
    path('add-product/', views.add_product, name='add_product'),
    path('edit-product/<int:product_id>/', views.edit_product, name='edit_product'),
    path("delete_product/<int:product_id>/", views.delete_product, name="delete_product"),
    path("rate/<int:product_id>/", views.rate_product, name="rate_product"),
    path('cart/', views.view_cart, name='view_cart'),
    path('cart/add/<int:product_id>/', views.add_to_cart, name='add_to_cart'),
    path('cart/remove/<int:item_id>/', views.remove_from_cart, name='remove_from_cart'),
    path("cart/update/<int:item_id>/", views.update_cart_quantity, name="update_cart_quantity"),
    path('checkout/', views.checkout, name='checkout'),
    path("checkout/success/", views.checkout_success, name="checkout_success"),
    path("cart/update/<int:item_id>/", views.update_cart_quantity, name="update_cart_quantity"),
    path("payment/callback/", views.payment_callback, name="payment_callback"),
]
