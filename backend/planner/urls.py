from django.urls import path

from . import views

urlpatterns = [
    path("health", views.health),
    path("geocode", views.geocode_view),
    path("plan", views.plan_view),
    path("heatmap/<str:plan_id>", views.heatmap_view),
]
