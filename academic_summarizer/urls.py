from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from . import views as project_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', project_views.home, name='home'),
    path('i18n/', include('django.conf.urls.i18n')),  # exposes /i18n/setlang/
    path('papers/', include('papers.urls', namespace='papers')),
    path('summarizer/', include('summarizer.urls', namespace='summarizer')),
    path('auth/', include('django.contrib.auth.urls')),
    path('auth/register/', include('papers.urls_auth')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
