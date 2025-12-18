from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import User, Vendor


@receiver(post_save, sender=User)
def create_vendor_profile(sender, instance, created, **kwargs):
    if created and instance.is_vendor:
        Vendor.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_vendor_profile(sender, instance, **kwargs):
    if instance.is_vendor:
        if hasattr(instance, 'vendor'):
            instance.vendor.save()
        else:
            Vendor.objects.create(user=instance)


@receiver(post_save, sender=User)
def set_default_otp(sender, instance, created, **kwargs):
    """
    Admins & Vendors → OTP ON
    Customers → OTP OFF (can enable manually)
    """
    if not created:
        return

    require_otp = False

    if instance.is_staff or instance.is_superuser:
        require_otp = True
    elif instance.is_vendor:
        require_otp = True

    if instance.require_otp != require_otp:
        instance.require_otp = require_otp
        instance.save(update_fields=["require_otp"])
