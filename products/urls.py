from django.urls import path, include
from . import views
from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
app_name = 'products'


urlpatterns = [
    path('', views.home, name='home'),
    path('contact/', views.contact, name='contact'),
    path('tinymce/', include('tinymce.urls')),

    path('global-search/', views.global_search_view, name='global_search_view'),

    path('about/', views.about, name='about'),
    path('delivery_info/', views.delivery_info, name='delivery_info'),
    path('privacy_policy/', views.privacy_policy, name='privacy_policy'),
    path('return_refund/', views.return_refund, name='return_refund'),
    path('terms_condition/', views.terms_condition, name='terms_condition'),

    path('product_grid/', views.product_grid, name='product_grid'),
    path('product_list/', views.product_list, name='product_list'),
    path('product_details/', views.product_grid, name='product_details'),
    path('product_details/<str:pid>/', views.product_details, name='product_details'),
    path('get_variant_data/<int:variant_id>/', views.get_variant_data, name='get_variant_data'),
    path('review/add/<str:pid>/', views.add_review, name='add_review'),
    path('review/edit/<int:review_id>/', views.edit_review, name='edit_review'),

    path('wishlist/', views.wishlist, name='wishlist'),
    path('add_to_wishlist/', views.add_to_wishlist, name='add_to_wishlist'),
    path('remove-from-wishlist/<int:product_id>/', views.remove_from_wishlist, name='remove-from-wishlist'),

    path('cart/', views.cart_view, name='cart_view'),
    path('add_to_cart/<str:pid>/', views.add_to_cart, name='add_to_cart'),
    path('remove_from_cart/<int:item_id>/', views.remove_from_cart, name='remove_from_cart'),
    path('update_cart_item/', views.update_cart_item, name='update_cart_item'),

    path('checkout/', views.checkout, name='checkout'),
    path('place-order-cod/', views.place_order_cod, name='place_order_cod'),
    path('process_order/', views.process_order, name='process_order'),
    path('save_info/', views.save_info, name='save_info'),
    path('product_service/', views.product_services, name='product_services'),
    path('order_details/', views.order_details, name='order_details'),
    path('order/invoice/<int:order_id>/', views.order_invoice, name='order_invoice'),

    path('order_tracking/', views.order_tracking, name='order_tracking'),
    path('update_order_status/', views.update_order_status, name='update_order_status'),
    path('order/<int:order_id>/cancel/', views.request_order_cancel, name='request_order_cancel'),
    path('order/return/<int:order_id>/', views.request_order_return, name='request_order_return'),
    path('order/replace/<int:order_id>/', views.request_order_replace, name='request_order_replace'),
    path('order/<int:order_id>/complete/', views.request_order_complete, name='request_order_complete'),
    path('order/<int:order_id>/<str:action>/', views.request_order_action, name='request_order_action'),

    path('order/<int:order_id>/', views.order_details, name='order_details'),
    path('webhook/razorpay/', views.razorpay_webhook, name='razorpay_webhook'),
    path("check-payment-status/", views.check_payment_status, name="check_payment_status"),
    path('payment-failed/', views.payment_failed, name='payment_failed'),

    path('category/<str:cid>/', views.product_grid, name='product_grid_by_main_category'),
    path('subcategory/<str:cid>/', views.product_grid, {'is_subcategory': True}, name='product_grid_by_sub_category'),
    path('category/<str:cid>/', views.product_grid, name='product_grid_by_category'),
    path('subcategory/<str:cid>/', views.product_grid, {'is_subcategory': True}, name='product_grid_by_sub_category'),

    path('hyperdeckcontroller/', views.hyperdeckcontroller, name='hyperdeckcontroller'),
    path('custom_admin/dashboard/', views.product_dashboard, name='product_dashboard'),  # Admin dashboard URL

    path('apply-coupon/', views.apply_coupon, name='apply_coupon'),
    path('remove-coupon/', views.remove_coupon, name='remove_coupon'),
    path('claim-discount/', views.claim_discount, name='claim_discount'),
    path('faq/', views.faq, name='faq'),

              ] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
