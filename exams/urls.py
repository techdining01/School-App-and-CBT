from django.urls import path
from . import views

urlpatterns = [
   
    # Create quiz page (manual + excel)
    path("create/", views.create_quiz_page, name="create_quiz_page"),
    path("api/create/", views.create_quiz_ajax, name="create_quiz_ajax"),
    path("quiz/<int:quiz_id>/json/", views.quiz_json_quiz_load, name="quiz_json"),   #  AJAX JSON create
    path("quiz/json/<int:quiz_id>/", views.quiz_json1, name="quiz_json_question"),   #  AJAX JSON create    

    # edit, json
    path("edit/<int:quiz_id>/", views.edit_quiz_page, name="edit_quiz_page"),
    path("api/edit/<int:quiz_id>/", views.edit_quiz_ajax, name="edit_quiz_ajax"),

    # Excel import (AJAX file upload)
    path("api/import_excel/", views.import_quiz_excel, name="import_quiz_excel"),
    path("download/template/xlsx/", views.download_excel_template, name="download_excel_template"),

    # AJAX manage actions
    path("api/<int:quiz_id>/publish_toggle/", views.publish_toggle_ajax, name="publish_toggle_ajax"),
    path("api/<int:quiz_id>/delete/", views.delete_quiz_ajax, name="delete_quiz_ajax"),

    # Leaderboard
    path("leaderboard/", views.leaderboard, name="leaderboard"),

    # Quiz management
    path("admin/quizzes/create/", views.create_quiz, name="create_quiz"),
    path("admin/quizzes/manage", views.manage_quizzes, name="manage_quizzes"),
    path("api/search_quizzes/", views.search_quizzes, name="search_quizzes"),
    path("admin/quizzes/upload-excel/", views.upload_quiz_excel, name="upload_quiz_excel"),
    path("admin/retake-requests/", views.retake_requests_list, name="retake_requests_list"),
    path("admin/retake-request/<int:request_id>/", views.handle_retake_request, name="handle_retake_request"),
    path("approve-retake/<int:quiz_id>/<int:student_id>/", views.approve_retake, name="approve_retake"),

    # Admin dashboard and retake requests from students
    path("admin/dashboard/", views.admin_dashboard, name="admin_dashboard"),
    path("admin/dashboard/data/", views.admin_dashboard_data, name="admin_dashboard_data"),
    path("admin/notifications/<int:pk>/mark-read/", views.mark_notification_read, name="mark_notification_read"),

    path('dashboard/superadmin/', views.superadmin_dashboard, name='superadmin_dashboard'),

    # Classes
    path("manage/classes-subject/", views.manage_classes_subjects, name="manage_classes_subjects"),

    # Class - Subject CRUD
    path("class-subject/", views.class_subject_crud, name="class_subject_crud"),
    
    # Teacher Dashboard management
    path("teacher/dashboard/", views.teacher_dashboard, name="teacher_dashboard"),
    path("teacher/dashboard/data/", views.teacher_dashboard_data, name="teacher_dashboard_data"),
    path("teacher/broadcast/", views.teacher_broadcast, name="teacher_broadcast"),
    path("teacher/grade/<int:answer_id>/", views.grade_answer, name="grade_answer"),
    path("teacher/notification/<int:notif_id>/read/", views.mark_notification_read, name="mark_notification_read"),


    # Teacher approval and settings, notification and broadcast
    path("teacher/student/<int:student_id>/review/", views.student_review, name="student_review"),
    path("teacher/retake/<int:quiz_id>/<int:student_id>/", views.approve_retake, name="approve_retake"),
    path("teacher/broadcast/", views.broadcast_message, name="broadcast_message"),
    path("teacher/download/student/<int:student_id>/", views.download_student_report, name="download_student_report"),
    path("teacher/download/quiz/<int:quiz_id>/", views.download_quiz_report, name="download_quiz_report"),
    path("notifications/mark-read/<int:notification_id>/", views.mark_notification_read, name="mark_notification_read"),
    path("broadcast/", views.teacher_broadcast, name="teacher_broadcast"),

    # Teacher report (all students in a quiz)
    path("reports/quiz/<int:quiz_id>/", views.download_closed_quiz_report, name="download_closed_quiz_report"),

    # Student quiz interaction
    path("student/dashboard/", views.student_dashboard, name="student_dashboard"),
    path("student/dashboard/data/", views.student_dashboard_data, name="student_dashboard_data"),
    path("student/notifications/mark-read/", views.api_notifications_mark_read, name="api_notifications_mark_read"),
    
    # Student report
    path("reports/student/<int:student_id>/", views.download_student_full_report, name="download_student_full_report"),
    
      
    # take quiz page
    path('quiz/<int:quiz_id>/take/', views.take_quiz_view, name='take_quiz'),

    # autosave single answer (POST JSON)
    path('attempt/<int:attempt_id>/submit-answer/', views.api_submit_answer, name='api_submit_answer'),

    # final submit (POST JSON) -> computes score, marks completed
    path('attempt/<int:attempt_id>/submit/', views.api_submit_attempt, name='api_submit_attempt'),

    # result view
    path('attempt/<int:attempt_id>/result/', views.quiz_result_view, name='quiz_result'),

    # review page (teacher or owner)
    path('attempt/<int:attempt_id>/review/', views.review_attempt_view, name='review_attempt'),

    # student requests retake
    path("quiz/<int:quiz_id>/request-retake/", views.request_retake_view, name="request_retake"),
  
    # admin/teacher approves retake request (POST)
    # path('retake-request/<int:req_id>/approve/', views.approve_request_retake_view, name='approve_retake_request'),

    path("quizzes/details/<int:quiz_id>/", views.quiz_details_page, name="quiz_details_page"),
    path("quiz/<int:quiz_id>/closed/", views.quiz_closed, name="quiz_closed_detail"),


    # API endpoints used by fetch in the template
    path('api/student/notifications/unread/', views.api_notifications_unread, name='api_notifications_unread'),
    path('api/student/notifications/mark-read/', views.api_notifications_mark_read, name='api_notifications_mark_read'),
    path("api/quizzes/<int:quiz_id>/toggle-publish/", views.toggle_quiz_publish, name="toggle_quiz_publish"),
    path("api/quizzes/<int:quiz_id>/", views.quiz_detail_api, name="quiz_detail_api"),
   
   
   
]


 # User management
    # path("admin/users/", views.manage_users, name="manage_users"),
    # path("admin/users/create/", views.create_user, name="create_user"),
    # path("attempt/<int:attempt_id>/result/", views.quiz_result, name="quiz_result"),


 # broadcast + notifications API endpoints
    # path("api/broadcast/", views.api_broadcast, name="api_broadcast"),
    # path("api/notifications/unread/", views.api_notifications_unread, name="api_notifications_unread"),
    # path("api/notifications/mark-read/", views.api_notifications_mark_read, name="api_notifications_mark_read"),


    # path("quiz/<int:quiz_id>/approve-retake/<int:student_id>/", views.approve_retake, name="approve_retake"),