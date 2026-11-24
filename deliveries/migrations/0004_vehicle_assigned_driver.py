from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [
        ("deliveries", "0003_vehicle_alter_delivery_options_delivery_created_by_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.AddField(
            model_name="vehicle", name="assigned_driver",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="primary_vehicles", to=settings.AUTH_USER_MODEL),
        ),
    ]
