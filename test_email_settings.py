"""
Email ayarlarını test etmek için script
Kullanım: python test_email_settings.py
"""

import os
from dotenv import load_dotenv

load_dotenv()

# Test edilecek konfigürasyonlar
configs = [
    {
        'name': 'SSL Port 465',
        'host': 'mail.meslas.com',
        'port': 465,
        'use_tls': False,
        'use_ssl': True,
    },
    {
        'name': 'TLS Port 587',
        'host': 'mail.meslas.com',
        'port': 587,
        'use_tls': True,
        'use_ssl': False,
    },
    {
        'name': 'Port 25 (No encryption)',
        'host': 'mail.meslas.com',
        'port': 25,
        'use_tls': False,
        'use_ssl': False,
    },
]

email_user = os.environ.get('EMAIL_HOST_USER', 'info@meslas.com')
email_password = os.environ.get('EMAIL_HOST_PASSWORD', '')

print(f"Email: {email_user}")
print(f"Password: {'*' * len(email_password)}")
print("\n" + "="*60)

for config in configs:
    print(f"\nTest ediliyor: {config['name']}")
    print(f"Host: {config['host']}, Port: {config['port']}")
    
    try:
        import smtplib
        
        if config['use_ssl']:
            server = smtplib.SMTP_SSL(config['host'], config['port'], timeout=10)
        else:
            server = smtplib.SMTP(config['host'], config['port'], timeout=10)
            if config['use_tls']:
                server.starttls()
        
        server.login(email_user, email_password)
        print(f"✅ BAŞARILI: {config['name']} çalışıyor!")
        server.quit()
        
        print(f"\n🎉 Çalışan konfigürasyon bulundu!")
        print(f"   .env dosyanızda şu ayarları kullanın:")
        print(f"   EMAIL_HOST={config['host']}")
        print(f"   EMAIL_PORT={config['port']}")
        print(f"   EMAIL_USE_TLS={config['use_tls']}")
        print(f"   EMAIL_USE_SSL={config['use_ssl']}")
        break
        
    except Exception as e:
        print(f"❌ HATA: {str(e)}")

print("\n" + "="*60)
