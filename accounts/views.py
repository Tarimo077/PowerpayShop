from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate
from django.contrib import messages
from django.contrib.auth import login
from .models import EmailOTP, User, Vendor
from .forms import LoginForm, RegistrationForm, UserProfileForm, VendorProfileForm
import secrets
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.contrib.auth.views import PasswordResetView
from django.utils.html import strip_tags
from django.urls import reverse_lazy
import datetime
from django.contrib.admin.views.decorators import staff_member_required
from notifications.utils import notify
from django.core.paginator import Paginator
from itertools import chain
from django.db.models import Q

MAX_ATTEMPTS = 5

def login_view(request):
    if request.method == "POST":
        form = LoginForm(request.POST)

        if form.is_valid():
            username = form.cleaned_data["username"]
            password = form.cleaned_data["password"]

            user = authenticate(request, username=username, password=password)

            if user:
                # ✅ OTP NOT REQUIRED → Login immediately
                if not user.require_otp:
                    login(request, user)
                    messages.success(request, "Login successful.")
                    return redirect("index")  # change as needed

                # 🔐 OTP REQUIRED
                EmailOTP.objects.filter(user=user).delete()

                otp = f"{secrets.randbelow(900000) + 100000}"
                EmailOTP.objects.create(user=user, otp=otp)

                send_otp_email(user, otp)
                messages.success(request, "An OTP has been sent to your email.")

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
    otp = f"{secrets.randbelow(900000) + 100000}"
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

            # Redirect based on user type
            if user.is_vendor and user.is_vendor_approved and hasattr(user, 'vendor') and not user.vendor.is_suspended:
                return redirect("vendor_dashboard")

            else:
                return redirect("index")  # Default landing page

        else:
            otp_obj.attempts += 1
            otp_obj.save()
            messages.error(request, f"Invalid OTP. Attempts left: {MAX_ATTEMPTS - otp_obj.attempts}")

    context = {
        "email": otp_obj.user.email
    }
    return render(request, "accounts/verify_otp.html", context)


def send_otp_email(user, otp):
    subject = "Your Cook Yami Shop OTP"
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
            subject="Reset Your Cook Yami Password",
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

            # User wants to be a vendor
            user.is_vendor = form.cleaned_data.get("is_vendor", False)

            # Vendor must be approved manually by admin
            if user.is_vendor:
                user.is_vendor_approved = False
                user.is_customer = False
            
            user.save()

            # Create a vendor placeholder profile ONLY if user checked 'is_vendor'
            #if user.is_vendor:
                #Vendor.objects.create(user=user)
            messages.success(request, "Account created successfully!")

            if user.is_vendor:
                messages.info(request, "Your vendor account requires admin approval.")
                return redirect("login")
            
            return redirect("login")

    else:
        form = RegistrationForm()

    return render(request, "accounts/register.html", {"form": form})


@login_required
def profile_page(request):
    user = request.user
    is_vendor = user.is_vendor_approved and hasattr(user, "vendor")
    vendor_instance = user.vendor if is_vendor else None

    if request.method == "POST":
        if "vendor_form_submit" in request.POST and vendor_instance:
            user_form = UserProfileForm(instance=user)
            vendor_form = VendorProfileForm(request.POST, request.FILES, instance=vendor_instance)
            if vendor_form.is_valid():
                vendor_form.save()
                messages.success(request, "Vendor profile updated successfully.")
                return redirect("profile")
            messages.error(request, "Please correct the errors in vendor form.")
        else:
            user_form = UserProfileForm(request.POST, instance=user)
            vendor_form = VendorProfileForm(instance=vendor_instance) if vendor_instance else None
            if user_form.is_valid():
                user_form.save()
                messages.success(request, "User profile updated successfully.")
                return redirect("profile")
            messages.error(request, "Please correct the errors in user form.")
    else:
        user_form = UserProfileForm(instance=user)
        vendor_form = VendorProfileForm(instance=vendor_instance) if vendor_instance else None

    return render(request, "accounts/profile.html", {"user_form": user_form, "vendor_form": vendor_form, "is_vendor": is_vendor})

@staff_member_required
def vendor_admin_list(request):
    search_query = request.GET.get("q", "").strip()
    per_page_raw = request.GET.get("per_page", "6")
    per_page = int(per_page_raw) if per_page_raw in {"6", "12", "24"} else 6
    page_number = request.GET.get("page", 1)

    pending_qs = User.objects.filter(is_vendor=True, is_vendor_approved=False).select_related("vendor")
    approved_qs = User.objects.filter(is_vendor=True, is_vendor_approved=True, vendor__is_suspended=False).select_related("vendor")
    suspended_qs = User.objects.filter(is_vendor=True, is_vendor_approved=True, vendor__is_suspended=True).select_related("vendor")

    if search_query:
        vendor_filter = Q(username__icontains=search_query) | Q(email__icontains=search_query) | Q(vendor__shop_name__icontains=search_query)
        pending_qs = pending_qs.filter(vendor_filter)
        approved_qs = approved_qs.filter(vendor_filter)
        suspended_qs = suspended_qs.filter(vendor_filter)

    pending_page = Paginator(pending_qs, per_page).get_page(page_number)
    approved_page = Paginator(approved_qs, per_page).get_page(page_number)
    suspended_page = Paginator(suspended_qs, per_page).get_page(page_number)
    all_vendors_page = Paginator(list(chain(pending_qs, approved_qs, suspended_qs)), per_page).get_page(page_number)

    return render(request, "accounts/vendors_list.html", {
        "all_vendors": all_vendors_page,
        "pending": pending_page,
        "approved": approved_page,
        "suspended": suspended_page,
        "per_page": per_page,
        "search_query": search_query,
    })

@staff_member_required
def vendor_approve(request, user_id):
    user = get_object_or_404(User, id=user_id)

    if not user.is_vendor:
        messages.error(request, "This user is not requesting vendor access.")
        return redirect("vendor_admin_list")

    # Approve vendor
    user.is_vendor_approved = True
    user.save()

    # Create vendor profile if missing
    Vendor.objects.get_or_create(user=user)

    # Notify vendor
    notify(
        user,
        "Vendor Approval",
        "Your vendor account has been approved by the admin.",
        "success"
    )

    messages.success(request, f"{user.username} is now an approved vendor.")
    return redirect("vendor_admin_list")


@staff_member_required
def vendor_suspend(request, user_id):
    user = get_object_or_404(User, id=user_id, is_vendor=True, is_vendor_approved=True)
    vendor = user.vendor
    vendor.is_suspended = True
    vendor.save()

    # Notify vendor
    notify(
        user,
        "Vendor Suspension",
        "Your vendor account has been suspended by the admin.",
        "error"
    )

    messages.warning(request, f"{user.username} has been suspended.")
    return redirect("vendor_admin_list")


@staff_member_required
def vendor_unsuspend(request, user_id):
    user = get_object_or_404(User, id=user_id, is_vendor=True, is_vendor_approved=True)
    vendor = user.vendor
    vendor.is_suspended = False
    vendor.save()

    # Notify vendor
    notify(
        user,
        "Vendor Re-Activation",
        "Your vendor account has been re-activated by the admin.",
        "success"
    )

    messages.success(request, f"{user.username} has been re-activated.")
    return redirect("vendor_admin_list")
