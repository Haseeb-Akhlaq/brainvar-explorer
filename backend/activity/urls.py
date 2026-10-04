from django.urls import path

from . import views

app_name = "activity"

urlpatterns = [
    path("activity/", views.ActivityListView.as_view(), name="activity-list"),
    path("activity/actors/", views.ActivityActorsView.as_view(), name="activity-actors"),
    path("activity/report/", views.ReportEventView.as_view(), name="activity-report"),
]
