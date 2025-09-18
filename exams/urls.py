from django.urls import path
from . import views

urlpatterns = [
   
    # Create quiz page (manual + excel)
    path("create/", views.create_quiz_page, name="create_quiz_page"),
    # AJAX JSON create
    path("api/create/", views.create_quiz_ajax, name="create_quiz_ajax"),
    # Excel import (AJAX file upload)
    path("api/import_excel/", views.import_quiz_excel, name="import_quiz_excel"),

    # Manage quizzes page
    path("manage/", views.manage_quizzes_page, name="manage_quizzes_page"),
    # AJAX manage actions
    path("api/<int:quiz_id>/publish_toggle/", views.publish_toggle_ajax, name="publish_toggle_ajax"),
    path("api/<int:quiz_id>/delete/", views.delete_quiz_ajax, name="delete_quiz_ajax"),

    # edit, json
    path("edit/<int:quiz_id>/", views.edit_quiz_page, name="edit_quiz_page"),
    path("api/edit/<int:quiz_id>/", views.edit_quiz_ajax, name="edit_quiz_ajax"),
    path("api/<int:quiz_id>/json/", views.quiz_json, name="quiz_json"),


    path("download/template/xlsx/", views.download_excel_template, name="download_excel_template"),
    path("take/<int:quiz_id>/", views.take_quiz, name="take_quiz"),


 # Page to start/take quiz (HTML shell)
    path("<int:quiz_id>/take/", views.take_quiz_page, name="take_quiz_page"),

    # AJAX endpoints (JSON)
    path("api/<int:quiz_id>/start_attempt/", views.api_start_attempt, name="api_start_attempt"),
    path("api/attempts/<int:attempt_id>/autosave/", views.api_autosave_attempt, name="api_autosave_attempt"),
    path("api/attempts/<int:attempt_id>/submit/", views.api_submit_attempt, name="api_submit_attempt"),
    path("api/attempts/<int:attempt_id>/review/", views.api_attempt_review, name="api_attempt_review"),

    # Leaderboard
    path("leaderboard/", views.leaderboard, name="leaderboard"),
    path("quiz/<int:quiz_id>/approve-retake/<int:student_id>/", views.approve_retake, name="approve_retake"),

    # User management
    # path("admin/users/", views.manage_users, name="manage_users"),
    # path("admin/users/create/", views.create_user, name="create_user"),

    # Quiz management
    path("admin/quizzes/", views.manage_quizzes, name="manage_quizzes"),
    path("admin/quizzes/create/", views.create_quiz, name="create_quiz"),
    path("admin/quizzes/upload-excel/", views.upload_quiz_excel, name="upload_quiz_excel"),
    path("admin/quizzes/sample-excel/", views.sample_quiz_excel, name="sample_quiz_excel"),

    path("admin/dashboard/", views.admin_dashboard, name="admin_dashboard"),
    path("admin/dashboard/data/", views.admin_dashboard_data, name="admin_dashboard_data"),
    path('dashboard/superadmin/', views.superadmin_dashboard, name='superadmin_dashboard'),

    path("teacher/dashboard/", views.teacher_dashboard, name="teacher_dashboard"),
    path("teacher/dashboard/data/", views.teacher_dashboard_data, name="teacher_dashboard_data"),

    # path("student/dashboard/", views.student_dashboard, name="student_dashboard"),
    # path("student/dashboard/data/", views.student_dashboard_data, name="student_dashboard_data"),

    #  # broadcast + notifications API endpoints
    # path("api/broadcast/", views.api_broadcast, name="api_broadcast"),
    # path("api/notifications/unread/", views.api_notifications_unread, name="api_notifications_unread"),
    # path("api/notifications/mark-read/", views.api_notifications_mark_read, name="api_notifications_mark_read"),



   path('dashboard/', views.student_dashboard, name='student_dashboard'),

    # API endpoints used by fetch in the template
    path('api/student/quizzes/', views.api_student_quizzes, name='api_student_quizzes'),
    path('api/student/attempts/', views.api_student_attempts, name='api_student_attempts'),
    path('api/student/notifications/unread/', views.api_notifications_unread, name='api_notifications_unread'),
    path('api/student/notifications/mark-read/', views.api_notifications_mark_read, name='api_notifications_mark_read'),
    path('api/student/take-quiz/', views.api_take_quiz, name='api_take_quiz'),
    path("quiz/<int:quiz_id>/toggle_publish/", views.toggle_quiz_publish, name="toggle_quiz_publish"),
    path("quiz/<int:quiz_id>/detail/", views.quiz_detail, name="quiz_detail"),

    

]
