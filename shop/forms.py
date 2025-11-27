from django import forms
from .models import Product, CheckoutOrder, ProductRating, ProductGallery

class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ['name', 'description', 'price', 'stock', 'image']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'input input-bordered w-full rounded-lg focus:ring focus:ring-green-200 focus:border-green-500',
                'placeholder': 'Product Name'
            }),
            'description': forms.Textarea(attrs={
                'class': 'textarea textarea-bordered w-full rounded-lg focus:ring focus:ring-green-200 focus:border-green-500',
                'rows': 3,
                'placeholder': 'Product Description'
            }),
            'price': forms.NumberInput(attrs={
                'class': 'input input-bordered w-full rounded-lg focus:ring focus:ring-green-200 focus:border-green-500',
                'placeholder': 'Price in Ksh'
            }),
            'stock': forms.NumberInput(attrs={
                'class': 'input input-bordered w-full rounded-lg focus:ring focus:ring-green-200 focus:border-green-500',
                'placeholder': 'Stock Quantity'
            }),
            'image': forms.ClearableFileInput(attrs={
                'class': 'file-input mt-2 w-full'
            }),
        }

class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            result = [single_file_clean(d, initial) for d in data]
        else:
            result = [single_file_clean(data, initial)]
        return result

class GalleryForm(forms.Form):
    images = MultipleFileField()


class CheckoutForm(forms.ModelForm):
    class Meta:
        model = CheckoutOrder
        fields = "__all__"
        #exclude = ("user",)
        widgets = {
            "first_name": forms.TextInput(attrs={"class": "input input-bordered rounded-lg w-full"}),
            "last_name": forms.TextInput(attrs={"class": "input input-bordered rounded-lg w-full"}),
            "email": forms.EmailInput(attrs={"class": "input input-bordered rounded-lg w-full"}),
            "phone": forms.TextInput(attrs={"class": "input input-bordered rounded-lg w-full"}),

            "country": forms.TextInput(attrs={"class": "input input-bordered rounded-lg w-full"}),
            "county": forms.TextInput(attrs={"class": "input input-bordered rounded-lg w-full"}),
            "city": forms.TextInput(attrs={"class": "input input-bordered rounded-lg w-full"}),
            "village": forms.TextInput(attrs={"class": "input input-bordered rounded-lg w-full"}),
            "address_detail": forms.TextInput(attrs={"class": "input input-bordered rounded-lg w-full"}),

            # Household Info
            "gender": forms.Select(attrs={"class": "input input-bordered rounded-lg w-full"}),
            "age": forms.NumberInput(attrs={"class": "input input-bordered rounded-lg w-full"}),
            "national_id": forms.NumberInput(attrs={"class": "input input-bordered rounded-lg w-full"}),
            "education": forms.Select(attrs={"class": "input input-bordered rounded-lg w-full"}),
            "marital_status": forms.Select(attrs={"class": "input input-bordered rounded-lg w-full"}),
            "employment": forms.Select(attrs={"class": "input input-bordered rounded-lg w-full"}),
            "economic_activity": forms.TextInput(attrs={"class": "input input-bordered rounded-lg w-full"}),
            "monthly_income": forms.Select(attrs={"class": "input input-bordered rounded-lg w-full"}),

            "buying_method": forms.Select(attrs={"class": "input input-bordered rounded-lg w-full"}),
            "other_loans": forms.Select(attrs={"class": "input input-bordered rounded-lg w-full"}),

            # Cooking / Energy
            "cooking_fuel": forms.CheckboxSelectMultiple(attrs={"class": "input input-bordered rounded-lg"}),
            "stove_type": forms.CheckboxSelectMultiple(attrs={"class": "input input-bordered rounded-lg"}),
            "is_cook_user": forms.Select(attrs={"class": "input input-bordered rounded-lg w-full"}),
            "grid_connection": forms.Select(attrs={"class": "input input-bordered rounded-lg w-full"}),
            "utility_provider": forms.Select(attrs={"class": "input input-bordered rounded-lg w-full"}),
            "monthly_electricity_cost": forms.NumberInput(attrs={"class": "input input-bordered rounded-lg w-full"}),

            # Loan-related fields
            "appliance_financed": forms.Select(attrs={"class": "input input-bordered rounded-lg w-full"}),
            "repayment_period": forms.NumberInput(attrs={"class": "input input-bordered rounded-lg w-full"}),
            "financier": forms.Select(attrs={"class": "input input-bordered rounded-lg w-full"}),

            # Home/Business usage
            "home_or_business": forms.Select(attrs={"class": "input input-bordered rounded-lg w-full"}),
        }


class PaymentForm(forms.Form):
    mpesa_phone = forms.CharField(
        label="Phone (Mpesa, start with 254...)",
        widget=forms.NumberInput(attrs={"class":"input input-bordered w-full","placeholder":"2547XXXXXXXX"})
    )

class RatingForm(forms.ModelForm):
    class Meta:
        model = ProductRating
        fields = ["rating"]
        widgets = {
            "rating": forms.NumberInput(attrs={
                "min": 1, "max": 5, "class": "input input-bordered w-24"
            })
        }
