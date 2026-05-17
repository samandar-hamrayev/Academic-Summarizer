from django.urls import path
from . import views

app_name = 'papers'

urlpatterns = [
    path('', views.PaperListView.as_view(), name='list'),
    path('upload/', views.PaperUploadView.as_view(), name='upload'),
    path('tag/<slug:tag_slug>/', views.papers_by_tag, name='by_tag'),
    path('<int:pk>/', views.PaperDetailView.as_view(), name='detail'),
    path('<int:pk>/delete/', views.PaperDeleteView.as_view(), name='delete'),
    path('<int:pk>/summarize/', views.trigger_summarize, name='summarize'),
    path('<int:pk>/citations/', views.paper_citations, name='citations'),
    path('<int:pk>/citations/bib/', views.paper_citation_bib, name='citations_bib'),
]
