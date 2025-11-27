from .models import Cart, Wishlist

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