# product/models.py
import os
from datetime import timedelta

import shortuuid
from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.utils import timezone
from django.db import models
from django.utils.timezone import now
from multiselectfield import MultiSelectField
from shortuuid.django_fields import ShortUUIDField
from django.utils.html import mark_safe
from accounts.models import User
from decimal import Decimal
from tinymce.models import HTMLField
from ckeditor.fields import RichTextField


STATUS_CHOICES = {
    ('process', 'Processing'),
    ('shipped', 'Shipped'),
    ('delivered', 'Delivered')
}

STATUS = {
    ('published', 'Published'),
    ('draft', 'Draft'),
    ('disabled', 'Disabled'),
    ('rejected', 'Rejected'),
    ('in_review', 'IN Review'),

}

RATING = {
    (1, "★✩✩✩✩"),
    (2, "★★✩✩✩"),
    (3, "★★★✩✩"),
    (4, "★★★★✩"),
    (5, "★★★★★")
}

def delete_file_if_exists(file_field):
    """Delete a file from the filesystem only if it exists and is not a default/dummy."""
    if file_field and hasattr(file_field, 'path') and os.path.isfile(file_field.path):
        try:
            os.remove(file_field.path)
        except Exception as e:
            print(f"Error deleting file: {e}")

def default_expected_delivery():
    return now().date() + timedelta(days=7)

def user_directory_path(instance, filename):
    # Check if the instance has a direct user attribute
    if hasattr(instance, 'user'):
        return 'user_{0}/{1}'.format(instance.user.id, filename)
    # Check if the instance has a product attribute with a related user
    elif hasattr(instance, 'product') and hasattr(instance.product, 'user'):
        return 'user_{0}/{1}'.format(instance.product.user.id, filename)
    # Default to a generic path if no user can be found
    return 'unknown_user/{0}'.format(filename)

def category_directory_path(instance, filename):
    if hasattr(instance, 'cid'):
        return 'category_{0}/{1}'.format(instance.cid, filename)
    return 'category_{0}/{1}'.format(instance.id, filename)

def supplier_directory_path(instance, filename):
    return 'supplier_{0}/{1}'.format(instance.Vid, filename)


# Image cleanup signals
@receiver(post_delete, sender='products.MainCategory')
def delete_maincategory_image(sender, instance, **kwargs):
    delete_file_if_exists(instance.image)

@receiver(post_delete, sender='products.SubCategory')
def delete_subcategory_image(sender, instance, **kwargs):
    delete_file_if_exists(instance.image)

@receiver(post_delete, sender='products.Supplier')
def delete_supplier_image(sender, instance, **kwargs):
    delete_file_if_exists(instance.image)

@receiver(post_delete, sender='products.ProductVariant')
def delete_variant_files(sender, instance, **kwargs):
    delete_file_if_exists(instance.image)
    delete_file_if_exists(instance.video)

@receiver(post_delete, sender='products.ExtraImages')
def delete_extra_images(sender, instance, **kwargs):
    delete_file_if_exists(instance.image)

@receiver(post_delete, sender='products.VariantExtraImage')
def delete_variant_extra_images(sender, instance, **kwargs):
    delete_file_if_exists(instance.image)

@receiver(post_delete, sender='products.About')
def delete_about_image(sender, instance, **kwargs):
    delete_file_if_exists(instance.image)

@receiver(post_delete, sender='products.BannerImage')
def delete_banner_image(sender, instance, **kwargs):
    delete_file_if_exists(instance.image)

@receiver(post_delete, sender='products.MediaLibrary')
def delete_media_file(sender, instance, **kwargs):
    delete_file_if_exists(instance.file)


class MainCategory(models.Model):
    cid = ShortUUIDField(unique=True, length=10, max_length=30, prefix="cat", alphabet="abcdefghijklmnop1234567890")
    title = models.CharField(max_length=100)
    image = models.ImageField(upload_to=category_directory_path)
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True)

    class Meta:
        verbose_name = "Main Category"
        verbose_name_plural = "Main Categories"

    def category_image(self):
        return mark_safe('<img src="%s" width="50" height="50" />' % (self.image.url))

    def __str__(self):
        return self.title


class SubCategory(models.Model):
    sid = ShortUUIDField(unique=True, length=10, max_length=30, prefix="subcat", alphabet="abcdefghijklmnop1234567890")
    main_category = models.ForeignKey(MainCategory, on_delete=models.CASCADE, related_name='subcategories')
    title = models.CharField(max_length=100)
    image = models.ImageField(upload_to=category_directory_path)
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    name = models.CharField(max_length=100, blank=True)

    class Meta:
        verbose_name = "Subcategory"
        verbose_name_plural = "Subcategories"

    def subcategory_image(self):
        return mark_safe('<img src="%s" width="50" height="50" />' % (self.image.url))

    def __str__(self):
        return self.title




class Tags(models.Model):
    tname = models.CharField(max_length=100)


class Supplier(models.Model):
    Vid = ShortUUIDField(unique=True, length=10, max_length=30, prefix="ven", alphabet="abcdefghijklmnop1234567890")
    item = models.CharField(max_length=50)
    image = models.ImageField(upload_to=supplier_directory_path)
    name = models.CharField(max_length=50)
    mail = models.EmailField()
    description = models.TextField(null=True, blank=True)
    address = models.CharField(max_length=100, null=True, blank=True)
    contact = models.CharField(max_length=100, null=True, blank=True)

    user = models.OneToOneField(User, on_delete=models.SET_NULL, null=True)

    class Meta:
        verbose_name_plural = "Suppliers"

    def vendors_image(self):
        return mark_safe('<img src="%s" width="50" height="50" />' % (self.image.url))

    def __str__(self):
        return self.name



class Product(models.Model):
    GENDER_CHOICES = [
        ('male', 'Male'),
        ('female', 'Female'),
        ('unisex', 'Unisex'),
    ]

    COLOR_CHOICES = [
        ('grey', 'Grey'), ('lemon', 'Lemon'), ('white', 'White'), ('red', 'Red'),
        ('black', 'Black'), ('pink', 'Pink'), ('navy', 'Navy'), ('brown', 'Brown'),
        ('beige', 'Beige'), ('tan', 'Tan'), ('burgundy', 'Burgundy'), ('olive', 'Olive'),
        ('camel', 'Camel'), ('cream', 'Cream'), ('teal', 'Teal'), ('purple', 'Purple'),
        ('orange', 'Orange'), ('gold', 'Gold'), ('silver', 'Silver'), ('blue', 'Blue'),
        ('green', 'Green'), ('yellow', 'Yellow'), ('coral', 'Coral'), ('turquoise', 'Turquoise'),
        ('khaki', 'Khaki'), ('lavender', 'Lavender'), ('mint', 'Mint'), ('taupe', 'Taupe'),
        ('blush', 'Blush'), ('cognac', 'Cognac')
    ]

    SIZE_CHOICES = [
        ('XS', 'Extra Small'), ('S', 'Small'), ('M', 'Medium'), ('L', 'Large'),
        ('XL', 'Extra Large'), ('XXL', 'Double Extra Large'), ('MINI', 'Mini/Micro'),
        ('ONE', 'One Size'), ('CARRY', 'Carry-on'), ('CABIN', 'Cabin'),
        ('TRAVEL', 'Travel/Weekender'), ('1L', '1 Liter'), ('5L', '5 Liter'),
        ('10L', '10 Liter'), ('15L', '15 Liter'), ('20L', '20 Liter'), ('25L', '25 Liter'),
        ('30L', '30 Liter'), ('35L', '35 Liter'), ('40L', '40 Liter'), ('45L', '45 Liter'),
        ('50L', '50+ Liter')
    ]

    pid = ShortUUIDField(unique=True, length=10, max_length=30, prefix="ven", alphabet="abcdefghijklmnop1234567890")
    name = models.CharField(max_length=100)
    title = models.CharField(max_length=100)
    description = models.TextField(null=True, blank=True)
    url = models.URLField(null=True, blank=True)
    specification = models.TextField(null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    product_status = models.CharField(choices=STATUS, max_length=10, default="published")
    status = models.BooleanField(default=True)
    in_stock = models.BooleanField(default=True)
    featured = models.BooleanField(default=False)
    sku = ShortUUIDField(unique=True, length=10, max_length=15, prefix="sku", alphabet="1234567890abcdefghijklmnop")
    date = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(null=True, blank=True)
    main_category = models.ForeignKey('MainCategory', on_delete=models.SET_NULL, null=True, related_name='products')
    sub_category = models.ForeignKey('SubCategory', on_delete=models.SET_NULL, null=True, related_name='products')
    def product_image(self):
        return mark_safe(f'<img src="{self.image.url}" width="50" height="50" />')

    def __str__(self):
        return self.name



class ProductVariant(models.Model):
    vid = ShortUUIDField(unique=True, length=10, max_length=30, prefix="var", alphabet="1234567890abcdef")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="variants")
    color = models.CharField(max_length=50, choices=Product.COLOR_CHOICES)
    image = models.ImageField(upload_to='variants/')
    video = models.FileField(upload_to='variants/videos/', null=True, blank=True)
    gender = models.CharField(max_length=10, choices=[('male', 'Male'), ('female', 'Female'), ('unisex', 'Unisex')])

    def __str__(self):
        return f"{self.product.name} - {self.color}"



class VariantSizeOption(models.Model):
    variant = models.ForeignKey(ProductVariant, on_delete=models.CASCADE, related_name='size_options')
    size = models.CharField(max_length=10, choices=Product.SIZE_CHOICES)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    old_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    stock_quantity = models.PositiveIntegerField()

    def __str__(self):
        return f"{self.variant} - {self.size}"


class ExtraImages(models.Model):
    image = models.ImageField(upload_to=user_directory_path, blank=True, null=True)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='extra_images')
    date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Image for {self.product.name}"

    def product_image(self):
        return mark_safe(f'<img src="{self.image.url}" width="50" height="50" />')


class VariantExtraImage(models.Model):
    image = models.ImageField(upload_to=user_directory_path, blank=True, null=True)
    product_variant = models.ForeignKey(ProductVariant, on_delete=models.CASCADE, related_name='extra_images')
    date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Image for {self.product_variant.product.name} - {self.product_variant.color}"

    def variant_image(self):
        return mark_safe(f'<img src="{self.image.url}" width="50" height="50" />')

################################ cart Order ####################

class DiscountCode(models.Model):
    code = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    discount_percentage = models.IntegerField(blank=True, null=True)
    valid_from = models.DateTimeField()
    valid_to = models.DateTimeField()
    active = models.BooleanField(default=True)
    min_spend = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    used_by = models.ManyToManyField(User, blank=True, related_name='used_coupons')

    usage_limit = models.IntegerField(null=True, blank=True)
    per_user_limit = models.IntegerField(null=True, blank=True)

    applicable_products = models.ManyToManyField('Product', blank=True)
    applicable_categories = models.ManyToManyField('SubCategory', blank=True)
    allowed_users = models.ManyToManyField(User, blank=True, related_name='allowed_coupons')
    auto_apply = models.BooleanField(default=False)
    is_stackable = models.BooleanField(default=False)
    min_quantity = models.IntegerField(default=0)

    def is_valid(self, user=None, cart=None):
        now = timezone.now()
        if not self.active or self.valid_from > now or self.valid_to < now:
            return False

        if self.usage_limit and self.used_by.count() >= self.usage_limit:
            return False

        if user:
            user_uses = self.used_by.filter(id=user.id).count()
            if self.per_user_limit and user_uses >= self.per_user_limit:
                return False
            if self.allowed_users.exists() and user not in self.allowed_users.all():
                return False

        if cart and self.min_spend and cart.total < self.min_spend:
            return False

        return True

    def __str__(self):
        return self.code

class Cart(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    updated = models.DateTimeField(auto_now=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    discount_code = models.ForeignKey(DiscountCode, on_delete=models.SET_NULL, null=True, blank=True, related_name='carts')
    selected_size = models.CharField(max_length=50, null=True, blank=True)  # NEW FIELD
    razorpay_order_id = models.CharField(max_length=100, null=True, blank=True)

    def update_total(self):
        self.total = sum(item.line_total for item in self.cartitem_set.all())
        self.save()

    def apply_discount(self):
        discount = Decimal('0.00')

        if self.discount_code and self.discount_code.is_valid(user=self.user, cart=self):
            cart_items = self.cartitem_set.all()

            if self.discount_code.applicable_products.exists():
                if not any(item.product in self.discount_code.applicable_products.all() for item in cart_items):
                    return discount

            if self.discount_code.applicable_categories.exists():
                if not any(item.product.sub_category in self.discount_code.applicable_categories.all() for item in
                           cart_items):
                    return discount

            if self.discount_code.min_quantity:
                total_quantity = sum(item.quantity for item in cart_items)
                if total_quantity < self.discount_code.min_quantity:
                    return discount

            if self.discount_code.discount_amount:
                discount = self.discount_code.discount_amount
            elif self.discount_code.discount_percentage:
                discount = (self.discount_code.discount_percentage / 100) * self.total

            if self.user:
                self.discount_code.used_by.add(self.user)

        return discount

    def __str__(self):
        return f"Cart id: {self.id}"

    def save(self, *args, **kwargs):
        if self.discount_code and self.discount_code.is_valid():
            self.apply_discount()
        super().save(*args, **kwargs)


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    product_variant = models.ForeignKey(ProductVariant, on_delete=models.CASCADE, null=True, blank=True)
    quantity = models.IntegerField(default=1)
    line_total = models.DecimalField(max_digits=10, decimal_places=2)
    selected_size = models.CharField(max_length=50, null=True, blank=True)  # ✅ Add this line

    def product_image(self):
        if self.product.image:
            return mark_safe('<img src="%s" width="50" height="50" />' % (self.product.image.url))
        return "(No Image)"
    product_image.short_description = 'Product Image'

    def __str__(self):
        return self.product.name




############################# Product Review ########################


class ProductsReviews(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True)
    review = models.TextField()
    rating = models.ImageField(choices=RATING, default=None)
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Products Reviews"

    def __str__(self):
        return self.product.name

    def get_ratings(self):
        return self.rating


class Wishlist(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True)
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "wishlists"

    def __str__(self):
        user_name = self.user.username if self.user else "No User"
        product_name = self.product.name if self.product else "No Product"
        return f"{user_name} - {product_name}"


class Address(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    address = models.CharField(max_length=100, null=True)
    status = models.BooleanField(default=False)

    class Meta:
        verbose_name_plural = "Address"


class ShippingAddress(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    shipping_full_name = models.CharField(max_length=300)
    shipping_email = models.EmailField(max_length=300)
    shipping_address1 = models.CharField(max_length=300)
    shipping_address2 = models.CharField(max_length=300)
    shipping_city = models.CharField(max_length=300)
    shipping_state = models.CharField(max_length=300)
    shipping_zipcode = models.CharField(max_length=300)
    shipping_country = models.CharField(max_length=300)
    shipping_phone = models.CharField(max_length=300)

    class Meta:
        verbose_name_plural = "Shipping Address"

    def __str__(self):
        return f'Shipping Address - {str(self.id)}'


class BillingAddress(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    billing_full_name = models.CharField(max_length=300)
    billing_email = models.EmailField(max_length=300)
    billing_address1 = models.CharField(max_length=300)
    billing_address2 = models.CharField(max_length=300)
    billing_city = models.CharField(max_length=300)
    billing_state = models.CharField(max_length=300)
    billing_zipcode = models.CharField(max_length=300)
    billing_country = models.CharField(max_length=300)
    billing_phone = models.CharField(max_length=300)

    class Meta:
        verbose_name_plural = "Billing Address"

    def __str__(self):
        return f'Billing Address - {str(self.id)}'


class SiteSettings(models.Model):
    shipping_charge = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('5.00'), help_text="Default shipping charge")

    class Meta:
        verbose_name = "Site Setting"
        verbose_name_plural = "Site Settings"

    def __str__(self):
        return "Site Settings"


############################# Order  ########################

class Order(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('shipped', 'Shipped'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
        ('returned', 'Returned'),
        ('replaced', 'Replaced'),
        ('completed', 'Completed'),

    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    order_id = models.CharField(max_length=8, unique=True, blank=True, editable=False)
    expected_delivery = models.DateField(default=default_expected_delivery)

    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)  # ✅ New Field
    discount_code = models.CharField(max_length=100, blank=True, null=True)  # ✅ New Field

    total = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    cancel_requested = models.BooleanField(default=False)
    return_requested = models.BooleanField(default=False)
    replace_requested = models.BooleanField(default=False)
    complete_requested = models.BooleanField(default=False)



    # Billing address fields
    billing_full_name = models.CharField(max_length=300)
    billing_email = models.EmailField(max_length=300)
    billing_address1 = models.CharField(max_length=300)
    billing_address2 = models.CharField(max_length=300, blank=True, null=True)
    billing_city = models.CharField(max_length=300)
    billing_state = models.CharField(max_length=300)
    billing_zipcode = models.CharField(max_length=300)
    billing_country = models.CharField(max_length=300)
    billing_phone = models.CharField(max_length=300)

    # Shipping address fields
    shipping_full_name = models.CharField(max_length=300)
    shipping_email = models.EmailField(max_length=300)
    shipping_address1 = models.CharField(max_length=300)
    shipping_address2 = models.CharField(max_length=300, blank=True, null=True)
    shipping_city = models.CharField(max_length=300)
    shipping_state = models.CharField(max_length=300)
    shipping_zipcode = models.CharField(max_length=300)
    shipping_country = models.CharField(max_length=300)
    shipping_phone = models.CharField(max_length=300)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    payment_method = models.CharField(max_length=50, blank=True, null=True)
    feedback_note = models.TextField(blank=True, null=True, help_text="Feedback for cancel, return, or replace requests")

    def save(self, *args, **kwargs):
        if not self.order_id:
            self.order_id = shortuuid.ShortUUID().random(length=8).upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return f'Order {self.id} - {self.user.username}'


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    product_variant = models.ForeignKey(ProductVariant, on_delete=models.CASCADE, null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    quantity = models.IntegerField(default=1)
    price = models.DecimalField(max_digits=10, decimal_places=2)  # Price at the time of order
    selected_size = models.CharField(max_length=50, null=True, blank=True)  # ✅ Add this field


    def product_image(self):
        if self.product.image:
            return mark_safe('<img src="%s" width="50" height="50" />' % (self.product.image.url))
        return "(No Image)"

    def __str__(self):
        return f'{self.quantity} of {self.product.name}'




class About(models.Model):
    title = models.CharField(max_length=200)
    content = RichTextField()
    image = models.ImageField(upload_to='about_images/', blank=True, null=True)

    def __str__(self):
        return self.title


class BannerImage(models.Model):
    title = models.CharField(max_length=100, blank=True, null=True)
    image = models.ImageField(upload_to='banner_images/')
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)  # Allows enabling/disabling banners

    def __str__(self):
        return self.title if self.title else "Banner Image"


class DiscountLead(models.Model):
    name = models.CharField(max_length=100)
    phone = models.CharField(max_length=15)
    email = models.EmailField()
    coupon_code = models.CharField(max_length=50)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.email


class MediaLibrary(models.Model):
    file = models.FileField(upload_to='uploads/media_library/')
    name = models.CharField(max_length=255, blank=True)

    def save(self, *args, **kwargs):
        if not self.name:
            self.name = os.path.basename(self.file.name)
        super().save(*args, **kwargs)


