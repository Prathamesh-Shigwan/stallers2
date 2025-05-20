from django.urls import path
from . import views
from django.conf import settings
from django.conf.urls.static import static


urlpatterns = [
    path('', views.blog_list, name='blog_list'),
    path('<slug:slug>/', views.blog_details, name='blog_details'),
]+ static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
