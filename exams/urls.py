from django.urls import path
from . import views

urlpatterns = [
    # # Homepage
    # path('', views.home, name='exam_home'),

    # Dashboards
    path('dashboard/admin/', views.admin_dashboard, name='admin_dashboard'),
    path('dashboard/teacher/', views.teacher_dashboard, name='teacher_dashboard'),
    path('dashboard/student/', views.student_dashboard, name='student_dashboard'),
    path("admin/dashboard/", views.admin_dashboard, name="admin_dashboard"),
    path("admin/dashboard/data/", views.admin_dashboard_data, name="admin_dashboard_data"),
    # AJAX endpoints
    path('ajax/student-summary/', views.ajax_student_summary, name='ajax_student_summary'),
    path('ajax/teacher-pending/', views.ajax_teacher_pending_subjectives, name='ajax_teacher_pending_subjectives'),

    # PDF
    path('export/consolidated-pdf/', views.consolidated_results_pdf, name='export_consolidated_pdf'),
    path("results/pdf/", views.student_consolidated_results_pdf, name="consolidated_results_pdf"),
    path("teacher/results/pdf/", views.teacher_class_results_pdf, name="teacher_class_results_pdf"),
    path("admin/results/pdf/", views.admin_overall_results_pdf, name="admin_overall_results_pdf"),

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




]

    # start, autosave, submit
    # path("api/<int:quiz_id>/start_attempt/", views.start_attempt, name="start_attempt"),
    # path("api/attempts/<int:attempt_id>/autosave/", views.autosave_attempt, name="autosave_attempt"),
    # path("api/attempts/<int:attempt_id>/submit/", views.submit_attempt, name="submit_attempt"),
    # path('broadcast/', views.broadcast, name='broadcast'),
    # path('grade/answer/<int:answer_id>/', views.grade_answer, name='grade_answer'),
    