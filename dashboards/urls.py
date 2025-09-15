from django.urls import path
from . import views

urlpatterns = [
    path("admin/grant-retake/<int:attempt_id>/", views.grant_retake, name="grant_retake"),
]
