from decimal import Decimal, InvalidOperation
import json
import uuid

import requests
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Avg, Count, F, Prefetch, Q, Sum
from django.http import JsonResponse, HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_POST

from accounts.models import Vendor
from notifications.utils import notify
from .forms import CheckoutForm, GalleryForm, PaymentForm, ProductForm, PromoCodeForm, RatingForm
from .models import (
    Cart,
    CartItem,
    CheckoutOrder,
    Product,
    ProductGallery,
    ProductRating,
    PromoCode,
    Sale,
    Wishlist,
)


def _safe_decimal(value):
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _safe_int_choice(request, name, allowed, default):
    requested = request.GET.get(name, str(default))
    return int(requested) if requested in {str(item) for item in allowed} else int(default)


def _safe_per_page(request, allowed, default):
    return _safe_int_choice(request, "per_page", allowed, default)


def _safe_columns(request):
    return _safe_int_choice(request, "columns", allowed=(3, 4, 5), default=4)


def _apply_product_sorting(products, sort):
    sort_map = {
        "latest": "-created_at",
        "price_low": "price",
        "price_high": "-price",
        "rating": "-avg_rating",
        "stock": "-stock",
    }
    return products.order_by(sort_map.get(sort, "-created_at"), "-id")


def _base_product_queryset():
    return (
        Product.objects.select_related("vendor", "vendor__user")
        .prefetch_related("gallery", "ratings")
        .annotate(avg_rating=Avg("ratings__rating"), rating_total=Count("ratings"))
        .order_by("-created_at")
    )


def _wishlist_product_ids(user):
    if not user.is_authenticated:
        return []
    return list(Wishlist.objects.filter(user=user).values_list("product_id", flat=True))


def _get_user_cart(user):
    return (
        Cart.objects.filter(user=user)
        .prefetch_related(
            Prefetch(
                "items",
                queryset=CartItem.objects.select_related("product", "product__vendor", "product__vendor__user"),
            )
        )
        .first()
    )


def _calculate_discount(cart, promo):
    if not promo or not promo.is_valid():
        return Decimal("0.00"), False

    allowed_product_ids = set(promo.products.values_list("id", flat=True))
    applies_store_wide = not allowed_product_ids
    discount = Decimal("0.00")
    found_applicable_product = False

    for item in cart.items.all():
        if applies_store_wide or item.product_id in allowed_product_ids:
            found_applicable_product = True
            item_total = item.total_price()
            if promo.discount_type == "percentage":
                discount += (promo.discount_value / Decimal("100")) * item_total
            else:
                discount += promo.discount_value

    return discount, found_applicable_product


def _add_product_to_cart(user, product):
    if product.stock <= 0:
        return None, "out_of_stock"

    cart, _ = Cart.objects.get_or_create(user=user)
    item, created = CartItem.objects.get_or_create(cart=cart, product=product, defaults={"quantity": 1})
    if not created:
        if item.quantity >= product.stock:
            return item, "max_stock"
        item.quantity = min(product.stock, item.quantity + 1)
        item.save(update_fields=["quantity"])
    return item, "added"


def index_page(request):
    products = _base_product_queryset()
    vendors = Vendor.objects.filter(products__isnull=False).select_related("user").distinct().order_by("shop_name")

    search = request.GET.get("search", "").strip()
    min_price_raw = request.GET.get("min_price", "").strip()
    max_price_raw = request.GET.get("max_price", "").strip()
    min_price = _safe_decimal(min_price_raw)
    max_price = _safe_decimal(max_price_raw)
    vendor = request.GET.get("vendor", "").strip()
    sort = request.GET.get("sort", "latest").strip()
    columns = _safe_columns(request)

    active_filters_count = sum(bool(value) for value in (search, vendor, min_price_raw, max_price_raw))

    if search:
        products = products.filter(Q(name__icontains=search) | Q(description__icontains=search) | Q(vendor__shop_name__icontains=search))
    if min_price is not None:
        products = products.filter(price__gte=min_price)
    if max_price is not None:
        products = products.filter(price__lte=max_price)
    if vendor.isdigit():
        products = products.filter(vendor_id=int(vendor))

    products = _apply_product_sorting(products, sort)
    per_page = _safe_per_page(request, allowed=(6, 9, 12, 15), default=12)
    page_obj = Paginator(products, per_page).get_page(request.GET.get("page"))

    context = {
        "products": page_obj,
        "per_page": per_page,
        "columns": columns,
        "sort": sort if sort in {"latest", "price_low", "price_high", "rating", "stock"} else "latest",
        "vendors": vendors,
        "wishlist_items": _wishlist_product_ids(request.user),
        "is_authenticated": request.user.is_authenticated,
        "search": search,
        "vendor": vendor,
        "min_price": min_price_raw,
        "max_price": max_price_raw,
        "active_filters_count": active_filters_count,
        "total_products": page_obj.paginator.count,
    }

    if request.headers.get("HX-Request"):
        return render(request, "shop/product_listing.html", context)
    return render(request, "shop/index.html", context)


def product_search(request):
    query = request.GET.get("q", "").strip()
    products = []
    if query:
        products = _base_product_queryset().filter(
            Q(name__icontains=query) | Q(description__icontains=query) | Q(vendor__shop_name__icontains=query)
        )[:8]

    template = "shop/search_results.html" if request.headers.get("HX-Request") else "shop/product_search.html"
    return render(request, template, {"query": query, "products": products, "is_authenticated": request.user.is_authenticated})


@login_required
def vendor_dashboard(request):
    user = request.user
    if not (user.is_vendor and user.is_vendor_approved and hasattr(user, "vendor") and not user.vendor.is_suspended):
        messages.error(request, "Only approved vendors can access the dashboard.")
        return redirect("index")

    vendor_instance = user.vendor
    products = _base_product_queryset().filter(vendor=vendor_instance)
    promo_codes = PromoCode.objects.filter(vendor=vendor_instance).prefetch_related("products").order_by("-created_at")

    search = request.GET.get("search", "").strip()
    min_price = _safe_decimal(request.GET.get("min_price"))
    max_price = _safe_decimal(request.GET.get("max_price"))

    if search:
        products = products.filter(Q(name__icontains=search) | Q(description__icontains=search))
    if min_price is not None:
        products = products.filter(price__gte=min_price)
    if max_price is not None:
        products = products.filter(price__lte=max_price)

    stats = Sale.objects.filter(product__vendor=vendor_instance).aggregate(total_sales=Count("id"), total_revenue=Sum("total_price"))
    per_page = _safe_per_page(request, allowed=(5, 10, 15), default=10)
    page_obj = Paginator(products, per_page).get_page(request.GET.get("page"))

    return render(
        request,
        "shop/vendor_dashboard.html",
        {
            "products": page_obj,
            "promo_codes": promo_codes,
            "product_count": products.count(),
            "total_sales": stats["total_sales"] or 0,
            "total_revenue": stats["total_revenue"] or 0,
            "is_authenticated": True,
            "per_page": per_page,
            "search": search,
            "min_price": request.GET.get("min_price", ""),
            "max_price": request.GET.get("max_price", ""),
        },
    )


def product_detail(request, pk):
    product = get_object_or_404(_base_product_queryset(), pk=pk)
    in_wishlist = request.user.is_authenticated and Wishlist.objects.filter(user=request.user, product=product).exists()
    similar_products = _base_product_queryset().filter(vendor=product.vendor).exclude(pk=product.pk)[:3]

    ratings_qs = product.ratings.select_related("user").order_by("-created_at")
    overall_rating = ratings_qs.aggregate(avg=Avg("rating"))["avg"] or 0
    rating_count = ratings_qs.count()
    star_summary = {i: 0 for i in range(1, 6)}
    for item in ratings_qs.values("rating").annotate(count=Count("rating")):
        star_summary[item["rating"]] = item["count"]
    star_percentages = {star: round(star_summary.get(star, 0) / rating_count * 100) if rating_count else 0 for star in range(1, 6)}

    return render(
        request,
        "shop/product_detail.html",
        {
            "product": product,
            "in_wishlist": in_wishlist,
            "similar_products": similar_products,
            "is_authenticated": request.user.is_authenticated,
            "wishlist_items": _wishlist_product_ids(request.user),
            "ratings": ratings_qs,
            "overall_rating": overall_rating,
            "rating_count": rating_count,
            "star_summary": star_summary,
            "star_percentages": star_percentages,
            "star_range": [1, 2, 3, 4, 5],
            "star_range_reverse": [5, 4, 3, 2, 1],
        },
    )


def product_image_swap(request, pk):
    product = get_object_or_404(Product, pk=pk)
    image_id = request.GET.get("image")

    if image_id == "main":
        image_url = product.image.url if product.image else ""
    else:
        gallery_photo = get_object_or_404(ProductGallery, pk=image_id, product=product)
        image_url = gallery_photo.image.url

    return HttpResponse(f'<img id="mainProductImage" src="{image_url}" class="rounded-xl w-full max-h-96 object-contain bg-white shadow-md transition duration-300" />')


@login_required
def add_product(request):
    if not (request.user.is_vendor and request.user.is_vendor_approved and hasattr(request.user, "vendor")):
        messages.error(request, "Only approved vendors can add products.")
        return redirect("index")

    if request.method == "POST":
        form = ProductForm(request.POST, request.FILES)
        gallery_form = GalleryForm(request.POST, request.FILES)
        if form.is_valid() and gallery_form.is_valid():
            product = form.save(commit=False)
            product.vendor = request.user.vendor
            product.max_stock = product.stock
            product.save()
            for img in gallery_form.cleaned_data.get("images", []):
                ProductGallery.objects.create(product=product, image=img)
            notify(request.user, "New Product", f"{product.name} has been added", "success")
            messages.success(request, "Product added successfully!")
            return redirect("vendor_dashboard")
    else:
        form = ProductForm()
        gallery_form = GalleryForm()

    return render(request, "shop/add_edit_product.html", {"form": form, "gallery_form": gallery_form, "title": "Add Product"})


@login_required
def edit_product(request, product_id):
    vendor = get_object_or_404(Vendor, user=request.user)
    product = get_object_or_404(Product.objects.prefetch_related("gallery"), id=product_id, vendor=vendor)

    if request.method == "POST":
        form = ProductForm(request.POST, request.FILES, instance=product)
        gallery_form = GalleryForm(request.POST, request.FILES)
        if form.is_valid() and gallery_form.is_valid():
            updated_product = form.save(commit=False)
            if updated_product.stock > updated_product.max_stock:
                updated_product.max_stock = updated_product.stock
            updated_product.save()
            for img in gallery_form.cleaned_data.get("images", []):
                ProductGallery.objects.create(product=updated_product, image=img)
            notify(request.user, "Product Change", f"{updated_product.name} has been edited", "info")
            messages.success(request, "Product updated successfully!")
            return redirect("vendor_dashboard")
    else:
        form = ProductForm(instance=product)
        gallery_form = GalleryForm()

    return render(request, "shop/add_edit_product.html", {"form": form, "gallery_form": gallery_form, "title": "Edit Product", "product": product})


@login_required
@require_POST
def delete_product(request, product_id):
    product = get_object_or_404(Product, id=product_id, vendor__user=request.user)
    product_name = product.name
    product.delete()
    notify(request.user, "Product Deleted", f"{product_name} has been removed from your shop.", "warning")
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
    _, status = _add_product_to_cart(request.user, product)
    if status == "out_of_stock":
        messages.error(request, f"{product.name} is out of stock.")
        return redirect(request.META.get("HTTP_REFERER", "index"))
    if status == "max_stock":
        messages.info(request, f"Your cart already has the available stock for {product.name}.")
    return redirect("view_cart")


@login_required
def add_to_cart(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    _, status = _add_product_to_cart(request.user, product)
    if status == "out_of_stock":
        messages.error(request, f"{product.name} is out of stock.")
    elif status == "max_stock":
        messages.info(request, f"Your cart already has the available stock for {product.name}.")
    else:
        messages.success(request, f"Added {product.name} to your cart.")
    return redirect(request.META.get("HTTP_REFERER", "index"))


@login_required
def view_cart(request):
    cart = _get_user_cart(request.user)
    if not cart or not cart.items.exists():
        messages.info(request, "Cart is empty.")
        return render(request, "shop/cart.html", {"cart": cart})
    return render(request, "shop/cart.html", {"cart": cart})


@login_required
def remove_from_cart(request, item_id):
    item = get_object_or_404(CartItem.objects.select_related("product"), id=item_id, cart__user=request.user)
    product_name = item.product.name
    item.delete()
    messages.success(request, f"{product_name} removed from cart.")
    return redirect("view_cart")


@login_required
@require_POST
def update_cart_quantity(request, item_id):
    item = get_object_or_404(CartItem.objects.select_related("cart", "product"), id=item_id, cart__user=request.user)
    try:
        new_qty = max(1, int(request.POST.get("quantity", 1)))
    except (TypeError, ValueError):
        return JsonResponse({"error": "Invalid quantity"}, status=400)

    item.quantity = min(new_qty, max(1, item.product.stock))
    item.save(update_fields=["quantity"])

    cart = _get_user_cart(request.user)
    subtotal = cart.total_price() if cart else Decimal("0.00")
    discount = Decimal("0.00")
    promo_code = request.POST.get("promo_code", "").strip()
    if promo_code and cart:
        promo = PromoCode.objects.filter(code__iexact=promo_code, is_active=True).prefetch_related("products").first()
        if promo:
            discount, _ = _calculate_discount(cart, promo)

    return JsonResponse(
        {
            "item_total": float(item.total_price()),
            "cart_total": float(subtotal),
            "discount_amount": float(discount),
            "new_total": float(max(Decimal("0.00"), subtotal - discount)),
        }
    )


@login_required
def wishlist_page(request):
    items = Wishlist.objects.filter(user=request.user).select_related("product", "product__vendor", "product__vendor__user")
    products = [item.product for item in items]
    wishlist_items = [item.product_id for item in items]
    return render(request, "shop/wishlist.html", {"items": items, "products": products, "wishlist_items": wishlist_items, "is_authenticated": True})


@login_required
def wishlist_remove(request, wid):
    item = get_object_or_404(Wishlist.objects.select_related("product"), id=wid, user=request.user)
    product_name = item.product.name
    item.delete()
    messages.info(request, f"{product_name} removed from wishlist.")
    return redirect(request.META.get("HTTP_REFERER", "wishlist_page"))


@login_required
def wishlist_move_to_cart(request, wid):
    item = get_object_or_404(Wishlist.objects.select_related("product"), id=wid, user=request.user)
    product_name = item.product.name
    _, status = _add_product_to_cart(request.user, item.product)
    if status == "out_of_stock":
        messages.error(request, f"{product_name} is out of stock.")
        return redirect("wishlist_page")
    if status == "max_stock":
        messages.info(request, f"Your cart already has the available stock for {product_name}.")
    else:
        messages.success(request, f"Moved {product_name} to your cart.")
    item.delete()
    return redirect("wishlist_page")


@login_required
def toggle_wishlist(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    wishlist_entry, created = Wishlist.objects.get_or_create(user=request.user, product=product)
    if created:
        messages.success(request, f"{product.name} added to wishlist!")
    else:
        wishlist_entry.delete()
        messages.info(request, f"{product.name} removed from wishlist.")
    return redirect(request.META.get("HTTP_REFERER", "index"))


@login_required
def rate_product(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    rating_obj = ProductRating.objects.filter(product=product, user=request.user).first()

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

    return render(request, "shop/rate_product.html", {"product": product, "form": form})


@login_required
def wishlist(request):
    return wishlist_page(request)


@login_required
@require_POST
def apply_promo(request):
    code_text = request.POST.get("code", "").strip()
    cart = _get_user_cart(request.user)
    if not cart:
        return JsonResponse({"success": False, "message": "Your cart is empty."})

    promo = PromoCode.objects.filter(code__iexact=code_text, is_active=True).prefetch_related("products").first()
    if not promo:
        return JsonResponse({"success": False, "message": "Invalid promo code"})
    if not promo.is_valid():
        return JsonResponse({"success": False, "message": "Code is expired or inactive"})

    discount, found_applicable_product = _calculate_discount(cart, promo)
    if not found_applicable_product:
        return JsonResponse({"success": False, "message": "This code does not apply to items in your cart."})

    subtotal = cart.total_price()
    return JsonResponse(
        {
            "success": True,
            "subtotal": float(subtotal),
            "discount_amount": float(discount),
            "new_total": float(max(Decimal("0.00"), subtotal - discount)),
        }
    )


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
            return redirect(reverse("vendor_dashboard") + "#promotions")
    else:
        form = PromoCodeForm(vendor=vendor)
    return render(request, "shop/vendor_promo_form.html", {"form": form})


@login_required
def edit_promo(request, promo_id):
    vendor = request.user.vendor
    promo = get_object_or_404(PromoCode, id=promo_id, vendor=vendor)
    if request.method == "POST":
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
    cart = _get_user_cart(request.user)

    if not cart or not cart.items.exists():
        messages.error(request, "Cart is empty.")
        return redirect("index")

    subtotal = cart.total_price()
    discount = Decimal("0.00")
    final_amount = subtotal
    promo_obj = None

    if request.method == "POST":
        form = CheckoutForm(request.POST)
        payment_form = PaymentForm(request.POST)

        promo_code_str = request.POST.get("promo_code", "").strip()

        if form.is_valid() and payment_form.is_valid():

            # ---------------------------------------------------------
            # PROMO CODE
            # ---------------------------------------------------------

            if promo_code_str:
                promo_obj = (
                    PromoCode.objects
                    .filter(
                        code__iexact=promo_code_str,
                        is_active=True,
                    )
                    .prefetch_related("products")
                    .first()
                )

                if promo_obj and promo_obj.is_valid():
                    discount, found = _calculate_discount(
                        cart,
                        promo_obj,
                    )

                    if not found:
                        discount = Decimal("0.00")
                        promo_obj = None

            # ---------------------------------------------------------
            # FINAL AMOUNT
            # ---------------------------------------------------------

            final_amount = max(
                Decimal("0.00"),
                subtotal - discount,
            )

            # ---------------------------------------------------------
            # CREATE ORDER
            # ---------------------------------------------------------

            order = form.save(commit=False)

            order.user = request.user
            order.total_amount = final_amount
            order.payment_status = "pending"

            order.save()

            # Your internal reference.
            #
            # This is NOT the Safaricom MerchantRequestID or
            # CheckoutRequestID.
            ref = f"order-{order.id}-{uuid.uuid4().hex[:6]}"

            order.payment_ref = ref
            order.save(update_fields=["payment_ref"])

            # ---------------------------------------------------------
            # CREATE SALES
            # ---------------------------------------------------------

            sales = [
                Sale(
                    order=order,
                    product=item.product,
                    customer=request.user,
                    vendor=item.product.vendor.user,
                    quantity=item.quantity,
                    total_price=item.total_price(),
                    status="pending",
                )
                for item in cart.items.all()
            ]

            Sale.objects.bulk_create(sales)

            # ---------------------------------------------------------
            # INITIATE STK PUSH
            # ---------------------------------------------------------

            success, resp = initiate_stk_push(
                amount=int(final_amount),
                contact=payment_form.cleaned_data["mpesa_phone"],
                ref=ref,
            )

            if success:

                # -----------------------------------------------------
                # SAVE SAFARICOM REQUEST IDs
                # -----------------------------------------------------

                merchant_request_id = resp.get("MerchantRequestID")
                checkout_request_id = resp.get("CheckoutRequestID")

                if not merchant_request_id or not checkout_request_id:
                    messages.error(
                        request,
                        "Payment request was accepted but no M-Pesa "
                        "request reference was returned.",
                    )

                    order.payment_status = "failed"
                    order.save(update_fields=["payment_status"])

                    return redirect("checkout")

                order.merchant_request_id = merchant_request_id
                order.checkout_request_id = checkout_request_id

                # Save the phone number used for the payment as well.
                order.mpesa_phone = str(
                    payment_form.cleaned_data["mpesa_phone"]
                )

                order.save(
                    update_fields=[
                        "merchant_request_id",
                        "checkout_request_id",
                        "mpesa_phone",
                    ]
                )

                # -----------------------------------------------------
                # PROMO USAGE
                # -----------------------------------------------------

                if promo_obj:
                    PromoCode.objects.filter(
                        pk=promo_obj.pk
                    ).update(
                        used_count=F("used_count") + 1
                    )

                # -----------------------------------------------------
                # EMAIL
                # -----------------------------------------------------

                send_checkout_emails(
                    order,
                    final_amount,
                    ref,
                )

                # -----------------------------------------------------
                # SESSION
                # -----------------------------------------------------

                request.session["checkout_ref"] = ref
                request.session["checkout_order_id"] = order.id

                return redirect("checkout_success")

            # ---------------------------------------------------------
            # STK PUSH REQUEST ITSELF FAILED
            # ---------------------------------------------------------

            messages.error(
                request,
                f"Payment failed: {resp}",
            )

            return redirect("checkout")

    else:
        form = CheckoutForm(
            initial={
                "email": request.user.email,
            }
        )

        payment_form = PaymentForm()

    return render(
        request,
        "shop/checkout.html",
        {
            "form": form,
            "payment_form": payment_form,
            "cart": cart,
            "items": cart.items.all(),
            "subtotal": subtotal,
            "discount": discount,
            "cart_total": final_amount,
        },
    )


@login_required
def checkout_success(request):
    ref = request.session.get("checkout_ref")
    order_id = request.session.get("checkout_order_id")

    order = (
        CheckoutOrder.objects.filter(id=order_id).first()
        if order_id
        else None
    )

    return render(
        request,
        "shop/checkout_success.html",
        {
            "ref": ref,
            "order": order,
        },
    )


def initiate_stk_push(amount, contact, ref):
    """
    Send the STK Push request to your M-Pesa middleware/API.

    Expected successful response:

    {
        "MerchantRequestID": "...",
        "CheckoutRequestID": "...",
        "ResponseCode": "0",
        "ResponseDescription": "...",
        "CustomerMessage": "..."
    }
    """

    url = getattr(settings, "MPESA_ENDPOINT")

    payload = {
        "amount": int(amount),
        "contact": str(contact),
        "ref": str(ref),
    }

    try:
        response = requests.post(
            url,
            json=payload,
            timeout=15,
        )

        response.raise_for_status()

        if response.headers.get(
            "content-type",
            ""
        ).startswith("application/json"):

            data = response.json()

            # M-Pesa STK Push accepted the request.
            if str(data.get("ResponseCode")) == "0":
                return True, data

            return False, data

        return True, response.text

    except requests.RequestException as exc:
        return False, str(exc)


@csrf_exempt
def payment_callback(request):
    """
    Safaricom STK callback endpoint.

    Expected callback:

    {
        "Body": {
            "stkCallback": {
                "MerchantRequestID": "...",
                "CheckoutRequestID": "...",
                "ResultCode": 0,
                "ResultDesc": "...",
                "CallbackMetadata": {
                    "Item": [...]
                }
            }
        }
    }
    """

    if request.method != "POST":
        return JsonResponse(
            {"detail": "Method not allowed"},
            status=405,
        )

    # -------------------------------------------------------------
    # PARSE JSON
    # -------------------------------------------------------------

    try:
        data = json.loads(request.body)

    except (json.JSONDecodeError, TypeError):
        return JsonResponse(
            {"detail": "Invalid callback payload"},
            status=400,
        )

    # -------------------------------------------------------------
    # GET STK CALLBACK
    # -------------------------------------------------------------

    callback = (
        data.get("Body", {})
        .get("stkCallback")
    )

    if not callback:
        return JsonResponse(
            {"detail": "Invalid callback structure"},
            status=400,
        )

    # -------------------------------------------------------------
    # REQUEST IDENTIFIERS
    # -------------------------------------------------------------

    merchant_request_id = callback.get(
        "MerchantRequestID"
    )

    checkout_request_id = callback.get(
        "CheckoutRequestID"
    )

    if not merchant_request_id and not checkout_request_id:
        return JsonResponse(
            {"detail": "M-Pesa request reference missing"},
            status=400,
        )

    # -------------------------------------------------------------
    # RESULT
    # -------------------------------------------------------------

    result_code = callback.get("ResultCode")

    try:
        result_code = int(result_code)
    except (TypeError, ValueError):
        return JsonResponse(
            {"detail": "Invalid ResultCode"},
            status=400,
        )

    result_desc = callback.get(
        "ResultDesc",
        "",
    )

    # -------------------------------------------------------------
    # FIND ORDER
    #
    # IMPORTANT:
    # We now search using the IDs returned by M-Pesa rather than
    # assuming MerchantRequestID == our payment_ref.
    # -------------------------------------------------------------

    order = None

    if checkout_request_id:
        order = (
            CheckoutOrder.objects
            .filter(
                checkout_request_id=checkout_request_id
            )
            .first()
        )

    if not order and merchant_request_id:
        order = (
            CheckoutOrder.objects
            .filter(
                merchant_request_id=merchant_request_id
            )
            .first()
        )

    if not order:
        return JsonResponse(
            {
                "detail": "Order not found",
                "MerchantRequestID": merchant_request_id,
                "CheckoutRequestID": checkout_request_id,
            },
            status=404,
        )

    # -------------------------------------------------------------
    # PROCESS ORDER ATOMICALLY
    # -------------------------------------------------------------

    with transaction.atomic():

        # Lock the order to prevent duplicate callbacks from
        # processing the same payment simultaneously.
        order = (
            CheckoutOrder.objects
            .select_for_update()
            .get(pk=order.pk)
        )

        # ---------------------------------------------------------
        # ALREADY PROCESSED
        #
        # This is important because M-Pesa callbacks should be
        # treated as potentially repeatable.
        # ---------------------------------------------------------

        if order.payment_status == "paid":
            return JsonResponse(
                {
                    "detail": "Payment already processed",
                },
                status=200,
            )

        # ---------------------------------------------------------
        # PAYMENT FAILED / CANCELLED
        #
        # Example:
        # ResultCode = 1032
        # ResultDesc = "Request Cancelled by user."
        # ---------------------------------------------------------

        if result_code != 0:

            order.payment_status = "failed"

            order.save(
                update_fields=[
                    "payment_status",
                ]
            )

            return JsonResponse(
                {
                    "detail": "Payment failed",
                    "ResultCode": result_code,
                    "ResultDesc": result_desc,
                },
                status=200,
            )

        # ---------------------------------------------------------
        # SUCCESS CALLBACK
        # ---------------------------------------------------------

        metadata = (
            callback
            .get("CallbackMetadata", {})
            .get("Item", [])
        )

        meta = {}

        for item in metadata:
            name = item.get("Name")

            if name:
                meta[name] = item.get("Value")

        # ---------------------------------------------------------
        # EXTRACT PAYMENT DETAILS
        # ---------------------------------------------------------

        mpesa_receipt = meta.get(
            "MpesaReceiptNumber"
        )

        mpesa_amount = meta.get(
            "Amount"
        )

        mpesa_phone = meta.get(
            "PhoneNumber"
        )

        transaction_date_raw = meta.get(
            "TransactionDate"
        )

        # ---------------------------------------------------------
        # TRANSACTION DATE
        #
        # M-Pesa sends:
        #
        # 20260819121149
        #
        # Format:
        # YYYYMMDDHHMMSS
        # ---------------------------------------------------------

        transaction_date = None

        if transaction_date_raw:

            try:
                from datetime import datetime

                transaction_date = datetime.strptime(
                    str(transaction_date_raw),
                    "%Y%m%d%H%M%S",
                )

            except (ValueError, TypeError):
                transaction_date = None

        # ---------------------------------------------------------
        # UPDATE ORDER
        # ---------------------------------------------------------

        order.payment_status = "paid"

        if mpesa_receipt:
            order.mpesa_receipt = str(
                mpesa_receipt
            )

        if mpesa_amount is not None:
            order.mpesa_amount = Decimal(
                str(mpesa_amount)
            )

        if mpesa_phone:
            order.mpesa_phone = str(
                mpesa_phone
            )

        if transaction_date:
            order.mpesa_transaction_date = transaction_date

        order.save(
            update_fields=[
                "payment_status",
                "mpesa_receipt",
                "mpesa_amount",
                "mpesa_phone",
                "mpesa_transaction_date",
            ]
        )

        # ---------------------------------------------------------
        # UPDATE SALES
        # ---------------------------------------------------------

        sales = order.sales.select_related(
            "product"
        )

        sales.update(
            status="paid"
        )

        # ---------------------------------------------------------
        # REDUCE STOCK
        # ---------------------------------------------------------

        for sale in sales:

            Product.objects.filter(
                pk=sale.product_id
            ).update(
                stock=F("stock") - sale.quantity
            )

        # ---------------------------------------------------------
        # CLEAR CART
        # ---------------------------------------------------------

        CartItem.objects.filter(
            cart__user=order.user
        ).delete()

    # -------------------------------------------------------------
    # RETURN SUCCESS TO M-PESA
    # -------------------------------------------------------------

    return JsonResponse(
        {
            "detail": "Payment processed",
            "MpesaReceiptNumber": mpesa_receipt,
            "CheckoutRequestID": checkout_request_id,
        },
        status=200,
    )


@login_required
def check_payment_status(request):
    """
    Used by checkout_success.html to poll the order status.
    """

    order_id = request.session.get(
        "checkout_order_id"
    )

    order = (
        CheckoutOrder.objects.filter(
            id=order_id
        ).first()
        if order_id
        else None
    )

    if not order:
        return JsonResponse(
            {"status": "unknown"}
        )

    return JsonResponse(
        {
            "status": order.payment_status,
            "receipt": order.mpesa_receipt,
        }
    )


def send_checkout_emails(order, cart_total, ref):
    html_user = render_to_string(
        "emails/checkout_user_email.html",
        {
            "order": order,
            "cart_total": cart_total,
            "ref": ref,
        },
    )

    send_mail(
        subject="Your PowerPay order",
        message="Your order has been received.",
        from_email=None,
        recipient_list=[order.email],
        html_message=html_user,
    )
