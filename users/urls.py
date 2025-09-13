from django.urls import path
from . import views

urlpatterns = [
    path('signup/', views.signup_view, name='signup'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path("teacher-admin-profile/<int:user_id>/", views.teacheradminprofile, name="teacheradminprofile"),
    path("profile/", views.view_profile, name="view_profile"),
    path("edit-profile/", views.edit_profile, name="edit_profile"),
    path("dashboard/", views.dashboard_redirect, name="dashboard"),
    path("broadcast/send/", views.send_broadcast, name="send_broadcast"),
    path("notification/<int:pk>/read/", views.mark_notification_read, name="mark_notification_read"),
]