# accounts/views.py
import openpyxl
from django.db.models import Sum, Count, Q
from django.views.decorators.http import require_POST
from products.models import MainCategory, SubCategory, Product, CartItem, Order, OrderItem, \
    ExtraImages, ProductVariant, VariantExtraImage, Cart, CartItem, \
    Wishlist, ShippingAddress, BillingAddress, BannerImage, About, SiteSettings, DiscountCode, VariantSizeOption
from accounts.models import User
from accounts.forms import UserRoleUpdateForm, ProfileForm, UserUpdateForm
from django.http import FileResponse

from blog.models import Blog
from django.contrib.admin.views.decorators import staff_member_required
from datetime import datetime, timedelta, date, timezone
from django.http import JsonResponse
from django.utils.timezone import make_aware, localtime
from django.contrib.admin.models import LogEntry
from django.db.models.functions import TruncDay, TruncMonth
from django.db.models.functions import ExtractWeek, ExtractYear

from django.utils.timezone import now
from django.db import models  # Import the models module
from custom_admin.utils import get_recent_actions_ut  # Ensure you have this function to fetch recent actions
from custom_admin.forms import DateRangeForm, MainCategoryForm, SubCategoryForm, \
    ProductForm, ExtraImagesFormSet, ProductVariantForm, VariantExtraImageForm, \
    OrderForm, CartForm, WishlistForm, VariantSizeOptionFormSet, VariantExtraImageFormSet, \
    BlogForm, BannerImageForm, CustomerForm, ProfileForm, AboutForm, SiteSettingsForm, DiscountCodeForm
from django.contrib.auth.decorators import user_passes_test
from django.shortcuts import get_object_or_404, redirect, render
from django.forms import modelformset_factory
from django.db import transaction
from django.forms import inlineformset_factory
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from PIL import Image, ImageDraw, ImageFont
import barcode
from barcode.writer import ImageWriter
import io
import pandas as pd
import os
from django.conf import settings
from django.contrib import messages
from django.core.files import File
from django.core.files.images import ImageFile
from django.utils.text import slugify
import json
import openpyxl
from django.http import HttpResponse
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from io import BytesIO
from products.models import ProductVariant, VariantSizeOption
from reportlab.graphics.barcode import code128
import zipfile

import datetime


def is_admin(user):
    return user.is_superuser


@staff_member_required
def dashboard(request):
    # Default date range (current month)
    today = now()
    default_start_date = today.replace(day=1).date()  # Convert to date
    default_end_date = today.date()  # Convert to date

    # Process the date filter form
    form = DateRangeForm(request.GET or None)
    start_date = default_start_date
    end_date = default_end_date

    if form.is_valid():
        start_date = form.cleaned_data.get('start_date') or default_start_date
        end_date = form.cleaned_data.get('end_date') or default_end_date

    start_date = make_aware(datetime.datetime.combine(start_date, datetime.time.min))
    end_date = make_aware(datetime.datetime.combine(end_date, datetime.time.max))

    # Total sales (sum of all orders' totals) within the date range
    total_sales = Order.objects.filter(status='completed', created_at__range=(start_date, end_date)) \
        .aggregate(Sum('total'))['total__sum'] or 0.00

    # Total orders count within the date range
    total_orders = Order.objects.filter(created_at__range=(start_date, end_date)).count()

    # Payment methods breakdown
    payment_methods = Order.objects.filter(created_at__range=(start_date, end_date)) \
        .values('payment_method').annotate(count=Count('payment_method'))

    # Total products count
    total_products = Product.objects.count()
    total_variants = ProductVariant.objects.count()

    # Products in cart
    products_in_cart = CartItem.objects.aggregate(total=Sum('quantity'))['total'] or 0

    # Canceled orders count within the date range
    canceled_orders = Order.objects.filter(status='cancelled', created_at__range=(start_date, end_date)).count()

    # Returned orders count within the date range
    returned_orders = Order.objects.filter(status='returned', created_at__range=(start_date, end_date)).count()

    # Replaced orders count within the date range
    replaced_orders = Order.objects.filter(status='replaced', created_at__range=(start_date, end_date)).count()

    # Total customers
    total_customers = User.objects.filter(is_staff=False).count()

    # Total blogs
    total_blogs = Blog.objects.count()

    # Recent orders
    recent_orders = Order.objects.select_related('user').order_by('-created_at')[:10]

    # Recent actions (custom utility function to fetch admin actions)
    recent_actions = get_recent_actions(request)

    context = {
        'form': form,
        'total_sales': total_sales,
        'total_orders': total_orders,
        'payment_methods': payment_methods,  # List of payment methods with counts
        'total_products': total_products,
        'products_in_cart': products_in_cart,
        'canceled_orders': canceled_orders,
        'returned_orders': returned_orders,
        'replaced_orders': replaced_orders,
        'total_customers': total_customers,
        'total_blogs': total_blogs,
        'recent_orders': recent_orders,
        'recent_actions': recent_actions,
        'total_variants': total_variants,

    }

    return render(request, 'custom_admin/dashboard.html', context)


from django.utils.timezone import localdate

def weekly_order_data(request):
    current_year = now().year

    orders = (
        Order.objects
        .annotate(
            week=ExtractWeek('created_at'),
            year=ExtractYear('created_at')
        )
        .filter(year=current_year)
        .values('week')
        .annotate(total=Count('id'))
        .order_by('week')
    )

    labels = []
    data = []

    for entry in orders:
        labels.append(f"Week {entry['week']}")
        data.append(entry['total'])

    return JsonResponse({'labels': labels, 'data': data})


def daily_sales_data(request):
    today = now().date()
    last_7_days = [today - timedelta(days=i) for i in range(6, -1, -1)]
    labels = [day.strftime("%A") for day in last_7_days]
    data = []

    for day in last_7_days:
        start = make_aware(datetime.datetime.combine(day, datetime.datetime.min.time()))
        end = make_aware(datetime.datetime.combine(day, datetime.datetime.max.time()))
        total = Order.objects.filter(status='completed', created_at__range=(start, end)).aggregate(Sum('total'))['total__sum'] or 0
        data.append(total)

    return JsonResponse({'labels': labels, 'data': data})



def monthly_sales_data(request):
    current_year = now().year
    labels = ["January", "February", "March", "April", "May", "June",
              "July", "August", "September", "October", "November", "December"]
    data = {month: 0 for month in labels}

    orders = Order.objects.filter(created_at__year=current_year) \
                .annotate(month=TruncMonth('created_at')) \
                .values('month') \
                .annotate(total=Sum('total'))

    for order in orders:
        month_label = order['month'].strftime("%B")
        data[month_label] = float(order['total'])

    return JsonResponse({'labels': labels, 'data': list(data.values())})


def generate_excel_report(labels, data, report_title):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = report_title

    ws.append([report_title])
    ws.append(['Date/Period', 'Value'])

    for label, value in zip(labels, data):
        ws.append([label, value])

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    filename = f"{report_title.replace(' ', '_').lower()}.xlsx"
    response['Content-Disposition'] = f'attachment; filename={filename}'
    wb.save(response)
    return response


def download_weekly_order_report(request):
    response = weekly_order_data(request)
    data_response = json.loads(response.content)
    return generate_excel_report(data_response['labels'], data_response['data'], 'Weekly Order Report')


def download_daily_sales_report(request):
    response = daily_sales_data(request)
    data_response = json.loads(response.content)
    return generate_excel_report(data_response['labels'], data_response['data'], 'Daily Sales Report')


def download_monthly_sales_report(request):
    response = monthly_sales_data(request)
    data_response = json.loads(response.content)
    return generate_excel_report(data_response['labels'], data_response['data'], 'Monthly Sales Report')

def get_recent_actions(request):
    # Fetch the 10 most recent log entries
    recent_actions = LogEntry.objects.select_related('content_type', 'user').order_by('-action_time')[:10]

    # Prepare the data for rendering
    actions = []
    for entry in recent_actions:
        actions.append({
            'object_repr': entry.object_repr,  # Object name
            'action_flag': entry.get_action_flag_display(),  # Action type (Add, Change, Delete)
            'content_type': entry.content_type.name,  # Content type (e.g., Order, Product)
            'user': entry.user.username,  # User who performed the action
            'action_time': localtime(entry.action_time),  # Localized action time
        })

    return actions


@staff_member_required
def main_categories_view(request):
    main_categories = MainCategory.objects.all()
    return render(request, 'custom_admin/products/main_categories.html', {'main_categories': main_categories})


def add_main_category_view(request):
    if request.method == 'POST':
        form = MainCategoryForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return redirect('custom_admin:main_categories')
    else:
        form = MainCategoryForm()
    return render(request, 'custom_admin/products/add_main_category.html', {'form': form})


def edit_main_category_view(request, pk):
    category = get_object_or_404(MainCategory, pk=pk)
    if request.method == 'POST':
        form = MainCategoryForm(request.POST, request.FILES, instance=category)
        if form.is_valid():
            form.save()
            return redirect('custom_admin:main_categories')
    else:
        form = MainCategoryForm(instance=category)
    return render(request, 'custom_admin/products/edit_main_category.html', {'form': form, 'category': category})


def delete_main_category_view(request, pk):
    category = get_object_or_404(MainCategory, pk=pk)
    if request.method == 'POST':
        category.delete()
        return redirect('custom_admin:main_categories')
    return render(request, 'custom_admin/products/delete_main_category.html', {'category': category})


def subcategories_view(request):
    subcategories = SubCategory.objects.all()
    return render(request, 'custom_admin/products/subcategories.html', {'subcategories': subcategories})


def add_subcategory_view(request):
    if request.method == 'POST':
        form = SubCategoryForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return redirect('custom_admin:subcategories')
    else:
        form = SubCategoryForm()
    return render(request, 'custom_admin/products/add_subcategory.html', {'form': form})


def edit_subcategory_view(request, pk):
    subcategory = get_object_or_404(SubCategory, pk=pk)
    if request.method == 'POST':
        form = SubCategoryForm(request.POST, request.FILES, instance=subcategory)
        if form.is_valid():
            form.save()
            return redirect('custom_admin:subcategories')
    else:
        form = SubCategoryForm(instance=subcategory)
    return render(request, 'custom_admin/products/edit_subcategory.html', {'form': form, 'subcategory': subcategory})


def delete_subcategory_view(request, pk):
    subcategory = get_object_or_404(SubCategory, pk=pk)
    if request.method == 'POST':
        subcategory.delete()
        return redirect('custom_admin:subcategories')
    return render(request, 'custom_admin/products/delete_subcategory.html', {'subcategory': subcategory})


@staff_member_required
def upload_main_categories_view(request):
    if request.method == 'POST' and request.FILES.get('excel_file'):
        excel_file = request.FILES['excel_file']
        df = pd.read_excel(excel_file)

        created_count = 0
        for _, row in df.iterrows():
            title = str(row.get('Title')).strip()
            price = row.get('Price') or 0.00

            # Safely skip image if not provided or invalid
            image_filename = row.get('Image') if 'Image' in row else None

            if image_filename and isinstance(image_filename, str) and image_filename.strip():
                image_path = os.path.join(settings.MEDIA_ROOT, 'uploads/categories', image_filename.strip())
                if os.path.exists(image_path):
                    with open(image_path, 'rb') as img_file:
                        image = ImageFile(img_file, name=image_filename.strip())
                        MainCategory.objects.create(title=title, price=price, image=image)
                        created_count += 1
                else:
                    # Skip image but create category without image
                    MainCategory.objects.create(title=title, price=price)
                    messages.warning(request, f"Image not found for category '{title}', created without image.")
                    created_count += 1
            else:
                # No image provided, just create the category
                MainCategory.objects.create(title=title, price=price)
                created_count += 1

        messages.success(request, f"{created_count} main categories uploaded successfully.")
        return redirect('custom_admin:main_categories')

    return render(request, 'custom_admin/products/upload_main_categories.html')

@staff_member_required
def upload_subcategories_view(request):
    if request.method == 'POST' and request.FILES.get('excel_file'):
        excel_file = request.FILES['excel_file']
        df = pd.read_excel(excel_file)

        created_count = 0
        for _, row in df.iterrows():
            main_category_title = str(row.get('Main Category Title')).strip()
            title = str(row.get('Title')).strip()
            price = row.get('Price') or 0.00
            name = str(row.get('Name') or '').strip()
            image_filename = row.get('Image') if 'Image' in row else None

            try:
                main_category = MainCategory.objects.get(title__iexact=main_category_title)
            except MainCategory.DoesNotExist:
                messages.warning(request, f"Main category '{main_category_title}' not found. Skipping '{title}'.")
                continue

            # Handle optional image
            if image_filename and isinstance(image_filename, str) and image_filename.strip():
                image_path = os.path.join(settings.MEDIA_ROOT, 'uploads/categories', image_filename.strip())
                if os.path.exists(image_path):
                    with open(image_path, 'rb') as img_file:
                        image = ImageFile(img_file, name=image_filename.strip())
                        SubCategory.objects.create(
                            main_category=main_category,
                            title=title,
                            price=price,
                            name=name,
                            image=image
                        )
                        created_count += 1
                else:
                    # Create without image if not found
                    SubCategory.objects.create(
                        main_category=main_category,
                        title=title,
                        price=price,
                        name=name
                    )
                    messages.warning(request, f"Image not found for subcategory '{title}', created without image.")
                    created_count += 1
            else:
                # Create without image if not provided
                SubCategory.objects.create(
                    main_category=main_category,
                    title=title,
                    price=price,
                    name=name
                )
                created_count += 1

        messages.success(request, f"{created_count} subcategories uploaded successfully.")
        return redirect('custom_admin:subcategories')

    return render(request, 'custom_admin/products/upload_subcategories.html')


def product_list_view(request):
    products = Product.objects.all()
    return render(request, 'custom_admin/products/product_list.html', {'products': products})


def add_product_view(request):
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES)
        formset = ExtraImagesFormSet(request.POST, request.FILES, instance=form.instance)

        if form.is_valid() and formset.is_valid():
            with transaction.atomic():  # Ensure atomicity
                product = form.save()
                formset.instance = product
                formset.save()
            return redirect('custom_admin:product_list')
        else:
            print(form.errors, formset.errors)  # Debug errors
    else:
        form = ProductForm()
        formset = ExtraImagesFormSet()

    return render(
        request,
        'custom_admin/products/add_product.html',
        {'form': form, 'formset': formset}
    )


def edit_product_view(request, pk):
    product = get_object_or_404(Product, pk=pk)

    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES, instance=product)
        formset = ExtraImagesFormSet(request.POST, request.FILES, instance=product)

        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                product = form.save()  # Save the product
                formset.instance = product  # Associate extra images with this product
                formset.save()  # Save all extra images
            return redirect('custom_admin:product_list')
        else:
            print("Form errors:", form.errors)
            print("Formset errors:", formset.errors)
    else:
        form = ProductForm(instance=product)
        formset = ExtraImagesFormSet(instance=product)

    return render(
        request,
        'custom_admin/products/edit_product.html',
        {'form': form, 'formset': formset, 'product': product}
    )


def delete_product_view(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if request.method == 'POST':
        product.delete()
        return redirect('custom_admin:product_list')
    return render(request, 'custom_admin/products/delete_product.html', {'product': product})


def variant_list_view(request):
    variants = ProductVariant.objects.all().prefetch_related('size_options')

    for variant in variants:
        variant.total_stock = sum(option.stock_quantity for option in variant.size_options.all())

    return render(request, 'custom_admin/products/variant_list.html', {
        'variants': variants
    })

@staff_member_required
def upload_products_view(request):
    if request.method == 'POST' and request.FILES.get('excel_file'):
        excel_file = request.FILES['excel_file']

        try:
            df = pd.read_excel(excel_file)
        except Exception as e:
            messages.error(request, f"Failed to read Excel file: {e}")
            return redirect('custom_admin:product_list')

        created_count = 0
        error_logs = []

        for index, row in df.iterrows():
            try:
                # Read both possible header variants
                main_category_title = str(row.get('Main Category Title') or row.get('Main Category') or '').strip()
                sub_category_title = str(row.get('Subcategory Title') or row.get('Sub Category') or '').strip()

                # DEBUG: Show row data in console
                print(f"Processing Row {index + 2}: {row.to_dict()}")
                print(f"Extracted Main Category: {main_category_title}, Sub Category: {sub_category_title}")

                if not main_category_title:
                    error_logs.append(f"Row {index + 2}: Missing Main Category.")
                    continue

                if not sub_category_title:
                    error_logs.append(f"Row {index + 2}: Missing Sub Category.")
                    continue

                # Fetch related objects
                try:
                    main_category = MainCategory.objects.get(title__iexact=main_category_title)
                except MainCategory.DoesNotExist:
                    error_logs.append(f"Row {index + 2}: Main category '{main_category_title}' not found.")
                    continue

                try:
                    sub_category = SubCategory.objects.get(title__iexact=sub_category_title, main_category=main_category)
                except SubCategory.DoesNotExist:
                    error_logs.append(f"Row {index + 2}: Subcategory '{sub_category_title}' not found under '{main_category_title}'.")
                    continue

                # Create Product
                product = Product.objects.create(
                    user=request.user,
                    name=row.get('Product Name', '').strip(),
                    title=row.get('Product Title', '').strip(),
                    description=row.get('Description', '').strip(),
                    specification=row.get('Specification', '').strip(),
                    main_category=main_category,
                    sub_category=sub_category,
                    product_status=row.get('Product Status', '').strip(),
                    status=bool(int(row.get('Status (1/0)', 0))),
                    in_stock=bool(int(row.get('In Stock (1/0)', 0))),
                    featured=bool(int(row.get('Featured (1/0)', 0))),
                )

                created_count += 1

            except Exception as e:
                error_logs.append(f"Row {index + 2}: Unexpected error - {e}")

        # Log all messages
        if error_logs:
            for log in error_logs:
                messages.warning(request, log)

        if created_count > 0:
            messages.success(request, f"{created_count} products uploaded successfully.")
        else:
            messages.error(request, "No products were added. Please check your file for errors.")

        return redirect('custom_admin:product_list')

    return render(request, 'custom_admin/products/upload_products.html')

def add_variant_view(request):
    if request.method == 'POST':
        form = ProductVariantForm(request.POST, request.FILES)
        size_formset = VariantSizeOptionFormSet(request.POST)
        image_formset = VariantExtraImageFormSet(request.POST, request.FILES)

        if form.is_valid() and size_formset.is_valid() and image_formset.is_valid():
            variant = form.save()
            size_formset.instance = variant
            size_formset.save()
            image_formset.instance = variant
            image_formset.save()
            return redirect('custom_admin:variant_list')
    else:
        form = ProductVariantForm()
        size_formset = VariantSizeOptionFormSet()
        image_formset = VariantExtraImageFormSet()

    return render(request, 'custom_admin/products/add_variant.html', {
        'form': form,
        'size_formset': size_formset,
        'image_formset': image_formset
    })


@staff_member_required
def edit_variant_view(request, pk):
    variant = get_object_or_404(ProductVariant, pk=pk)

    if request.method == 'POST':
        form = ProductVariantForm(request.POST, request.FILES, instance=variant)
        size_formset = VariantSizeOptionFormSet(request.POST, instance=variant)
        image_formset = VariantExtraImageFormSet(request.POST, request.FILES, instance=variant)

        if form.is_valid() and size_formset.is_valid() and image_formset.is_valid():
            form.save()
            size_formset.save()
            image_formset.save()
            return redirect('custom_admin:variant_list')
    else:
        form = ProductVariantForm(instance=variant)
        size_formset = VariantSizeOptionFormSet(instance=variant)
        image_formset = VariantExtraImageFormSet(instance=variant)

    return render(request, 'custom_admin/products/edit_variant.html', {
        'form': form,
        'size_formset': size_formset,
        'image_formset': image_formset,
        'variant': variant,
    })



def delete_variant_view(request, pk):
    variant = get_object_or_404(ProductVariant, pk=pk)
    if request.method == 'POST':
        variant.delete()
        return redirect('custom_admin:variant_list')
    return render(request, 'custom_admin/products/delete_variant.html', {'variant': variant})

@staff_member_required
def upload_variants_view(request):
    if request.method == 'POST' and request.FILES.get('excel_file'):
        excel_file = request.FILES['excel_file']
        try:
            df = pd.read_excel(excel_file)
        except Exception as e:
            messages.error(request, f"Failed to read Excel file: {e}")
            return redirect('custom_admin:variant_list')

        created_count = 0
        error_logs = []

        for index, row in df.iterrows():
            try:
                sku = str(row.get('Product SKU')).strip()
                color = str(row.get('Color')).strip()
                gender = str(row.get('Gender')).strip()
                size = str(row.get('Size')).strip()
                price = row.get('Price')
                old_price = row.get('Old Price', None)
                stock_quantity = int(row.get('Stock Quantity', 0))
                image_filename = str(row.get('Variant Image')).strip()

                # Validate and fetch the product
                try:
                    product = Product.objects.get(sku__iexact=sku)
                except Product.DoesNotExist:
                    error_logs.append(f"Row {index + 2}: Product with SKU '{sku}' not found.")
                    continue

                # Load variant image or dummy image
                variant_image = None
                image_dir = os.path.join(settings.MEDIA_ROOT, 'variants')
                image_path = os.path.join(image_dir, image_filename)
                dummy_path = os.path.join(image_dir, 'dummy.jpg')

                if image_filename and os.path.exists(image_path):
                    with open(image_path, 'rb') as img_file:
                        image_content = img_file.read()
                        variant_image = ImageFile(io.BytesIO(image_content), name=image_filename)
                elif os.path.exists(dummy_path):
                    with open(dummy_path, 'rb') as img_file:
                        image_content = img_file.read()
                        variant_image = ImageFile(io.BytesIO(image_content), name='dummy.jpg')
                else:
                    error_logs.append(f"Row {index + 2}: Dummy image not found at {dummy_path}")
                    continue

                # Create Variant
                variant = ProductVariant.objects.create(
                    product=product,
                    color=color,
                    gender=gender,
                    image=variant_image
                )

                # Create Size Option
                VariantSizeOption.objects.create(
                    variant=variant,
                    size=size,
                    price=price,
                    old_price=old_price if not pd.isna(old_price) else None,
                    stock_quantity=stock_quantity
                )

                created_count += 1

            except Exception as e:
                error_logs.append(f"Row {index + 2}: Unexpected error - {e}")

        # Show errors and success messages
        if error_logs:
            for log in error_logs:
                messages.warning(request, log)

        if created_count > 0:
            messages.success(request, f"{created_count} variants and size options uploaded successfully.")
        else:
            messages.error(request, "No variants were added. Please check your file for errors.")

        return redirect('custom_admin:variant_list')

    return render(request, 'custom_admin/products/upload_variants.html')



def generate_variant_label(request, variant_id, size):
    from products.models import ProductVariant, VariantSizeOption

    try:
        variant = ProductVariant.objects.get(vid=variant_id)
        size_option = variant.size_options.get(size=size)
    except (ProductVariant.DoesNotExist, VariantSizeOption.DoesNotExist):
        return HttpResponse("Variant or size not found.", status=404)

    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=(70 * mm, 38 * mm))

    # Header
    c.setFont("Helvetica-Bold", 8)
    c.drawString(10, 95, "BAG LABEL")
    c.drawString(120, 95, "CONVERSION")

    # Basic Info
    c.setFont("Helvetica", 7)
    c.drawString(10, 85, variant.vid.upper())
    c.drawString(120, 85, "BAG")
    c.drawString(10, 70, "2274")
    c.drawString(160, 70, "11118454")

    # Draw Barcode (directly on canvas)
    barcode = code128.Code128(variant.vid.upper(), barHeight=20, barWidth=0.6)
    barcode.drawOn(c, 10, 45)

    # SKU, Price, Color, Size
    c.setFont("Helvetica", 7)
    c.drawString(10, 35, f"M.R.P. ₹ :- {size_option.price}")
    c.drawString(100, 35, "COLOUR")
    c.drawString(160, 35, "SIZE")
    c.drawString(10, 25, "Pkt. Dt. Apr-24")
    c.drawString(100, 25, variant.color.upper())
    c.drawString(160, 25, size.upper())

    c.showPage()
    c.save()
    buffer.seek(0)

    return FileResponse(buffer, as_attachment=True, filename=f"{variant.vid}_{size}.pdf")


def generate_all_variant_labels(request):
    buffer = BytesIO()
    zip_buffer = zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED)

    for variant in ProductVariant.objects.prefetch_related('size_options').all():
        for size_option in variant.size_options.all():
            # Generate PDF
            pdf_stream = BytesIO()
            c = canvas.Canvas(pdf_stream, pagesize=(70 * mm, 38 * mm))

            c.setFont("Helvetica-Bold", 8)
            c.drawString(10, 95, "BAG LABEL")
            c.drawString(120, 95, "CONVERSION")

            c.setFont("Helvetica", 7)
            c.drawString(10, 85, variant.vid.upper())
            c.drawString(120, 85, "BAG")
            c.drawString(10, 70, "2274")
            c.drawString(160, 70, "11118454")

            # Barcode
            barcode = code128.Code128(variant.vid.upper(), barHeight=20, barWidth=0.6)
            barcode.drawOn(c, 10, 45)

            # SKU, Price, Color, Size
            c.drawString(10, 35, f"M.R.P. ₹ :- {size_option.price}")
            c.drawString(100, 35, "COLOUR")
            c.drawString(160, 35, "SIZE")
            c.drawString(10, 25, "Pkt. Dt. Apr-24")
            c.drawString(100, 25, variant.color.upper())
            c.drawString(160, 25, size_option.size.upper())

            c.showPage()
            c.save()
            pdf_stream.seek(0)

            # Add to zip
            filename = f"{variant.vid}_{size_option.size}.pdf"
            zip_buffer.writestr(filename, pdf_stream.getvalue())

    zip_buffer.close()
    buffer.seek(0)

    response = HttpResponse(buffer, content_type='application/zip')
    response['Content-Disposition'] = 'attachment; filename=all_variant_tags.zip'
    return response
# Order List View

def order_list_view(request):
    orders = Order.objects.all()
    query = request.GET.get('user')
    status = request.GET.get('status')
    date = request.GET.get('date')

    if query:
        orders = orders.filter(user__username__icontains=query)

    if status:
        orders = orders.filter(status=status)

    if date:
        try:
            date_obj = datetime.datetime.strptime(date, '%Y-%m-%d').date()
            orders = orders.filter(created_at__date=date_obj)
        except ValueError:
            pass  # Invalid date, ignore the filter

    # Calculate final_total for display
    for order in orders:
        order.final_total = order.total - order.discount if order.discount else order.total

    statuses = Order.STATUS_CHOICES

    return render(request, 'custom_admin/order/order_list.html', {
        'orders': orders,
        'statuses': statuses,
    })
# Add Order View
def add_order_view(request):
    if request.method == 'POST':
        form = OrderForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('custom_admin:order_list')
    else:
        form = OrderForm()
    return render(request, 'custom_admin/order/add_order.html', {'form': form})


# Edit Order View
def edit_order_view(request, pk):
    order = get_object_or_404(Order, pk=pk)
    if request.method == 'POST':
        form = OrderForm(request.POST, instance=order)
        if form.is_valid():
            form.save()
            return redirect('custom_admin:order_list')
    else:
        form = OrderForm(instance=order)
    return render(request, 'custom_admin/order/edit_order.html', {'form': form, 'order': order})


# Delete Order View
def delete_order_view(request, pk):
    order = get_object_or_404(Order, pk=pk)
    if request.method == 'POST':
        order.delete()
        return redirect('custom_admin:order_list')
    return render(request, 'custom_admin/order/delete_order.html', {'order': order})


def cart_list_view(request):
    carts = Cart.objects.all()
    return render(request, 'custom_admin/order/cart_list.html', {'carts': carts})


def add_cart_view(request):
    if request.method == 'POST':
        form = CartForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('custom_admin:cart_list')
    else:
        form = CartForm()
    return render(request, 'custom_admin/order/add_cart.html', {'form': form})


def edit_cart_view(request, pk):
    cart = get_object_or_404(Cart, pk=pk)
    if request.method == 'POST':
        form = CartForm(request.POST, instance=cart)
        if form.is_valid():
            form.save()
            return redirect('custom_admin:cart_list')
    else:
        form = CartForm(instance=cart)
    return render(request, 'custom_admin/order/edit_cart.html', {'form': form, 'cart': cart})


def delete_cart_view(request, pk):
    cart = get_object_or_404(Cart, pk=pk)
    if request.method == 'POST':
        cart.delete()
        return redirect('custom_admin:cart_list')
    return render(request, 'custom_admin/order/delete_cart.html', {'cart': cart})


def wishlist_list_view(request):
    wishlists = Wishlist.objects.all()
    return render(request, 'custom_admin/order/wishlist_list.html', {'wishlists': wishlists})

# Add View
def add_wishlist_view(request):
    if request.method == 'POST':
        form = WishlistForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('custom_admin:wishlist_list')
    else:
        form = WishlistForm()
    return render(request, 'custom_admin/order/add_wishlist.html', {'form': form})

# Edit View
def edit_wishlist_view(request, pk):
    wishlist = get_object_or_404(Wishlist, pk=pk)
    if request.method == 'POST':
        form = WishlistForm(request.POST, instance=wishlist)
        if form.is_valid():
            form.save()
            return redirect('custom_admin:wishlist_list')
    else:
        form = WishlistForm(instance=wishlist)
    return render(request, 'custom_admin/order/edit_wishlist.html', {'form': form, 'wishlist': wishlist})


# Delete View
def delete_wishlist_view(request, pk):
    wishlist = get_object_or_404(Wishlist, pk=pk)
    if request.method == 'POST':
        wishlist.delete()
        return redirect('custom_admin:wishlist_list')
    return render(request, 'custom_admin/order/delete_wishlist.html', {'wishlist': wishlist})


def user_addresses_view(request, user_id):
    # Fetch user
    user = get_object_or_404(User, id=user_id)

    # Fetch user's shipping and billing addresses
    shipping_addresses = ShippingAddress.objects.filter(user=user)
    billing_addresses = BillingAddress.objects.filter(user=user)

    context = {
        'user': user,
        'shipping_addresses': shipping_addresses,
        'billing_addresses': billing_addresses
    }

    return render(request, 'custom_admin/order/user_addresses.html', context)


# Blog List View
def blog_list_view(request):
    blogs = Blog.objects.all()
    return render(request, 'custom_admin/order/blog_list.html', {'blogs': blogs})

def add_blog_view(request):
    if request.method == 'POST':
        form = BlogForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return redirect('custom_admin:blog_list')
    else:
        form = BlogForm()
    return render(request, 'custom_admin/order/add_blog.html', {'form': form})

def edit_blog_view(request, pk):
    blog = get_object_or_404(Blog, pk=pk)
    if request.method == 'POST':
        form = BlogForm(request.POST, request.FILES, instance=blog)
        if form.is_valid():
            form.save()
            return redirect('custom_admin:blog_list')
    else:
        form = BlogForm(instance=blog)
    return render(request, 'custom_admin/order/edit_blog.html', {'form': form, 'blog': blog})

@require_POST
def delete_blog_view(request, pk):
    blog = get_object_or_404(Blog, pk=pk)
    blog.delete()
    return redirect('custom_admin:blog_list')


@staff_member_required
def banner_list_view(request):
    banners = BannerImage.objects.all()
    return render(request, 'custom_admin/order/banner_list.html', {'banners': banners})

@staff_member_required
def add_banner_view(request):
    if request.method == 'POST':
        form = BannerImageForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return redirect('custom_admin:banner_list')
    else:
        form = BannerImageForm()
    return render(request, 'custom_admin/order/add_banner.html', {'form': form})

@staff_member_required
def edit_banner_view(request, pk):
    banner = get_object_or_404(BannerImage, pk=pk)
    if request.method == 'POST':
        form = BannerImageForm(request.POST, request.FILES, instance=banner)
        if form.is_valid():
            form.save()
            return redirect('custom_admin:banner_list')
    else:
        form = BannerImageForm(instance=banner)
    return render(request, 'custom_admin/order/edit_banner.html', {'form': form, 'banner': banner})

@staff_member_required
def delete_banner_view(request, pk):
    banner = get_object_or_404(BannerImage, pk=pk)
    if request.method == 'POST':
        banner.delete()
        return redirect('custom_admin:banner_list')
    return render(request, 'custom_admin/order/delete_banner.html', {'banner': banner})


@staff_member_required
def customer_list_view(request):
    customers = User.objects.filter(is_staff=False)
    return render(request, 'custom_admin/order/customer_list.html', {'customers': customers})

@staff_member_required
def add_customer_view(request):
    if request.method == 'POST':
        user_form = CustomerForm(request.POST)
        profile_form = ProfileForm(request.POST)

        if user_form.is_valid() and profile_form.is_valid():
            with transaction.atomic():
                user = user_form.save()
                profile = profile_form.save(commit=False)
                profile.user = user
                profile.save()
            return redirect('custom_admin:customer_list')
    else:
        user_form = CustomerForm()
        profile_form = ProfileForm()

    return render(request, 'custom_admin/order/add_customer.html', {'user_form': user_form, 'profile_form': profile_form})

@staff_member_required
def edit_customer_view(request, pk):
    user = get_object_or_404(User, pk=pk)
    profile = user.profile

    if request.method == 'POST':
        user_form = CustomerForm(request.POST, instance=user)
        profile_form = ProfileForm(request.POST, instance=profile)

        if user_form.is_valid() and profile_form.is_valid():
            with transaction.atomic():
                user_form.save()
                profile_form.save()
            return redirect('custom_admin:customer_list')
    else:
        user_form = CustomerForm(instance=user)
        profile_form = ProfileForm(instance=profile)

    return render(request, 'custom_admin/order/edit_customer.html', {'user_form': user_form, 'profile_form': profile_form, 'customer': user})

@staff_member_required
def delete_customer_view(request, pk):
    customer = get_object_or_404(User, pk=pk)
    if request.method == 'POST':
        customer.delete()
        return redirect('custom_admin:customer_list')
    return render(request, 'custom_admin/order/delete_customer.html', {'customer': customer})



@staff_member_required
def about_list_view(request):
    about_items = About.objects.all()
    return render(request, 'custom_admin/order/about_list.html', {'about_items': about_items})


@staff_member_required
def add_about_view(request):
    if request.method == 'POST':
        form = AboutForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return redirect('custom_admin:about_list')
    else:
        form = AboutForm()

    return render(request, 'custom_admin/order/add_about.html', {'form': form})


@staff_member_required
def edit_about_view(request, pk):
    about_item = get_object_or_404(About, pk=pk)
    if request.method == 'POST':
        form = AboutForm(request.POST, request.FILES, instance=about_item)
        if form.is_valid():
            form.save()
            return redirect('custom_admin:about_list')
    else:
        form = AboutForm(instance=about_item)

    return render(request, 'custom_admin/order/edit_about.html', {'form': form, 'about_item': about_item})

@staff_member_required
def delete_about_view(request, pk):
    about_item = get_object_or_404(About, pk=pk)
    if request.method == 'POST':
        about_item.delete()
        return redirect('custom_admin:about_list')
    return render(request, 'custom_admin/order/delete_about.html', {'about_item': about_item})


@login_required
def user_list_view(request):
    if request.user.role != 'admin':
        return render(request, 'custom_admin/access_denied.html', {
            'message': "You do not have permission to view this page."
        })

    users = User.objects.exclude(is_superuser=True)
    return render(request, 'custom_admin/user_list.html', {'users': users})


@login_required
def edit_user_role(request, user_id):
    if request.user.role != 'admin':
        return render(request, 'custom_admin/access_denied.html', {
            'message': "You do not have permission to access this functionality."
        })

    user = get_object_or_404(User, id=user_id)
    form = UserRoleUpdateForm(request.POST or None, instance=user)

    if request.method == 'POST':
        if form.is_valid():
            form.save()
            messages.success(request, f"Role updated for {user.email}")
            return redirect('custom_admin:user_list')

    return render(request, 'custom_admin/edit_user_role.html', {'form': form, 'user': user})


@login_required
def profile_view(request):
    user = request.user
    profile = user.profile
    user_form = UserUpdateForm(request.POST or None, instance=user)
    profile_form = ProfileForm(request.POST or None, request.FILES or None, instance=profile)

    if request.method == 'POST':
        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            messages.success(request, "Profile updated successfully!")

    return render(request, 'custom_admin/profile.html', {
        'user_form': user_form,
        'profile_form': profile_form,
        'profile': profile
    })

def site_settings_list(request):
    settings = SiteSettings.objects.all()
    return render(request, 'custom_admin/site_settings/list.html', {'settings': settings})

def site_settings_create(request):
    form = SiteSettingsForm(request.POST or None)
    if form.is_valid():
        form.save()
        return redirect('custom_admin:site_settings_list')
    return render(request, 'custom_admin/site_settings/form.html', {'form': form, 'title': 'Create Site Settings'})

def site_settings_update(request, pk):
    instance = get_object_or_404(SiteSettings, pk=pk)
    form = SiteSettingsForm(request.POST or None, instance=instance)
    if form.is_valid():
        form.save()
        return redirect('custom_admin:site_settings_list')
    return render(request, 'custom_admin/site_settings/form.html', {'form': form, 'title': 'Update Site Settings'})

def site_settings_delete(request, pk):
    instance = get_object_or_404(SiteSettings, pk=pk)
    if request.method == "POST":
        instance.delete()
        return redirect('custom_admin:site_settings_list')
    return render(request, 'custom_admin/site_settings/confirm_delete.html', {'object': instance})


def discount_code_list_view(request):
    coupons = DiscountCode.objects.all()
    return render(request, 'custom_admin/discount_code_list.html', {'coupons': coupons})


def coupon_list_view(request):
    coupons = DiscountCode.objects.all()
    return render(request, 'custom_admin/discount_code_list.html', {'coupons': coupons})

def add_coupon_view(request):
    form = DiscountCodeForm(request.POST or None)
    if form.is_valid():
        form.save()
        return redirect('custom_admin:coupon_list')
    return render(request, 'custom_admin/discount_code_form.html', {'form': form, 'title': 'Add Coupon'})

def edit_coupon_view(request, pk):
    coupon = get_object_or_404(DiscountCode, pk=pk)
    form = DiscountCodeForm(request.POST or None, instance=coupon)
    if form.is_valid():
        form.save()
        return redirect('custom_admin:coupon_list')
    return render(request, 'custom_admin/discount_code_form.html', {'form': form, 'title': 'Edit Coupon'})

def delete_coupon_view(request, pk):
    coupon = get_object_or_404(DiscountCode, pk=pk)
    if request.method == 'POST':
        coupon.delete()
        return redirect('custom_admin:coupon_list')
    return render(request, 'custom_admin/confirm_delete.html', {'object': coupon, 'title': 'Delete Coupon'})