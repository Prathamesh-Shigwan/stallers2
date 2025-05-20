from django.urls import path
from . import views
from django.conf import settings
from django.conf.urls.static import static

app_name = 'accounts'

urlpatterns = [
    path('signup/', views.sign_up, name='signup'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('userprofile/', views.user_profile, name='user_profile'),
    path('updateinfo/', views.update_info, name='update_info'),
    path('verify-otp/', views.verify_otp, name='verify_otp'),
    path('verify-signup-otp/', views.verify_signup_otp, name='verify_signup_otp'),
    path("password-reset/", views.password_reset_request, name="password_reset_request"),
    path("reset/<uidb64>/<token>/", views.password_reset_confirm, name="password_reset_confirm"),

] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
