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
        # Only save if vendor profile exists
        if hasattr(instance, 'vendor'):
            instance.vendor.save()
        else:
            # Optionally create it automatically if missing
            Vendor.objects.create(user=instance)
