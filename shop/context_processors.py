from django.db.models import Sum

from .models import Cart, Wishlist


def unread_notifications_count(request):
    if request.user.is_authenticated:
        return {"unread_notif_count": request.user.notifications.filter(is_read=False).count()}
    return {"unread_notif_count": 0}


def cart_item_count(request):
    if request.user.is_authenticated:
        total = Cart.objects.filter(user=request.user).aggregate(total=Sum("items__quantity"))["total"] or 0
        return {"cart_item_count": total}
    return {"cart_item_count": 0}


def wishlist_count(request):
    if request.user.is_authenticated:
        return {"wishlist_count": Wishlist.objects.filter(user=request.user).count()}
    return {"wishlist_count": 0}


def is_approved_vendor(request):
    user = request.user
    approved = False
    if user.is_authenticated and getattr(user, "is_vendor", False) and getattr(user, "is_vendor_approved", False) and hasattr(user, "vendor"):
        approved = not user.vendor.is_suspended
    return {"is_approved_vendor": approved}


def is_admin(request):
    return {"is_admin": request.user.is_authenticated and request.user.is_staff}
