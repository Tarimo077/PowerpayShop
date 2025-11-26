from django.shortcuts import render, redirect
from django.contrib.auth import authenticate
from django.core.mail import send_mail
from django.contrib import messages
from django.contrib.auth import login
from .models import EmailOTP, User
from .forms import LoginForm, OTPForm, RegistrationForm, UserProfileForm, VendorProfileForm
import random
from django.contrib import messages
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth.decorators import login_required
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.contrib.auth.views import PasswordResetView
from django.utils.html import strip_tags
from django.contrib.auth.forms import PasswordResetForm
from django.urls import reverse_lazy
from django.conf import settings
import datetime

MAX_ATTEMPTS = 5


def login_view(request):
    if request.method == "POST":
        form = LoginForm(request.POST)

        if form.is_valid():
            username = form.cleaned_data["username"]
            password = form.cleaned_data["password"]

            user = authenticate(request, username=username, password=password)

            if user:
                EmailOTP.objects.filter(user=user).delete()  # remove old OTPs
                # Generate OTP
                otp = str(random.randint(100000, 999999))

                # Save OTP
                EmailOTP.objects.create(user=user, otp=otp)

                send_otp_email(user, otp)
                messages.success(request, "An OTP has been sent to your email.")

                # Store user temporarily in session
                request.session["otp_user_id"] = user.id

                return redirect("verify_otp")
            else:
                messages.error(request, "Invalid username or password")
    else:
        form = LoginForm()

    return render(request, "accounts/login.html", {"form": form})

def resend_otp(request):
    user_id = request.session.get("otp_user_id")
    if not user_id:
        messages.error(request, "Session expired. Please login again.")
        return redirect("login")

    user = User.objects.get(id=user_id)

    # Delete old OTPs
    EmailOTP.objects.filter(user=user).delete()

    # Generate new OTP
    otp = str(random.randint(100000, 999999))
    EmailOTP.objects.create(user=user, otp=otp)

    send_otp_email(user, otp)
    messages.success(request, "A new OTP has been sent to your email.")
    return redirect("verify_otp")

def verify_otp(request):
    user_id = request.session.get("otp_user_id")
    if not user_id:
        messages.error(request, "Session expired. Please login again.")
        return redirect("login")

    otp_obj = EmailOTP.objects.filter(user_id=user_id).order_by('-created_at').first()
    if not otp_obj:
        messages.error(request, "No OTP found. Please resend OTP.")
        return redirect("resend_otp")

    if request.method == "POST":
        otp_input = request.POST.get("otp")
        if otp_obj.is_expired():
            messages.error(request, "OTP expired. Please resend OTP.")
            return redirect("resend_otp")

        if otp_obj.attempts >= MAX_ATTEMPTS:
            messages.error(request, "Maximum attempts reached. OTP locked. Resend OTP.")
            return redirect("resend_otp")

        if otp_input == otp_obj.otp:
            # Successful login
            user = otp_obj.user
            login(request, user)
            # Clear session and OTP
            request.session.pop("otp_user_id")
            otp_obj.delete()
            messages.success(request, "Login successful!")
            return redirect("index")  # Change to your landing page
        else:
            otp_obj.attempts += 1
            otp_obj.save()
            messages.error(request, f"Invalid OTP. Attempts left: {MAX_ATTEMPTS - otp_obj.attempts}")

    context = {
        "email": otp_obj.user.email
    }
    return render(request, "accounts/verify_otp.html", context)

def send_otp_email(user, otp):
    subject = "Your PowerPayShop OTP"
    from_email = None  # will use DEFAULT_FROM_EMAIL
    to_email = [user.email]

    # Render HTML content
    html_content = render_to_string("accounts/otp_email.html", {"user": user, "otp": otp})

    msg = EmailMultiAlternatives(subject, otp, from_email, to_email)
    msg.attach_alternative(html_content, "text/html")
    msg.send()

class CustomPasswordResetView(PasswordResetView):
    template_name = "accounts/password_reset.html"
    html_email_template_name = "accounts/password_reset_email.html"  # HTML template
    success_url = reverse_lazy("password_reset_done")
    from_email = None

    def send_mail(self, subject_template_name, email_template_name,
                  context, from_email, to_email, html_email_template_name=None):
        html_body = render_to_string(email_template_name, {**context, "year": datetime.date.today()})
        text_body = strip_tags(html_body)

        msg = EmailMultiAlternatives(
            subject="Reset Your PowerPay Password",
            body=text_body,
            from_email=self.from_email,
            to=[to_email],
        )
        msg.attach_alternative(html_body, "text/html")
        msg.send()

def register_view(request):
    if request.method == "POST":
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            # Set vendor status
            user.is_vendor = form.cleaned_data.get("is_vendor", False)
            user.save()
            # Auto-login
            login(request, user)
            messages.success(request, "Registration successful!")
            if user.is_vendor:
                return redirect('profile')
            else:
                return redirect("index")  # Landing page
        else:
            messages.error(request, "Please fix the errors below.")
    else:
        form = RegistrationForm()
    
    return render(request, "accounts/register.html", {"form": form})

@login_required
def profile_page(request):
    user = request.user
    is_vendor = user.is_vendor

    if request.method == "POST":
        # Determine which form was submitted
        if 'vendor_form_submit' in request.POST:
            user_form = UserProfileForm(instance=user)  # keep user form unchanged
            vendor_form = VendorProfileForm(request.POST, request.FILES, instance=user.vendor)
            if vendor_form.is_valid():
                vendor_form.save()
                messages.success(request, "Vendor profile updated successfully.")
                return redirect('profile')
            else:
                messages.error(request, "Please correct the errors in vendor form.")
        else:  # default to user form
            user_form = UserProfileForm(request.POST, instance=user)
            vendor_form = VendorProfileForm(instance=user.vendor) if is_vendor else None
            if user_form.is_valid():
                user_form.save()
                messages.success(request, "User profile updated successfully.")
                return redirect('profile')
            else:
                messages.error(request, "Please correct the errors in user form.")
    else:
        user_form = UserProfileForm(instance=user)
        vendor_form = VendorProfileForm(instance=user.vendor) if is_vendor else None

    context = {
        "user_form": user_form,
        "vendor_form": vendor_form,
        "is_vendor": is_vendor
    }
    return render(request, "accounts/profile.html", context)