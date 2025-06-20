# Generated by Django 4.2.11 on 2025-06-13 14:11

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0014_alter_order_order_id_alter_product_product_status'),
    ]

    operations = [
        migrations.AlterField(
            model_name='product',
            name='product_status',
            field=models.CharField(choices=[('rejected', 'Rejected'), ('in_review', 'IN Review'), ('disabled', 'Disabled'), ('draft', 'Draft'), ('published', 'Published')], default='published', max_length=10),
        ),
    ]
