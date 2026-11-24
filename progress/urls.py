from django.urls import path
from . import views

app_name = "progress"

urlpatterns = [
    path("", views.progress_dashboard, name="dashboard"),
    path("section/<slug:section>/", views.section, name="section"),
]
