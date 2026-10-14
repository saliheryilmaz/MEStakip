from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import TransactionCategory, UserProfile

@receiver(post_save, sender=User)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    """Kullanıcı profili oluştur - sadece profil yoksa oluştur, rolü değiştirme"""
    # Sadece profil yoksa oluştur, mevcut rolü değiştirme
    if not hasattr(instance, 'userprofile'):
        UserProfile.objects.get_or_create(user=instance, defaults={'role': 'yonetici'})
    
    # Sadece süperuser/staff kullanıcıları için admin rolünü zorla ata
    elif (instance.is_superuser or instance.is_staff) and hasattr(instance, 'userprofile'):
        if instance.userprofile.role != 'admin':
            instance.userprofile.role = 'admin'
            instance.userprofile.save(update_fields=['role'])