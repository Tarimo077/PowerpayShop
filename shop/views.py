from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import Product, PromoCode, Sale, Cart, CartItem, CheckoutOrder, ProductRating, Wishlist, ProductGallery
from django.contrib import messages
from .forms import ProductForm, CheckoutForm, PaymentForm, RatingForm, GalleryForm, PromoCodeForm
from django.db.models import Sum, Avg, Count, Q
from django.core.paginator import Paginator
from django.http import JsonResponse, HttpResponse, HttpResponseForbidden
import requests
from django.views.decorators.csrf import csrf_exempt
from django.template.loader import render_to_string
from django.conf import settings
from django.core.mail import send_mail
import uuid
import json
from accounts.models import Vendor
from django.views.decorators.http import require_http_methods
from notifications.utils import notify
from django.urls import reverse


def index_page(request):
    """Customer-facing view: shows all products"""
    products = Product.objects.all()
    vendors = Vendor.objects.filter(products__isnull=False).distinct()
    wishlist_items = []
    if request.user.is_authenticated:
        wishlist_items = Wishlist.objects.filter(user=request.user).values_list('product', flat=True)

    # Filters
    search = request.GET.get("search")
    min_price = request.GET.get("min_price")
    max_price = request.GET.get("max_price")
    vendor = request.GET.get("vendor")

    if search:
        products = products.filter(name__icontains=search)
    if min_price:
        products = products.filter(price__gte=min_price)
    if max_price:
        products = products.filter(price__lte=max_price)
    if vendor:
        products = products.filter(vendor__id=vendor)

    # ITEMS PER PAGE OPTIONS
    per_page = request.GET.get("per_page", 6)
    if per_page not in ["6", "9", "12"]:
        per_page = 6

    paginator = Paginator(products, per_page)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "products": page_obj,
        "per_page": int(per_page),
        "vendors": vendors,
        "wishlist_items": wishlist_items,
        "is_authenticated": request.user.is_authenticated,
        "search": search,
        "vendor": vendor,
        "min_price": min_price,
        "max_price": max_price,
    }

    if request.headers.get('HX-Request'):
        # HTMX request → render only the grid
        return render(request, "shop/product_grid.html", context)
    
    return render(request, "shop/index.html", context)

def product_search(request):
    query = request.GET.get("q", "")

    products = Product.objects.filter(
        Q(name__icontains=query) | 
        Q(vendor__shop_name__icontains=query)
    ) if query else []

    # If HTMX request → return partial
    if request.headers.get("HX-Request"):
        return render(request, "shop/search_results.html", {"products": products})

    # Standard full-page view
    return render(request, "shop/product_search.html", {
        "query": query,
        "products": products,
        
        "is_authenticated": request.user.is_authenticated,
    })


def vendor_dashboard(request):
    """Vendor-only view"""
    user = request.user
    if not (user.is_authenticated and user.is_vendor and user.is_vendor_approved and hasattr(user, "vendor")):
        return redirect("index")  # Redirect non-vendors

    vendor_instance = user.vendor
    products = Product.objects.filter(vendor=vendor_instance)
    promo_codes = PromoCode.objects.filter(vendor=vendor_instance)

    # Filters for products
    search = request.GET.get("search")
    min_price = request.GET.get("min_price")
    max_price = request.GET.get("max_price")

    if search:
        products = products.filter(name__icontains=search)
    if min_price:
        products = products.filter(price__gte=min_price)
    if max_price:
        products = products.filter(price__lte=max_price)

    # Stats
    product_count = products.count()
    total_sales = Sale.objects.filter(product__vendor=vendor_instance).count()
    total_revenue = Sale.objects.filter(product__vendor=vendor_instance).aggregate(Sum("total_price"))["total_price__sum"] or 0

    # Items per page (default: 5)
    per_page = request.GET.get("per_page", 5)
    if per_page not in ["5", "10"]:
        per_page = 5

    paginator = Paginator(products, per_page)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(request, "shop/vendor_dashboard.html", {
        "products": page_obj,
        "promo_codes": promo_codes,
        "product_count": product_count,
        "total_sales": total_sales,
        "total_revenue": total_revenue,
        "is_authenticated": True,
        "per_page": int(per_page),
    })


def product_detail(request, pk):
    product = get_object_or_404(Product, pk=pk)

    # Wishlist check
    in_wishlist = False
    if request.user.is_authenticated:
        in_wishlist = Wishlist.objects.filter(user=request.user, product=product).exists()

    # Similar products from same vendor
    similar_products = Product.objects.filter(
        vendor=product.vendor
    ).exclude(pk=product.pk)[:3]

    # Reviews and ratings
    ratings_qs = product.ratings.all()
    overall_rating = ratings_qs.aggregate(avg=Avg('rating'))['avg'] or 0
    rating_count = ratings_qs.count()

    # Count of each star
    star_counts = ratings_qs.values('rating').annotate(count=Count('rating'))
    star_summary = {i: 0 for i in range(1, 6)}
    for item in star_counts:
        star_summary[item['rating']] = item['count']

    # Calculate percentage for each star for the bars
    star_percentages = {}
    for star in range(1, 6):
        if rating_count > 0:
            star_percentages[star] = round(star_summary.get(star, 0) / rating_count * 100)
        else:
            star_percentages[star] = 0

    return render(request, "shop/product_detail.html", {
        "product": product,
        "in_wishlist": in_wishlist,
        "similar_products": similar_products,
        "is_authenticated": request.user.is_authenticated,
        "wishlist_items": Wishlist.objects.filter(user=request.user).values_list("product_id", flat=True) if request.user.is_authenticated else [],
        # Ratings
        "ratings": ratings_qs,
        "overall_rating": overall_rating,
        "rating_count": rating_count,
        "star_summary": star_summary,
        "star_percentages": star_percentages,
        "star_range": [1, 2, 3, 4, 5],
        "star_range_reverse": [5, 4, 3, 2, 1],  # For displaying 5→1 stars
    })


def product_image_swap(request, pk):
    product = get_object_or_404(Product, pk=pk)
    image_id = request.GET.get('image')

    if image_id == "main":
        image_url = product.image.url
    else:
        gallery_photo = get_object_or_404(ProductGallery, pk=image_id)
        image_url = gallery_photo.image.url

    # Return only the main image tag
    return HttpResponse(f'<img id="mainProductImage" src="{image_url}" class="rounded-xl w-full max-h-96 object-contain bg-white shadow-md transition duration-300" />')

@login_required
def add_product(request):
    if not request.user.is_vendor_approved:
        messages.error(request, "Only vendors can add products.")
        return redirect('index')

    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES)
        gallery_form = GalleryForm(request.POST, request.FILES)

        if form.is_valid() and gallery_form.is_valid():
            product = form.save(commit=False)
            product.vendor = request.user.vendor
            # Set max_stock to initial stock
            product.max_stock = product.stock
            product.save()

            # Save gallery images
            for img in gallery_form.cleaned_data['images']:
                ProductGallery.objects.create(product=product, image=img)
            
            notify(
                request.user,
                "New Product",
                f"{product.name} has been added",
                "success"
            )
            messages.success(request, "Product added successfully!")
            return redirect('vendor_dashboard')
    else:
        form = ProductForm()
        gallery_form = GalleryForm()

    return render(request, 'shop/add_edit_product.html', {
        'form': form,
        'gallery_form': gallery_form,
        'title': 'Add Product'
    })


@login_required
def edit_product(request, product_id):
    vendor = get_object_or_404(Vendor, user=request.user)
    product = get_object_or_404(Product, id=product_id, vendor=vendor)

    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES, instance=product)
        gallery_form = GalleryForm(request.POST, request.FILES)

        if form.is_valid() and gallery_form.is_valid():
            updated_product = form.save(commit=False)
            # If stock increased above max_stock, update max_stock
            #if updated_product.stock > product.max_stock:
            updated_product.max_stock = updated_product.stock
            updated_product.save()

            # Add new gallery images
            for img in gallery_form.cleaned_data['images']:
                ProductGallery.objects.create(product=product, image=img)
            notify(
                request.user,
                "Product Change",
                f"{updated_product.name} has been edited",
                "info"
            )
            messages.success(request, "Product updated successfully!")
            return redirect('vendor_dashboard')
    else:
        form = ProductForm(instance=product)
        gallery_form = GalleryForm()

    return render(request, 'shop/add_edit_product.html', {
        'form': form,
        'gallery_form': gallery_form,
        'title': 'Edit Product'
    })

def delete_product(request, product_id):
    product = get_object_or_404(Product, id=product_id)

    # Ensure user is authenticated
    if not request.user.is_authenticated:
        return redirect("login")

    # Ensure user is a vendor + approved + has vendor profile
    if not (request.user.is_vendor and request.user.is_vendor_approved and hasattr(request.user, "vendor")):
        messages.error(request, "You must be an approved vendor to perform this action.")
        return redirect("index")

    # Ensure this vendor owns the product
    if request.user.vendor != product.vendor:
        messages.error(request, "Not allowed. You can only delete your own products.")
        return redirect("vendor_dashboard")

    # Delete product
    product.delete()

    # Send notification
    notify(
        request.user,
        "Product Deleted",
        f"{product.name} has been removed from your shop.",
        "warning"
    )

    messages.warning(request, "Product deleted successfully!")
    return redirect("vendor_dashboard")


@login_required
@require_http_methods(["DELETE"])
def delete_gallery_image(request, image_id):
    vendor = get_object_or_404(Vendor, user=request.user)
    image = get_object_or_404(ProductGallery, id=image_id, product__vendor=vendor)
    image.delete()
    return HttpResponse("", status=200)

@login_required
def buy_now(request, product_id):
    product = get_object_or_404(Product, id=product_id)

    # Get or create user's cart
    cart, created = Cart.objects.get_or_create(user=request.user)

    # Add item (qty=1) OR update if already exists
    item, created = CartItem.objects.get_or_create(cart=cart, product=product)
    if not created:
        item.quantity += 1
        item.save()

    # Redirect to cart page
    return redirect('view_cart')

@login_required
def add_to_cart(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    
    # Use get_or_create to find the cart or create a new one if it doesn't exist
    # 'created' will be a boolean indicating if a new object was created
    cart, created = Cart.objects.get_or_create(user=request.user)
    
    # Now that we know the cart exists, we can proceed with adding the item
    item, item_created = CartItem.objects.get_or_create(cart=cart, product=product)

    if not item_created:
        # If the item already existed, increment its quantity
        item.quantity += 1
        item.save()

    messages.success(request, f"Added {product.name} to your cart.")
    return redirect(request.META.get('HTTP_REFERER', 'index'))


@login_required
def view_cart(request):
    try:
        cart = Cart.objects.get(user=request.user)
    except Cart.DoesNotExist:
        messages.error(request, "Cart is empty.")
        # Redirects to the previous page, defaulting to the root URL (/) if no referer is found
        return redirect(request.META.get('HTTP_REFERER', '/'))

    return render(request, 'shop/cart.html', {'cart': cart})

@login_required
def remove_from_cart(request, item_id):
    item = get_object_or_404(CartItem, id=item_id, cart__user=request.user)
    item.delete()
    messages.success(request, f"{item.product.name} removed from cart.")
    return redirect('view_cart')

@login_required
def update_cart_quantity(request, item_id):
    if request.method == "POST":
        new_qty = int(request.POST.get("quantity", 1))
        item = get_object_or_404(CartItem, id=item_id, cart__user=request.user)
        item.quantity = max(1, new_qty)
        item.save()

        cart = item.cart
        subtotal = cart.total_price()
        discount = 0
        
        promo_code = request.POST.get('promo_code')
        if promo_code:
            try:
                promo = PromoCode.objects.get(code__iexact=promo_code, is_active=True)
                if promo.is_valid():
                    # Recalculate discount ONLY for the specific product linked to the promo
                    applicable_item = cart.items.filter(product=promo.product).first()
                    if applicable_item:
                        item_total = applicable_item.total_price()
                        if promo.discount_type == 'percentage':
                            discount = (promo.discount_value / 100) * item_total
                        else:
                            discount = promo.discount_value
            except PromoCode.DoesNotExist:
                pass

        return JsonResponse({
            "item_total": item.total_price(),
            "cart_total": subtotal,
            "discount_amount": float(discount),
            "new_total": float(max(0, subtotal - discount))
        })
    

@login_required
def wishlist_page(request):
    items = Wishlist.objects.filter(user=request.user)

    # Extract product objects from wishlist entries
    products = [w.product for w in items]

    # For highlighting wishlist icons (hearts filled)
    wishlist_items = [w.product.id for w in items]

    return render(request, "shop/wishlist.html", {
        "items": items,           # raw wishlist entries
        "products": products,     # actual product objects
        "wishlist_items": wishlist_items,
        "is_authenticated": True,
    })


@login_required
def wishlist_remove(request, wid):
    item = get_object_or_404(Wishlist, id=wid, user=request.user)
    item.delete()
    messages.info(request, f"{item.product.name} removed from wishlist.")
    return redirect(request.META.get('HTTP_REFERER', 'wishlist_page'))


@login_required
def wishlist_move_to_cart(request, wid):
    item = get_object_or_404(Wishlist, id=wid, user=request.user)

    # Use your existing add_to_cart logic
    product_id = item.product.id

    # Add product to cart
    cart, created = Cart.objects.get_or_create(user=request.user)
    cart_item, new = CartItem.objects.get_or_create(cart=cart, product=item.product)

    if not new:
        cart_item.quantity += 1
        cart_item.save()

    # Remove from wishlist after moving to cart
    item.delete()

    messages.success(request, f"Moved {item.product.name} to your cart.")

    return redirect("wishlist_page")

@login_required
def toggle_wishlist(request, product_id):
    product = get_object_or_404(Product, id=product_id)

    wishlist_entry, created = Wishlist.objects.get_or_create(
        user=request.user,
        product=product
    )

    if not created:
        # Already exists → remove
        wishlist_entry.delete()
        messages.info(request, f"{product.name} removed from wishlist.")
    else:
        messages.success(request, f"{product.name} added to wishlist!")

    return redirect(request.META.get("HTTP_REFERER", "index"))

    
@login_required
def rate_product(request, product_id):
    product = get_object_or_404(Product, id=product_id)

    try:
        rating_obj = ProductRating.objects.get(product=product, user=request.user)
    except ProductRating.DoesNotExist:
        rating_obj = None

    if request.method == "POST":
        form = RatingForm(request.POST, instance=rating_obj)
        if form.is_valid():
            rating = form.save(commit=False)
            rating.user = request.user
            rating.product = product
            rating.save()
            messages.success(request, "Rating submitted!")
            return redirect("product_detail", pk=product.id)
    else:
        form = RatingForm(instance=rating_obj)

    return render(request, "shop/rate_product.html", {
        "product": product,
        "form": form,
    })

@login_required
def wishlist(request):
    wishlist_items = Wishlist.objects.filter(user=request.user).select_related('product')
    products = [item.product for item in wishlist_items]

    context = {
        'products': products,
        'wishlist_items': wishlist_items  # optional for hearts
    }
    return render(request, 'shop/wishlist.html', context)


@login_required
def apply_promo(request):
    if request.method == "POST":
        code_text = request.POST.get('code', '').strip()
        try:
            cart = Cart.objects.get(user=request.user)
            # Find the promo
            promo = PromoCode.objects.get(code__iexact=code_text, is_active=True)

            # Check if dates/usage limits are valid
            if not promo.is_valid():
                return JsonResponse({'success': False, 'message': 'Code is expired or inactive'})

            cart_items = cart.items.all()
            discount = 0
            applicable_products = promo.products.all()
            found_applicable_product = False

            for item in cart_items:
                # If no products specified (Store-wide) OR item is in the allowed list
                if not applicable_products.exists() or item.product in applicable_products:
                    found_applicable_product = True
                    item_total = item.total_price()
                    
                    if promo.discount_type == 'percentage':
                        discount += (promo.discount_value / 100) * item_total
                    else:
                        # Fixed amount applied per qualifying product type
                        discount += promo.discount_value

            if not found_applicable_product:
                return JsonResponse({
                    'success': False, 
                    'message': 'This code does not apply to items in your cart.'
                })

            subtotal = cart.total_price()
        
            return JsonResponse({
                'success': True,
                'subtotal': float(subtotal),
                'discount_amount': float(discount),
                'new_total': float(max(0, subtotal - discount))
            })

        except PromoCode.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'Invalid promo code'})
    
    return JsonResponse({'success': False, 'message': 'Invalid request'})

@login_required
def create_promo_code(request):
    if not request.user.is_vendor or not request.user.is_vendor_approved:
        return HttpResponseForbidden()

    vendor = request.user.vendor

    if request.method == "POST":
        form = PromoCodeForm(request.POST, vendor=vendor)
        if form.is_valid():
            promo = form.save(commit=False)
            promo.vendor = vendor
            promo.save()
            form.save_m2m()
            messages.success(request, "Promo code created successfully!")
            # Redirect to dashboard with #promotions fragment
            return redirect(reverse("vendor_dashboard") + "#promotions")
    else:
        form = PromoCodeForm(vendor=vendor)

    return render(request, "shop/vendor_promo_form.html", {"form": form})

@login_required
def edit_promo(request, promo_id):
    vendor = request.user.vendor
    promo = get_object_or_404(PromoCode, id=promo_id, vendor=vendor)
    
    if request.method == "POST":
        # Added vendor=vendor here so the product list stays filtered during edit
        form = PromoCodeForm(request.POST, instance=promo, vendor=vendor)
        if form.is_valid():
            form.save()
            messages.success(request, "Promo code updated!")
            return redirect(reverse("vendor_dashboard") + "#promotions")
    else:
        form = PromoCodeForm(instance=promo, vendor=vendor)
        
    return render(request, "shop/vendor_promo_form.html", {"form": form, "edit": True, "promo": promo})

@login_required
def delete_promo(request, promo_id):
    promo = get_object_or_404(PromoCode, id=promo_id, vendor=request.user.vendor)
    if request.method == "POST":
        promo.delete()
        messages.success(request, "Promo code deleted.")
        return redirect(reverse("vendor_dashboard") + "#promotions")
    return render(request, "shop/vendor_promo_confirm_delete.html", {"promo": promo})

@login_required
def checkout(request):
    try:
        cart = Cart.objects.get(user=request.user)
    except Cart.DoesNotExist:
        messages.error(request, "Cart is empty.")
        return redirect("index")

    subtotal = cart.total_price()

    discount = 0
    final_amount = subtotal
    promo_obj = None

    if request.method == "POST":
        form = CheckoutForm(request.POST)
        payment_form = PaymentForm(request.POST)

        promo_code_str = request.POST.get("promo_code", "").strip()

        if form.is_valid() and payment_form.is_valid():

            # Promo code validation
            if promo_code_str:
                try:
                    promo_obj = PromoCode.objects.get(code__iexact=promo_code_str, is_active=True)

                    if promo_obj.is_valid():
                        applicable_products = promo_obj.products.all()

                        if applicable_products.exists():
                            for item in cart.items.all():
                                if item.product in applicable_products:
                                    if promo_obj.discount_type == "percentage":
                                        discount += (promo_obj.discount_value / 100) * item.total_price()
                                    else:
                                        discount += promo_obj.discount_value
                        else:
                            if promo_obj.discount_type == "percentage":
                                discount = (promo_obj.discount_value / 100) * subtotal
                            else:
                                discount = promo_obj.discount_value

                except PromoCode.DoesNotExist:
                    discount = 0

            final_amount = max(0, subtotal - discount)

            # Create order
            order = form.save(commit=False)
            order.user = request.user
            order.total_amount = final_amount
            order.payment_status = "pending"
            order.save()

            # Generate payment reference
            ref = f"order-{order.id}-{uuid.uuid4().hex[:6]}"
            order.payment_ref = ref
            order.save()

            # Create sales BEFORE payment
            for item in cart.items.all():
                Sale.objects.create(
                    order=order,
                    product=item.product,
                    customer=request.user,
                    vendor=item.product.vendor.user,
                    quantity=item.quantity,
                    total_price=item.total_price(),
                    status="pending"
                )

            mpesa_phone = payment_form.cleaned_data["mpesa_phone"]

            success, resp = initiate_stk_push(
                amount=int(final_amount),
                contact=mpesa_phone,
                ref=ref
            )

            if success:

                if promo_obj:
                    promo_obj.used_count += 1
                    promo_obj.save()

                send_checkout_emails(order, final_amount, ref)

                request.session["checkout_ref"] = ref
                request.session["checkout_order_id"] = order.id

                return redirect("checkout_success")

            else:
                messages.error(request, f"Payment failed: {resp}")
                return redirect("checkout")

    else:
        form = CheckoutForm(initial={"email": request.user.email})
        payment_form = PaymentForm()

    return render(request, "shop/checkout.html", {
        "form": form,
        "payment_form": payment_form,
        "cart": cart,
        "items": cart.items.all(),
        "subtotal": subtotal,
        "discount": discount,
        "cart_total": final_amount,
    })

@login_required
def checkout_success(request):

    ref = request.session.get("checkout_ref")
    order_id = request.session.get("checkout_order_id")

    order = None
    if order_id:
        try:
            order = CheckoutOrder.objects.get(id=order_id)
        except CheckoutOrder.DoesNotExist:
            order = None

    return render(request, "shop/checkout_success.html", {
        "ref": ref,
        "order": order,
    })

def initiate_stk_push(amount, contact, ref):

    url = getattr(settings, "MPESA_ENDPOINT")

    payload = {
        "amount": int(amount),
        "contact": str(contact),
        "ref": str(ref)
    }

    try:
        r = requests.post(url, json=payload, timeout=15)
        r.raise_for_status()

        if r.headers.get("content-type", "").startswith("application/json"):
            return True, r.json()
        else:
            return True, r.text

    except Exception as e:
        return False, str(e)


@csrf_exempt
def payment_callback(request):

    if request.method != "POST":
        return JsonResponse({"detail": "Method not allowed"}, status=405)

    try:
        data = json.loads(request.body)
    except Exception:
        return JsonResponse({"detail": "Invalid JSON"}, status=400)

    try:
        callback = data["Body"]["stkCallback"]
    except KeyError:
        return JsonResponse({"detail": "Invalid callback structure"}, status=400)

    result_code = callback.get("ResultCode")
    merchant_request_id = callback.get("MerchantRequestID")

    if not merchant_request_id:
        return JsonResponse({"detail": "Reference missing"}, status=400)

    try:
        order = CheckoutOrder.objects.get(payment_ref=merchant_request_id)
    except CheckoutOrder.DoesNotExist:
        return JsonResponse({"detail": "Order not found"}, status=404)

    # Payment cancelled or failed
    if result_code != 0:
        order.payment_status = "failed"
        order.save()
        return JsonResponse({"detail": "Payment failed"}, status=200)

    metadata = callback.get("CallbackMetadata", {}).get("Item", [])

    meta = {item["Name"]: item.get("Value") for item in metadata if "Name" in item}

    receipt = meta.get("MpesaReceiptNumber")

    # Update order
    order.payment_status = "paid"
    order.mpesa_receipt = receipt
    order.save()

    # Update sales
    sales = order.sales.all()

    for sale in sales:
        sale.status = "paid"
        sale.save()

        # Reduce stock
        product = sale.product
        product.stock -= sale.quantity
        product.save()

    # Clear cart
    cart = Cart.objects.filter(user=order.user).first()
    if cart:
        cart.items.all().delete()

    return JsonResponse({"detail": "Payment processed"}, status=200)


@login_required
def check_payment_status(request):

    order_id = request.session.get("checkout_order_id")

    if not order_id:
        return JsonResponse({"status": "unknown"})

    try:
        order = CheckoutOrder.objects.get(id=order_id)
    except CheckoutOrder.DoesNotExist:
        return JsonResponse({"status": "unknown"})

    return JsonResponse({
        "status": order.payment_status,
        "receipt": order.mpesa_receipt
    })

def send_checkout_emails(order, cart_total, ref):
    # user email
    html_user = render_to_string("emails/checkout_user_email.html", {
        "order": order, "cart_total": cart_total, "ref": ref,
        #"site_logo_url": requests.build_absolute_uri(static('images/pplogo.png'))  # or static url
    })
    send_mail(
        subject="Your PowerPay order",
        message="Your order has been received.",
        from_email=None,
        recipient_list=[order.email],
        html_message=html_user
    )