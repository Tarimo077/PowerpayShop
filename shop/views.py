from decimal import Decimal, InvalidOperation
import json
import uuid

import requests
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.core.files.base import ContentFile
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Avg, Count, F, Prefetch, Q, Sum
from django.db.models.functions import TruncMonth
from django.http import JsonResponse, HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_POST

from accounts.models import Vendor
from notifications.utils import notify
from .forms import CheckoutForm, GalleryForm, PaymentForm, ProductForm, PromoCodeForm, RatingForm, WarrantyRegistrationForm
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
from .warranty import build_warranty_pdf


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
    public_promos = PromoCode.objects.filter(visibility="public").prefetch_related("products")
    return (
        Product.objects.select_related("vendor", "vendor__user")
        .prefetch_related(
            "gallery",
            "ratings",
            Prefetch("promo_codes", queryset=public_promos, to_attr="prefetched_public_promos"),
            Prefetch("vendor__promo_codes", queryset=public_promos, to_attr="prefetched_public_promos"),
        )
        .annotate(avg_rating=Avg("ratings__rating"), rating_total=Count("ratings"))
        .order_by("-created_at")
    )


def _wishlist_product_ids(user):
    if not user.is_authenticated:
        return []
    return list(Wishlist.objects.filter(user=user).values_list("product_id", flat=True))


def _get_user_cart(user):
    public_promos = PromoCode.objects.filter(visibility="public").prefetch_related("products")
    return (
        Cart.objects.filter(user=user)
        .prefetch_related(
            Prefetch(
                "items",
                queryset=CartItem.objects.select_related(
                    "product", "product__vendor", "product__vendor__user"
                ).prefetch_related(
                    Prefetch("product__promo_codes", queryset=public_promos, to_attr="prefetched_public_promos"),
                    Prefetch("product__vendor__promo_codes", queryset=public_promos, to_attr="prefetched_public_promos"),
                ),
            )
        )
        .first()
    )


def _calculate_discount(cart, promo):
    manual_is_valid = bool(promo and promo.is_valid())
    allowed_product_ids = set(promo.products.values_list("id", flat=True)) if manual_is_valid else set()
    applies_store_wide = manual_is_valid and not allowed_product_ids
    discount = Decimal("0.00")
    found_applicable_product = False
    promo_discounts = {}

    for item in cart.items.all():
        applied_promo = None
        if manual_is_valid and (applies_store_wide or item.product_id in allowed_product_ids):
            found_applicable_product = True
            applied_promo = promo
        else:
            applied_promo = item.product.best_public_promo()

        if applied_promo:
            item_discount = applied_promo.discount_for(item.product.price) * item.quantity
            discount += item_discount
            promo_discounts[applied_promo.pk] = (
                applied_promo,
                promo_discounts.get(applied_promo.pk, (None, Decimal("0.00")))[1] + item_discount,
            )

    applied_promos = []
    for applied_promo, promo_discount in promo_discounts.values():
        applied_promo.cart_discount = promo_discount
        applied_promos.append(applied_promo)
    return discount, found_applicable_product, applied_promos


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
    vendor_products = _base_product_queryset().filter(vendor=vendor_instance)
    products = vendor_products
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

    sales = Sale.objects.filter(product__vendor=vendor_instance).select_related("product", "customer", "order")
    confirmed_sales = sales.filter(status__in=("paid", "shipped", "completed"))
    stats = confirmed_sales.aggregate(
        total_sales=Sum("quantity"),
        total_orders=Count("id"),
        total_revenue=Sum("total_price"),
    )
    total_revenue = stats["total_revenue"] or Decimal("0")
    total_orders = stats["total_orders"] or 0

    today = timezone.localdate()
    month_starts = []
    for offset in range(5, -1, -1):
        month_index = today.year * 12 + today.month - 1 - offset
        month_starts.append(today.replace(year=month_index // 12, month=month_index % 12 + 1, day=1))
    monthly_rows = {
        row["month"].date(): row
        for row in confirmed_sales.filter(created_at__date__gte=month_starts[0])
        .annotate(month=TruncMonth("created_at"))
        .values("month")
        .annotate(revenue=Sum("total_price"), units=Sum("quantity"))
        .order_by("month")
    }
    revenue_chart = [
        {
            "label": month.strftime("%b"),
            "revenue": float(monthly_rows.get(month, {}).get("revenue") or 0),
            "units": monthly_rows.get(month, {}).get("units") or 0,
        }
        for month in month_starts
    ]

    status_counts = {choice: 0 for choice, _ in Sale.STATUS_CHOICES}
    status_counts.update(dict(sales.values_list("status").annotate(total=Count("id"))))
    status_chart = [
        {"label": label, "value": status_counts[value], "key": value}
        for value, label in Sale.STATUS_CHOICES
    ]
    top_products = list(
        confirmed_sales.values("product__name")
        .annotate(units=Sum("quantity"), revenue=Sum("total_price"))
        .order_by("-units", "-revenue")[:5]
    )
    product_metrics = vendor_products.aggregate(
        product_count=Count("id", distinct=True),
        low_stock_count=Count("id", filter=Q(stock__lte=5), distinct=True),
        wishlist_count=Count("wishlist", distinct=True),
    )
    average_rating = ProductRating.objects.filter(product__vendor=vendor_instance).aggregate(value=Avg("rating"))["value"] or 0
    low_stock_products = vendor_products.filter(stock__lte=5).order_by("stock", "name")[:5]
    active_promos = sum(1 for promo in promo_codes if promo.is_valid())
    promo_uses = sum(promo.used_count for promo in promo_codes)
    recent_sales = sales.order_by("-created_at")[:6]
    per_page = _safe_per_page(request, allowed=(5, 10, 15), default=10)
    page_obj = Paginator(products, per_page).get_page(request.GET.get("page"))

    return render(
        request,
        "shop/vendor_dashboard.html",
        {
            "products": page_obj,
            "promo_codes": promo_codes,
            "product_count": product_metrics["product_count"] or 0,
            "total_sales": stats["total_sales"] or 0,
            "total_orders": total_orders,
            "total_revenue": total_revenue,
            "average_order_value": total_revenue / total_orders if total_orders else 0,
            "average_rating": average_rating,
            "wishlist_count": product_metrics["wishlist_count"] or 0,
            "low_stock_count": product_metrics["low_stock_count"] or 0,
            "low_stock_products": low_stock_products,
            "active_promos": active_promos,
            "promo_uses": promo_uses,
            "recent_sales": recent_sales,
            "revenue_chart": revenue_chart,
            "status_chart": status_chart,
            "top_products": top_products,
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
    discount, _, applied_promos = _calculate_discount(cart, None)
    subtotal = cart.total_price()
    return render(request, "shop/cart.html", {
        "cart": cart,
        "discount": discount,
        "applied_promos": applied_promos,
        "cart_total": max(Decimal("0.00"), subtotal - discount),
    })


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
    promo = None
    applied_promos = []
    if promo_code and cart:
        promo = PromoCode.objects.filter(
            code__iexact=promo_code, is_active=True, visibility="private"
        ).prefetch_related("products").first()
    if cart:
        discount, _, applied_promos = _calculate_discount(cart, promo)

    return JsonResponse(
        {
            "item_total": float(item.total_price()),
            "cart_total": float(subtotal),
            "discount_amount": float(discount),
            "new_total": float(max(Decimal("0.00"), subtotal - discount)),
            "applied_promos": [
                {"code": applied.code, "auto": not promo or applied.pk != promo.pk, "discount": float(applied.cart_discount)}
                for applied in applied_promos
            ],
        }
    )


@login_required
def wishlist_page(request):
    items = Wishlist.objects.filter(user=request.user).select_related("product", "product__vendor", "product__vendor__user")
    products = list(_base_product_queryset().filter(pk__in=items.values("product_id")))
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

    promo = PromoCode.objects.filter(
        code__iexact=code_text, is_active=True, visibility="private"
    ).prefetch_related("products").first()
    if not promo:
        return JsonResponse({"success": False, "message": "Invalid promo code"})
    if not promo.is_valid():
        return JsonResponse({"success": False, "message": "Code is expired or inactive"})

    discount, found_applicable_product, applied_promos = _calculate_discount(cart, promo)
    if not found_applicable_product:
        return JsonResponse({"success": False, "message": "This code does not apply to items in your cart."})

    subtotal = cart.total_price()
    return JsonResponse(
        {
            "success": True,
            "subtotal": float(subtotal),
            "discount_amount": float(discount),
            "new_total": float(max(Decimal("0.00"), subtotal - discount)),
            "applied_promos": [
                {"code": item.code, "auto": item.pk != promo.pk, "discount": float(item.cart_discount)}
                for item in applied_promos
            ],
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
    applied_promos = []

    discount, _, applied_promos = _calculate_discount(cart, None)
    final_amount = max(Decimal("0.00"), subtotal - discount)

    if request.method == "POST":
        form = CheckoutForm(request.POST)
        payment_form = PaymentForm(request.POST)
        promo_code_str = request.POST.get("promo_code", "").strip()

        if form.is_valid() and payment_form.is_valid():
            if promo_code_str:
                promo_obj = PromoCode.objects.filter(
                    code__iexact=promo_code_str, is_active=True, visibility="private"
                ).prefetch_related("products").first()
                if promo_obj and promo_obj.is_valid():
                    discount, found, applied_promos = _calculate_discount(cart, promo_obj)
                    if not found:
                        promo_obj = None
                        discount, _, applied_promos = _calculate_discount(cart, None)

            final_amount = max(Decimal("0.00"), subtotal - discount)

            order = form.save(commit=False)
            order.user = request.user
            order.total_amount = final_amount
            order.payment_status = "pending"
            order.save()

            ref = f"order-{order.id}-{uuid.uuid4().hex[:6]}"
            order.payment_ref = ref
            order.save(update_fields=["payment_ref"])

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

            success, resp = initiate_stk_push(request, amount=int(final_amount), contact=payment_form.cleaned_data["mpesa_phone"], ref=ref)

            if success:
                if applied_promos:
                    PromoCode.objects.filter(pk__in={promo.pk for promo in applied_promos}).update(used_count=F("used_count") + 1)
                send_checkout_emails(order, final_amount, ref)
                request.session["checkout_ref"] = ref
                request.session["checkout_order_id"] = order.id
                return redirect("checkout_success")

            messages.error(request, f"Payment failed: {resp}")
            return redirect("checkout")
    else:
        form = CheckoutForm(initial={
            "first_name": request.user.first_name,
            "last_name": request.user.last_name,
            "email": request.user.email,
            "phone": request.user.phone,
        })
        payment_form = PaymentForm()

    return render(
        request,
        "shop/checkout.html",
        {"form": form, "payment_form": payment_form, "cart": cart, "items": cart.items.all(), "subtotal": subtotal, "discount": discount, "cart_total": final_amount, "applied_promos": applied_promos},
    )


@login_required
def checkout_success(request):
    ref = request.session.get("checkout_ref")
    order_id = request.session.get("checkout_order_id")
    order = CheckoutOrder.objects.prefetch_related("sales__product").filter(id=order_id, user=request.user).first() if order_id else None
    return render(request, "shop/checkout_success.html", {"ref": ref, "order": order})


def initiate_stk_push(request, amount, contact, ref):
    url = getattr(settings, "MPESA_ENDPOINT")
    payload = {"amount": int(amount), "contact": str(contact), "ref": str(ref), "callback": request.build_absolute_uri(reverse("payment_callback"))}
    try:
        response = requests.post(url, json=payload, timeout=15)
        response.raise_for_status()
        if response.headers.get("content-type", "").startswith("application/json"):
            return True, response.json()
        return True, response.text
    except requests.RequestException as exc:
        return False, str(exc)


@csrf_exempt
def payment_callback(request):
    if request.method != "POST":
        return JsonResponse({"detail": "Method not allowed"}, status=405)

    try:
        data = json.loads(request.body)
        callback = data["Body"]["stkCallback"]
    except (json.JSONDecodeError, KeyError, TypeError):
        return JsonResponse({"detail": "Invalid callback payload"}, status=400)

    result_code = callback.get("ResultCode")
    merchant_request_id = callback.get("MerchantRequestID") or callback.get("CheckoutRequestID")
    if not merchant_request_id:
        return JsonResponse({"detail": "Reference missing"}, status=400)

    try:
        with transaction.atomic():
            order = CheckoutOrder.objects.select_for_update().get(payment_ref=merchant_request_id)
            if result_code != 0:
                order.payment_status = "failed"
                order.save(update_fields=["payment_status"])
                return JsonResponse({"detail": "Payment failed"}, status=200)

            if order.payment_status == "paid":
                return JsonResponse({"detail": "Payment already processed"}, status=200)

            metadata = callback.get("CallbackMetadata", {}).get("Item", [])
            meta = {item.get("Name"): item.get("Value") for item in metadata if item.get("Name")}
            order.payment_status = "paid"
            order.mpesa_receipt = meta.get("MpesaReceiptNumber")
            order.save(update_fields=["payment_status", "mpesa_receipt"])

            sales = order.sales.select_related("product")
            sales.update(status="paid")
            for sale in sales:
                Product.objects.filter(pk=sale.product_id).update(stock=F("stock") - sale.quantity)

            vendor_sales = {}
            for sale in sales:
                vendor_sales.setdefault(sale.vendor, []).append(sale)
            for vendor_user, items in vendor_sales.items():
                item_summary = ", ".join(f"{item.quantity} × {item.product.name}" for item in items)
                vendor_total = sum((item.total_price for item in items), Decimal("0.00"))
                notify(
                    vendor_user,
                    "New paid order",
                    f"Payment confirmed for {item_summary}. Order value: Ksh. {vendor_total:,.2f}.",
                    "success",
                )
            if order.user:
                notify(
                    order.user,
                    "Payment confirmed",
                    f"Your order {order.payment_ref} has been paid and is being prepared by the vendor.",
                    "success",
                )

            CartItem.objects.filter(cart__user=order.user).delete()
    except CheckoutOrder.DoesNotExist:
        return JsonResponse({"detail": "Order not found"}, status=404)

    return JsonResponse({"detail": "Payment processed"}, status=200)


@login_required
def check_payment_status(request):
    order_id = request.session.get("checkout_order_id")
    order = CheckoutOrder.objects.filter(id=order_id).first() if order_id else None
    if not order:
        return JsonResponse({"status": "unknown"})
    return JsonResponse({"status": order.payment_status, "receipt": order.mpesa_receipt})


@login_required
def warranties(request):
    orders = (
        CheckoutOrder.objects.filter(user=request.user)
        .prefetch_related(
            Prefetch(
                "sales",
                queryset=Sale.objects.select_related("product", "product__vendor").order_by("id"),
            )
        )
        .order_by("-submitted_at")
    )
    for order in orders:
        order.warranty_editable = order.payment_status == "paid" and not any(
            sale.status in {"shipped", "completed"} for sale in order.sales.all()
        )

    customer_warranties = Sale.objects.none()
    if (
        request.user.is_vendor
        and request.user.is_vendor_approved
        and hasattr(request.user, "vendor")
        and not request.user.vendor.is_suspended
    ):
        customer_warranties = (
            Sale.objects.filter(
                product__vendor=request.user.vendor,
                order__payment_status="paid",
                order__warranty_selected=True,
                order__warranty_signature__isnull=False,
            )
            .exclude(order__warranty_signature="")
            .select_related("order", "customer", "product")
            .order_by("-order__warranty_accepted_at", "-created_at")
        )
    return render(
        request,
        "shop/warranties.html",
        {"orders": orders, "customer_warranties": customer_warranties},
    )


@login_required
def order_tracking(request):
    orders = (
        CheckoutOrder.objects.filter(user=request.user)
        .prefetch_related(
            Prefetch(
                "sales",
                queryset=Sale.objects.select_related("product", "product__vendor").order_by("id"),
            )
        )
        .order_by("-submitted_at")
    )
    return render(request, "shop/order_tracking.html", {"orders": orders})


@require_POST
@login_required
def update_sale_status(request, sale_id):
    user = request.user
    if not (user.is_vendor and user.is_vendor_approved and hasattr(user, "vendor") and not user.vendor.is_suspended):
        return HttpResponseForbidden("Only approved vendors can update order status.")

    sale = get_object_or_404(
        Sale.objects.select_related("customer", "product", "order"),
        pk=sale_id,
        product__vendor=user.vendor,
    )
    requested_status = request.POST.get("status", "")
    allowed_transition = {"paid": "shipped", "shipped": "completed"}.get(sale.status)
    if requested_status != allowed_transition:
        messages.error(request, "That order status change is not allowed.")
        return redirect(reverse("vendor_dashboard") + "#orders")

    update_fields = ["status"]
    if requested_status == "shipped":
        serial_number = request.POST.get("serial_number", "").strip()
        serial_confirmed = request.POST.get("confirm_serial") == "on"
        if not serial_number:
            messages.error(request, "Enter the product serial number before marking it shipped.")
            return redirect(reverse("vendor_dashboard") + "#orders")
        if len(serial_number) > 100:
            messages.error(request, "The serial number cannot exceed 100 characters.")
            return redirect(reverse("vendor_dashboard") + "#orders")
        if not serial_confirmed:
            messages.error(request, "Confirm that you checked the serial number before shipping.")
            return redirect(reverse("vendor_dashboard") + "#orders")
        sale.serial_number = serial_number
        update_fields.append("serial_number")

    sale.status = requested_status
    sale.save(update_fields=update_fields)
    status_label = sale.get_status_display()
    notify(
        sale.customer,
        f"Order {status_label.lower()}",
        f"{sale.product.name} is now {status_label.lower()}. "
        f"{'Your warranty certificate is ready to download. ' if requested_status == 'shipped' and sale.order and sale.order.warranty_selected else ''}"
        f"Reference: {sale.order.payment_ref if sale.order else sale.id}.",
        "success" if requested_status == "completed" else "info",
    )
    messages.success(request, f"{sale.product.name} marked {status_label.lower()}.")
    return redirect(reverse("vendor_dashboard") + "#orders")


@login_required
def register_warranty(request, order_id):
    order = get_object_or_404(
        CheckoutOrder.objects.prefetch_related("sales__product"),
        pk=order_id,
        user=request.user,
        payment_status="paid",
    )
    if not order.sales.exists():
        messages.error(request, "No purchased products were found for this order.")
        return redirect("warranties")
    is_editing = bool(order.warranty_selected and order.warranty_signature)
    if any(sale.status in {"shipped", "completed"} for sale in order.sales.all()):
        messages.error(request, "Warranty information cannot be changed after an item has shipped.")
        return redirect("warranties")

    if request.method == "POST":
        form = WarrantyRegistrationForm(request.POST, instance=order)
        if form.is_valid():
            order = form.save(commit=False)
            order.warranty_selected = True
            order.warranty_accepted_at = timezone.now()
            if form.cleaned_data.get("signature_bytes"):
                order.warranty_signature.save(
                    f"order-{order.pk}-signature.png",
                    ContentFile(form.cleaned_data["signature_bytes"]),
                    save=False,
                )
            order.save()
            messages.success(request, "Warranty information updated." if is_editing else "Warranty registered. Your certificates are ready to download.")
            return redirect("warranties")
    else:
        form = WarrantyRegistrationForm(instance=order)

    return render(request, "shop/warranty_form.html", {"form": form, "order": order, "is_editing": is_editing})


@login_required
def vendor_warranty_detail(request, sale_id):
    if not (
        request.user.is_vendor
        and request.user.is_vendor_approved
        and hasattr(request.user, "vendor")
        and not request.user.vendor.is_suspended
    ):
        return HttpResponseForbidden("Only approved vendors can view customer warranty details.")

    sale = get_object_or_404(
        Sale.objects.select_related("order", "customer", "product", "product__vendor"),
        pk=sale_id,
        product__vendor=request.user.vendor,
        order__payment_status="paid",
        order__warranty_selected=True,
    )
    order = sale.order

    def displayed(field_name):
        display = getattr(order, f"get_{field_name}_display", None)
        return display() if callable(display) else getattr(order, field_name, None)

    detail_sections = [
        ("Customer and purchase", [
            ("Customer", f"{order.first_name} {order.last_name}"),
            ("Phone", order.phone), ("Email", order.email),
            ("Product", sale.product.name), ("Quantity", sale.quantity),
            ("Serial number", sale.serial_number),
            ("Order reference", order.payment_ref), ("M-Pesa receipt", order.mpesa_receipt),
            ("Purchase date", order.submitted_at), ("Fulfilment", sale.get_status_display()),
        ]),
        ("Location and household", [
            ("Country", order.country), ("County / State", order.county), ("City / Town", order.city),
            ("Village", order.village), ("Street / address", order.address_detail),
            ("Gender", displayed("gender")), ("Age", order.age), ("National ID", order.national_id),
            ("Education", displayed("education")), ("Marital status", displayed("marital_status")),
            ("Employment", displayed("employment")), ("Economic activity", order.economic_activity),
            ("Monthly income", displayed("monthly_income")), ("Other loans", displayed("other_loans")),
            ("Home or business", displayed("home_or_business")),
        ]),
        ("Cooking and energy", [
            ("Cooking fuel", displayed("cooking_fuel")), ("Cooking stove", displayed("stove_type")),
            ("Appliance used for cooking", displayed("is_cook_user")),
            ("Monthly cooking cost", order.monthly_cooking_cost),
            ("Grid connection", displayed("grid_connection")), ("Utility provider", displayed("utility_provider")),
            ("Monthly electricity cost", order.monthly_electricity_cost),
        ]),
    ]
    return render(
        request,
        "shop/vendor_warranty_detail.html",
        {"sale": sale, "order": order, "detail_sections": detail_sections},
    )


@login_required
def download_warranty(request, sale_id):
    sale = get_object_or_404(
        Sale.objects.select_related("order", "product__vendor"),
        pk=sale_id,
    )
    is_customer = sale.customer_id == request.user.id and sale.order.user_id == request.user.id
    is_owning_vendor = bool(
        request.user.is_vendor
        and request.user.is_vendor_approved
        and hasattr(request.user, "vendor")
        and not request.user.vendor.is_suspended
        and sale.product.vendor_id == request.user.vendor.id
    )
    if not (is_customer or is_owning_vendor):
        return HttpResponseForbidden("You do not have access to this warranty certificate.")
    if sale.order.payment_status != "paid":
        return HttpResponseForbidden("The warranty becomes available after payment is confirmed.")
    if not sale.order.warranty_selected or not sale.order.warranty_signature:
        return HttpResponseForbidden("This order does not include a warranty certificate.")
    if sale.status not in {"shipped", "completed"} or not sale.serial_number:
        return HttpResponseForbidden("The warranty becomes available after the product is shipped and its serial number is confirmed.")

    pdf = build_warranty_pdf(sale)
    filename = f"warranty-{slugify(sale.product.name) or 'product'}-{sale.pk}.pdf"
    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response["X-Content-Type-Options"] = "nosniff"
    return response


def send_checkout_emails(order, cart_total, ref):
    html_user = render_to_string("emails/checkout_user_email.html", {"order": order, "cart_total": cart_total, "ref": ref})
    if order.email:
        send_mail(
            subject="Your Cook Yami order",
            message="Your order has been received.",
            from_email=None,
            recipient_list=[order.email],
            html_message=html_user,
        )
