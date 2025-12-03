from .models import Cart, Wishlist
from notifications.models import Notification

def unread_notifications_count(request):
    if request.user.is_authenticated:
        return {'unread_notif_count': request.user.notifications.filter(is_read=False).count()}
    return {'unread_notif_count': 0}

def cart_item_count(request):
    if request.user.is_authenticated:
        try:
            cart = Cart.objects.get(user=request.user)
            return {"cart_item_count": cart.items.count()}
        except Cart.DoesNotExist:
            return {"cart_item_count": 0}
    return {"cart_item_count": 0}

def wishlist_count(request):
    if request.user.is_authenticated:
        return {
            "wishlist_count": Wishlist.objects.filter(user=request.user).count()
        }
    return {"wishlist_count": 0}

def is_approved_vendor(request):
    user = request.user
    return {
        "is_approved_vendor": (
            user.is_authenticated
            and user.is_vendor
            and user.is_vendor_approved
            and hasattr(user, "vendor")
            and not user.vendor.is_suspended  # check suspension
        )
    }


def is_admin(request):
    return {
        "is_admin": request.user.is_authenticated and request.user.is_staff
    }
