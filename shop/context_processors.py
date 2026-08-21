from django.db.models import Count, IntegerField, OuterRef, Subquery, Sum, Value
from django.db.models.functions import Coalesce

from accounts.models import User
from notifications.models import Notification
from .models import CartItem, Wishlist


def navigation_context(request):
    cached = getattr(request, "_shop_navigation_context", None)
    if cached is not None:
        return cached

    user = request.user
    defaults = {
        "unread_notif_count": 0,
        "cart_item_count": 0,
        "wishlist_count": 0,
        "is_approved_vendor": False,
        "is_admin": False,
    }
    if not user.is_authenticated:
        request._shop_navigation_context = defaults
        return defaults

    wishlist_count = (
        Wishlist.objects.filter(user_id=OuterRef("pk"))
        .values("user_id")
        .annotate(total=Count("pk"))
        .values("total")
    )
    unread_count = (
        Notification.objects.filter(user_id=OuterRef("pk"), is_read=False)
        .values("user_id")
        .annotate(total=Count("pk"))
        .values("total")
    )
    cart_count = (
        CartItem.objects.filter(cart__user_id=OuterRef("pk"))
        .values("cart__user_id")
        .annotate(total=Sum("quantity"))
        .values("total")
    )
    counts = (
        User.objects.filter(pk=user.pk)
        .annotate(
            nav_wishlist_count=Coalesce(Subquery(wishlist_count, output_field=IntegerField()), Value(0)),
            nav_unread_count=Coalesce(Subquery(unread_count, output_field=IntegerField()), Value(0)),
            nav_cart_count=Coalesce(Subquery(cart_count, output_field=IntegerField()), Value(0)),
        )
        .values("nav_wishlist_count", "nav_unread_count", "nav_cart_count", "vendor__is_suspended")
        .first()
    ) or {}

    context = {
        "unread_notif_count": counts.get("nav_unread_count", 0),
        "cart_item_count": counts.get("nav_cart_count", 0),
        "wishlist_count": counts.get("nav_wishlist_count", 0),
        "is_approved_vendor": bool(
            getattr(user, "is_vendor", False)
            and getattr(user, "is_vendor_approved", False)
            and not counts.get("vendor__is_suspended", True)
        ),
        "is_admin": user.is_staff,
    }
    request._shop_navigation_context = context
    return context


# Backward-compatible entry points for deployments whose settings still list
# the original individual context processors. They share the cached combined
# result, so using all five does not repeat the database query.
def cart_item_count(request):
    context = navigation_context(request)
    return {"cart_item_count": context["cart_item_count"]}


def wishlist_count(request):
    context = navigation_context(request)
    return {"wishlist_count": context["wishlist_count"]}


def unread_notifications_count(request):
    context = navigation_context(request)
    return {"unread_notif_count": context["unread_notif_count"]}


def is_approved_vendor(request):
    context = navigation_context(request)
    return {"is_approved_vendor": context["is_approved_vendor"]}


def is_admin(request):
    context = navigation_context(request)
    return {"is_admin": context["is_admin"]}
