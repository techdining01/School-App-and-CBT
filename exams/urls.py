from django.urls import path
from . import views

urlpatterns = [
    # Homepage
    path('', views.home, name='exam_home'),

    # Dashboards
    path('dashboard/admin/', views.admin_dashboard, name='admin_dashboard'),
    path('dashboard/teacher/', views.teacher_dashboard, name='teacher_dashboard'),
    path('dashboard/student/', views.student_dashboard, name='student_dashboard'),
    path('dashboard/superadmin/', views.superadmin_dashboard, name='superadmin_dashboard'),
    path('broadcast/', views.broadcast, name='broadcast'),
    path('grade/answer/<int:answer_id>/', views.grade_answer, name='grade_answer'),
    
    # AJAX endpoints
    path('ajax/student-summary/', views.ajax_student_summary, name='ajax_student_summary'),
    path('ajax/teacher-pending/', views.ajax_teacher_pending_subjectives, name='ajax_teacher_pending_subjectives'),

    # PDF
    path('export/consolidated-pdf/', views.consolidated_results_pdf, name='export_consolidated_pdf'),


]
