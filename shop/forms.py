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
    "country", "county", "buying_method",
]

WARRANTY_FIELD_NAMES = [
    "phone", "city", "village", "address_detail", "gender", "age", "national_id",
    "education", "marital_status", "employment", "economic_activity",
    "monthly_income", "other_loans", "home_or_business", "cooking_fuel",
    "stove_type", "is_cook_user", "monthly_cooking_cost", "grid_connection",
    "utility_provider", "monthly_electricity_cost",
]

COUNTRY_CODE_CHOICES = [
    ("+254", "Kenya (+254)"),
    ("+255", "Tanzania (+255)"),
    ("+256", "Uganda (+256)"),
    ("+250", "Rwanda (+250)"),
    ("+257", "Burundi (+257)"),
    ("+211", "South Sudan (+211)"),
    ("+251", "Ethiopia (+251)"),
    ("+252", "Somalia (+252)"),
    ("+27", "South Africa (+27)"),
    ("+234", "Nigeria (+234)"),
    ("+233", "Ghana (+233)"),
    ("+1", "United States / Canada (+1)"),
    ("+44", "United Kingdom (+44)"),
    ("+971", "United Arab Emirates (+971)"),
    ("+91", "India (+91)"),
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
    class Meta:
        model = CheckoutOrder
        fields = CHECKOUT_FIELD_NAMES
        widgets = {
            "first_name": forms.TextInput(attrs={"class": CHECKOUT_INPUT_CLASSES, "placeholder": "First name"}),
            "last_name": forms.TextInput(attrs={"class": CHECKOUT_INPUT_CLASSES, "placeholder": "Last name"}),
            "email": forms.EmailInput(attrs={"class": CHECKOUT_INPUT_CLASSES, "placeholder": "email@example.com"}),
            "phone": forms.TextInput(attrs={"class": CHECKOUT_INPUT_CLASSES, "placeholder": "07XX XXX XXX"}),
            "country": forms.TextInput(attrs={"class": CHECKOUT_INPUT_CLASSES, "placeholder": "Country"}),
            "county": forms.TextInput(attrs={"class": CHECKOUT_INPUT_CLASSES, "placeholder": "County / State"}),
            "buying_method": forms.Select(attrs={"class": CHECKOUT_SELECT_CLASSES}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].required = False
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


class WarrantyRegistrationForm(forms.ModelForm):
    country_code = forms.ChoiceField(choices=COUNTRY_CODE_CHOICES, initial="+254")
    warranty_consent = forms.BooleanField(required=True)
    signature_data = forms.CharField(required=False, widget=forms.HiddenInput())

    class Meta:
        model = CheckoutOrder
        fields = ["country_code", *WARRANTY_FIELD_NAMES]
        widgets = {
            "cooking_fuel": forms.CheckboxSelectMultiple(attrs={"class": CHECKOUT_CHECKBOX_CLASSES}),
            "stove_type": forms.CheckboxSelectMultiple(attrs={"class": CHECKOUT_CHECKBOX_CLASSES}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if name in {"warranty_consent", "signature_data", "cooking_fuel", "stove_type"}:
                continue
            field.widget.attrs["class"] = CHECKOUT_SELECT_CLASSES if isinstance(field.widget, forms.Select) else CHECKOUT_INPUT_CLASSES

        required = set(WARRANTY_FIELD_NAMES) - {"utility_provider", "monthly_electricity_cost"}
        for name in required:
            self.fields[name].required = True
        self.fields["address_detail"].widget.attrs["placeholder"] = "Street, estate, house number, landmark..."
        self.fields["phone"].widget.attrs.update({"placeholder": "712 345 678", "inputmode": "tel", "autocomplete": "tel-national"})
        self.fields["country_code"].widget.attrs.update({"class": CHECKOUT_SELECT_CLASSES, "autocomplete": "tel-country-code"})
        self.fields["economic_activity"].widget.attrs["placeholder"] = "Economic activity"
        self.fields["monthly_cooking_cost"].widget.attrs["placeholder"] = "Monthly cooking cost"
        self.fields["monthly_electricity_cost"].widget.attrs["placeholder"] = "Monthly electricity cost"

        if not self.is_bound and self.instance and self.instance.phone:
            saved_phone = "".join(character for character in str(self.instance.phone) if character.isdigit() or character == "+")
            for code, _label in sorted(COUNTRY_CODE_CHOICES, key=lambda choice: len(choice[0]), reverse=True):
                if saved_phone.startswith(code):
                    self.initial["country_code"] = code
                    self.initial["phone"] = saved_phone[len(code):]
                    break

    def clean_phone(self):
        code = self.cleaned_data.get("country_code", "+254")
        number = "".join(character for character in self.cleaned_data.get("phone", "") if character.isdigit())
        code_digits = code.lstrip("+")
        if number.startswith(code_digits):
            number = number[len(code_digits):]
        number = number.lstrip("0")
        if not 7 <= len(number) <= 12:
            raise forms.ValidationError("Enter a valid phone number without the country code.")
        return f"{code}{number}"

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("grid_connection") == "yes":
            if not cleaned.get("utility_provider"):
                self.add_error("utility_provider", "Utility provider is required when connected to the grid.")
            if cleaned.get("monthly_electricity_cost") in (None, ""):
                self.add_error("monthly_electricity_cost", "Monthly electricity cost is required when connected to the grid.")

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
