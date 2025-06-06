# Generated by Django 4.2.11 on 2025-05-28 15:18

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0005_medialibrary_alter_product_product_status_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='product',
            name='product_status',
            field=models.CharField(choices=[('draft', 'Draft'), ('in_review', 'IN Review'), ('disabled', 'Disabled'), ('rejected', 'Rejected'), ('published', 'Published')], default='published', max_length=10),
        ),
        migrations.AlterField(
            model_name='productsreviews',
            name='rating',
            field=models.ImageField(choices=[(3, '★★★✩✩'), (2, '★★✩✩✩'), (4, '★★★★✩'), (5, '★★★★★'), (1, '★✩✩✩✩')], default=None, upload_to=''),
        ),
    ]
