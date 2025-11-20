#!/usr/bin/env python
"""
Railway'de superuser oluşturmak için script
Kullanım: python create_superuser.py
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'metis_admin.settings')
django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()

# Environment variables'dan al veya varsayılan değerler
username = os.environ.get('DJANGO_SUPERUSER_USERNAME', 'admin')
email = os.environ.get('DJANGO_SUPERUSER_EMAIL', 'admin@mestakip.com')
password = os.environ.get('DJANGO_SUPERUSER_PASSWORD', 'admin123')

if not User.objects.filter(username=username).exists():
    User.objects.create_superuser(username=username, email=email, password=password)
    print(f'✅ Superuser "{username}" oluşturuldu!')
    print(f'📧 Email: {email}')
    print(f'🔑 Şifre: {password}')
else:
    print(f'ℹ️  Superuser "{username}" zaten mevcut.')
