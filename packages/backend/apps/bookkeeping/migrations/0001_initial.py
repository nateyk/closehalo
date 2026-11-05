from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("multitenancy", "0023_alter_permission_category"),
    ]

    operations = [
        migrations.CreateModel(
            name="BookkeepingClient",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=200)),
                ("contact_email", models.EmailField(blank=True, max_length=254)),
                ("is_active", models.BooleanField(default=True)),
                ("tenant", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="bookkeeping_clients",
                    to="multitenancy.tenant",
                )),
            ],
            options={"ordering": ("name", "id")},
        ),
        migrations.AddIndex(
            model_name="bookkeepingclient",
            index=models.Index(fields=["tenant", "is_active"], name="bk_client_tenant_active"),
        ),
    ]
