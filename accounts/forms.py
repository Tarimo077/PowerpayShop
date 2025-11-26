from django import forms
from django.contrib.auth.forms import PasswordResetForm, SetPasswordForm, UserCreationForm
from .models import User, Vendor


class LoginForm(forms.Form):
    username = forms.CharField()
    password = forms.CharField(widget=forms.PasswordInput())


class OTPForm(forms.Form):
    otp = forms.CharField(max_length=6)


class StyledPasswordResetForm(PasswordResetForm):
    email = forms.EmailField(
        widget=forms.EmailInput(
            attrs={
                "placeholder": "you@example.com",
                "class": (
                    "input input-bordered w-full border-green-300 "
                    "focus:border-green-500 focus:ring focus:ring-green-200 "
                    "rounded-lg transition bg-white dark:bg-gray-800"
                )
            }
        )
    )


class StyledSetPasswordForm(SetPasswordForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["new_password1"].widget.attrs.update({
            "placeholder": "Enter new password",
            "class": "input input-bordered w-full border-green-300 "
                     "focus:border-green-500 focus:ring focus:ring-green-200 "
                     "rounded-lg bg-white dark:bg-gray-800 transition"
        })
        self.fields["new_password2"].widget.attrs.update({
            "placeholder": "Confirm new password",
            "class": "input input-bordered w-full border-green-300 "
                     "focus:border-green-500 focus:ring focus:ring-green-200 "
                     "rounded-lg bg-white dark:bg-gray-800 transition"
        })


class RegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True, widget=forms.EmailInput(
        attrs={
            "placeholder": "you@example.com",
            "class": "input input-bordered w-full border-green-300 focus:border-green-500 focus:ring focus:ring-green-200 rounded-lg transition bg-white dark:bg-gray-800"
        }
    ))
    username = forms.CharField(widget=forms.TextInput(
        attrs={
            "placeholder": "Username",
            "class": "input input-bordered w-full border-green-300 focus:border-green-500 focus:ring focus:ring-green-200 rounded-lg transition bg-white dark:bg-gray-800"
        }
    ))
    password1 = forms.CharField(widget=forms.PasswordInput(
        attrs={
            "placeholder": "Password",
            "class": "input input-bordered w-full border-green-300 focus:border-green-500 focus:ring focus:ring-green-200 rounded-lg transition bg-white dark:bg-gray-800"
        }
    ))
    password2 = forms.CharField(widget=forms.PasswordInput(
        attrs={
            "placeholder": "Confirm Password",
            "class": "input input-bordered w-full border-green-300 focus:border-green-500 focus:ring focus:ring-green-200 rounded-lg transition bg-white dark:bg-gray-800"
        }
    ))
    is_vendor = forms.BooleanField(
        required=False,
        label="Register as Vendor",
        widget=forms.CheckboxInput(attrs={"class": "checkbox checkbox-success"})
    )

    class Meta:
        model = User
        fields = ["username", "email", "password1", "password2", "is_vendor"]


# ======================
# USER & VENDOR PROFILE FORMS
# ======================

class UserProfileForm(forms.ModelForm):
    username = forms.CharField(widget=forms.TextInput(attrs={
        "class": "input input-bordered w-full border-green-300 focus:border-green-500 focus:ring focus:ring-green-200 rounded-lg",
    }))
    email = forms.EmailField(widget=forms.EmailInput(attrs={
        "class": "input input-bordered w-full border-green-300 focus:border-green-500 focus:ring focus:ring-green-200 rounded-lg",
    }))
    first_name = forms.CharField(required=False, widget=forms.TextInput(attrs={
        "class": "input input-bordered w-full border-green-300 focus:border-green-500 focus:ring focus:ring-green-200 rounded-lg",
    }))
    last_name = forms.CharField(required=False, widget=forms.TextInput(attrs={
        "class": "input input-bordered w-full border-green-300 focus:border-green-500 focus:ring focus:ring-green-200 rounded-lg",
    }))

    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name']


class VendorProfileForm(forms.ModelForm):
    shop_name = forms.CharField(widget=forms.TextInput(attrs={
        "class": "input input-bordered w-full border-green-300 focus:border-green-500 focus:ring focus:ring-green-200 rounded-lg",
    }))
    logo = forms.ImageField(required=False, widget=forms.FileInput(attrs={
        "class": "file-input file-input-bordered w-full"
    }))
    description = forms.CharField(required=False, widget=forms.Textarea(attrs={
        "class": "textarea textarea-bordered w-full rounded-lg border-green-300 focus:border-green-500 focus:ring focus:ring-green-200",
        "rows": 3
    }))
    address = forms.CharField(required=False, widget=forms.TextInput(attrs={
        "class": "input input-bordered w-full border-green-300 focus:border-green-500 focus:ring focus:ring-green-200 rounded-lg",
    }))

    class Meta:
        model = Vendor
        fields = ['shop_name', 'logo', 'description', 'address']
