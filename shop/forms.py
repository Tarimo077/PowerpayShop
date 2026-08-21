import base64
import binascii
from io import BytesIO

from django import forms
from PIL import Image, UnidentifiedImageError
from .models import Product, PromoCode, CheckoutOrder, ProductRating, ProductGallery

class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ['name', 'description', 'price', 'stock', 'image']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'input h-10 border-2 border-black w-full rounded-lg focus:ring focus:ring-green-200 focus:border-green-500',
                'placeholder': '\tProduct Name'
            }),
            'description': forms.Textarea(attrs={
                'class': 'textarea h-18 border-2 border-black w-full rounded-lg focus:ring focus:ring-green-200 focus:border-green-500',
                'rows': 3,
                'placeholder': '\tProduct Description'
            }),
            'price': forms.NumberInput(attrs={
                'class': 'input h-10 border-2 border-black w-full rounded-lg focus:ring focus:ring-green-200 focus:border-green-500',
                'placeholder': '\tPrice in Ksh'
            }),
            'stock': forms.NumberInput(attrs={
                'class': 'input h-10 border-2 border-black w-full rounded-lg focus:ring focus:ring-green-200 focus:border-green-500',
                'placeholder': '\tStock Quantity'
            }),
            'image': forms.ClearableFileInput(attrs={
                'class': 'file-input mt-2 w-full'
            }),
        }

class PromoCodeForm(forms.ModelForm):
    class Meta:
        model = PromoCode
        fields = ["code", "discount_type", "discount_value", "visibility", "products", "valid_from", "valid_to", "usage_limit", "is_active"]
        
        widgets = {
            "code": forms.TextInput(attrs={'class': 'border-2 h-10 w-full rounded-lg border-black shadow-sm focus:border-green-500 focus:ring-green-500'}),
            "discount_type": forms.Select(attrs={'class': 'border-2 h-10 w-full rounded-lg border-black shadow-sm focus:border-green-500 focus:ring-green-500'}),
            "discount_value": forms.NumberInput(attrs={'class': 'border-2 h-10 w-full rounded-lg border-black shadow-sm focus:border-green-500 focus:ring-green-500'}),
            "visibility": forms.Select(attrs={'class': 'border-2 h-10 w-full rounded-lg border-black shadow-sm focus:border-green-500 focus:ring-green-500'}),
            "products": forms.CheckboxSelectMultiple(attrs={'class': 'rounded border-black ml-2 focus:ring-green-500'}),
            "valid_from": forms.DateTimeInput(attrs={"type": "datetime-local", 'class': 'border-2 h-10 w-full rounded-lg border-black shadow-sm focus:border-green-500 focus:ring-green-500'}),
            "valid_to": forms.DateTimeInput(attrs={"type": "datetime-local", 'class': 'border-2 h-10 w-full rounded-lg border-black shadow-sm focus:border-green-500 focus:ring-green-500'}),
            "usage_limit": forms.NumberInput(attrs={'class': 'border-2 h-10 w-full rounded-lg border-black shadow-sm focus:border-green-500 focus:ring-green-500'}),
            "is_active": forms.CheckboxInput(attrs={'class': 'border-2 h-10 rounded border-black text-green-600 focus:ring-green-500'}),
        }

    def __init__(self, *args, **kwargs):
        vendor = kwargs.pop('vendor', None)
        super(PromoCodeForm, self).__init__(*args, **kwargs)
        if vendor:
            self.fields['products'].queryset = self.fields['products'].queryset.filter(vendor=vendor)

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
    images = MultipleFileField(required=False)


CHECKOUT_FIELD_NAMES = [
    "first_name", "last_name", "email", "phone",
    "country", "county", "city", "village", "address_detail",
    "gender", "age", "national_id", "education", "marital_status",
    "employment", "economic_activity", "monthly_income", "buying_method",
    "other_loans", "cooking_fuel", "stove_type", "is_cook_user",
    "monthly_cooking_cost", "grid_connection", "utility_provider", "monthly_electricity_cost",
    "appliance_financed", "repayment_period", "financier", "home_or_business",
    "warranty_selected",
]

CHECKOUT_INPUT_CLASSES = (
    "block min-h-12 w-full rounded-[18px] border border-slate-300 "
    "bg-white px-4 py-3 text-sm font-semibold text-slate-900 shadow-sm outline-none "
    "transition placeholder:text-slate-400 focus:border-emerald-600 "
    "focus:ring-4 focus:ring-emerald-500/15"
)

CHECKOUT_SELECT_CLASSES = (
    "block min-h-12 w-full rounded-[18px] border border-slate-300 "
    "bg-white px-4 py-3 text-sm font-semibold text-slate-900 shadow-sm outline-none "
    "transition cursor-pointer focus:border-emerald-600 "
    "focus:ring-4 focus:ring-emerald-500/15"
)

CHECKOUT_CHECKBOX_CLASSES = (
    "h-5 w-5 shrink-0 rounded-md border-slate-300 text-emerald-600 "
    "cursor-pointer focus:ring-2 focus:ring-emerald-500 focus:ring-offset-2"
)


class CheckoutForm(forms.ModelForm):
    warranty_consent = forms.BooleanField(required=False)
    signature_data = forms.CharField(required=False, widget=forms.HiddenInput())

    class Meta:
        model = CheckoutOrder
        fields = CHECKOUT_FIELD_NAMES

        widgets = {
            "first_name": forms.TextInput(attrs={
                "class": CHECKOUT_INPUT_CLASSES,
                "placeholder": "First name"
            }),
            "last_name": forms.TextInput(attrs={
                "class": CHECKOUT_INPUT_CLASSES,
                "placeholder": "Last name"
            }),
            "email": forms.EmailInput(attrs={
                "class": CHECKOUT_INPUT_CLASSES,
                "placeholder": "email@example.com"
            }),
            "phone": forms.TextInput(attrs={
                "class": CHECKOUT_INPUT_CLASSES,
                "placeholder": "07XX XXX XXX"
            }),

            "warranty_selected": forms.CheckboxInput(attrs={
                "class": CHECKOUT_CHECKBOX_CLASSES,
            }),

            "country": forms.TextInput(attrs={
                "class": CHECKOUT_INPUT_CLASSES,
                "placeholder": "Country"
            }),
            "county": forms.TextInput(attrs={
                "class": CHECKOUT_INPUT_CLASSES,
                "placeholder": "County / State"
            }),
            "city": forms.TextInput(attrs={
                "class": CHECKOUT_INPUT_CLASSES,
                "placeholder": "City / Town"
            }),
            "village": forms.TextInput(attrs={
                "class": CHECKOUT_INPUT_CLASSES,
                "placeholder": "Village"
            }),
            "address_detail": forms.TextInput(attrs={
                "class": CHECKOUT_INPUT_CLASSES,
                "placeholder": "Street, estate, house number, landmark..."
            }),

            "gender": forms.Select(attrs={
                "class": CHECKOUT_SELECT_CLASSES
            }),
            "age": forms.NumberInput(attrs={
                "class": CHECKOUT_INPUT_CLASSES,
                "placeholder": "Age"
            }),
            "national_id": forms.NumberInput(attrs={
                "class": CHECKOUT_INPUT_CLASSES,
                "placeholder": "National ID"
            }),
            "education": forms.Select(attrs={
                "class": CHECKOUT_SELECT_CLASSES
            }),
            "marital_status": forms.Select(attrs={
                "class": CHECKOUT_SELECT_CLASSES
            }),
            "employment": forms.Select(attrs={
                "class": CHECKOUT_SELECT_CLASSES
            }),
            "economic_activity": forms.TextInput(attrs={
                "class": CHECKOUT_INPUT_CLASSES,
                "placeholder": "Economic activity"
            }),
            "monthly_income": forms.Select(attrs={
                "class": CHECKOUT_SELECT_CLASSES
            }),

            "buying_method": forms.Select(attrs={
                "class": CHECKOUT_SELECT_CLASSES
            }),
            "other_loans": forms.Select(attrs={
                "class": CHECKOUT_SELECT_CLASSES
            }),

            "cooking_fuel": forms.CheckboxSelectMultiple(attrs={
                "class": CHECKOUT_CHECKBOX_CLASSES
            }),
            "stove_type": forms.CheckboxSelectMultiple(attrs={
                "class": CHECKOUT_CHECKBOX_CLASSES
            }),

            "monthly_cooking_cost": forms.NumberInput(attrs={
                "class": CHECKOUT_INPUT_CLASSES,
                "placeholder": "Monthly cooking cost"
            }),

            "is_cook_user": forms.Select(attrs={
                "class": CHECKOUT_SELECT_CLASSES
            }),
            "grid_connection": forms.Select(attrs={
                "class": CHECKOUT_SELECT_CLASSES
            }),
            "utility_provider": forms.Select(attrs={
                "class": CHECKOUT_SELECT_CLASSES
            }),
            "monthly_electricity_cost": forms.NumberInput(attrs={
                "class": CHECKOUT_INPUT_CLASSES,
                "placeholder": "Monthly electricity cost"
            }),

            "appliance_financed": forms.Select(attrs={
                "class": CHECKOUT_SELECT_CLASSES
            }),
            "repayment_period": forms.NumberInput(attrs={
                "class": CHECKOUT_INPUT_CLASSES,
                "placeholder": "Repayment period in months"
            }),
            "financier": forms.Select(attrs={
                "class": CHECKOUT_SELECT_CLASSES
            }),

            "home_or_business": forms.Select(attrs={
                "class": CHECKOUT_SELECT_CLASSES
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].required = False
        self.fields["city"].required = False
        self.fields["buying_method"].choices = [
            ("", "Select buying method"),
            ("cash", "Cash"),
            ("loan", "Loan - coming soon"),
        ]
        self.fields["buying_method"].widget.attrs["data-disable-value"] = "loan"

    def clean_buying_method(self):
        method = self.cleaned_data.get("buying_method")
        if method != "cash":
            raise forms.ValidationError("Cash is currently the only available buying method.")
        return method

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("warranty_selected"):
            return cleaned

        required_warranty_fields = {
            "city": "City / Town",
            "village": "Village",
            "address_detail": "Street / address details",
            "gender": "Gender",
            "age": "Age",
            "national_id": "National ID",
            "education": "Education",
            "marital_status": "Marital status",
            "employment": "Employment",
            "economic_activity": "Economic activity",
            "monthly_income": "Monthly income",
            "other_loans": "Other loans",
            "home_or_business": "Home or business",
            "cooking_fuel": "Cooking fuel",
            "stove_type": "Cooking stove",
            "is_cook_user": "Appliance cooking use",
            "monthly_cooking_cost": "Monthly cooking cost",
            "grid_connection": "Grid connection",
        }
        if cleaned.get("grid_connection") == "yes":
            required_warranty_fields.update({
                "utility_provider": "Utility provider",
                "monthly_electricity_cost": "Monthly electricity cost",
            })

        for field_name, label in required_warranty_fields.items():
            if cleaned.get(field_name) in (None, "", [], ()):
                self.add_error(field_name, f"{label} is required for the warranty certificate.")

        if not cleaned.get("warranty_consent"):
            self.add_error("warranty_consent", "Consent is required to issue the warranty certificate.")

        signature = cleaned.get("signature_data", "")
        if not signature.startswith("data:image/png;base64,"):
            self.add_error("signature_data", "Please add your electronic signature.")
        elif len(signature) > 1_500_000:
            self.add_error("signature_data", "The signature is too large. Please clear it and sign again.")
        else:
            try:
                signature_bytes = base64.b64decode(signature.split(",", 1)[1], validate=True)
                image = Image.open(BytesIO(signature_bytes))
                image.verify()
                if image.format != "PNG" or image.width < 50 or image.height < 20:
                    raise ValueError
                cleaned["signature_bytes"] = signature_bytes
            except (binascii.Error, UnidentifiedImageError, OSError, ValueError):
                self.add_error("signature_data", "Please clear the signature and sign again.")

        return cleaned

class PaymentForm(forms.Form):
    mpesa_phone = forms.CharField(
        label="Phone (Mpesa, start with 254...)",
        widget=forms.NumberInput(attrs={
            "class": "min-h-12 w-full rounded-[18px] border border-slate-200 bg-white/90 px-4 py-3 text-slate-900 shadow-inner outline-none transition focus:border-green-600 focus:ring-4 focus:ring-emerald-500/10",
            "placeholder": "254XXXXXXXXX"
        })
    )

class RatingForm(forms.ModelForm):
    class Meta:
        model = ProductRating
        fields = ["rating", "review"]
        widgets = {
            "rating": forms.NumberInput(attrs={
                "min": 1, "max": 5, "class": "input input-bordered w-24"
            }),
            "review": forms.Textarea(attrs={
                'class': 'textarea textarea-bordered w-full rounded-lg focus:ring focus:ring-green-200 focus:border-green-500',
                'rows': 4,
                'placeholder': 'Write your review (optional)...'
            })
        }
