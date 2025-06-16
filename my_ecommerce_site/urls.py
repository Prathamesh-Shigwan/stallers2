from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include
from products.views import home
from django.contrib.auth import views as auth_views


urlpatterns = [
    path('', home, name='home'),                     # Home page
    path('products/', include('products.urls', namespace='products')),
    path('accounts/', include('accounts.urls')),     # Accounts URLs
    path('blog/', include('blog.urls')),             # Blog URLs
    path('tinymce/', include('tinymce.urls')),       # TinyMCE URLs
    path('custom-admin/', include('custom_admin.urls')),
    path('password-reset/', auth_views.PasswordResetView.as_view(), name="reset_password"),
    path('password-reset/done/', auth_views.PasswordResetDoneView.as_view(), name="password_reset_done"),
    path('password-reset-confirm/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(),
         name="password_reset_confirm"),
    path('password-reset-complete/', auth_views.PasswordResetCompleteView.as_view(template_name="resources/password_reset_complete.html"), name="password_reset_complete"),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
