# products/views.py


import hmac
import hashlib
import json
from django.db.models import Q, Min, OuterRef, Exists

import logging
from django.utils import timezone
from datetime import timedelta
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import Order
from datetime import timedelta
from decimal import Decimal
from django.contrib.admin.views.decorators import staff_member_required
from venv import logger
from django.utils import timezone
from datetime import datetime, timedelta
from django.core.mail import send_mail
from django.db import transaction
from django.http import JsonResponse, HttpResponse, HttpResponseRedirect
from django.shortcuts import render, redirect, get_object_or_404
from django.template.loader import render_to_string
from django.urls import reverse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt, csrf_protect
from django.views.decorators.http import require_http_methods, require_POST
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.conf import settings
import razorpay
from django.core.mail import EmailMultiAlternatives
from django.utils.html import strip_tags
from .models import *
from .forms import *
from django.shortcuts import render
from django.contrib.auth.models import User
from .models import Order, Product, Cart
from django.db.models import Sum, Count
from blog.models import Blog  # Import Blog model
from django.contrib.admin import AdminSite
from django.db.models.functions import TruncDay, TruncMonth
from django.utils.timezone import now
from decimal import Decimal
from django.urls import reverse_lazy

client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
COLOR_HEX_MAP = {
    "grey": "#808080",
    "lemon": "#FFF700",
    "white": "#FFFFFF",
    "red": "#FF0000",
    "black": "#000000",
    "pink": "#FFC0CB",
    "navy": "#000080",
    "brown": "#A52A2A",
    "beige": "#F5F5DC",
    "tan": "#D2B48C",
    "burgundy": "#800020",
    "olive": "#808000",
    "camel": "#C19A6B",
    "cream": "#FFFDD0",
    "teal": "#008080",
    "purple": "#800080",
    "orange": "#FFA500",
    "gold": "#FFD700",
    "silver": "#C0C0C0",
    "blue": "#0000FF",
    "green": "#008000",
    "yellow": "#FFFF00",
    "coral": "#FF7F50",
    "turquoise": "#40E0D0",
    "khaki": "#F0E68C",
    "lavender": "#E6E6FA",
    "mint": "#98FF98",
    "taupe": "#483C32",
    "blush": "#F4C2C2",
    "cognac": "#9A463D"
}

def home(request):
    products = Product.objects.filter(product_status="published", featured=True).order_by('-id')

    # Add first variant, size, and discount to each product
    for product in products:
        first_variant = product.variants.first()  # Related name 'variants'
        if first_variant:
            product.first_variant = first_variant
            first_size = first_variant.size_options.first()
            if first_size:
                product.first_size = first_size
                if first_size.old_price and first_size.old_price > first_size.price:
                    discount = round(((first_size.old_price - first_size.price) / first_size.old_price) * 100)
                    product.first_discount = discount
                else:
                    product.first_discount = None
            else:
                product.first_size = None
                product.first_discount = None
        else:
            product.first_variant = None
            product.first_size = None
            product.first_discount = None

    sub_categories = SubCategory.objects.all().order_by('-id')[:9]
    color_choices = ProductVariant.objects.values_list('color', flat=True).distinct()
    banner_images = BannerImage.objects.filter(is_active=True)
    blogs = Blog.objects.order_by('-created_at')[:4]
    featured_products = Product.objects.filter(featured=True).order_by('-id')[:8]
    main_categories = MainCategory.objects.prefetch_related('subcategories').all()

    context = {
        'products': products,
        'sub_categories': sub_categories,
        'color_choices': color_choices,
        'banner_images': banner_images,
        'blogs': blogs,
        'featured_products': featured_products,
        'main_categories': main_categories
    }

    return render(request, 'home.html', context)


@require_POST
@login_required
@csrf_protect
def apply_coupon(request):
    code = request.POST.get('code')
    try:
        cart = Cart.objects.get(user=request.user)
    except Cart.DoesNotExist:
        return JsonResponse({"success": False, "message": "Cart not found."})

    try:
        discount = DiscountCode.objects.get(code=code)
        if not discount.is_valid(user=request.user, cart=cart):
            return JsonResponse({"success": False, "message": "Coupon is not valid."})

        cart.discount_code = discount
        cart.save()  # Just save the coupon association, don’t apply discount to total

        discount_amount = cart.apply_discount()
        try:
            shipping = SiteSettings.objects.first().shipping_charge
        except (SiteSettings.DoesNotExist, AttributeError):
            shipping = Decimal('0.00')

        final_total = cart.total - discount_amount + shipping

        return JsonResponse({
            "success": True,
            "message": "Coupon applied successfully!",
            "discount": float(discount_amount),
            "final_total": float(final_total)
        })

    except DiscountCode.DoesNotExist:
        return JsonResponse({"success": False, "message": "Invalid coupon code."})


@require_POST
@login_required
@csrf_protect
def remove_coupon(request):
    try:
        cart = Cart.objects.get(user=request.user)
        cart.discount_code = None
        cart.save()

        try:
            shipping = SiteSettings.objects.first().shipping_charge
        except (SiteSettings.DoesNotExist, AttributeError):
            shipping = Decimal('0.00')

        final_total = cart.total + shipping

        return JsonResponse({
            "success": True,
            "message": "Coupon removed successfully.",
            "final_total": float(final_total)
        })
    except Cart.DoesNotExist:
        return JsonResponse({"success": False, "message": "Cart not found."})


@login_required(login_url=reverse_lazy('accounts:login'))
@csrf_protect
def cart_view(request):
    cart, _ = Cart.objects.get_or_create(user=request.user, defaults={'total': Decimal('0.00')})
    items = CartItem.objects.filter(cart=cart)

    discount = cart.apply_discount() if cart.discount_code else Decimal('0.00')

    try:
        shipping = SiteSettings.objects.first().shipping_charge
    except (SiteSettings.DoesNotExist, AttributeError):
        shipping = Decimal('0.00')

    final_total = cart.total - discount + shipping

    context = {
        'cart': cart,
        'items': items,
        'total': cart.total,
        'discount': discount,
        'final_total': final_total,
        'shipping': shipping,
    }
    return render(request, 'cart.html', context)

def contact(request):
    success_message = None  # Initialize the success message variable
    if request.method == 'POST':
        form = ContactForm(request.POST)
        if form.is_valid():
            name = form.cleaned_data['name']
            email = form.cleaned_data['email']  # Sender's email
            subject = form.cleaned_data['subject']
            message = form.cleaned_data['message']

            email_subject = f"Contact Form Submission from {name}: {subject}"
            email_message = f"Message from {email}:\n\n{message}"

            try:
                send_mail(
                    email_subject,
                    email_message,
                    email,  # From email (sender's email)
                    ['stellarspvt@gmail.com'],  # To email (your email or business email)
                    fail_silently=False,
                )
                success_message = "Your message has been sent successfully. Thank you for contacting us!"
            except Exception as e:
                success_message = "An error occurred while sending your message. Please try again."

    else:
        form = ContactForm()

    return render(request, 'contact.html', {
        'form': form,
        'success_message': success_message
    })

def base(request, cid=None, is_subcategory=False):
    color = request.GET.get('color')
    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')
    page = request.GET.get('page', 1)
    products = Product.objects.filter(product_status="published", featured=True).order_by('-id')

    if cid:
        if is_subcategory:
            category = get_object_or_404(SubCategory, sid=cid)
            products = products.filter(sub_category=category)
        else:
            category = get_object_or_404(MainCategory, cid=cid)
            products = products.filter(main_category=category)

    if min_price and max_price:
        products = products.filter(price__gte=min_price, price__lte=max_price)

    if color:
        products = products.filter(variants__color=color).distinct()

    main_categories = MainCategory.objects.all().order_by('-id')
    sub_categories = SubCategory.objects.all().order_by('-id')

    paginator = Paginator(products, 10)
    try:
        products_page = paginator.page(page)
    except PageNotAnInteger:
        products_page = paginator.page(1)
    except EmptyPage:
        products_page = paginator.page(paginator.num_pages)

    color_choices = {color[0]: color[1] for color in ProductVariant.COLOR_CHOICES}

    context = {
        'products': products_page,
        'main_categories': main_categories,
        'sub_categories': sub_categories,
        'color_choices': color_choices,
        'color_hex_map': COLOR_HEX_MAP,

    }
    return render(request, 'base11.html', context)


def product_grid(request, cid=None, is_subcategory=False):
    color = request.GET.get('color')
    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')
    gender = request.GET.get('gender')
    page = request.GET.get('page', 1)
    sort = request.GET.get('sort')

    # Filter only products that have at least one valid variant with a size option
    valid_variants = ProductVariant.objects.filter(
        product=OuterRef('pk'),
        size_options__isnull=False
    )

    products = Product.objects.filter(
        product_status="published"
    ).annotate(
        has_valid_variant=Exists(valid_variants)
    ).filter(
        has_valid_variant=True
    ).prefetch_related(
        'variants__size_options'
    ).distinct()

    # Category filtering
    if cid:
        if is_subcategory:
            category = get_object_or_404(SubCategory, sid=cid)
            products = products.filter(sub_category=category)
        else:
            category = get_object_or_404(MainCategory, cid=cid)
            products = products.filter(main_category=category)

    # Gender filter
    if gender:
        gender_list = gender.split(',')
        products = products.filter(variants__gender__in=gender_list).distinct()

    # Price filter
    if min_price and max_price:
        products = products.filter(
            variants__size_options__price__gte=min_price,
            variants__size_options__price__lte=max_price
        ).distinct()

    # Color filter
    if color:
        products = products.filter(variants__color=color).distinct()

    # Sorting
    if sort == 'low_to_high':
        products = products.annotate(min_price=Min('variants__size_options__price')).order_by('min_price')
    elif sort == 'high_to_low':
        products = products.annotate(min_price=Min('variants__size_options__price')).order_by('-min_price')

    # Pagination
    paginator = Paginator(products, 9)
    try:
        products_page = paginator.page(page)
    except PageNotAnInteger:
        products_page = paginator.page(1)
    except EmptyPage:
        products_page = paginator.page(paginator.num_pages)

    # Context
    main_categories = MainCategory.objects.all().order_by('-id')
    sub_categories = SubCategory.objects.all().order_by('-id')
    color_choices = {color[0]: color[1] for color in Product.COLOR_CHOICES}

    context = {
        'products': products_page,
        'main_categories': main_categories,
        'sub_categories': sub_categories,
        'color_choices': color_choices.items(),
        'color_hex_map': COLOR_HEX_MAP,
        'sort': sort,
    }

    return render(request, 'product-grid.html', context)


def product_list(request):
    page = request.GET.get('page', 1)
    products = Product.objects.filter(product_status="published", featured=True).order_by('-id')

    paginator = Paginator(products, 9)
    try:
        products_page = paginator.page(page)
    except PageNotAnInteger:
        products_page = paginator.page(1)
    except EmptyPage:
        products_page = paginator.page(paginator.num_pages)

    context = {
        'products': products_page,
    }
    return render(request, 'product-list.html', context)


def product_details(request, pid):
    product = get_object_or_404(Product, pid=pid)
    variants = ProductVariant.objects.filter(product=product).prefetch_related('extra_images')
    variant = variants.first()  # ✅ default variant to show first

    context = {
        'product': product,
        'variants': variants,
        'variant': variant,  # ✅ pass default variant to template
    }
    return render(request, 'product-details.html', context)


def get_variant_data(request, variant_id):
    try:
        variant = ProductVariant.objects.get(id=variant_id)
        sizes = VariantSizeOption.objects.filter(variant=variant)
        extra_images = [img.image.url for img in variant.extra_images.all()]

        return JsonResponse({
            "name": f"{variant.product.name} - {variant.color}",
            "price": str(sizes[0].price) if sizes else "0.00",
            "old_price": str(sizes[0].old_price) if sizes and sizes[0].old_price else "",
            "image": variant.image.url if variant.image else "",
            "video": variant.video.url if variant.video else "",
            "sizes": [
                {
                    "size": s.size,
                    "stock_quantity": s.stock_quantity,
                    "price": str(s.price),
                    "old_price": str(s.old_price) if s.old_price else ""
                } for s in sizes
            ],
            "extra_images": extra_images,
        })
    except ProductVariant.DoesNotExist:
        return JsonResponse({"error": "Variant not found"}, status=404)


@login_required(login_url=reverse_lazy('accounts:login'))
def wishlist(request):
    # Only keep wishlist items where product still exists
    raw_wishlist = Wishlist.objects.filter(user=request.user).select_related('product')

    # Only include items where product, variant, and size option exist
    wishlist_items = [
        item for item in raw_wishlist
        if item.product
           and item.product.variants.exists()
           and item.product.variants.first().size_options.exists()
    ]

    context = {"w": wishlist_items}
    return render(request, 'wishlist.html', context)


@login_required
@require_POST
def add_to_wishlist(request):
    product_id = request.POST.get('id')
    user = request.user

    try:
        product = Product.objects.get(id=product_id)
        if Wishlist.objects.filter(product=product, user=user).exists():
            return JsonResponse({"bool": False, "message": "Product already in wishlist"})
        else:
            Wishlist.objects.create(product=product, user=user)
            return JsonResponse({"bool": True, "message": "Product added to wishlist"})
    except Product.DoesNotExist:
        return JsonResponse({"bool": False, "message": "Product not found"})


@login_required
def remove_from_wishlist(request, product_id):
    Wishlist.objects.filter(user=request.user, product_id=product_id).delete()
    return HttpResponseRedirect(request.META.get('HTTP_REFERER', '/'))



@require_POST
@login_required
def add_to_cart(request, pid):
    try:
        data = json.loads(request.body)
        product_id = data.get('product_id')
        variant_id = data.get('variant_id')
        selected_size = data.get('size')
        quantity = int(data.get('quantity', 1))

        product = get_object_or_404(Product, pid=product_id)
        cart, _ = Cart.objects.get_or_create(user=request.user, defaults={'total': Decimal('0.00')})

        # Variant Handling
        if variant_id:
            variant = get_object_or_404(ProductVariant, id=variant_id, product=product)
            size_option = variant.size_options.filter(size=selected_size).first()

            if not size_option:
                return JsonResponse({"success": False, "error": "Invalid size for variant"}, status=400)

            if size_option.stock_quantity < quantity:
                return JsonResponse({"success": False, "error": "Insufficient stock"}, status=400)

            cart_item, created = CartItem.objects.get_or_create(
                cart=cart,
                product=product,
                product_variant=variant,
                selected_size=selected_size,
                defaults={'quantity': quantity, 'line_total': size_option.price * quantity}
            )

            if not created:
                if cart_item.quantity + quantity > size_option.stock_quantity:
                    return JsonResponse({"success": False, "error": "Insufficient stock"}, status=400)
                cart_item.quantity += quantity
                cart_item.line_total = cart_item.quantity * size_option.price
                cart_item.save()

        # Main Product Handling
        else:
            size_option = None
            if selected_size:
                size_option = product.size_options.filter(size=selected_size).first()
                if not size_option:
                    return JsonResponse({"success": False, "error": "Invalid size for product"}, status=400)
                price_to_use = size_option.price
                stock_to_check = size_option.stock_quantity
            else:
                price_to_use = product.price
                stock_to_check = product.inventory.stock_quantity

            if stock_to_check < quantity:
                return JsonResponse({"success": False, "error": "Insufficient stock"}, status=400)

            cart_item, created = CartItem.objects.get_or_create(
                cart=cart,
                product=product,
                product_variant=None,
                selected_size=selected_size,
                defaults={'quantity': quantity, 'line_total': price_to_use * quantity}
            )

            if not created:
                if cart_item.quantity + quantity > stock_to_check:
                    return JsonResponse({"success": False, "error": "Insufficient stock"}, status=400)
                cart_item.quantity += quantity
                cart_item.line_total = cart_item.quantity * price_to_use
                cart_item.save()

        # Recalculate cart total
        cart.total = sum(item.line_total for item in cart.cartitem_set.all())
        cart.save()

        return JsonResponse({
            "success": True,
            "total_items": cart.cartitem_set.count(),
            "cart_total": float(cart.total)
        })

    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)


def remove_from_cart(request, item_id):
    try:
        if request.user.is_authenticated:
            item = get_object_or_404(CartItem, id=item_id, cart__user=request.user)
            cart = item.cart  # Get the related cart before deleting
            item.delete()

            # Recalculate and update the cart total
            cart.total = sum(i.line_total for i in cart.cartitem_set.all())
            cart.save()

            messages.success(request, "Item removed from cart.")
        else:
            messages.error(request, "You need to be logged in to remove items from the cart.")
    except CartItem.DoesNotExist:
        messages.error(request, "Item not found in cart.")

    return redirect('products:cart_view')  # or wherever your cart page is


@require_POST
def update_cart_item(request):
    data = json.loads(request.body)
    item_id = data['item_id']
    quantity = int(data['quantity'])

    cart_item = get_object_or_404(CartItem, id=item_id)
    cart_item.quantity = quantity

    # Handle variant and size-specific pricing correctly
    if cart_item.product_variant:
        if cart_item.selected_size:
            size_option = cart_item.product_variant.size_options.filter(size=cart_item.selected_size).first()
            if size_option:
                cart_item.line_total = size_option.price * Decimal(quantity)
            else:
                return JsonResponse({'success': False, 'error': 'Invalid size for variant'}, status=400)
        else:
            return JsonResponse({'success': False, 'error': 'Size not selected for variant'}, status=400)
    else:
        if cart_item.selected_size:
            size_option = cart_item.product.size_options.filter(size=cart_item.selected_size).first()
            if size_option:
                cart_item.line_total = size_option.price * Decimal(quantity)
            else:
                return JsonResponse({'success': False, 'error': 'Invalid size for product'}, status=400)
        else:
            cart_item.line_total = cart_item.product.price * Decimal(quantity)

    cart_item.save()

    cart = cart_item.cart
    cart.total = sum(item.line_total for item in cart.cartitem_set.all())
    cart.save()

    try:
        shipping = SiteSettings.objects.first().shipping_charge
    except AttributeError:
        shipping = Decimal('0.00')

    final_total = cart.total + shipping

    return JsonResponse({
        'success': True,
        'new_line_total': float(cart_item.line_total),
        'cart_total': float(cart.total),
        'shipping': float(shipping),
        'final_total': float(final_total)
    })

@login_required
def save_info(request):
    try:
        billing_address = BillingAddress.objects.filter(user=request.user).first()
        shipping_address = ShippingAddress.objects.filter(user=request.user).first()

        if request.method == 'POST':
            billing_form = BillingForm(request.POST, instance=billing_address)
            shipping_form = ShippingForm(request.POST, instance=shipping_address)

            if billing_form.is_valid() and shipping_form.is_valid():
                saved_billing = billing_form.save(commit=False)
                saved_billing.user = request.user
                saved_billing.save()

                saved_shipping = shipping_form.save(commit=False)
                saved_shipping.user = request.user
                saved_shipping.save()

                messages.success(request, "Billing and shipping information saved successfully.")
                return redirect('products:checkout')
            else:
                messages.error(request, "There was an error saving your information. Please try again.")
        else:
            billing_form = BillingForm(instance=billing_address)
            shipping_form = ShippingForm(instance=shipping_address)

        context = {
            'billing_form': billing_form,
            'shipping_form': shipping_form,
        }
        return render(request, 'checkout.html', context)
    except Exception as e:
        logger.error(f"Error in save_info process: {e}")
        messages.error(request, 'Error accessing the save info page. Please try again.')
        return redirect('home')

@login_required
@csrf_protect
def save_info(request):
    billing_address = BillingAddress.objects.filter(user=request.user).first()
    shipping_address = ShippingAddress.objects.filter(user=request.user).first()

    if request.method == 'POST':
        billing_form = BillingForm(request.POST, instance=billing_address)
        shipping_form = ShippingForm(request.POST, instance=shipping_address)

        if billing_form.is_valid() and shipping_form.is_valid():
            saved_billing = billing_form.save(commit=False)
            saved_billing.user = request.user
            saved_billing.save()

            saved_shipping = shipping_form.save(commit=False)
            saved_shipping.user = request.user
            saved_shipping.save()

            messages.success(request, "Billing and shipping information saved successfully.")
        else:
            messages.error(request, "There was an error saving your information. Please try again.")

    return redirect('products:checkout')

@login_required
@csrf_protect
def checkout(request):
    try:
        # Get or create cart for the logged-in user
        cart, _ = Cart.objects.get_or_create(user=request.user, defaults={'total': Decimal('0.00')})
        items = CartItem.objects.filter(cart=cart)

        if not items.exists():
            messages.error(request, "Your cart is empty. Please add items to your cart before proceeding to checkout.")
            return redirect('products:cart_view')

        billing_address = BillingAddress.objects.filter(user=request.user).first()
        shipping_address = ShippingAddress.objects.filter(user=request.user).first()

        # ✅ Calculate discount without altering cart.total directly
        discount = cart.apply_discount()
        shipping = SiteSettings.objects.first().shipping_charge if SiteSettings.objects.exists() else Decimal('0.00')
        final_total = cart.total - discount + shipping

        # ✅ Calculate unit price for display
        for item in items:
            item.unit_price = item.line_total / item.quantity if item.quantity > 0 else Decimal('0.00')

        if request.method == 'POST' and 'process_payment' in request.POST:
            try:
                amount = int(float(final_total) * 100)  # Razorpay expects amount in paise
                razorpay_order = client.order.create({
                    "amount": amount,
                    "currency": "INR",
                    "payment_capture": "1"
                })

                # Save order details in session
                request.session['razorpay_order_id'] = razorpay_order['id']
                request.session['amount'] = float(amount)

                context = {
                    'razorpay_order_id': razorpay_order['id'],
                    'razorpay_merchant_key': settings.RAZORPAY_KEY_ID,
                    'currency': 'INR',
                    'amount': amount,
                    'billing_address': billing_address,
                    'shipping_address': shipping_address,
                    'callback_url': reverse('products:process_order'),
                }
                return render(request, 'payment.html', context)

            except Exception as e:
                logger.error(f"Exception during Razorpay order creation: {e}")
                messages.error(request, "An error occurred during the payment process.")
                return redirect('products:checkout')

        # Prepare forms
        billing_form = BillingForm(instance=billing_address)
        shipping_form = ShippingForm(instance=shipping_address)

        # Prepare context
        context = {
            'cart': cart,
            'items': items,
            'total': cart.total,
            'discount': discount,
            'final_total': final_total,
            'shipping': shipping,
            'billing_form': billing_form,
            'shipping_form': shipping_form,
        }
        return render(request, 'checkout.html', context)

    except Exception as e:
        logger.error(f"Error in checkout process: {e}")
        messages.error(request, "Error loading checkout page.")
        return redirect('home')


@login_required
@csrf_protect
def process_order(request):
    if request.method == 'POST':
        payment_id = request.POST.get('razorpay_payment_id')
        razorpay_order_id = request.POST.get('razorpay_order_id')
        signature = request.POST.get('razorpay_signature')

        if not payment_id or not razorpay_order_id or not signature:
            messages.error(request, "Payment was canceled.")
            return redirect('products:cart_view')

        params_dict = {
            'razorpay_order_id': razorpay_order_id,
            'razorpay_payment_id': payment_id,
            'razorpay_signature': signature
        }

        try:
            client.utility.verify_payment_signature(params_dict)

            payment_details = client.payment.fetch(payment_id)
            payment_method = payment_details['method']

            user = request.user
            cart = Cart.objects.get(user=user)
            billing_address = BillingAddress.objects.filter(user=user).first()
            shipping_address = ShippingAddress.objects.filter(user=user).first()

            discount_amount = cart.apply_discount() if cart.discount_code else Decimal('0.00')
            discount_code_value = cart.discount_code.code if cart.discount_code else None

            with transaction.atomic():
                items = CartItem.objects.filter(cart=cart)

                for item in items:
                    if item.product_variant:
                        variant_size = item.product_variant.size_options.filter(size=item.selected_size).first()
                        if not variant_size or item.quantity > variant_size.stock_quantity:
                            messages.error(request, f"Insufficient stock for {item.product_variant.color} - {item.selected_size}.")
                            return redirect('products:cart_view')
                        price = variant_size.price
                    else:
                        if item.quantity > item.product.stock_quantity:
                            messages.error(request, f"Insufficient stock for {item.product.name}.")
                            return redirect('products:cart_view')
                        price = item.product.price

                order = Order.objects.create(
                    user=user,
                    billing_full_name=billing_address.billing_full_name,
                    billing_email=billing_address.billing_email,
                    billing_address1=billing_address.billing_address1,
                    billing_address2=billing_address.billing_address2,
                    billing_city=billing_address.billing_city,
                    billing_state=billing_address.billing_state,
                    billing_zipcode=billing_address.billing_zipcode,
                    billing_country=billing_address.billing_country,
                    billing_phone=billing_address.billing_phone,
                    shipping_full_name=shipping_address.shipping_full_name,
                    shipping_email=shipping_address.shipping_email,
                    shipping_address1=shipping_address.shipping_address1,
                    shipping_address2=shipping_address.shipping_address2,
                    shipping_city=shipping_address.shipping_city,
                    shipping_state=shipping_address.shipping_state,
                    shipping_zipcode=shipping_address.shipping_zipcode,
                    shipping_country=shipping_address.shipping_country,
                    shipping_phone=shipping_address.shipping_phone,
                    total=cart.total,
                    payment_method=payment_method,
                    discount=discount_amount,
                    discount_code=discount_code_value,
                )

                for item in items:
                    if item.product_variant:
                        variant_size = item.product_variant.size_options.filter(size=item.selected_size).first()
                        price = variant_size.price
                    else:
                        price = item.product.price

                    OrderItem.objects.create(
                        order=order,
                        product=item.product,
                        product_variant=item.product_variant,
                        user=user,
                        quantity=item.quantity,
                        price=price,
                        selected_size=item.selected_size
                    )

                    if item.product_variant:
                        variant_size.stock_quantity -= item.quantity
                        variant_size.save()
                    else:
                        item.product.stock_quantity -= item.quantity
                        item.product.save()

                    item.delete()

                cart.total = Decimal('0.00')
                cart.discount_code = None
                cart.save()

                send_order_email(request, order.id)

            messages.success(request, "Your order has been placed successfully.")
            return redirect('products:order_tracking')

        except razorpay.errors.SignatureVerificationError:
            messages.error(request, "Payment verification failed. Please try again.")
            return redirect('products:cart_view')
        except Exception as e:
            logger.error(f"Error placing order: {e}")
            messages.error(request, "An error occurred during the payment process.")
            return redirect('products:cart_view')

    return redirect('home')

@login_required
@csrf_protect
def place_order_cod(request):
    if request.method == 'POST':
        try:
            user = request.user
            cart = Cart.objects.get(user=user)
            items = CartItem.objects.filter(cart=cart)

            if not items.exists():
                messages.error(request, "Your cart is empty. Please add items before placing an order.")
                return redirect('products:checkout')

            billing_address = BillingAddress.objects.filter(user=user).first()
            shipping_address = ShippingAddress.objects.filter(user=user).first()

            discount_amount = cart.apply_discount() if cart.discount_code else Decimal('0.00')
            discount_code_value = cart.discount_code.code if cart.discount_code else None

            with transaction.atomic():
                for item in items:
                    if item.product_variant:
                        variant_size = item.product_variant.size_options.filter(size=item.selected_size).first()
                        if not variant_size or item.quantity > variant_size.stock_quantity:
                            messages.error(request, f"Insufficient stock for {item.product_variant.color} - {item.selected_size}.")
                            return redirect('products:cart_view')
                        price = variant_size.price
                    else:
                        if item.quantity > item.product.stock_quantity:
                            messages.error(request, f"Insufficient stock for {item.product.name}.")
                            return redirect('products:cart_view')
                        price = item.product.price

                order = Order.objects.create(
                    user=user,
                    billing_full_name=billing_address.billing_full_name,
                    billing_email=billing_address.billing_email,
                    billing_address1=billing_address.billing_address1,
                    billing_address2=billing_address.billing_address2,
                    billing_city=billing_address.billing_city,
                    billing_state=billing_address.billing_state,
                    billing_zipcode=billing_address.billing_zipcode,
                    billing_country=billing_address.billing_country,
                    billing_phone=billing_address.billing_phone,
                    shipping_full_name=shipping_address.shipping_full_name,
                    shipping_email=shipping_address.shipping_email,
                    shipping_address1=shipping_address.shipping_address1,
                    shipping_address2=shipping_address.shipping_address2,
                    shipping_city=shipping_address.shipping_city,
                    shipping_state=shipping_address.shipping_state,
                    shipping_zipcode=shipping_address.shipping_zipcode,
                    shipping_country=shipping_address.shipping_country,
                    shipping_phone=shipping_address.shipping_phone,
                    total=cart.total,
                    payment_method="Cash on Delivery",
                    status="pending",
                    discount=discount_amount,
                    discount_code=discount_code_value,
                )

                for item in items:
                    if item.product_variant:
                        variant_size = item.product_variant.size_options.filter(size=item.selected_size).first()
                        price = variant_size.price
                    else:
                        price = item.product.price

                    OrderItem.objects.create(
                        order=order,
                        product=item.product,
                        product_variant=item.product_variant,
                        user=user,
                        quantity=item.quantity,
                        price=price,
                        selected_size=item.selected_size
                    )

                    if item.product_variant:
                        variant_size.stock_quantity -= item.quantity
                        variant_size.save()
                    else:
                        item.product.stock_quantity -= item.quantity
                        item.product.save()

                    item.delete()

                cart.total = Decimal('0.00')
                cart.discount_code = None
                cart.save()

                send_order_email(request, order.id)

            messages.success(request, "Your order has been placed successfully under Cash on Delivery.")
            return redirect('products:order_tracking')

        except Exception as e:
            logger.error(f"Error placing COD order: {e}")
            messages.error(request, "An error occurred while placing your order. Please try again.")
            return redirect('products:checkout')

    return redirect('home')


@csrf_exempt
def razorpay_webhook(request):
    try:
        webhook_secret = settings.RAZORPAY_WEBHOOK_SECRET
        received_signature = request.headers.get('X-Razorpay-Signature')
        body = request.body

        # Signature validation
        generated_signature = hmac.new(
            webhook_secret.encode(),
            msg=body,
            digestmod=hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(received_signature, generated_signature):
            return HttpResponse(status=403)

        data = json.loads(body)
        event = data.get('event')

        if event == "payment.captured":
            payment_entity = data['payload']['payment']['entity']
            razorpay_order_id = payment_entity.get('order_id')
            payment_id = payment_entity.get('id')
            method = payment_entity.get('method')

            amount = Decimal(payment_entity.get('amount', 0)) / 100

            try:
                cart = Cart.objects.get(razorpay_order_id=razorpay_order_id)
                user = cart.user
                items = CartItem.objects.filter(cart=cart)

                billing_address = BillingAddress.objects.filter(user=user).first()
                shipping_address = ShippingAddress.objects.filter(user=user).first()

                with transaction.atomic():
                    for item in items:
                        if item.product_variant and item.quantity > item.product_variant.stock_quantity:
                            return HttpResponse("Insufficient stock", status=400)
                        elif not item.product_variant and item.quantity > item.product.stock_quantity:
                            return HttpResponse("Insufficient stock", status=400)

                    order = Order.objects.create(
                        user=user,
                        billing_full_name=billing_address.billing_full_name,
                        billing_email=billing_address.billing_email,
                        billing_address1=billing_address.billing_address1,
                        billing_address2=billing_address.billing_address2,
                        billing_city=billing_address.billing_city,
                        billing_state=billing_address.billing_state,
                        billing_zipcode=billing_address.billing_zipcode,
                        billing_country=billing_address.billing_country,
                        billing_phone=billing_address.billing_phone,
                        shipping_full_name=shipping_address.shipping_full_name,
                        shipping_email=shipping_address.shipping_email,
                        shipping_address1=shipping_address.shipping_address1,
                        shipping_address2=shipping_address.shipping_address2,
                        shipping_city=shipping_address.shipping_city,
                        shipping_state=shipping_address.shipping_state,
                        shipping_zipcode=shipping_address.shipping_zipcode,
                        shipping_country=shipping_address.shipping_country,
                        shipping_phone=shipping_address.shipping_phone,
                        total=cart.total,
                        payment_method=method
                    )

                    for item in items:
                        OrderItem.objects.create(
                            order=order,
                            product=item.product,
                            product_variant=item.product_variant if item.product_variant else None,
                            user=user,
                            quantity=item.quantity,
                            price=item.product_variant.price if item.product_variant else item.product.price
                        )

                        if item.product_variant:
                            item.product_variant.stock_quantity -= item.quantity
                            item.product_variant.save()
                        else:
                            item.product.stock_quantity -= item.quantity
                            item.product.save()

                        item.delete()

                    cart.total = Decimal('0.00')
                    cart.razorpay_order_id = None
                    cart.save()

                    send_order_email(request, order.id)

                    return HttpResponse(status=200)

            except Exception as e:
                return HttpResponse(f"Order processing error: {str(e)}", status=500)

        return HttpResponse(status=400)

    except Exception as e:
        return HttpResponse(f"Webhook error: {str(e)}", status=500)

@login_required
def check_payment_status(request):
    try:
        cart = Cart.objects.get(user=request.user)

        # Look for the latest order created with the cart's total
        order_exists = Order.objects.filter(user=request.user).order_by('-created_at').first()

        if order_exists and order_exists.total == cart.total:
            return JsonResponse({'status': 'completed'})

        return JsonResponse({'status': 'pending'})
    except:
        return JsonResponse({'status': 'error'})


def payment_failed(request):
    return render(request, 'products/payment_failed.html')  # Customize this template


@login_required
def send_order_email(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    items = OrderItem.objects.filter(order=order)
    billing_address = BillingAddress.objects.filter(user=request.user).first()
    shipping_address = BillingAddress.objects.filter(user=request.user).first()

    site_settings = SiteSettings.objects.first()
    shipping_charge = site_settings.shipping_charge if site_settings else Decimal('0.00')
    final_total = order.total + shipping_charge

    invoice_link = request.build_absolute_uri(reverse('products:order_invoice', args=[order.id]))

    subject = f" Your Order Confirmation with Stellars - Order #{order.id}"
    html_content = render_to_string('order_email.html', {
        'order': order,
        'items': items,
        'billing_address': billing_address,
        'shipping_address': shipping_address,
        'shipping_charge': shipping_charge,
        'final_total': final_total,
        'user': request.user,
        'invoice_link': invoice_link,  # Pass the invoice link to the email template

    })
    text_content = strip_tags(html_content)
    from_email = settings.DEFAULT_FROM_EMAIL
    to_email = ['stellarspvt@gmail.com', request.user.email]

    email = EmailMultiAlternatives(subject, text_content, from_email, to_email)
    email.attach_alternative(html_content, "text/html")
    email.send()

    return JsonResponse({'success': True, 'message': 'Email sent successfully'})



@login_required(login_url=reverse_lazy('accounts:login'))
def order_tracking(request):
    user_orders = Order.objects.filter(user=request.user)
    context = {'orders': user_orders}
    return render(request, 'order_tracking.html', context)

@csrf_exempt
def update_order_status(request):
    if request.method == 'POST':
        order_id = request.POST.get('order_id')
        status = request.POST.get('status')
        order = get_object_or_404(Order, id=order_id, user=request.user)
        order.status = status
        order.save()
        return JsonResponse({'success': True})
    return JsonResponse({'success': False})


def order_details(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    items = OrderItem.objects.filter(order=order)

    can_cancel = order.status in ['pending', 'processing', 'shipped']

    context = {
        'order': order,
        'items': items,
        'billing_address': {
            'full_name': order.billing_full_name,
            'email': order.billing_email,
            'address1': order.billing_address1,
            'address2': order.billing_address2,
            'city': order.billing_city,
            'state': order.billing_state,
            'zipcode': order.billing_zipcode,
            'country': order.billing_country,
            'phone': order.billing_phone,
        },
        'shipping_address': {
            'full_name': order.shipping_full_name,
            'email': order.shipping_email,
            'address1': order.shipping_address1,
            'address2': order.shipping_address2,
            'city': order.shipping_city,
            'state': order.shipping_state,
            'zipcode': order.shipping_zipcode,
            'country': order.shipping_country,
            'phone': order.shipping_phone,
        },
        'final_total': order.total,
        'user': request.user,
        'can_cancel': can_cancel,  # Pass the boolean to the template

    }
    return render(request, 'order_details.html', context)



@login_required
def order_invoice(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    items = OrderItem.objects.filter(order=order)

    for item in items:
        # Assign price for each item based on variant size
        if item.product_variant:
            variant_size = item.product_variant.size_options.filter(size=item.selected_size).first()
            item.unit_price = variant_size.price if variant_size else Decimal('0.00')
        else:
            item.unit_price = item.product.price

    discount = order.discount or Decimal('0.00')
    discount_code = order.discount_code or None

    # Get shipping charge from site settings
    shipping_charge = SiteSettings.objects.first().shipping_charge if SiteSettings.objects.exists() else Decimal('0.00')

    # Taxable amount based on 18% GST
    taxable_amount = order.total * Decimal('0.18')
    total_excluding = order.total - taxable_amount
    final_total = (order.total - discount) + shipping_charge

    # Determine if it's an interstate transaction
    shipping_state = order.shipping_state.strip().lower()
    is_interstate = shipping_state != "maharashtra"  # Replace with your business base state if different

    context = {
        'order': order,
        'items': items,
        'billing_address': {
            'full_name': order.billing_full_name,
            'email': order.billing_email,
            'address1': order.billing_address1,
            'address2': order.billing_address2,
            'city': order.billing_city,
            'state': order.billing_state,
            'zipcode': order.billing_zipcode,
            'country': order.billing_country,
            'phone': order.billing_phone,
        },
        'shipping_address': {
            'full_name': order.shipping_full_name,
            'email': order.shipping_email,
            'address1': order.shipping_address1,
            'address2': order.shipping_address2,
            'city': order.shipping_city,
            'state': order.shipping_state,
            'zipcode': order.shipping_zipcode,
            'country': order.shipping_country,
            'phone': order.shipping_phone,
        },
        'discount': discount,
        'discount_code': discount_code,
        'shipping_charge': shipping_charge,
        'taxable_amount': taxable_amount,
        'total_excluding': total_excluding,
        'final_total': final_total,
        'is_interstate': is_interstate,
    }

    return render(request, 'invoice_temp.html', context)


def request_order_cancel(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)

    if request.method == 'POST':
        # Process the cancellation form
        cancellation_reason = request.POST.get('cancellation_reason')
        other_text = request.POST.get('other_text', '').strip()
        reason = f"{cancellation_reason}: {other_text}" if cancellation_reason == "Other" and other_text else cancellation_reason

        if order.status in ['pending', 'processing', 'shipped']:
            order.status = 'cancelled'
            order.feedback_note = reason  # Save the cancellation reason
            order.cancel_requested = True
            order.save()

            send_order_cancellation_email(order, reason)

            messages.success(request, "Your order has been cancelled successfully.")
            return redirect('products:order_tracking')
        else:
            messages.error(request, "Order cannot be cancelled at this stage.")
            return redirect('products:order_details', order_id=order.id)

    # Display the cancellation form
    return render(request, 'order_cancel_form.html', {'order': order})

@login_required
def request_order_return(request, order_id):
    if request.method == 'POST':
        order = get_object_or_404(Order, id=order_id, user=request.user)
        return_deadline = order.updated_at + timedelta(days=7)

        # Check if the order is eligible for return
        if order.status == 'delivered' and order.updated_at <= return_deadline:
            order.return_requested = True
            order.status = 'returned'
            order.save()

            # Send email notifications
            return JsonResponse({'success': True, 'message': 'Return request processed successfully.'})
        else:
            return JsonResponse({'success': False, 'message': 'Return period has expired or order not delivered yet.'})
    else:
        return JsonResponse({'success': False, 'message': 'Invalid request method.'})



@login_required
def request_order_replace(request, order_id):
    if request.method == 'POST':
        order = get_object_or_404(Order, id=order_id, user=request.user)
        replace_deadline = order.updated_at + timedelta(days=7)

        # Check if the order is eligible for replacement
        if order.status == 'delivered' and order.updated_at <= replace_deadline:
            order.replace_requested = True
            order.status = 'replaced'
            order.save()

            # Send email notifications
            return JsonResponse({'success': True, 'message': 'Replacement request processed successfully.'})
        else:
            return JsonResponse({'success': False, 'message': 'Replacement period has expired or order not delivered yet.'})
    else:
        return JsonResponse({'success': False, 'message': 'Invalid request method.'})


@login_required
def request_order_complete(request, order_id):
    if request.method == 'POST':
        order = get_object_or_404(Order, id=order_id, user=request.user)

        # Check if order is eligible to be marked as complete
        if order.status == 'delivered':
            order.status = 'completed'  # Make sure this status is valid in your model
            order.save()
            return JsonResponse({'success': True, 'message': 'Order marked as complete successfully.'})
        else:
            return JsonResponse({'success': False, 'message': 'Order cannot be completed at this stage.'})
    else:
        return JsonResponse({'success': False, 'message': 'Invalid request method.'})


@login_required
def request_order_action(request, order_id, action):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    action_lower = action.lower()

    if request.method == 'POST':
        form = FeedbackForm(request.POST)
        if form.is_valid():
            feedback_note = form.cleaned_data['feedback_note']
            order.feedback_note = feedback_note

            # Process the return or replace actions
            if action_lower == 'return' and order.status == 'delivered':
                order.status = 'returned'
                order.return_requested = True
            elif action_lower == 'replace' and order.status == 'delivered':
                order.status = 'replaced'
                order.replace_requested = True
            else:
                messages.error(request, "Invalid action or order status.")
                return redirect('products:order_details', order_id=order.id)

            order.save()

            # Send feedback email to user and custom_admin with the action
            send_feedback_email(order, feedback_note, action_lower)

            messages.success(request, f"Your {action} request has been processed successfully.")
            return redirect('products:order_tracking')
    else:
        form = FeedbackForm()

    return render(request, 'order_feedback.html', {
        'form': form,
        'order': order,
        'action': action.capitalize(),
        'action_lower': action_lower,
    })



# send email when order is cancel return and replaced


def send_order_cancellation_email(order, reason):
    # Prepare email content for the user
    user_subject = "Your Order Has Been Cancelled"
    user_email_template = 'user_order_canceled.html'
    user_email_content = render_to_string(user_email_template, {
        'user': order.user,
        'order': order,
        'reason': reason,
    })

    # Prepare email content for the custom_admin
    admin_subject = "Order Cancellation Notification"
    admin_email_template = 'admin_order_canceled.html'
    admin_email_content = render_to_string(admin_email_template, {
        'user': order.user,
        'order': order,
        'reason': reason,
    })

    # Send email to the user
    send_mail(
        subject=user_subject,
        message="",
        html_message=user_email_content,
        from_email=settings.EMAIL_HOST_USER,
        recipient_list=[order.user.email],
        fail_silently=False,
    )

    # Send email to the custom_admin
    admin_email = settings.EMAIL_HOST_USER  # Admin's email address
    send_mail(
        subject=admin_subject,
        message="",
        html_message=admin_email_content,
        from_email=settings.EMAIL_HOST_USER,
        recipient_list=[admin_email],
        fail_silently=False,
    )


def send_feedback_email(order, feedback_note, action):
    action_capitalized = action.capitalize()

    # Determine subject and templates based on action
    if action == 'return':
        user_subject = f"Return Request Received for Order #{order.id}"
        admin_subject = f"New Return Request for Order #{order.id}"
        user_email_template = 'email/user_return_feedback.html'
        admin_email_template = 'email/admin_return_feedback.html'
    elif action == 'replace':
        user_subject = f"Replacement Request Received for Order #{order.id}"
        admin_subject = f"New Replacement Request for Order #{order.id}"
        user_email_template = 'email/user_replace_feedback.html'
        admin_email_template = 'email/admin_replace_feedback.html'
    else:
        user_subject = f"Feedback Received for Order #{order.id}"
        admin_subject = f"New Feedback for Order #{order.id}"
        user_email_template = 'email/user_feedback.html'
        admin_email_template = 'email/admin_feedback.html'

    # Render email content
    user_email_content = render_to_string(user_email_template, {
        'user': order.user,
        'order': order,
        'feedback_note': feedback_note,
        'action': action_capitalized,
    })
    user_text_content = strip_tags(user_email_content)

    admin_email_content = render_to_string(admin_email_template, {
        'user': order.user,
        'order': order,
        'feedback_note': feedback_note,
        'action': action_capitalized,
    })
    admin_text_content = strip_tags(admin_email_content)

    # Send email to the user
    send_mail(
        subject=user_subject,
        message=user_text_content,
        html_message=user_email_content,
        from_email=settings.EMAIL_HOST_USER,
        recipient_list=[order.user.email],
        fail_silently=False,
    )

    # Send email to the custom_admin
    admin_email = settings.EMAIL_HOST_USER  # Replace with actual custom_admin email if different
    send_mail(
        subject=admin_subject,
        message=admin_text_content,
        html_message=admin_email_content,
        from_email=settings.EMAIL_HOST_USER,
        recipient_list=[admin_email],
        fail_silently=False,
    )



def product_dashboard(request):
    return render(request, 'product_dashboard.html')


def product_services(request):
    return render(request, 'products-services.html')

def hyperdeckcontroller(request):
    return render(request, 'hyperdeckcontroller.html')

def about(request):
    about_content = About.objects.first()
    return render(request, 'about.html', {'about_content': about_content})

def delivery_info(request):
    return render(request, 'information/delivery_info.html')

def privacy_policy(request):
    return render(request, 'information/privacy_policy.html')

def return_refund(request):
    return render(request, 'information/return_refund.html')

def terms_condition(request):
    return render(request, 'information/terms_condition.html')


def faq(request):
    return render(request, 'information/faq.html')



def global_search_view(request):
    query = request.GET.get('q', '').strip().lower()

    if not query:
        return JsonResponse({'status': 'empty', 'message': 'Empty search query'}, status=400)

    product = Product.objects.filter(name__iexact=query).first()
    if product:
        return JsonResponse({'status': 'redirect', 'url': reverse('products:product_details', args=[product.pid])})

    main_category = MainCategory.objects.filter(title__iexact=query).first()
    if main_category:
        return JsonResponse({'status': 'redirect', 'url': reverse('products:product_grid_by_main_category', args=[main_category.cid])})

    sub_category = SubCategory.objects.filter(title__iexact=query).first()
    if sub_category:
        return JsonResponse({'status': 'redirect', 'url': reverse('products:product_grid_by_sub_category', args=[sub_category.sid])})

    blog = Blog.objects.filter(title__iexact=query).first()
    if blog:
        return JsonResponse({'status': 'redirect', 'url': blog.get_absolute_url()})

    static_pages = {
        'about us': reverse('products:about'),
        'terms and conditions': reverse('products:terms_condition'),
        'privacy policy': reverse('products:privacy_policy'),
        'return and refund': reverse('products:return_refund'),
        'delivery information': reverse('products:delivery_info'),
    }
    if query in static_pages:
        return JsonResponse({'status': 'redirect', 'url': static_pages[query]})

    if request.user.is_authenticated:
        try:
            order = Order.objects.get(user=request.user, id=int(query))
            return JsonResponse({'status': 'redirect', 'url': reverse('products:order_details', args=[order.id])})
        except (Order.DoesNotExist, ValueError):
            pass

    return JsonResponse({'status': 'not_found', 'message': 'No matching result found.'})


def claim_discount(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        phone = request.POST.get('phone')
        email = request.POST.get('email')

        coupon_code = 'WELCOME10'  # You can also randomize if needed

        # Save to Database
        DiscountLead.objects.create(
            name=name,
            phone=phone,
            email=email,
            coupon_code=coupon_code
        )

        # Prepare Email Content
        subject = '🎉 Here’s Your 10% OFF Coupon Code!'
        plain_message = f"""
Hello {name},

Thank you for signing up with us!

Here is your 10% OFF Coupon Code: {coupon_code}

Apply this code during checkout to enjoy your discount.

Happy Shopping!

- YourCompany Team
"""

        html_message = f"""
<html>
<body style="font-family: Arial, sans-serif; padding: 20px; background-color: #f4f4f4;">
  <div style="max-width: 600px; margin: auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
    <h2 style="color: #2E8B57;">Hello {name},</h2>
    <p style="font-size: 16px;">Thank you for signing up with us!</p>
    <p style="font-size: 18px; margin: 20px 0;">🎁 Your <strong>10% OFF Coupon Code</strong> is:</p>
    <div style="background: #2E8B57; color: white; padding: 15px; font-size: 24px; border-radius: 5px; letter-spacing: 2px; margin: 20px 0;">
      {coupon_code}
    </div>
    <p style="font-size: 16px;">Use this code at checkout and enjoy your discount!</p>
    <p style="font-size: 14px; color: #888; margin-top: 30px;">Happy Shopping!<br><strong>YourCompany Team</strong></p>
  </div>
</body>
</html>
"""

        from_email = settings.DEFAULT_FROM_EMAIL
        recipient_list = [email]

        try:
            send_mail(
                subject,
                plain_message,
                from_email,
                recipient_list,
                html_message=html_message
            )
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})

        # Optional: Set session so the discount is auto applied
        # request.session['applied_coupon_code'] = coupon_code

        return JsonResponse({'success': True})

    return JsonResponse({'success': False, 'error': 'Invalid request method'})

