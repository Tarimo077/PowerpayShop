from django.db import models
from accounts.models import Vendor, User
from django.conf import settings
from multiselectfield import MultiSelectField
from django.core.validators import MaxValueValidator
from decimal import Decimal
from django.utils import timezone

class Product(models.Model):
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name="products")
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock = models.IntegerField(default=0)
    image = models.ImageField(upload_to='product_images/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    max_stock = models.IntegerField(default=100)  # optional: set maximum stock

    class Meta:
        indexes = [
            models.Index(fields=["vendor", "-created_at"], name="shop_prod_vendor_created_idx"),
            models.Index(fields=["price"], name="shop_product_price_idx"),
        ]

    def average_rating(self):
        ratings = self.ratings.all()
        if not ratings:
            return 0
        return round(sum(r.rating for r in ratings) / ratings.count(), 1)

    def rating_count(self):
        return self.ratings.count()
    
    def stock_percentage(self):
        if self.max_stock == 0:
            return 0
        return round((self.stock / self.max_stock) * 100)

    def best_public_promo(self):
        product_promos = getattr(self, "prefetched_public_promos", None)
        if product_promos is None:
            product_promos = self.promo_codes.filter(visibility="public")

        vendor_promos = getattr(self.vendor, "prefetched_public_promos", None)
        if vendor_promos is None:
            vendor_promos = self.vendor.promo_codes.filter(visibility="public").prefetch_related("products")

        candidates = list(product_promos)
        for promo in vendor_promos:
            product_ids = {product.id for product in promo.products.all()}
            if not product_ids and promo not in candidates:
                candidates.append(promo)

        valid_promos = [promo for promo in candidates if promo.is_valid()]
        return max(valid_promos, key=lambda promo: promo.discount_for(self.price), default=None)

    def discounted_price(self):
        promo = self.best_public_promo()
        return self.price - promo.discount_for(self.price) if promo else self.price

    def discount_percentage(self):
        promo = self.best_public_promo()
        if not promo or not self.price:
            return 0
        return int((promo.discount_for(self.price) / self.price * Decimal("100")).quantize(Decimal("1")))

    def __str__(self):
        return self.name
    
class ProductGallery(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="gallery")
    image = models.ImageField(upload_to='product_gallery/')
    alt_text = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return f"{self.product.name} - {self.id}"

class ProductRating(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="ratings")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    rating = models.PositiveSmallIntegerField(validators=[MaxValueValidator(5)],default=5)  # 1–5 stars
    created_at = models.DateTimeField(auto_now_add=True)
    review = models.TextField(blank=True, null=True)

    class Meta:
        unique_together = ("product", "user")  # user can rate once

    def __str__(self):
        return f"{self.product.name} - {self.rating} stars"


class PromoCode(models.Model):
    DISCOUNT_TYPE_CHOICES = (
        ('percentage', 'Percentage'),
        ('fixed', 'Fixed Amount'),
    )
    VISIBILITY_CHOICES = (
        ('public', 'Public'),
        ('private', 'Private'),
    )

    vendor = models.ForeignKey(
        Vendor, 
        on_delete=models.CASCADE, 
        related_name='promo_codes'
    )

    code = models.CharField(max_length=20, unique=True)
    discount_type = models.CharField(max_length=10, choices=DISCOUNT_TYPE_CHOICES)
    discount_value = models.DecimalField(max_digits=10, decimal_places=2)
    visibility = models.CharField(max_length=7, choices=VISIBILITY_CHOICES, default='private')

    products = models.ManyToManyField(Product, blank=True, related_name='promo_codes')

    is_active = models.BooleanField(default=True)
    usage_limit = models.PositiveIntegerField(null=True, blank=True)
    used_count = models.PositiveIntegerField(default=0)

    valid_from = models.DateTimeField(default=timezone.now)
    valid_to = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(
                fields=["visibility", "is_active", "valid_to"],
                name="shop_promo_public_valid_idx",
            ),
        ]

    def is_valid(self):
        now = timezone.now()
        if not self.is_active:
            return False
        if self.valid_from and now < self.valid_from:
            return False
        if self.valid_to and now > self.valid_to:
            return False
        if self.usage_limit and self.used_count >= self.usage_limit:
            return False
        return True

    def discount_for(self, price):
        price = Decimal(price)
        if self.discount_type == "percentage":
            discount = price * self.discount_value / Decimal("100")
        else:
            discount = self.discount_value
        return min(price, max(Decimal("0.00"), discount))

    def __str__(self):
        return f"{self.code} ({self.vendor.shop_name})"


class Wishlist(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'product')


class Cart(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    def total_price(self):
        return sum(item.total_price() for item in self.items.all())

    def __str__(self):
        return f"Cart({self.user.username})"


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)

    def total_price(self):
        return self.product.price * self.quantity

    def __str__(self):
        return f"{self.quantity} x {self.product.name}"
    

class CheckoutOrder(models.Model):
    COOKING_FUEL_CHOICES = [
    ('charcoal', 'Charcoal'),
    ('firewood', 'Firewood'),
    ('lpg', 'LPG'),
    ('electricity', 'Electricity'),
    ('biogas', 'Biogas'),
    ('briquettes', 'Briquettes'),
    ('ethanol', 'Ethanol'),
    ('pellets', 'Pellets'),
    ('kerosene', 'Kerosene'),
    ('sawdust', 'Sawdust'),
    ('other', 'Other'),
    ]
    COOKING_STOVE_CHOICES = [
    ('traditional_charcoal', 'Traditional Charcoal'),
    ('improved_charcoal', 'Improved Charcoal'),
    ('traditional_firewood', 'Improved Firewood'),
    ('lpg', 'LPG'),
    ('electric', 'Electric'),
    ('bio_ethanol', 'Bio-ethanol'),
    ('other', 'Other'),
    ]

    PAYMENT_STATUS = [
        ("pending", "Pending"),
        ("paid", "Paid"),
        ("failed", "Failed"),
        ("cancelled", "Cancelled"),
    ]
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    payment_ref = models.CharField(max_length=200, blank=True, null=True)
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS, default="pending")
    mpesa_receipt = models.CharField(max_length=100, blank=True, null=True)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    # Basic info
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20)

    buying_method = models.CharField(max_length=20, choices=[('cash', 'Cash'), ('loan', 'Loan')])
    is_cook_user = models.CharField(max_length=10, blank=True, null=True, choices=[('yes', 'Yes'), ('no', 'No')])
    gender = models.CharField(max_length=10, blank=True, null=True, choices=[('male', 'Male'), ('female', 'Female'), ('other', 'Other')])
    age = models.IntegerField(blank=True, null=True)
    national_id = models.IntegerField(blank=True, null=True)

    education = models.CharField(max_length=30, blank=True, null=True, choices=[('primary', 'Primary'), ('secondary', 'Secondary'), ('tertiary', 'Tertiary')])
    marital_status = models.CharField(max_length=20, blank=True, null=True, choices=[('single', 'Single'),('married', 'Married')])
    employment = models.CharField(max_length=50, blank=True, null=True, choices=[('self_employed', 'Self Employed'), ('formal', 'Formal'), ('business_owner', 'Business Owner')])
    economic_activity = models.CharField(max_length=255, blank=True, null=True)

    monthly_income = models.CharField(max_length=200, blank=True, null=True, choices=[('below_30,000', 'Below Ksh 30,000'), ('30,000_50,000', 'Ksh 30,000 - Ksh 50,000'), ('50,000_100,000', 'Ksh 50,000 - Ksh 100,000'), ('above_100,000', 'Above Ksh 100,000') ])
    other_loans = models.CharField(max_length=10, blank=True, null=True, choices=[('yes', 'Yes'), ('no', 'No')])
    grid_connection = models.CharField(max_length=10, blank=True, null=True, choices=[('yes', 'Yes'), ('no', 'No')])

    cooking_fuel = MultiSelectField(
        choices=COOKING_FUEL_CHOICES,
        blank=True,
        null=True,
        verbose_name="Cooking Fuel Currently In Use"
    )

    stove_type = MultiSelectField(
        choices=COOKING_STOVE_CHOICES,
        blank=True,
        null=True,
        verbose_name="Cooking Stove Currently In Use"
    )

    monthly_cooking_cost = models.IntegerField(blank=True, null=True)
    home_or_business = models.CharField(blank=True, null=True, choices=[('home', 'Home'), ('business', 'Business')])
    appliance_financed = models.CharField(blank=True, null=True,  choices=[('electric_pressure_cooker', 'Electric Pressure cooker'), ('induction_cooker', 'Induction Cooker'), ('fridge', 'Fridge'), ('tv', 'TV'), ('electric_mill', 'Electric Mill'), ('air_conditioner', 'Air Conditioner')])
    repayment_period = models.IntegerField(blank=True, null=True, validators=[MaxValueValidator(12)])

    utility_provider = models.CharField(blank=True, null=True, choices=[('kenya_power', 'Kenya Power'), ('other', 'Other')])
    monthly_electricity_cost = models.IntegerField(blank=True, null=True)
    financier = models.CharField(blank=True, null=True, choices=[('powerpayafrica', 'Powerpay Africa'), ('cms', 'CMS')])

    country = models.CharField(max_length=100)
    county = models.CharField(max_length=100)
    city = models.CharField(max_length=100, blank=True)
    village = models.CharField(max_length=100, blank=True, null=True)
    address_detail = models.CharField(max_length=255, blank=True, null=True)

    warranty_selected = models.BooleanField(default=False)
    warranty_signature = models.ImageField(upload_to="warranty_signatures/%Y/%m/", blank=True, null=True)
    warranty_accepted_at = models.DateTimeField(blank=True, null=True)


    def __str__(self):
        return f"{self.first_name} {self.last_name} - {self.buying_method}"
    

class Sale(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('shipped', 'Shipped'),
        ('completed', 'Completed'),
    ]

    order = models.ForeignKey(CheckoutOrder, on_delete=models.CASCADE, related_name="sales", null=True, blank=True)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='sales')
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='purchases')
    vendor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='sales')
    quantity = models.PositiveIntegerField(default=1)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    serial_number = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return f"{self.quantity} x {self.product.name} for {self.customer.username} [{self.status}]"
