from django.contrib import admin
from django.urls import include, path
from django.views.generic import TemplateView

from .views import healthz

# Uploaded PDFs are intentionally NOT served from MEDIA_URL: they are only
# reachable through the owner-checked ``papers:download`` view.
urlpatterns = [
    path('admin/', admin.site.urls),
    path('healthz/', healthz, name='healthz'),
    path('', TemplateView.as_view(template_name='home.html'), name='home'),
    path('papers/', include('papers.urls', namespace='papers')),
    path('summarizer/', include('summarizer.urls', namespace='summarizer')),
    path('auth/', include('django.contrib.auth.urls')),
    path('auth/register/', include('papers.urls_auth')),
]
