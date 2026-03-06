from django.urls import path
from . import views

urlpatterns = [
    path('', views.index_page, name='index'),
    path('search/', views.product_search, name='product_search'),
    path('vendor/', views.vendor_dashboard, name='vendor_dashboard'),
     path("product/<int:pk>/", views.product_detail, name="product_detail"),
    path('add-product/', views.add_product, name='add_product'),
    path('edit-product/<int:product_id>/', views.edit_product, name='edit_product'),
    path("delete_product/<int:product_id>/", views.delete_product, name="delete_product"),
    path('gallery/delete/<int:image_id>/', views.delete_gallery_image, name='delete_gallery_image'),
    path("rate/<int:product_id>/", views.rate_product, name="rate_product"),
    path("wishlist/toggle/<int:product_id>/", views.toggle_wishlist, name="toggle_wishlist"),
    path("wishlist/", views.wishlist_page, name="wishlist_page"),
    path("wishlist/remove/<int:wid>/", views.wishlist_remove, name="wishlist_remove"),
    path("wishlist/move-to-cart/<int:wid>/", views.wishlist_move_to_cart, name="wishlist_move_to_cart"),
    path("buy-now/<int:product_id>/", views.buy_now, name="buy_now"),
    path('cart/', views.view_cart, name='view_cart'),
    path('cart/add/<int:product_id>/', views.add_to_cart, name='add_to_cart'),
    path('cart/remove/<int:item_id>/', views.remove_from_cart, name='remove_from_cart'),
    path("cart/update/<int:item_id>/", views.update_cart_quantity, name="update_cart_quantity"),
    path('promo/apply', views.apply_promo, name='apply_promo'),
    path("promo/create/", views.create_promo_code, name='create_promo'),
    path('promo/edit/<int:promo_id>/', views.edit_promo, name='edit_promo'),
    path('promo/delete/<int:promo_id>/', views.delete_promo, name='delete_promo'),
    path('checkout/', views.checkout, name='checkout'),
    path("checkout/success/", views.checkout_success, name="checkout_success"),
    path("cart/update/<int:item_id>/", views.update_cart_quantity, name="update_cart_quantity"),
    path("payment/callback/", views.payment_callback, name="payment_callback"),
    path("check-payment-status/", views.check_payment_status, name="check_payment_status"),

]
