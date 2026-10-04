from django.urls import path

from . import views

app_name = "brainvar"

urlpatterns = [
    path("stats/", views.dataset_stats, name="dataset-stats"),
    path("genes/", views.gene_search, name="gene-search"),
    path("genes/<str:query>/", views.gene_detail, name="gene-detail"),
]
