from django.db import models
from accounts.models import Vendor, User
from django.conf import settings
from multiselectfield import MultiSelectField
from django.core.validators import MaxValueValidator

class Product(models.Model):
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name="products")
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock = models.IntegerField(default=0)
    image = models.ImageField(upload_to='product_images/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def average_rating(self):
        ratings = self.ratings.all()
        if not ratings:
            return 0
        return round(sum(r.rating for r in ratings) / ratings.count(), 1)

    def rating_count(self):
        return self.ratings.count()

    def __str__(self):
        return self.name

class ProductRating(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="ratings")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    rating = models.PositiveSmallIntegerField(validators=[MaxValueValidator(5)],default=5)  # 1–5 stars
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("product", "user")  # user can rate once

    def __str__(self):
        return f"{self.product.name} - {self.rating} stars"

class Wishlist(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'product')


class Sale(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('shipped', 'Shipped'),
        ('completed', 'Completed'),
    ]

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='sales')
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='purchases')
    vendor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='sales')
    quantity = models.PositiveIntegerField(default=1)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')

    def __str__(self):
        return f"{self.quantity} x {self.product.name} for {self.customer.username} [{self.status}]"

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
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    payment_ref = models.CharField(max_length=200, blank=True, null=True)
    # Basic info
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField()
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
    city = models.CharField(max_length=100)
    village = models.CharField(max_length=100, blank=True, null=True)
    address_detail = models.CharField(max_length=255, blank=True, null=True)


    def __str__(self):
        return f"{self.first_name} {self.last_name} - {self.buying_method}"