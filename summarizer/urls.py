from django.urls import path
from . import views

app_name = 'summarizer'

urlpatterns = [
    path('history/', views.SummaryHistoryView.as_view(), name='history'),
    path('<int:pk>/', views.SummaryDetailView.as_view(), name='detail'),
    path('<int:pk>/export/pdf/', views.export_summary_pdf, name='export_pdf'),
    path('<int:pk>/export/word/', views.export_summary_word, name='export_word'),
]
