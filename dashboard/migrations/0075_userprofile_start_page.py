from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("dashboard", "0074_saklama_plan_sonucu")]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="start_page",
            field=models.CharField(
                max_length=32,
                default="dashboard:index",
                choices=[
                    ("dashboard:index", "Dashboard"),
                    ("mesbul:index", "MesBul"),
                    ("erp:stok_listesi", "DİA stok"),
                    ("dashboard:elements", "Siparişler"),
                    ("dashboard:lastik_saklama", "Lastik Saklama"),
                    ("dashboard:cikma_lastikler", "Çıkma Lastikler"),
                ],
            ),
        ),
    ]
