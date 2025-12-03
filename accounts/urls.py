from django.urls import path
from .views import login_view, verify_otp, resend_otp, CustomPasswordResetView, register_view, profile_page, vendor_admin_list, vendor_approve, vendor_suspend, vendor_unsuspend
from django.contrib.auth import views as auth_views
from .forms import StyledPasswordResetForm, StyledSetPasswordForm


urlpatterns = [
    path("login/", login_view, name="login"),
    path("logout/", auth_views.LogoutView.as_view(next_page="/"), name="logout"),
    path("register/", register_view, name="register"),
    path("verify-otp/", verify_otp, name="verify_otp"),
    path("resend-otp/", resend_otp, name="resend_otp"),
    path('profile/', profile_page, name='profile'),
    path(
        "password-reset/",
        CustomPasswordResetView.as_view(
            form_class=StyledPasswordResetForm
        ),
        name="password_reset"
    ),
    path("password-reset/done/", auth_views.PasswordResetDoneView.as_view(
        template_name="accounts/password_reset_done.html"
    ), name="password_reset_done"),
    path("password-reset-confirm/<uidb64>/<token>/", auth_views.PasswordResetConfirmView.as_view(
        template_name="accounts/password_reset_confirm.html",
        form_class=StyledSetPasswordForm,
        success_url="/accounts/password-reset-complete/"
    ), name="password_reset_confirm"),
    path("password-reset-complete/", auth_views.PasswordResetCompleteView.as_view(
        template_name="accounts/password_reset_complete.html"
    ), name="password_reset_complete"),
    path("vendors/", vendor_admin_list, name="vendor_admin_list"),
    path("vendors/approve/<int:user_id>/", vendor_approve, name="vendor_approve"),
    path('vendors/suspend/<int:user_id>/', vendor_suspend, name='vendor_suspend'),
    path('vendors/unsuspend/<int:user_id>/', vendor_unsuspend, name='vendor_unsuspend'),

]
