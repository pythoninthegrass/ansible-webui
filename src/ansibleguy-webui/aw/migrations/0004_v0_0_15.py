# Generated by Django 5.0.2 on 2024-03-03 09:27

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("aw", "0003_v0_0_14"),
    ]

    operations = [
        migrations.AlterField(
            model_name="systemconfig",
            name="timezone",
            field=models.CharField(default="UTC", max_length=300),
        ),
    ]
