from django.urls import path
from . import views

app_name = 'summarizer'

urlpatterns = [
    path('preview-tags/',               views.preview_tags,                  name='preview_tags'),
    path('history/',                    views.SummaryHistoryView.as_view(),  name='history'),
    path('<int:pk>/',                   views.SummaryDetailView.as_view(),   name='detail'),
    path('<int:pk>/export/pdf/',        views.export_summary_pdf,            name='export_pdf'),
    path('<int:pk>/export/word/',       views.export_summary_word,           name='export_word'),
    path('<int:pk>/share/',             views.create_share_link,             name='create_share'),
    path('share/revoke/<int:link_pk>/', views.revoke_share_link,             name='revoke_share'),
    path('shared/<uuid:token>/',        views.shared_summary_view,           name='shared'),
]
