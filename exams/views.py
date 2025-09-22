from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.utils import timezone
from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse, HttpResponse, HttpResponseBadRequest, HttpResponseForbidden
from django.db.models import Sum, Avg, Count, Min, Max, Q
from django.template.loader import render_to_string
from django.core.paginator import Paginator
from django.views.decorators.http import require_POST, require_http_methods
import json, os, io
from io import BytesIO
import openpyxl
from openpyxl import load_workbook
from datetime import datetime, timedelta

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from reportlab.lib.units import inch
from django.db import transaction

# ✅ Always use get_user_model
from django.contrib.auth import get_user_model
User = get_user_model()

# Your models
from .models import Quiz, Question, Choice, StudentQuizAttempt, ActionLog, Answer, Class, Subject,RetakeRequest
from users.models import Notification
from .utils import log_action
from django.views.decorators.csrf import csrf_exempt

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.contrib import messages
from django.db.models import Avg





def is_teacher_or_admin(user):
    return user.is_authenticated and user.role in ('teacher', 'admin', 'superadmin')


def home(request):
    return render(request, "exams/home.html")


def take_quiz(request, quiz_id):
    quiz = get_object_or_404(Quiz, id=quiz_id)
    now = timezone.now()

    # Check if quiz is active
    if not (quiz.start_time <= now <= quiz.end_time):
        return render(request, "exams/quiz_closed.html", {"quiz": quiz})


    # get or create attempt
    attempt, created = StudentQuizAttempt.objects.get_or_create(
        student=request.user, quiz=quiz, completed=False
    )

    # check if can resume
    if attempt.can_resume():
        pass  # just continue same attempt
    elif attempt.can_retake():
        # reset for retake
        attempt.retake_allowed = False
        attempt.retake_count += 1
        attempt.completed = False
        attempt.started_at = timezone.now()
        attempt.end_time = timezone.now() + quiz.duration
        attempt.save()
    else:
        return JsonResponse({"error": "You cannot retake this quiz."}, status=403)

    # prepare questions JSON for frontend (AJAX)
    questions = []
    for q in quiz.questions.prefetch_related("choices"):
        qd = {"id": q.id, "text": q.text, "question_type": q.question_type}
        if q.question_type == "objective":
            qd["choices"] = [{"id": c.id, "text": c.text} for c in q.choices.all()]
        questions.append(qd)

    return render(request, "exams/partials/quiz_modal.html", {
        "quiz": quiz,
        "attempt": attempt,
        "questions_json": json.dumps(questions)
    })



def some_view(request):
    messages.success(request, "Quiz submitted successfully!")
    messages.error(request, "Something went wrong.")
    return redirect("dashboard")


# --------------------------------------------------------------#

def is_teacher(user):
    return user.is_authenticated and user.role == 'teacher'

def is_admin(user):
    return user.is_authenticated and user.role in ('admin', 'superadmin')


def is_admin_or_superadmin(user):
    return user.is_authenticated and user.role in ["admin", "superadmin"]


@login_required
@user_passes_test(is_admin_or_superadmin)
def superadmin_dashboard(request):
    if request.user.role !=  "superadmin":
        return HttpResponseForbidden("Unauthorized")
    # counts
    approved = User.objects.filter(role__in=['admin', 'teacher', 'student'], approved=True).count()
    pended = User.objects.filter(approved=False).count()
    teachers = User.objects.filter(role='teacher', approved=True).count()
    students = User.objects.filter(role='student', approved=True).count()

    # leaderboard: top students by average total_score (only graded attempts)
    leaderboard = (
        StudentQuizAttempt.objects.filter(completed=True)
        .values("student__username")
        .annotate(avg_score=Avg("score"))
        .order_by("-avg_score")[:10]  # top 10
    )

    # recent action logs
    actions = ActionLog.objects.order_by('-timestamp')[:20]

    notifications = Notification.objects.filter(role='superadmin').order_by('-created_at')[:10]
    

    context = {
        "approved": approved,
        "pended": pended,
        "teachers": teachers,
        "students": students,
        "leaderboard": leaderboard,
        "actions": actions,
        "notifications": notifications,
        "total_admins": User.objects.filter(role="admin", approved=True).count(),
        "total_quizzes": Quiz.objects.count(),
        "total_classes": Class.objects.count(),
        'total_subjects': Subject.objects.count(),
    }
    return render(request, "exams/superadmin_dashboard.html", context)



# @login_required
# @user_passes_test(is_admin)
# def admin_dashboard(request):
#     # counts
#     approved = User.objects.filter(approved=True).count()
#     pended = User.objects.filter(approved=False).count()
#     teachers = User.objects.filter(role='teacher', approved=True).count()
#     students = User.objects.filter(role='student', approved=True).count()
#     # leaderboard: top students by average total_score (only graded attempts)
#     leaderboard = (
#         StudentQuizAttempt.objects.filter(completed=True)
#         .values("student__username")
#         .annotate(avg_score=Avg("score"))
#         .order_by("-avg_score")[:10]  # top 10
#     )

#     # recent action logs
#     actions = ActionLog.objects.order_by('-timestamp')[:20]

#     notifications = Notification.objects.filter(role='admin').order_by('-created_at')[:10]
    

#     context = {
#         "approved": approved,
#         "pended": pended,
#         "teachers": teachers,
#         "students": students,
#         "leaderboard": leaderboard,
#         "actions": actions,
#         "notifications": notifications,
#         "total_admins": User.objects.filter(role="admin", approved=True).count(),
#         "total_quizzes": Quiz.objects.count(),
#         "total_classes": Class.objects.count(),
#         'total_subjects': Subject.objects.count(),
#     }
#     return render(request, "exams/admin_dashboard.html", context)

  
# @login_required
# def admin_dashboard_data(request):
#     if request.user.role not in ("admin", "superadmin"):
#         return JsonResponse({"error": "forbidden"}, status=403)

#     # Stats
#     stats = {
#         "total_users": User.objects.filter(role__in=["admin", "teacher", "student"]).count(),
#         "admins": User.objects.filter(role="admin", approved=True).count(),
#         "teachers": User.objects.filter(role="teacher", approved=True).count(),
#         "students": User.objects.filter(role="student", approved=True).count(),
#         "pending_users": User.objects.filter(approved=False).count(),
#         "classes": Class.objects.count(),
#         "subjects": Subject.objects.count(),
#         "quizzes": Quiz.objects.count(),
#     }

    
#     # Pending users list (serialize to list of dicts)
#     pending_list = list(User.objects.filter(approved=False).values("id","username", "email", "role", "date_joined"))

#     # Activity log entries (adapt field names of your ActivityLog model)
#     logs_qs = ActionLog.objects.order_by("-timestamp")[:10]
#     logs = [
#         {
#             "action": l.action,
#             "user": (l.user.username if getattr(l, "user", None) else getattr(l, "performed_by__username", None)),
#             "timestamp": l.timestamp.isoformat()
#         }
#         for l in logs_qs
#     ]

#     # Leaderboard (top students by avg score). Adjust Result model fields
#     leaderboard_qs = Answer.objects.values("attempt__student__username").annotate(avg_score=Avg("obtained_marks")).order_by("-avg_score")[:10]

#     leaderboard = [{"username": r["attempt__student__username"], "avg_score": float(r["avg_score"] or 0)} for r in leaderboard_qs]

#     # Class performance (avg score per class); adjust keys to your schema
#     class_perf_qs = Answer.objects.values("attempt__quiz__subject__school_class__name").annotate(avg_score=Avg("obtained_marks")).order_by("attempt__quiz__subject__school_class__name")
    
#     class_performance = [
#         {"class_name": row["attempt__quiz__subject__school_class__name"] or "Unknown", "avg_score": float(row["avg_score"] or 0)}
#         for row in class_perf_qs
#     ]

#     # Notifications for the admin user (last 10) - adapt Notification model fields
#     notifications_qs = Notification.objects.filter(recipient=request.user).order_by("-created_at")[:10]
#     notifications = [
#         {"id": n.id, "message": n.message, "sender": (n.sender.username if n.sender else None), "created_at": n.created_at.isoformat(), "is_read": n.is_read}
#         for n in notifications_qs
#     ]

#     return JsonResponse({
#         "stats": stats,
#         "pending_list": pending_list,
#         "logs": logs, 
#         "leaderboard": leaderboard,
#         "class_performance": class_performance,
#         "notifications": notifications,
#     })



# @login_required
# @user_passes_test(is_teacher)
# def teacher_dashboard(request):
#     user = request.user
#     # list classes teacher handles: depends on your data model. Here we take subjects created_by teacher
#     teacher_subjects = request.user.student_class  # adapt: this is quizzes created_by teacher
#     # For performance chart we aggregate attempts by quiz or subject
#     # Example: average score per quiz created by teacher
#     performance = StudentQuizAttempt.objects.filter(quiz__subject__school_class=user.student_class).values('quiz__title').annotate(avg_score=Avg('score'), attempts=Count('id')).order_by('-avg_score')

#     # subjectives pending for this teacher's quizzes
#     pending_subjectives = SubjectiveAnswer.objects.filter(question__quiz__subject__school_class=user.student_class, graded=False).select_related('attempt','question').order_by('attempt__started_at')

#     # recent action logs
#     actions = ActionLog.objects.order_by('-timestamp')[:20]

#     # notifications visible to teachers or all
#     notifications = Notification.objects.filter(role='teacher').order_by('-created_at')[:10]


#     context = {
#         "performance": performance,
#         "pending_subjectives": pending_subjectives,
#         "notifications": notifications,
#         'actions': actions
#     }
#     return render(request, "exams/teacher_dashboard.html", context)


  
# @login_required
# def student_dashboard(request):
#     user = request.user
#     # summary: total attempts, avg score, pending subjectives count
#     attempts = StudentQuizAttempt.objects.filter(student=user)
#     total_attempts = attempts.count()
#     avg_score = attempts.aggregate(avg=Avg('score'))['avg'] or 0
#     pending_count = Answer.objects.filter(attempt__student=user, is_pending=True).count()

#     available = get_quizzes_with_status(user)

#     # recent attempts with ability to review wrong answers
#     recent_attempts = attempts.select_related('quiz').order_by('-started_at')[:5]

#     # recent action logs
#     actions = ActionLog.objects.order_by('-timestamp')[:20]

#     # notifications for students or all
#     notifications = Notification.objects.filter(role='students').order_by('-created_at')[:5]
    

#     context = {
#         "total_attempts": total_attempts,
#         "avg_score": avg_score,
#         "pending_count": pending_count,
#         "available_quizzes": available,
#         "recent_attempts": recent_attempts,
#         "notifications": notifications,
#         'actions': actions
#     }
#     return render(request, "exams/student_dashboard.html", context)




# helper: admin check
def is_admin(user):
    return user.is_authenticated and user.role in ("admin", "superadmin")

# Admin dashboard page (HTML shell)
@login_required
@user_passes_test(is_admin)
def admin_dashboard(request):
    # Render the shell; the dynamic data comes from admin_dashboard_data
    return render(request, "exams/admin_dashboard.html", {})


# Admin dashboard data endpoint (GET -> fetch data; POST -> perform actions such as approve/reject/broadcast/download)
@login_required
def admin_dashboard_data(request):
    if request.user.role not in ("admin", "superadmin", "teacher"):
        return JsonResponse({"error": "forbidden"}, status=403)

    # Handle POST actions: approve/reject/pending user, broadcast, download
    if request.method == "POST":
        try:
            payload = json.loads(request.body.decode())
        except Exception:
            return JsonResponse({"error": "invalid JSON"}, status=400)

        action = payload.get("action")

        # ---------------------------
        # Approve / Reject / Pend user
        # ---------------------------
        if action == "update_user_status":
            if request.user.role not in ("admin", "superadmin"):
                return JsonResponse({"error": "forbidden"}, status=403)
            user_id = payload.get("user_id")
            new_status = payload.get("status")  # "approve"/"reject"/"pending"
            target_user = get_object_or_404(User, id=user_id)
            old_approved = target_user.approved
            if new_status == "approve":
                target_user.approved = True
            elif new_status == "reject":
                # we don't delete here automatically; mark approved False and optionally flag
                target_user.approved = False
            elif new_status == "pending":
                target_user.approved = False
            else:
                return JsonResponse({"error": "invalid status"}, status=400)
            target_user.save(update_fields=["approved"])
            # Log action
            ActionLog.objects.create(
                user=request.user,
                action=f"Updated user status -> {new_status}",
                model_name="User",
                object_id=str(target_user.id),
                details={"old_approved": old_approved, "new_approved": target_user.approved},
            )
            return JsonResponse({"ok": True, "message": f"{target_user.username} set to {new_status}"})

        # ---------------------------
        # Broadcast (admin can to teachers/students; teacher can to students only)
        # ---------------------------
        if action == "broadcast":
            role = payload.get("role")  # 'teacher' or 'student'
            message = payload.get("message", "").strip()
            if not role or not message:
                return JsonResponse({"error": "role & message required"}, status=400)
            # permission check: teacher can only send to 'student'
            if request.user.role == "teacher" and role != "student":
                return JsonResponse({"error": "forbidden"}, status=403)
            # admins can send to both teachers/students
            recipients = User.objects.filter(role=role, approved=True)
            created = 0
            for r in recipients:
                Notification.objects.create(sender=request.user, recipient=r, message=message, role=role, is_broadcast=True)
                created += 1
                ActionLog.objects.create(
                user=request.user,
                action="Broadcast",
                model_name="Notification",
                object_id="bulk",
                details={"role": role, "count": created, "message": message[:200]},
            )
            return JsonResponse({"ok": True, "message": f"Broadcast sent to {created} {role}(s).", "count": created})

        # ---------------------------
        # Download all attempts (excel or pdf)
        # payload: {action: "download", format: "pdf"|"excel"}
        # ---------------------------
        if action == "download":
            if request.user.role not in ("admin", "superadmin"):
                return JsonResponse({"error": "forbidden"}, status=403)

            fmt = payload.get("format", "pdf")
            # Query attempts (all completed attempts)
            attempts_qs = StudentQuizAttempt.objects.filter(completed=True).select_related("quiz", "student")

            # Build in-memory file
            if fmt == "excel":
                wb = openpyxl.Workbook()
                ws = wb.active
                ws.title = "AllAttempts"
                headers = ["Student", "Username", "Quiz", "Score", "Started At", "Completed At"]
                ws.append(headers)
                for a in attempts_qs:
                    student_username = a.student.username if hasattr(a.student, "username") else str(a.student)
                    started = a.started_at.strftime("%Y-%m-%d %H:%M") if a.started_at else ""
                    completed_at = a.completed_at.strftime("%Y-%m-%d %H:%M") if getattr(a, "completed_at", None) else ""
                    ws.append([getattr(a.student, "get_full_name", student_username) or student_username, student_username, a.quiz.title, a.score, started, completed_at])
                # save to bytes
                bio = io.BytesIO()
                wb.save(bio)
                bio.seek(0)
                ActionLog.objects.create(user=request.user, action="Downloaded all attempts (excel)", model_name="StudentQuizAttempt", object_id="all", details={"count": attempts_qs.count()})
                response = HttpResponse(bio.read(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                response["Content-Disposition"] = "attachment; filename=all_attempts.xlsx"
                return response

            # PDF via ReportLab
            buffer = io.BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=A4)
            elements = []
            styles = getSampleStyleSheet()
            elements.append(Paragraph("All Attempts Results", styles["Title"]))
            elements.append(Spacer(1, 12))

            table_data = [["Student", "Username", "Quiz", "Score", "Started At", "Completed At"]]
            for a in attempts_qs:
                student_username = a.student.username if hasattr(a.student, "username") else str(a.student)
                started = a.started_at.strftime("%Y-%m-%d %H:%M") if a.started_at else ""
                completed_at = a.completed_at.strftime("%Y-%m-%d %H:%M") if getattr(a, "completed_at", None) else ""
                table_data.append([getattr(a.student, "get_full_name", student_username) or student_username, student_username, a.quiz.title, str(a.score), started, completed_at])
            tbl = Table(table_data, repeatRows=1)
            tbl.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.gray),
                                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                                    ("GRID", (0, 0), (-1, -1), 0.5, colors.black),]))
            elements.append(tbl)
            doc.build(elements)
            buffer.seek(0)
            ActionLog.objects.create(user=request.user, action="Downloaded all attempts (pdf)", model_name="StudentQuizAttempt", object_id="all", details={"count": attempts_qs.count()})
            response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
            response["Content-Disposition"] = "attachment; filename=all_attempts.pdf"
            return response

        return JsonResponse({"error": "unknown action"}, status=400)

    # -----------------------
    # GET: return dashboard data JSON
    # Supports pagination parameters: logs_page, quizzes_page, quizzes_page_size, logs_page_size
    # -----------------------
    # Stats
    stats = {
        "total_users": User.objects.filter(role__in=["admin", "teacher", "student"], approved=True).count(),
        "admins": User.objects.filter(role="admin", approved=True).count(),
        "teachers": User.objects.filter(role="teacher", approved=True).count(),
        "students": User.objects.filter(role="student", approved=True).count(),
        "pending_users": User.objects.filter(approved=False).count(),
        "classes": Class.objects.count(),
        "subjects": Subject.objects.count(),
        "quizzes": Quiz.objects.count(),
    }
    
    # Pending users (basic)
    pending_list_qs = User.objects.filter(approved=False).order_by("-date_joined")
    pending_list = list(pending_list_qs.values("id", "username", "email", "role", "date_joined")[:50])

    # Action logs paginated
    logs_page = int(request.GET.get("logs_page", 1))
    logs_page_size = int(request.GET.get("logs_page_size", 10))
    logs_qs = ActionLog.objects.order_by("-timestamp")
    paginator_logs = Paginator(logs_qs, logs_page_size)
    page_logs = paginator_logs.get_page(logs_page)
    logs = [
        {"action": l.action_type, "user": (l.user.username if l.user else "system"), "timestamp": l.timestamp.isoformat(), "details": l.details}
        for l in page_logs
    ]

    # Leaderboard (top students by average obtained_marks across answers)
    leaderboard_qs = Answer.objects.values("attempt__student__username").annotate(avg_score=Avg("obtained_marks")).order_by("-avg_score")[:10]
    leaderboard = [{"username": r["attempt__student__username"], "avg_score": float(r["avg_score"] or 0)} for r in leaderboard_qs]

    # Class performance (avg obtained marks grouped by class)
    class_perf_qs = Answer.objects.values("attempt__quiz__subject__school_class__name").annotate(avg_score=Avg("obtained_marks")).order_by("attempt__quiz__subject__school_class__name")
    class_performance = [
        {"class_name": row["attempt__quiz__subject__school_class__name"] or "Unknown", "avg_score": float(row["avg_score"] or 0)}
        for row in class_perf_qs
    ]

    # Available quizzes (paginated) - show basic metadata
    quizzes_page = int(request.GET.get("quizzes_page", 1))
    quizzes_page_size = int(request.GET.get("quizzes_page_size", 10))
    quizzes_qs = Quiz.objects.select_related("subject", "created_by").order_by("-created_at")
    paginator_quiz = Paginator(quizzes_qs, quizzes_page_size)
    page_quiz = paginator_quiz.get_page(quizzes_page)
    quizzes = [
        {
            "id": q.id,
            "title": q.title,
            "subject": q.subject.name,
            "class_name": q.subject.school_class.name,
            "created_by": getattr(q.created_by, "username", str(q.created_by)),
            "start_time": q.start_time.isoformat(),
            "end_time": q.end_time.isoformat(),
            "is_published": q.is_published,
            "allow_retake": getattr(q, "allow_retake", False),
        }
        for q in page_quiz
    ]

    # Notifications for this admin (last 10)
    notifications_qs = Notification.objects.filter(recipient=request.user, is_read=False).order_by("-created_at")[:10]
    notifications = [{"id": n.id, "message": n.message, "sender": getattr(n.sender, "username", None), "created_at": n.created_at.isoformat()} for n in notifications_qs]


    return JsonResponse({
        "stats": stats,
        "pending_list": pending_list,
        "logs": logs,
        "logs_total_pages": paginator_logs.num_pages,
        "leaderboard": leaderboard,
        "class_performance": class_performance,
        "notifications": notifications,
        "quizzes": quizzes,
        "quizzes_total_pages": paginator_quiz.num_pages,
    })

#-------------------------- Teacher Dashboard --------------------------###

def is_teacher(user):
    return user.is_authenticated and user.role == "teacher"



# ----------------- TEACHER DASHBOARD -------------------
@login_required
@user_passes_test(is_teacher)
def teacher_dashboard(request):
    return render(request, "exams/teacher_dashboard", {})

@login_required
@user_passes_test(is_teacher)
def teacher_dashboard_data(request):
    teacher = request.user
    admin = User.objects.filter(role="admin", approved=True).first()
    superadmin = User.objects.filter(role="superadmin", approved=True).first()  

    # Paginated quizzes
    quiz_qs = Quiz.objects.filter(created_by__in=[teacher, admin, superadmin]).order_by("-start_time")
    quiz_page = Paginator(quiz_qs, 5).get_page(request.GET.get("quiz_page", 1))

     # Example queryset
    notifications = Notification.objects.filter(recipient=request.user).order_by('-created_at')

    # Paginator for notifications
    page = request.GET.get("page", 1)
    paginator = Paginator(notifications, 5)  # 5 per page
    notif_page = paginator.get_page(page)    # ✅ returns a Page object

    # Active class performance (aggregate on Answer model)
    class_performance = (
        Answer.objects.filter(question__quiz__in=quiz_qs)
        .values("question__quiz__subject__school_class__name")
        .annotate(avg_score=Avg("obtained_marks"))
    )

    # Notifications
    notif_qs = Notification.objects.filter(sender=teacher).order_by("-created_at")
    notif_page = Paginator(notif_qs, 5).get_page(request.GET.get("notif_page", 1))


    # pagination params
    notif_page_num = int(request.GET.get("notif_page", 1))
    notif_page_size = int(request.GET.get("notif_page_size", 6))

    # teacher broadcasts (they are just notifications they sent)
    broadcasts_qs = Notification.objects.filter(
        sender__role__in=["admin", "student"],
        message__startswith="📢",
    ).order_by("-created_at")

    paginator = Paginator(broadcasts_qs, notif_page_size)
    page = paginator.get_page(notif_page_num)

    broadcasts_data = [
        {
            "id": n.id,
            "message": n.message,
            "created_at": n.created_at.isoformat(),
            "is_read": n.is_read,
        }
        for n in page.object_list
    ]

    notifications_data = [{"id": n.id, "message": n.message, "is_read": n.is_read} for n in notif_page]

    # ... other data (quizzes, grading, performance, etc.)
    summary = {
        "total_attempts": 42,
        "auto_graded_count": 18,
        "pending_subjectives": 3,
    }

    return JsonResponse({
        "summary": summary,
        "broadcasts": broadcasts_data,
        "broadcasts_meta": {
            "page": page.number,
            "pages": paginator.num_pages,
            "total": paginator.count,
        },
        "quizzes": list(quiz_page.object_list.values("id", "title", "subject__name", "start_time", "end_time")),
        # "class_performance": list(class_performance),
        "notifications": notifications_data,
        "pagination": {
            "quizzes": quiz_page.has_next(),
            "notifications": notif_page.has_next(),
        },
        # keep other fields: quizzes, attempts, leaderboard, performance_chart
    })

   

# ----------------- GRADE QUIZ -------------------
@login_required
@user_passes_test(is_teacher)
def grade_quiz(request, quiz_id):
    quiz = get_object_or_404(Quiz, id=quiz_id, created_by=request.user)
    attempts = StudentQuizAttempt.objects.filter(quiz=quiz)

    if request.method == "POST":
        for ans in Answer.objects.filter(attempt__quiz=quiz, is_pending=True):
            marks = float(request.POST.get(f"marks_{ans.id}", 0))
            ans.obtained_marks = marks
            ans.is_pending = False
            ans.graded_by = request.user
            ans.graded_at = timezone.now()
            ans.save()

        ActionLog.objects.create(user=request.user, action="Graded Quiz", model_name="Quiz", object_id=str(quiz.id))
        return JsonResponse({"success": True})

    return render(request, "teacher/grade_quiz.html", {"quiz": quiz, "attempts": attempts})

# ----------------- STUDENT REVIEW -------------------
@login_required
@user_passes_test(is_teacher)
def student_review(request, student_id):
    student = get_object_or_404(User, id=student_id, role="student")
    attempts = StudentQuizAttempt.objects.filter(student=student).select_related("quiz")
    return render(request, "teacher/student_review.html", {"student": student, "attempts": attempts})

# ----------------- RETAKE REQUEST -------------------
@login_required
@user_passes_test(is_teacher)
def approve_retake(request, quiz_id, student_id):
    student = get_object_or_404(User, id=student_id, role="student")
    quiz = get_object_or_404(Quiz, id=quiz_id, created_by=request.user)

    attempt, _ = StudentQuizAttempt.objects.get_or_create(student=student, quiz=quiz)
    attempt.retake_allowed = True
    attempt.completed = False
    attempt.end_time = None
    attempt.retake_count += 1
    attempt.save()

    Notification.objects.create(user=student, message=f"You can now retake quiz: {quiz.title}")
    ActionLog.objects.create(user=request.user, action="Approved Retake", model_name="Quiz", object_id=str(quiz.id))

    return JsonResponse({"success": True})

# ----------------- BROADCAST MESSAGE -------------------
@login_required
@user_passes_test(is_teacher)
def broadcast_message(request):
    if request.method == "POST":
        message = request.POST.get("message")
        students = User.objects.filter(role="student", school_class__in=request.user.classes.all())
        for student in students:
            Notification.objects.create(recipient=student, message=message, sender=request.user, is_broadcast=True, defaults={"role": "student", "created_at": timezone.now()})

        ActionLog.objects.create(user=request.user, action="Broadcast Message", model_name="BroadcastMessage", object_id=str(request.user.id))
        return JsonResponse({"success": True})
    return JsonResponse({"error": "Invalid request"}, status=400)



def teacher_broadcast(request):
    """Teacher sends broadcast notifications to admins, students, or all."""
    if request.method == "POST":
        message = request.POST.get("message")
        target = request.POST.get("target")  # admins | students | all

        if not message or not target:
            return JsonResponse({"ok": False, "error": "Message and target required."})

        # recipients
        if target == "admins":
            recipients = User.objects.filter(role="admin")
        elif target == "students":
            recipients = User.objects.filter(role="student", classroom__in=request.user.classroom_set.all())
        else:  # all
            recipients = User.objects.filter(role__in=["admin", "student"])

        # create notifications
        notifications = [
            Notification(
                user=r,
                message=f"📢 {message}",
                created_at=timezone.now(),
                is_read=False,
            )
            for r in recipients
        ]
        Notification.objects.bulk_create(notifications)

        # log action
        log_action(request.user, f"Broadcasted to {target}: {message}")

        return JsonResponse({"ok": True, "message": f"Broadcast sent to {target}"})

    return JsonResponse({"ok": False, "error": "Invalid request"})




# ----------------- DOWNLOAD REPORTS -------------------
@login_required
@user_passes_test(is_teacher)
def download_student_report(request, student_id):
    student = get_object_or_404(User, id=student_id, role="student")
    attempts = StudentQuizAttempt.objects.filter(student=student)

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer)
    story = []
    styles = getSampleStyleSheet()

    story.append(Paragraph(f"<b>School Name</b>", styles["Title"]))
    story.append(Paragraph(f"Student: {student.get_full_name()}", styles["Heading2"]))
    story.append(Spacer(1, 12))

    for attempt in attempts:
        story.append(Paragraph(f"Quiz: {attempt.quiz.title} | Date: {attempt.start_time}", styles["Normal"]))
        for ans in attempt.answers.all():
            story.append(Paragraph(f"- {ans.question.text}: {ans.obtained_marks}", styles["Normal"]))

    doc.build(story)
    response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{student.username}_report.pdf"'
    return response

@login_required
@user_passes_test(is_teacher)
def download_quiz_report(request, quiz_id):
    quiz = get_object_or_404(Quiz, id=quiz_id, created_by=request.user)
    attempts = StudentQuizAttempt.objects.filter(quiz=quiz)

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer)
    story = []
    styles = getSampleStyleSheet()

    story.append(Paragraph(f"<b>School Name</b>", styles["Title"]))
    story.append(Paragraph(f"Quiz Report: {quiz.title}", styles["Heading2"]))
    story.append(Spacer(1, 12))

    for attempt in attempts:
        student = attempt.student
        story.append(Paragraph(f"Student: {student.get_full_name()} | Date: {attempt.start_time}", styles["Normal"]))
        for ans in attempt.answers.all():
            story.append(Paragraph(f"- {ans.question.text}: {ans.obtained_marks}", styles["Normal"]))
        story.append(Spacer(1, 6))

    doc.build(story)
    response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="quiz_{quiz.id}_report.pdf"'
    return response

# ----------------- MARK NOTIFICATION READ -------------------
@login_required
def mark_notification_read(request, notification_id):
    notif = get_object_or_404(Notification, id=notification_id, user=request.user)
    notif.is_read = True
    notif.save()
    return JsonResponse({"success": True})


# ----------------------Teacher dashboard data endpoint (JSON) (for AJAX refresh)-------------------------#

# @login_required
# @user_passes_test(lambda u: u.role == "teacher")
# def teacher_dashboard_data(request):
#     teacher = request.user

#     # Teacher’s created quizzes
#     quizzes = Quiz.objects.filter(created_by=teacher)

#     stats = {
#         "total_quizzes": quizzes.count(),
#         "published_quizzes": quizzes.filter(is_published=True).count(),
#         "pending_quizzes": quizzes.filter(is_published=False).count(),
#         "total_students_attempted": StudentQuizAttempt.objects.filter(quiz__in=quizzes, completed=True).values("student").distinct().count(),
#     }

#     # Leaderboard for teacher’s quizzes
#     leaderboard_qs = (
#         StudentQuizAttempt.objects.filter(quiz__in=quizzes, completed=True)
#         .values("student__username")
#         .annotate(avg_score=Avg("score"))
#         .order_by("-avg_score")[:10]
#     )
#     leaderboard = [{"username": x["student__username"], "avg_score": float(x["avg_score"] or 0)} for x in leaderboard_qs]

#     # Action logs
#     actions = list(
#         ActionLog.objects.filter(user=teacher).order_by("-timestamp")[:10].values("action", "timestamp")
#     )

#     return JsonResponse({"stats": stats, "leaderboard": leaderboard, "actions": actions})



###--------------------------------Student Dashboard -------------------------------###

def is_student(user):
    return user.is_authenticated and user.role == 'student' 


# helper
def is_student(user):
    return user.is_authenticated and getattr(user, "role", None) == "student"


@login_required
@user_passes_test(is_student)
def student_dashboard(request):
    """Render the student dashboard shell. Data comes from student_dashboard_data (AJAX)."""
    return render(request, "exams/student_dashboard.html")


@login_required
@user_passes_test(is_student)
def student_dashboard_data(request):
    """
    Returns JSON containing:
      - notifications (paginated)
      - summary (counts)
      - available_quizzes (paginated)
      - past_attempts (paginated)
      - leaderboard (top 10)
      - performance_chart (subject -> %)
    Query params (optional):
      notif_page, notif_page_size, quizzes_page, quizzes_page_size, attempts_page, attempts_page_size
    """
    student = request.user
    student_class = getattr(student, "student_class", None)

    # pagination params
    notif_page = int(request.GET.get("notif_page", 1))
    notif_page_size = int(request.GET.get("notif_page_size", 6))
    quizzes_page = int(request.GET.get("quizzes_page", 1))
    quizzes_page_size = int(request.GET.get("quizzes_page_size", 6))
    attempts_page = int(request.GET.get("attempts_page", 1))
    attempts_page_size = int(request.GET.get("attempts_page_size", 6))

    # ---------------- Notifications (paginated) ----------------
    notif_qs = Notification.objects.filter(recipient=student).order_by("-created_at")
    notif_p = Paginator(notif_qs, notif_page_size)
    notif_page_obj = notif_p.get_page(notif_page)
    notifications = [
        {"id": n.id, "message": n.message, "is_read": n.is_read, "created_at": n.created_at.isoformat()}
        for n in notif_page_obj
    ]
    notif_meta = {"page": notif_page_obj.number, "pages": notif_p.num_pages, "total": notif_p.count}

    # ---------------- Summary ----------------
    total_attempts = StudentQuizAttempt.objects.filter(student=student).count()
    auto_graded_count = Answer.objects.filter(attempt__student=student, is_pending=False).count()
    pending_subjectives = Answer.objects.filter(attempt__student=student, is_pending=True).count()

    summary = {
        "total_attempts": total_attempts,
        "auto_graded_count": auto_graded_count,
        "pending_subjectives": pending_subjectives,
    }

    # ---------------- Available quizzes (paginated) ----------------
    now = timezone.now()
    if student_class is None:
        available_qs = Quiz.objects.none()
    else:
        available_qs = Quiz.objects.filter(
            subject__school_class=student_class,
            is_published=True,
            start_time__lte=now,
            end_time__gte=now,
        ).order_by("-created_at")

        # exclude quizzes already completed without retake allowed
        exclude_ids = StudentQuizAttempt.objects.filter(
            student=student, completed=True, retake_allowed=False
        ).values_list("quiz_id", flat=True)
        available_qs = available_qs.exclude(id__in=exclude_ids)

    qp = Paginator(available_qs, quizzes_page_size)
    qp_obj = qp.get_page(quizzes_page)

    quizzes_data = []
    # build rich data (can't easily get allow_retake from values; use getattr)
    for q in qp_obj:
        # check last attempt status
        last_attempt = StudentQuizAttempt.objects.filter(student=student, quiz=q).order_by("-started_at").first()
        already_completed = StudentQuizAttempt.objects.filter(student=student, quiz=q, completed=True).exists()
        student_retake_override = bool(last_attempt and getattr(last_attempt, "retake_allowed", False))
        allow_retake_global = getattr(q, "allow_retake", False) if hasattr(q, "allow_retake") else False

        quizzes_data.append({
            "id": q.id,
            "title": q.title,
            "subject": q.subject.name if q.subject else "",
            "class_name": q.subject.school_class.name if (q.subject and q.subject.school_class) else "",
            "start_time": q.start_time.isoformat() if q.start_time else None,
            "end_time": q.end_time.isoformat() if q.end_time else None,
            "duration_minutes": getattr(q, "duration_minutes", None),
            "is_published": bool(q.is_published),
            "allow_retake": bool(allow_retake_global),
            "already_completed": bool(already_completed),
            "student_retake_override": student_retake_override,
        })

    quizzes_meta = {"page": qp_obj.number, "pages": qp.num_pages, "total": qp.count}

    # ---------------- Past attempts (paginated) ----------------
    attempts_qs = StudentQuizAttempt.objects.filter(student=student).select_related("quiz").order_by("-started_at")
    ap = Paginator(attempts_qs, attempts_page_size)
    ap_obj = ap.get_page(attempts_page)

    past_attempts = []
    for a in ap_obj:
        # compute totals for this attempt using Answer model
        answers = Answer.objects.filter(attempt=a).select_related("question", "selected_choice")
        total_marks = 0
        obtained = 0.0
        pending_subjectives_count = 0
        wrong_review = []
        for ans in answers:
            q_marks = getattr(ans.question, "marks", 0) or 0
            total_marks += q_marks
            if ans.is_pending:
                pending_subjectives_count += 1
                # subjective might not have marks yet; don't include
            else:
                # for objective and graded subjective
                obtained += float(ans.obtained_marks or 0.0)
            # for review: detect wrong objective answers
            # if question is objective and selected_choice exists but is incorrect
            if getattr(ans.question, "question_type", getattr(ans.question, "type", None)) in ("objective", "multiple_choice"):
                if not (ans.selected_choice and getattr(ans.selected_choice, "is_correct", False)):
                    # get correct answer text(s)
                    correct_choices = ans.question.choices.filter(is_correct=True).values_list("text", flat=True)
                    correct_text = ", ".join(correct_choices) if correct_choices else ""
                    user_ans = ans.selected_choice.text if ans.selected_choice else "-"
                    wrong_review.append({
                        "question": ans.question.text,
                        "your_answer": user_ans,
                        "correct_answer": correct_text
                    })

        past_attempts.append({
            "attempt_id": a.id,
            "quiz": a.quiz.title if a.quiz else "",
            "score": float(a.score or obtained),
            "obtained_marks": obtained,
            "total_marks": total_marks,
            "pending_subjectives": pending_subjectives_count,
            "completed": bool(a.completed),
            "started_at": a.started_at.isoformat() if getattr(a, "started_at", None) else None,
            "completed_at": getattr(a, "completed_at", None).isoformat() if getattr(a, "completed_at", None) else None,
            "wrong_answers": wrong_review,
            "retake_count": getattr(a, "retake_count", 0),
        })

    attempts_meta = {"page": ap_obj.number, "pages": ap.num_pages, "total": ap.count}

    # ---------------- Leaderboard (top 10 students) ----------------
    lb_qs = (
        StudentQuizAttempt.objects.filter(completed=True)
        .values("student__id", "student__username", "student__first_name", "student__last_name")
        .annotate(avg_score=Avg("score"))
        .order_by("-avg_score")[:10]
    )
    leaderboard = [
        {
            "student_id": r["student__id"],
            "username": r.get("student__username"),
            "full_name": f"{r.get('student__first_name') or ''} {r.get('student__last_name') or ''}".strip(),
            "avg_score": float(r["avg_score"] or 0)
        }
        for r in lb_qs
    ]

    # ---------------- Performance Chart (per subject in student's class) ----------------
    perf_qs = Answer.objects.filter(
        attempt__student=student,
        attempt__quiz__subject__school_class=student_class
    ).values("attempt__quiz__subject__name").annotate(
        obtained=Sum("obtained_marks"),
        possible=Sum("question__marks")
    )

    performance_chart = []
    for r in perf_qs:
        subj = r.get("attempt__quiz__subject__name") or "Unknown"
        obtained = float(r.get("obtained") or 0)
        possible = float(r.get("possible") or 0) or 0.0
        pct = round((obtained / possible) * 100, 2) if possible > 0 else 0.0
        performance_chart.append({"subject": subj, "obtained": obtained, "possible": possible, "percentage": pct})

    # ---------------- Return JSON ----------------
    return JsonResponse({
        "notifications": notifications,
        "notifications_meta": notif_meta,
        "summary": summary,
        "available_quizzes": quizzes_data,
        "available_quizzes_meta": quizzes_meta,
        "past_attempts": past_attempts,
        "past_attempts_meta": attempts_meta,
        "leaderboard": leaderboard,
        "performance_chart": performance_chart,
    })


@require_POST
@login_required
@user_passes_test(is_student)
def api_notifications_mark_read(request):
    """Mark notification read (AJAX POST: {id: notification_id})"""
    import json
    try:
        payload = json.loads(request.body.decode())
    except Exception:
        return JsonResponse({"ok": False, "error": "invalid json"}, status=400)

    nid = payload.get("id")
    if not nid:
        return JsonResponse({"ok": False, "error": "id required"}, status=400)

    notif = get_object_or_404(Notification, id=nid, recipient=request.user)
    notif.is_read = True
    notif.save(update_fields=["is_read"])
    return JsonResponse({"ok": True, "id": nid})


### ------------------------------ Student_dashboard Ended ----------------------------------------------------##

def _is_admin(user):
    return user.is_authenticated and user.role in ("admin", "superadmin")

def _is_teacher(user):
    return user.is_authenticated and user.role == "teacher"


# Broadcast endpoint
# -------------------
@login_required
@require_POST
def api_broadcast(request):
    """
    POST JSON { "role": "student"|"teacher", "message": "..." }
    - Admins (admin/superadmin) may broadcast to 'teacher' or 'student'
    - Teachers may broadcast only to 'student'
    Creates Notification objects for each recipient and logs ActionLog.
    """
    try:
        payload = json.loads(request.body.decode())
    except Exception:
        return JsonResponse({"ok": False, "error": "Invalid JSON"}, status=400)

    role = payload.get("role")
    message = (payload.get("message") or "").strip()
    if not role or not message:
        return JsonResponse({"ok": False, "error": "role and message required"}, status=400)

    # Permissions: teacher can only send to students
    if request.user.role == "teacher" and role != "student":
        return JsonResponse({"ok": False, "error": "forbidden"}, status=403)

    # Only allow admin/teacher to broadcast
    if request.user.role not in ("admin", "superadmin", "teacher"):
        return JsonResponse({"ok": False, "error": "forbidden"}, status=403)

    recipients = User.objects.filter(role=role, approved=True)
    created = 0
    for r in recipients:
        # Notification.objects.create(sender=request.user, recipient=r, role=role, message=message, created_at=timezone.now())
        created += 1

    ActionLog.objects.create(
        user=request.user,
        action="Broadcast sent",
        model_name="Notification",
        object_id="bulk",
        details={"role": role, "count": created, "sample": message[:120]},
        timestamp=timezone.now()
    )

    return JsonResponse({"ok": True, "message": f"Broadcast sent to {created} {role}(s).", "count": created})


# -------------------
# Get unread notifications for current user
# -------------------
@login_required
def api_notifications_unread(request):
    """
    GET -> returns unread (is_read=False) notifications for request.user
    """
    qs = Notification.objects.filter(recipient=request.user, is_read=False).order_by("-created_at")
    data = [
        {
            "id": n.id,
            "message": n.message,
            "sender": n.sender.username if n.sender else None,
            "created_at": n.created_at.isoformat()
        }
        for n in qs
    ]
    return JsonResponse({"ok": True, "notifications": data})


# -------------------
# Mark notification as read
# -------------------

@login_required
@require_POST
def api_notifications_mark_read(request):
    """
    # POST JSON { "id": <notification_id> } -> set is_read = True for that notification if it belongs to current user
    """
    try:
        payload = json.loads(request.body.decode())
    except Exception:
        return JsonResponse({"ok": False, "error": "Invalid JSON"}, status=400)

    nid = payload.get("id")
    if not nid:
        return JsonResponse({"ok": False, "error": "id required"}, status=400)

    notif = get_object_or_404(Notification, id=nid, recipient=request.user)
    notif.is_read = True
    notif.save(update_fields=["is_read"])

    ActionLog.objects.create(
        user=request.user,
        action="Read notification",
        model_name="Notification",
        object_id=str(nid),
        # details={"message_sample": (notif.message[:80] if notif.message else "")},
        timestamp=timezone.now()
    )

    return JsonResponse({"ok": True, "message": "marked read", "id": nid})


####--------------------------No 1 Endpoint Ended----------------------------####


def _is_student(user):
    return user.is_authenticated and user.role == "student"


@require_http_methods(["GET"])
def api_student_quizzes(request):
    """Return available quizzes for the logged-in student (AJAX)."""
    if not _is_student(request.user):
        return JsonResponse({"ok": False, "error": "forbidden"}, status=403)

    now = timezone.now()
    # student's class is stored on user.student_class (per your model)
    student_class = getattr(request.user, "student_class", None)

    # exclude quizzes the student already completed unless allow_retake or specific retake allowed
    completed_q_ids = StudentQuizAttempt.objects.filter(
        student=request.user, completed=True
    ).values_list("quiz_id", flat=True)

    # Build queryset: published, in time window, for the student's class
    qset = Quiz.objects.filter(
        is_published=True,
        subject__school_class=student_class,
        start_time__lte=now,
        end_time__gte=now,
    ).order_by("-created_at")

    quizzes = []
    for q in qset:
        already_completed = q.id in completed_q_ids
        can_retake_global = getattr(q, "allow_retake", False)
        # find last attempt
        last_attempt = StudentQuizAttempt.objects.filter(student=request.user, quiz=q).order_by("-started_at").first()
        # student-specific retake override
        student_retake_override = last_attempt.retake_allowed if last_attempt else False
        show = (not already_completed) or can_retake_global or student_retake_override
        quizzes.append({
            "id": q.id,
            "title": q.title,
            "subject": q.subject.name,
            "class_name": q.subject.school_class.name,
            "start_time": q.start_time.isoformat(),
            "end_time": q.end_time.isoformat(),
            "duration_minutes": q.duration_minutes,
            "allow_retake": bool(can_retake_global),
            "already_completed": bool(already_completed),
            "show": show,
        })

    return JsonResponse({"ok": True, "quizzes": [q for q in quizzes if q["show"]]})


@require_http_methods(["GET"])
def api_student_attempts(request):
    """Return past attempts for the logged-in student."""
    if not _is_student(request.user):
        return JsonResponse({"ok": False, "error": "forbidden"}, status=403)

    attempts_qs = StudentQuizAttempt.objects.filter(student=request.user).select_related("quiz").order_by("-started_at")
    attempts = []
    for a in attempts_qs:
        attempts.append({
            "id": a.id,
            "quiz_id": a.quiz.id,
            "quiz": a.quiz.title,
            "score": float(a.score or 0.0),
            "retake_count": getattr(a, "retake_count", 0),
            "completed": bool(a.completed),
            "started_at": a.started_at.isoformat() if getattr(a, "started_at", None) else None,
            "end_time": a.end_time.isoformat() if getattr(a, "end_time", None) else None,
            # completed_at might not exist; use getattr
            "completed_at": getattr(a, "completed_at", None) and a.completed_at.isoformat() or None,
            "can_resume": getattr(a, "can_resume", lambda: False)() if hasattr(a, "can_resume") else (not a.completed and (not a.end_time or timezone.now() < a.end_time)),
            "can_retake": bool(getattr(a, "retake_allowed", False) or getattr(a.quiz, "allow_retake", False))
        })
    return JsonResponse({"ok": True, "attempts": attempts})


@require_http_methods(["GET"])
def api_notifications_unread(request):
    """Return unread notifications for current user."""
    if not request.user.is_authenticated:
        return JsonResponse({"ok": False, "error": "forbidden"}, status=403)

    from users.models import Notification  # import here to avoid circular issues
    qs = Notification.objects.filter(recipient=request.user, is_read=False).order_by("-created_at")
    notifs = [{
        "id": n.id,
        "message": n.message,
        "sender": n.sender.username if n.sender else None,
        "created_at": n.created_at.isoformat()
    } for n in qs]
    return JsonResponse({"ok": True, "notifications": notifs})


@require_http_methods(["POST"])
def api_notifications_mark_read(request):
    """Mark notification as read (student/teacher/admin)."""
    if not request.user.is_authenticated:
        return JsonResponse({"ok": False, "error": "forbidden"}, status=403)

    try:
        payload = json.loads(request.body.decode())
    except Exception:
        return JsonResponse({"ok": False, "error": "invalid json"}, status=400)

    nid = payload.get("id")
    if not nid:
        return JsonResponse({"ok": False, "error": "id required"}, status=400)

    from users.models import Notification
    notif = get_object_or_404(Notification, id=nid, recipient=request.user)
    notif.is_read = True
    notif.save(update_fields=["is_read"])
    ActionLog.objects.create(user=request.user, action="Read notification", model_name="Notification", object_id=str(nid))
    return JsonResponse({"ok": True, "id": nid})


@require_http_methods(["GET"])
def api_take_quiz(request):
    """
    Returns rendered HTML for the quiz modal. Query params:
      - quiz_id (required)
      - mode: 'start' (default) or 'retake'
    """
    if not _is_student(request.user):
        return JsonResponse({"ok": False, "error": "forbidden"}, status=403)

    quiz_id = request.GET.get("quiz_id")
    mode = request.GET.get("mode", "start")
    if not quiz_id:
        return JsonResponse({"ok": False, "error": "quiz_id required"}, status=400)

    quiz = get_object_or_404(Quiz, id=quiz_id)
    now = timezone.now()

    # Basic availability checks (published & time window)
    if not quiz.is_published:
        return JsonResponse({"ok": False, "error": "Quiz not published"}, status=403)
    if not (quiz.start_time <= now <= quiz.end_time):
        # allow retake if mode == retake and admin override, otherwise forbid
        if not (mode == "retake" and (quiz.allow_retake or request.user.is_staff)):
            return JsonResponse({"ok": False, "error": "Quiz not currently available"}, status=403)

    # Find or create attempt
    attempt = None
    if mode == "start":
        # resume existing attempt if not completed and not expired
        attempt = StudentQuizAttempt.objects.filter(student=request.user, quiz=quiz, completed=False).order_by("-started_at").first()
        if attempt and not getattr(attempt, "can_resume", lambda: True)():
            attempt = None
        if not attempt:
            # create new attempt
            attempt = StudentQuizAttempt.objects.create(
                student=request.user,
                quiz=quiz,
                started_at=timezone.now(),
                end_time=timezone.now() + timezone.timedelta(minutes=quiz.duration_minutes),
                completed=False,
                retake_allowed=False,
                retake_count=0,
                score=0.0
            )
    elif mode == "retake":
        # allow retake if quiz.allow_retake or last attempt has retake_allowed True
        last_attempt = StudentQuizAttempt.objects.filter(student=request.user, quiz=quiz).order_by("-started_at").first()
        if not (quiz.allow_retake or (last_attempt and last_attempt.retake_allowed)):
            return JsonResponse({"ok": False, "error": "Retake not allowed"}, status=403)
        # create a new attempt
        prev_count = last_attempt.retake_count if last_attempt else 0
        attempt = StudentQuizAttempt.objects.create(
            student=request.user,
            quiz=quiz,
            started_at=timezone.now(),
            end_time=timezone.now() + timezone.timedelta(minutes=quiz.duration_minutes),
            completed=False,
            retake_allowed=False,
            retake_count=(prev_count + 1),
            score=0.0
        )

    # Prefetch questions & choices
    questions = list(quiz.questions.prefetch_related("choices").all())
    # Render partial template with context (use request to have csrf_token)
    context = {"quiz": quiz, "attempt": attempt, "questions": questions}
    html = render_to_string("exams/partials/quiz_modal.html", context=context, request=request)
    return JsonResponse({"ok": True, "quiz_title": quiz.title, "html": html})


@require_http_methods(["POST"])
def api_submit_answer(request):
    """Save one answer (autosave). Payload JSON: {attempt_id, question_id, answer, type}"""
    if not _is_student(request.user):
        return JsonResponse({"ok": False, "error": "forbidden"}, status=403)

    try:
        payload = json.loads(request.body.decode())
    except Exception:
        return JsonResponse({"ok": False, "error": "invalid json"}, status=400)

    attempt_id = payload.get("attempt_id")
    qid = payload.get("question_id")
    answer = payload.get("answer")
    qtype = payload.get("type")

    if not all([attempt_id, qid]):
        return JsonResponse({"ok": False, "error": "attempt_id and question_id required"}, status=400)

    attempt = get_object_or_404(StudentQuizAttempt, id=attempt_id, student=request.user)
    # do not allow saving if attempt is completed or expired
    if attempt.completed:
        return JsonResponse({"ok": False, "error": "attempt already completed"}, status=400)
    if attempt.end_time and timezone.now() > attempt.end_time:
        return JsonResponse({"ok": False, "error": "attempt time expired"}, status=400)

    question = get_object_or_404(Question, id=qid, quiz=attempt.quiz)

    # create or update Answer
    ans_obj, _ = Answer.objects.get_or_create(attempt=attempt, question=question)

    if question.question_type == "objective":
        # answer is choice id
        try:
            choice = Choice.objects.get(id=int(answer), question=question)
        except Exception:
            choice = None
        ans_obj.selected_choice = choice
        ans_obj.text_answer = None
        # auto-grade objective
        if choice and getattr(choice, "is_correct", False):
            ans_obj.obtained_marks = float(question.marks)
        else:
            ans_obj.obtained_marks = 0.0
        ans_obj.is_pending = False
    else:
        # subjective
        ans_obj.text_answer = str(answer or "")
        ans_obj.selected_choice = None
        ans_obj.obtained_marks = None  # teacher will grade later
        ans_obj.is_pending = True

    ans_obj.save()
    return JsonResponse({"ok": True})


@require_http_methods(["POST"])
def api_submit_attempt(request):
    """Mark an attempt as submitted, compute score for objective parts and persist. Payload: {attempt_id}"""
    if not _is_student(request.user):
        return JsonResponse({"ok": False, "error": "forbidden"}, status=403)

    try:
        payload = json.loads(request.body.decode())
    except Exception:
        return JsonResponse({"ok": False, "error": "invalid json"}, status=400)

    attempt_id = payload.get("attempt_id")
    if not attempt_id:
        return JsonResponse({"ok": False, "error": "attempt_id required"}, status=400)

    attempt = get_object_or_404(StudentQuizAttempt, id=attempt_id, student=request.user)
    if attempt.completed:
        return JsonResponse({"ok": False, "error": "attempt already submitted"}, status=400)

    # compute score from answers: sum of obtained_marks where not None
    answers = Answer.objects.filter(attempt=attempt)
    total = 0.0
    for a in answers:
        # For objectives, obtained_marks is set earlier
        if a.obtained_marks is None:
            # subjective unanswered by teacher -> 0 for now
            continue
        try:
            total += float(a.obtained_marks)
        except Exception:
            pass

    attempt.score = total
    attempt.completed = True
    # set completed_at if field exists
    if hasattr(attempt, "completed_at"):
        attempt.completed_at = timezone.now()
    attempt.save()

    # log
    ActionLog.objects.create(user=request.user, action="Submitted attempt", model_name="StudentQuizAttempt", object_id=str(attempt.id),
                             details={"score": attempt.score})

    return JsonResponse({"ok": True, "score": float(attempt.score)})

# -------------------------- No 2 Endpoint Ended -------------------------- #



# ---- USER MANAGEMENT ----
@login_required
@user_passes_test(is_admin)
def manage_users(request):
    users = User.objects.exclude(role="superadmin").order_by("-date_joined")
    return render(request, "exams/manage_users.html", {"users": users})


@login_required
@user_passes_test(is_admin)
def create_user(request):
    if request.method == "POST":
        username = request.POST["username"]
        email = request.POST["email"]
        role = request.POST["role"]
        password = request.POST["password"]

        user = User.objects.create_user(username=username, email=email, password=password, role=role, approved=True)
        ActionLog.objects.create(user=request.user, action=f"Created user {user.username} ({role})")
        messages.success(request, f"User {username} created successfully.")
        return redirect("manage_users")

    return render(request, "exams/create_user.html")


# ---- QUIZ MANAGEMENT ----
@login_required
@user_passes_test(is_admin)
def manage_quizzes(request):
    quizzes = Quiz.objects.all().order_by("-created_at")

    page = Paginator(quizzes, 7)
    page_number = request.GET.get("page")
    page_obj = page.get_page(page_number)

    return render(request, "exams/manage_quizzes.html", {"page_obj": page_obj})


@login_required
@user_passes_test(is_admin)
def create_quiz(request):
    if request.method == "POST":
        title = request.POST["title"]
        subject_id = request.POST["subject"]
        duration = int(request.POST["duration"])

        subject = Subject.objects.get(id=subject_id)
        quiz = Quiz.objects.create(title=title, subject=subject, duration=duration, created_by=request.user)
        ActionLog.objects.create(user=request.user, action=f"Created quiz {quiz.title}")
        messages.success(request, f"Quiz {title} created successfully.")
        return redirect("manage_quizzes")

    subjects = Subject.objects.all()
    return render(request, "exams/create_quiz.html", {"subjects": subjects})


@login_required
@user_passes_test(is_admin)
def upload_quiz_excel(request):
    if request.method == "POST" and request.FILES["file"]:
        file = request.FILES["file"]
        fs = FileSystemStorage()
        filename = fs.save(file.name, file)
        filepath = fs.path(filename)

        wb = openpyxl.load_workbook(filepath)
        sheet = wb.active

        for row in sheet.iter_rows(min_row=2, values_only=True):  # skip header
            title, subject_name, duration = row[:3]
            subject, _ = Subject.objects.get_or_create(name=subject_name)
            Quiz.objects.create(title=title, subject=subject, duration=int(duration), created_by=request.user)

        ActionLog.objects.create(user=request.user, action=f"Uploaded quizzes from Excel")
        messages.success(request, "Quizzes uploaded successfully.")
        return redirect("manage_quizzes")

    return render(request, "exams/upload_quiz_excel.html")


@login_required
@user_passes_test(is_admin)
def sample_quiz_excel(request):
    response = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response["Content-Disposition"] = 'attachment; filename="sample_quiz.xlsx"'

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Title", "Subject", "Duration(minutes)"])
    ws.append(["Sample Quiz 1", "Mathematics", 30])
    ws.append(["Sample Quiz 2", "English", 40])
    wb.save(response)
    return response


from django.db.models import Q  

def get_quizzes_with_status(student):
    # Fetch all quizzes for student's class
    quizzes = Quiz.objects.filter(
        subject__school_class=student.student_class,
        created_by__role__in=["teacher", "admin", "superadmin"]
    ).select_related("subject", "created_by")

    # Map quiz attempts
    attempts = StudentQuizAttempt.objects.filter(student=student).select_related("quiz")
    attempts_map = {a.quiz_id: a for a in attempts}

    quizzes_with_status = []
    for quiz in quizzes:
        attempt = attempts_map.get(quiz.id)

        if attempt and attempt.completed:
            if quiz.allow_retake:
                status = "Available for Retake"
            else:
                status = "Completed"
        else:
            status = "Not Started"

        quizzes_with_status.append({
            "quiz": quiz,
            "status": status
        })

    return quizzes_with_status



# -----------------------------Retake Approval & Request---------------------------------#
@login_required
@user_passes_test(is_admin)
def approve_retake(request, quiz_id, student_id):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request"}, status=400)

    quiz = get_object_or_404(Quiz, id=quiz_id)
    student = get_object_or_404(User, id=student_id, role="student")

    # find last attempt or create a fresh one
    attempt, created = StudentQuizAttempt.objects.get_or_create(
        student=student, quiz=quiz,
        defaults={"retake_allowed": True, "completed": False}
    )

    # mark retake
    attempt.retake_allowed = True
    attempt.completed = False  # reset if admin wants them to take again
    attempt.end_time = None
    attempt.retake_count += 1
    attempt.save()

    # log the action
    ActionLog.objects.create(
        user=request.user,
        action="Approved Retake",
        model_name="StudentQuizAttempt",
        object_id=str(attempt.id),
        details={"student": student.username, "quiz": quiz.title, "retake_count": attempt.retake_count},
    )

    return JsonResponse({
        "success": True,
        "message": f"{student.username} can now retake {quiz.title}.",
        "retake_count": attempt.retake_count
    })



@login_required
@user_passes_test(is_admin)
def retake_requests_list(request):
    # Fetch only attempts where retake is pending
    attempts = StudentQuizAttempt.objects.filter(retake_allowed=False, completed=True).select_related("student", "quiz").order_by("-started_at")

    # Pagination
    paginator = Paginator(attempts, 10)  # 10 per page
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(request, "exams/approve_retake.html", {"page_obj": page_obj})



@login_required
@user_passes_test(is_student)
def request_retake(request, quiz_id):
    quiz = get_object_or_404(Quiz, id=quiz_id)

    # prevent duplicate pending requests
    existing = RetakeRequest.objects.filter(student=request.user, quiz=quiz, status="pending").first()
    if existing:
        return JsonResponse({"error": "You already have a pending retake request for this quiz."}, status=400)

    reason = request.POST.get("reason", "No reason given")

    req = RetakeRequest.objects.create(student=request.user, quiz=quiz, reason=reason)

    # log + notify
    ActionLog.objects.create(
        user=request.user,
        action="Requested Retake",
        model_name="RetakeRequest",
        object_id=str(req.id),
        details={"quiz": quiz.title, "reason": reason}
    )
    Notification.objects.create(
        user=quiz.created_by,  # teacher who owns quiz
        message=f"{request.user.username} requested a retake for {quiz.title}."
    )

    return JsonResponse({"success": True, "message": "Retake request submitted."})



@login_required
@user_passes_test(is_teacher_or_admin)
def handle_retake_request(request, request_id):
    retake_req = get_object_or_404(RetakeRequest, id=request_id, status="pending")
    decision = request.POST.get("decision")  # "approve" or "deny"

    if decision == "approve":
        # reset attempt or allow new
        attempt, created = StudentQuizAttempt.objects.get_or_create(
            student=retake_req.student,
            quiz=retake_req.quiz,
            defaults={"retake_allowed": True, "completed": False, "retake_count": 1}
        )
        if not created:
            attempt.retake_allowed = True
            attempt.completed = False
            attempt.end_time = None
            attempt.retake_count += 1
            attempt.save()

        retake_req.status = "approved"
        message = f"Your retake request for {retake_req.quiz.title} was approved."

    else:
        retake_req.status = "denied"
        message = f"Your retake request for {retake_req.quiz.title} was denied."

    retake_req.reviewed_by = request.user
    retake_req.reviewed_at = timezone.now()
    retake_req.save()

    # log
    ActionLog.objects.create(
        user=request.user,
        action=f"Retake {retake_req.status.capitalize()}",
        model_name="RetakeRequest",
        object_id=str(retake_req.id),
        details={"student": retake_req.student.username, "quiz": retake_req.quiz.title}
    )

    # notify student
    Notification.objects.create(user=retake_req.student, message=message)

    return JsonResponse({"success": True, "message": message})

# -----------------------------Retake Approval & Request ended ---------------------------------#

# ----------------------------------------------------------------------------------------------#

@login_required
@user_passes_test(is_teacher_or_admin)
def teacher_dashboard(request):
    teacher = request.user

    # Quizzes created by this teacher
    quizzes = Quiz.objects.filter(created_by=teacher).order_by("-start_time")

    # Student attempts on teacher’s quizzes
    attempts = (
        StudentQuizAttempt.objects.filter(quiz__in=quizzes)
        .select_related("student", "quiz")
        .order_by("-end_time")
    )

    # Retake requests for teacher’s quizzes
    retake_requests = (
        RetakeRequest.objects.filter(quiz__in=quizzes)
        .select_related("student", "quiz", "reviewed_by")
        .order_by("-created_at")
    )

    return render(request, "exams/teacher_dashboard.html", {
        "quizzes": quizzes,
        "attempts": attempts,
        "retake_requests": retake_requests,
    })


# -------------------------Teacher Dashboard -------------------------------------#
# AJAX endpoints (JSON) for periodic refresh (every 10 seconds)
@login_required
def ajax_student_summary(request):
    user = request.user
    attempts = StudentQuizAttempt.objects.filter(student=user)
    total_attempts = attempts.count()
    avg_score = attempts.aggregate(avg=Avg('total_score'))['avg'] or 0
    pending_count = Answer.objects.filter(attempt__student=user, is_pending=True).count()
    data = {
        "total_attempts": total_attempts,
        "avg_score": float(avg_score),
        "pending_count": pending_count,
    }
    return JsonResponse(data)


@login_required
@user_passes_test(is_teacher)
def ajax_teacher_pending_subjectives(request):
    user = request.user
    pending_count = Answer.objects.filter(question__quiz__created_by=user, is_pending=True).count()
    return JsonResponse({"pending_count": pending_count})


# --------------------------------------------------------------#
# PDF export (consolidated results for a student)

def download_student_full_report(request, student_id):
    """Download full report for a single student (all quizzes)."""
    # Fetch attempts for this student
    attempts = StudentQuizAttempt.objects.filter(student_id=student_id).select_related("quiz", "quiz__subject")

    # Prepare PDF response
    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="student_{student_id}_results.pdf"'

    doc = SimpleDocTemplate(response, pagesize=A4)
    styles = getSampleStyleSheet()
    elements = []

    # Header: logo | school name + student | student photo
    school_logo = os.path.join(settings.MEDIA_ROOT, "school_logo.png")
    student = attempts.first().student if attempts.exists() else None
    school_name = getattr(settings, "SCHOOL_NAME", "My School Name")
    student_photo = getattr(student, "profile_picture", None)  # assuming User has photo field

    header_data = [
        [
            Image(school_logo, width=50, height=50) if os.path.exists(school_logo) else "",
            Paragraph(f"<b>{school_name}</b><br/> " + (student.get_full_name() if student else "Unknown"), styles["Title"]),
            Image(student_photo.path, width=50, height=50) if student_photo and os.path.exists(student_photo.path) else "",
        ]
    ]
    header_table = Table(header_data, colWidths=[70, 350, 70])
    header_table.setStyle(TableStyle([("ALIGN", (1, 0), (1, 0), "CENTER")]))
    elements.append(header_table)
    elements.append(Spacer(1, 20))

    # Loop through attempts
    for attempt in attempts:
        elements.append(Paragraph(f"<b>Exam:</b> {attempt.quiz.title}", styles["Heading3"]))
        elements.append(Paragraph(f"Subject: {attempt.quiz.subject.name}", styles["Normal"]))
        elements.append(Paragraph(f"Date: {attempt.started_at.strftime('%d-%m-%Y %H:%M')}", styles["Normal"]))

        # Collect answers
        answers = Answer.objects.filter(attempt=attempt).select_related("question", "selected_choice")

        data = [["Question", "Answer", "Marks", "Feedback"]]
        for ans in answers:
            if ans.selected_choice:
                ans_text = ans.selected_choice.text
            else:
                ans_text = ans.text_answer or "-"
            data.append([ans.question.text, ans_text, ans.obtained_marks, ans.feedback or ""])

        table = Table(data, colWidths=[200, 150, 60, 100])
        table.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightblue),
        ]))
        elements.append(table)
        elements.append(Spacer(1, 15))

    doc.build(elements)
    return response


def download_closed_quiz_report(request, quiz_id):
    """Download report for all students who attempted a closed quiz."""
    quiz = Quiz.objects.get(id=quiz_id)
    attempts = StudentQuizAttempt.objects.filter(quiz=quiz).select_related("student")

    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="quiz_{quiz_id}_report.pdf"'

    doc = SimpleDocTemplate(response, pagesize=A4)
    styles = getSampleStyleSheet()
    elements = []

    # Header
    school_logo = os.path.join(settings.MEDIA_ROOT, "school_logo.png")
    school_name = getattr(settings, "SCHOOL_NAME", "My school name")
    header_data = [
        [
            Image(school_logo, width=50, height=50) if os.path.exists(school_logo) else "",
            Paragraph(f"<b>{school_name}</b><br/>Exam Report: {quiz.title}", styles["Title"]),
            "",
        ]
    ]
    header_table = Table(header_data, colWidths=[70, 350, 70])
    header_table.setStyle(TableStyle([("ALIGN", (1, 0), (1, 0), "CENTER")]))
    elements.append(header_table)
    elements.append(Spacer(1, 20))

    # Loop through each student's attempt
    for attempt in attempts:
        student = attempt.student
        elements.append(Paragraph(f"<b>Student:</b> {student.get_full_name()} ({getattr(student, 'student_class', 'N/A')})", styles["Heading3"]))
        elements.append(Paragraph(f"Date: {attempt.started_at.strftime('%d-%m-%Y %H:%M')}", styles["Normal"]))

        answers = Answer.objects.filter(attempt=attempt).select_related("question", "selected_choice")

        data = [["Question", "Answer", "Marks", "Feedback"]]
        for ans in answers:
            if ans.selected_choice:
                ans_text = ans.selected_choice.text
            else:
                ans_text = ans.text_answer or "-"
            data.append([ans.question.text, ans_text, ans.obtained_marks, ans.feedback or ""])

        table = Table(data, colWidths=[200, 150, 60, 100])
        table.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightblue),
        ]))
        elements.append(table)
        elements.append(Spacer(1, 15))

    doc.build(elements)
    return response


# def consolidated_results_pdf(request):
#     # response
#     response = HttpResponse(content_type='application/pdf')
#     response['Content-Disposition'] = 'attachment; filename="consolidated_results.pdf"'

#     # setup doc
#     doc = SimpleDocTemplate(response, pagesize=A4)
#     styles = getSampleStyleSheet()
#     elements = []

#     # === HEADER SECTION ===
#     # static school logo
#     school_logo_path = os.path.join(settings.BASE_DIR, "static/images/school_logo.png")
#     # user profile picture (from your User model)
#     profile_picture = None
#     if request.user.profile_picture:
#         try:
#             profile_picture = request.user.profile_picture
#         except Exception:
#             profile_picture = None

#     # header row (logo | school name | profile picture)
#     header_data = []

#     logo_img = Image(school_logo_path, width=1*inch, height=1*inch) if os.path.exists(school_logo_path) else ""
#     profile_img = Image(profile_picture, width=1*inch, height=1*inch) if profile_picture and os.path.exists(profile_picture) else ""

#     school_name = getattr(settings, "SCHOOL_NAME", "My School")

#     header_data.append([
#         logo_img,
#         Paragraph(f"<b>{school_name}</b>", styles["Title"]),
#         profile_img
#     ])

#     header_table = Table(header_data, colWidths=[1.5*inch, 3.5*inch, 1.5*inch])
#     header_table.setStyle(TableStyle([
#         ("ALIGN", (0, 0), (0, 0), "LEFT"),
#         ("ALIGN", (1, 0), (1, 0), "CENTER"),
#         ("ALIGN", (2, 0), (2, 0), "RIGHT"),
#         ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
#     ]))

#     elements.append(header_table)
#     elements.append(Spacer(1, 20))

#     # subtitle
#     elements.append(Paragraph("Consolidated Exam Results", styles["Heading2"]))
#     elements.append(Spacer(1, 12))

#     # === RESULTS TABLE ===
#     attempts = StudentQuizAttempt.objects.filter(student=request.user)

#     data = [["Quiz", "Score", "Total", "Completed At"]]
#     for attempt in attempts:
#         data.append([
#             attempt.quiz.title,
#             attempt.score,
#             attempt.total_marks,
#             attempt.completed_at.strftime("%d-%m-%Y %H:%M") if attempt.completed_at else "In Progress",
#         ])

#     # create table
#     table = Table(data, colWidths=[200, 70, 70, 120])
#     table.setStyle(TableStyle([
#         ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
#         ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
#         ("ALIGN", (0, 0), (-1, -1), "CENTER"),
#         ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
#         ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
#         ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
#         ("GRID", (0, 0), (-1, -1), 1, colors.black),
#     ]))

#     elements.append(table)

#     # build pdf
#     doc.build(elements)
#     return response



# @login_required
# def student_consolidated_results_pdf(request):
#     student = request.user
#     response = HttpResponse(content_type='application/pdf')
#     response['Content-Disposition'] = f'attachment; filename="{student.username}_results.pdf"'

#     p = canvas.Canvas(response, pagesize=A4)
#     width, height = A4

#     # Header: logo + profile
#     p.drawImage("static/images/school_logo.png", 40, height - 100, width=60, height=60, mask='auto')
#     if student.profile_picture:
#         try:
#             p.drawImage(student.profile_picture.path, width - 100, height - 100, width=60, height=60, mask='auto')
#         except Exception:
#             pass

#     p.setFont("Helvetica-Bold", 16)
#     p.drawCentredString(width/2, height - 50, "SCHOOL NAME")
#     p.setFont("Helvetica", 12)
#     p.drawCentredString(width/2, height - 70, f"Student: {student.get_full_name()}")

#     y = height - 150

#     attempts = StudentQuizAttempt.objects.filter(student=student).select_related("quiz")

#     for attempt in attempts:
#         quiz = attempt.quiz
   
#         # Score computation
#         total_obj = Answer.objects.filter(attempt=attempt).count()
#         correct_obj = Answer.objects.filter(attempt=attempt, selected_choice__is_correct=True).count()
#         obj_score = Answer.objective_score(Answer, attempt=attempt)
#         # graded_subj = Answer.objects.filter(attempt=attempt, marks_awarded__isnull=False)
#         # subj_score = sum(ans.marks_awarded for ans in graded_subj)
#         # subj_total = sum(ans.question.marks for ans in graded_subj)
#         # total_score = correct_obj + subj_score
#         # total_marks = total_obj + subj_total + pending_subj  # pending ones reserved, no awarded marks yet
#         subj_score = Answer.subjective_score(Answer, attempt=attempt)
#         total_score = Answer.total_score(Answer, attempt=attempt)
#         pending_subj = Answer.objects.filter(attempt=attempt, is_pending=True).count()

#         total_marks = total_score #  + pending_subj  # pending ones reserved, no awarded marks yet

#         # Print quiz title & result
#         p.setFont("Helvetica-Bold", 13)
#         p.drawString(50, y, f"Quiz: {quiz.title} ({quiz.subject.name})")
#         y -= 20
#         p.setFont("Helvetica", 11)
#         p.drawString(70, y, f"Score: {total_score}/{total_marks} | Pending: {pending_subj}")
#         y -= 20

#         # List wrongly answered objective questions (review)
#         wrong_obj = Answer.objects.filter(attempt=attempt, choice__is_correct=False)
#         if wrong_obj.exists():
#             p.setFont("Helvetica-Oblique", 11)
#             p.drawString(70, y, "Review of Wrong Answers:")
#             y -= 20
#             for obj in wrong_obj:
#                 q_text = obj.question.text[:60] + ("..." if len(obj.question.text) > 60 else "")
#                 p.drawString(90, y, f"- {q_text}")
#                 y -= 15
#                 if y < 100:
#                     p.showPage()
#                     y = height - 100

#         y -= 15
#         if y < 100:
#             p.showPage()
#             y = height - 100

#     p.showPage()
#     p.save()
#     return response





# --------------------------------------------------------------#



# @login_required
# @user_passes_test(is_teacher)
# def grade_answer(request, answer_id):
#     # simple grade form: GET shows form, POST submits grade and feedback
#     ans = get_object_or_404(Answer, id=answer_id, question__quiz__created_by=request.user)
#     if request.method == 'POST':
#         marks = float(request.POST.get('marks') or 0)
#         feedback = request.POST.get('feedback', '')
#         ans.obtained_marks = marks
#         ans.feedback = feedback
#         ans.graded_by = request.user
#         ans.graded_at = timezone.now()
#         ans.is_pending = False
#         ans.save()
#         # update attempt total if all subjectives graded
#         attempt = ans.attempt
#         if not attempt.answers.filter(is_pending=True).exists():
#             # sum marks objective + subjective into attempt.total_score
#             total = attempt.answers.aggregate(total=Sum('obtained_marks'))['total'] or 0
#             attempt.total_score = total
#             attempt.graded = True
#             attempt.save()
#         log_action(request.user, "Graded answer", "Answer", ans.id, {"marks": marks})
#         messages.success(request, "Answer graded.")
#         return redirect('teacher_dashboard')
#     return render(request, 'quizzes/grade_answer.html', {'ans': ans})



# def is_teacher_or_admin(user):
#     return user.is_authenticated and user.role in ('teacher', 'admin', 'superadmin')


# @login_required
# @user_passes_test(is_teacher_or_admin)
# def create_quiz_page(request):
#     """
#     Renders the page with the create quiz UI (dynamic JS will handle adding questions & choices).
#     """
#     subjects = Subject.objects.all()
#     return render(request, "quizzes/create_quiz.html", {"subjects": subjects})


# @login_required
# @user_passes_test(is_teacher_or_admin)
# @require_POST
# def create_quiz_ajax(request):
#     """
#     Expects JSON payload like:
#     {
#       "title": "Midterm 1",
#       "subject_id": 1,
#       "duration_minutes": 30,
#       "is_published": true,
#       "questions": [
#         {
#           "text": "What is 2+2?",
#           "question_type": "objective",
#           "marks": 2,
#           "choices": [
#             {"text": "3", "is_correct": false},
#             {"text": "4", "is_correct": true}
#           ]
#         },
#         {
#           "text": "Explain photosynthesis",
#           "question_type": "subjective",
#           "marks": 5
#         }
#       ]
#     }
#     """
#     try:
#         payload = json.loads(request.body.decode('utf-8'))
#     except Exception as e:
#         return HttpResponseBadRequest("Invalid JSON")

#     # Basic quiz data validation
#     quiz_data = {
#         "title": payload.get("title"),
#         "subject_id": payload.get("subject_id"),
#         "duration_minutes": payload.get("duration_minutes"),
#         "is_published": payload.get("is_published", False),
#     }
#     if not quiz_data["title"] or not quiz_data["subject_id"]:
#         return JsonResponse({"ok": False, "error": "Title and subject are required."}, status=400)

#     subject = get_object_or_404(Subject, id=quiz_data["subject_id"])

#     # Create the quiz
#     quiz = Quiz.objects.create(
#         title=quiz_data["title"],
#         subject=subject,
#         created_by=request.user,
#         duration_minutes=int(quiz_data.get("duration_minutes") or 30),
#         is_published=bool(quiz_data.get("is_published", False))
#     )

#     questions = payload.get("questions", [])
#     created_questions = []
#     for q_idx, q in enumerate(questions):
#         q_text = q.get("text")
#         q_type = q.get("question_type")
#         q_marks = q.get("marks", 1)
#         if not q_text or q_type not in ("objective", "subjective"):
#             # rollback: delete quiz and return error
#             quiz.delete()
#             return JsonResponse({"ok": False, "error": f"Invalid question data at index {q_idx}"}, status=400)

#         question = Question.objects.create(
#             quiz=quiz,
#             text=q_text,
#             question_type=q_type,
#             marks=float(q_marks)
#         )
#         created_questions.append(question)

#         # If objective, create choices
#         if q_type == "objective":
#             choices = q.get("choices", [])
#             if not choices or not isinstance(choices, list):
#                 quiz.delete()
#                 return JsonResponse({"ok": False, "error": f"Objective question must have choices at index {q_idx}"}, status=400)

#             # create choices
#             correct_exists = False
#             for c_idx, choice in enumerate(choices):
#                 c_text = choice.get("text")
#                 c_is_correct = bool(choice.get("is_correct", False))
#                 if not c_text:
#                     quiz.delete()
#                     return JsonResponse({"ok": False, "error": f"Choice text missing for question {q_idx} choice {c_idx}"}, status=400)
#                 Choice.objects.create(question=question, text=c_text, is_correct=c_is_correct)
#                 if c_is_correct:
#                     correct_exists = True

#             if not correct_exists:
#                 quiz.delete()
#                 return JsonResponse({"ok": False, "error": f"At least one correct choice required for objective question {q_idx}"}, status=400)


#     return JsonResponse({"ok": True, "quiz_id": quiz.id, "message": "Quiz created successfully."})


#     # Log action
#     log_action(request.user, "Created quiz", "Quiz", quiz.id, {"title": quiz.title, "questions": len(created_questions)})
# @require_POST
# @login_required
# def attempt_submit(request, attempt_id):
#     attempt = get_object_or_404(StudentQuizAttempt, id=attempt_id, student=request.user, is_submitted=False)
#     # mark submitted
#     attempt.is_submitted = True
#     attempt.completed_at = timezone.now()

#     # grade objective answers
#     total_score = 0
#     total_marks = 0
#     for obj in attempt.objective_answers.select_related('choice','question'):
#         q = obj.question
#         total_marks += q.marks
#         if obj.choice and obj.choice.is_correct:
#             total_score += q.marks

#     # subjectives remain pending - teacher will grade later.
#     # compute partial score now and store totals
#     attempt.score = total_score
#     attempt.total_marks = total_marks + sum(q.marks for q in attempt.subjective_answers.values_list('question__marks', flat=True))
#     attempt.save()

#     # Optionally notify teacher(s) that new subjectives need grading (create Notification)
#     # log action
#     log_action(request.user, "Submitted attempt", "StudentQuizAttempt", attempt.id, {"score_so_far": total_score})

#     return JsonResponse({"ok": True, "score": total_score})

# ---------------------------------------------------------------------#

# -------------------------
# Helper: auto-grade objective for an attempt
# -------------------------
def _auto_grade_objectives(attempt):
    """
    Ensure Answer objects for objective questions have obtained_marks set based on selected_choice,
    and return objective total.
    """
    obj_answers = Answer.objects.filter(attempt=attempt, question__question_type="objective")
    total = 0.0
    for ans in obj_answers.select_related("selected_choice", "question"):
        q_marks = ans.question.marks or 0
        if ans.selected_choice and ans.selected_choice.is_correct:
            ans.obtained_marks = q_marks
        else:
            ans.obtained_marks = 0.0
        ans.is_pending = False
        ans.graded_at = timezone.now()
        ans.save(update_fields=["obtained_marks", "is_pending", "graded_at"])
        total += ans.obtained_marks
    return total

# -------------------------
# Render page: take quiz
# -------------------------
@login_required
def take_quiz_page(request, quiz_id):
    quiz = get_object_or_404(Quiz, id=quiz_id, is_published=True)
    # Only quizzes for student's class and within start/end should be accessible in practice.
    # But view will still let JS call start endpoint which enforces timing/permissions.
    # Prepare questions JSON for client rendering:
    questions = []
    for q in quiz.questions.prefetch_related("choices").all():
        qd = {"id": q.id, "text": q.text, "question_type": q.question_type, "marks": q.marks}
        if q.question_type == "objective":
            qd["choices"] = [{"id": c.id, "text": c.text} for c in q.choices.all()]
        questions.append(qd)

    context = {
        "quiz": quiz,
        "questions_json": json.dumps(questions),
    }
    return render(request, "exams/take_quiz.html", context)


# -------------------------
# API: start / resume attempt
# -------------------------
@login_required
def api_start_attempt(request, quiz_id):
    """
    POST / GET (we allow GET from fetch): create or resume an attempt.
    Response:
      {"ok": True, "attempt_id": id, "end_time": iso, "resume": bool}
    If resume not allowed and time elapsed -> server auto-submits previous attempt and returns error.
    """
    quiz = get_object_or_404(Quiz, id=quiz_id, is_published=True)
    now = timezone.now()
    # enforce quiz window (start_time/end_time)
    if not (quiz.start_time <= now <= quiz.end_time):
        return JsonResponse({"ok": False, "error": "Quiz not active."}, status=400)

    # find existing uncompleted attempt
    existing = StudentQuizAttempt.objects.filter(student=request.user, quiz=quiz, completed=False).order_by("-started_at").first()
    if existing:
        # existing end_time should exist; if not compute
        if not existing.end_time:
            existing.end_time = existing.started_at + timedelta(minutes=quiz.duration_minutes)
            existing.save(update_fields=["end_time"])
        if timezone.now() <= existing.end_time:
            return JsonResponse({"ok": True, "attempt_id": existing.id, "end_time": existing.end_time.isoformat(), "resume": True})
        else:
            # time elapsed -> auto-submit this attempt
            with transaction.atomic():
                _auto_grade_objectives(existing)
                existing.completed = True
                existing.save(update_fields=["completed"])
            return JsonResponse({"ok": False, "error": "Previous attempt timed out and was auto-submitted."}, status=400)

    # no existing -> create new attempt
    with transaction.atomic():
        started = timezone.now()
        end_time = started + timedelta(minutes=quiz.duration_minutes)
        attempt = StudentQuizAttempt.objects.create(
            student=request.user,
            quiz=quiz,
            started_at=started,
            end_time=end_time,
            completed=False,
        )
        # initialize Answer rows for all questions (optional but helpful)
        answers_bulk = []
        for q in quiz.questions.all():
            a = Answer(attempt=attempt, question=q)
            # objective default selected_choice null; subjective text null; is_pending False by default
            if q.question_type == "subjective":
                a.is_pending = True  # pending until graded
            answers_bulk.append(a)
        Answer.objects.bulk_create(answers_bulk)

    return JsonResponse({"ok": True, "attempt_id": attempt.id, "end_time": end_time.isoformat(), "resume": False})


# -------------------------
# API: autosave attempt answers
# -------------------------


@login_required
def api_autosave_attempt(request, attempt_id):
    """
    Expects JSON body: {"answers": [ {"question_id": x, "choice_id": y} | {"question_id": x, "text": "..." } , ... ] }
    Saves into Answer objects. For objective: set selected_choice and auto-grade obtained_marks.
    For subjective: set text_answer and mark is_pending True.
    """
    attempt = get_object_or_404(StudentQuizAttempt, id=attempt_id, student=request.user)
    if attempt.completed:
        return JsonResponse({"ok": False, "error": "Attempt already submitted."}, status=400)
    now = timezone.now()
    if attempt.end_time and now > attempt.end_time:
        # time elapsed -> auto-submit
        with transaction.atomic():
            _auto_grade_objectives(attempt)
            attempt.completed = True
            attempt.save(update_fields=["completed"])
        return JsonResponse({"ok": False, "error": "Attempt time elapsed; auto-submitted."}, status=400)

    try:
        payload = json.loads(request.body.decode())
    except Exception:
        return JsonResponse({"ok": False, "error": "Invalid JSON"}, status=400)

    answers = payload.get("answers", [])
    # process each answer
    for a in answers:
        qid = a.get("question_id")
        if not qid:
            continue
        q = get_object_or_404(Question, id=qid, quiz=attempt.quiz)
        # get or create Answer row
        ans_obj, _ = Answer.objects.get_or_create(attempt=attempt, question=q)
        if q.question_type == "objective":
            choice_id = a.get("choice_id")
            if choice_id:
                # set selected choice and auto-grade
                choice = get_object_or_404(Choice, id=choice_id, question=q)
                ans_obj.selected_choice = choice
                # grade immediately
                if choice.is_correct:
                    ans_obj.obtained_marks = q.marks or 0.0
                else:
                    ans_obj.obtained_marks = 0.0
                ans_obj.is_pending = False
                ans_obj.graded_at = timezone.now()
                ans_obj.save(update_fields=["selected_choice", "obtained_marks", "is_pending", "graded_at"])
            else:
                # no selection -> clear
                ans_obj.selected_choice = None
                ans_obj.obtained_marks = 0.0
                ans_obj.is_pending = False
                ans_obj.save(update_fields=["selected_choice", "obtained_marks", "is_pending"])
        else:  # subjective
            text = a.get("text", "")
            ans_obj.text_answer = text
            ans_obj.is_pending = True
            ans_obj.save(update_fields=["text_answer", "is_pending"])

    return JsonResponse({"ok": True})


# -------------------------
# API: submit attempt
# -------------------------
@login_required
def api_submit_attempt(request, attempt_id):
    attempt = get_object_or_404(StudentQuizAttempt, id=attempt_id, student=request.user)
    if attempt.completed:
        return JsonResponse({"ok": False, "message": "Already submitted."}, status=400)

    now = timezone.now()
    # If time elapsed, auto-grade and finalize
    if attempt.end_time and now > attempt.end_time:
        with transaction.atomic():
            obj_total = _auto_grade_objectives(attempt)
            attempt.score = obj_total + Answer.subjective_score(attempt)  # subjective_score returns graded only
            attempt.completed = True
            attempt.save(update_fields=["score", "completed"])
        return JsonResponse({"ok": True, "message": "Time elapsed — auto-submitted.", "score": attempt.score})

    # Regular submit: auto-grade objectives, leave subjectives pending
    with transaction.atomic():
        obj_total = _auto_grade_objectives(attempt)
        # subjective_score: only graded subjective answers count now (likely 0)
        subj_total = Answer.subjective_score(attempt)
        attempt.score = obj_total + subj_total
        attempt.completed = True
        attempt.save(update_fields=["score", "completed"])
        # log action
        ActionLog.objects.create(user=request.user, action="Submitted attempt", model_name="StudentQuizAttempt", object_id=str(attempt.id), details={"quiz": attempt.quiz.id})

    # notify teacher that subjectives need grading (optional)
    # (you can create Notification here if you have a model)
    return JsonResponse({"ok": True, "message": "Submitted", "score": attempt.score})


# -------------------------
# API: attempt review (student views after submission or partially after autosave objectives)
# -------------------------
@login_required
def api_attempt_review(request, attempt_id):
    attempt = get_object_or_404(StudentQuizAttempt, id=attempt_id, student=request.user)
    # prepare review: objectives (correct/wrong + selected), subjectives (text + marks if graded)
    answers = []
    for a in attempt.answers.select_related("question", "selected_choice").all():
        q = a.question
        item = {
            "question_id": q.id,
            "question_text": q.text,
            "question_type": q.question_type,
            "marks": q.marks,
        }
        if q.question_type == "objective":
            item["selected_choice_id"] = a.selected_choice.id if a.selected_choice else None
            item["selected_choice_text"] = a.selected_choice.text if a.selected_choice else None
            item["is_correct"] = a.selected_choice.is_correct if a.selected_choice else False
            item["obtained_marks"] = a.obtained_marks
        else:
            item["answer_text"] = a.text_answer
            item["is_pending"] = a.is_pending
            item["obtained_marks"] = a.obtained_marks if not a.is_pending else None
            item["feedback"] = a.feedback
            item["graded_by"] = a.graded_by.username if a.graded_by else None
        answers.append(item)

    totals = {
        "objective_total": Answer.objective_score(attempt),
        "subjective_total_graded": Answer.subjective_score(attempt),
        "grand_total": Answer.total_score(attempt),
    }

    return JsonResponse({"ok": True, "answers": answers, "totals": totals})


# -------------------------
# Leaderboard (global top students by average score)
# -------------------------
@login_required
def leaderboard(request):
    """
    Renders a leaderboard template showing top students by average score across their completed attempts.
    """
    # compute average attempt scores per student; use StudentQuizAttempt.score (we ensure it's set on submit)
    qs = StudentQuizAttempt.objects.filter(completed=True).values("student").annotate(
        avg_score=Avg("score"), attempts=Sum("score")
    ).order_by("-avg_score")[:50]

    # map to user objects + scores
    leaderboard_list = []
    for item in qs:
        user_id = item["student"]
        try:
            user = User.objects.get(id=user_id)
            leaderboard_list.append({"student": user, "avg_score": item["avg_score"] or 0})
        except User.DoesNotExist:
            continue

    return render(request, "exams/leaderboard.html", {"leaderboard": leaderboard_list})



# ---- Page: create quiz (manual + excel upload) ----

def is_teacher_or_admin(user):
    return user.is_authenticated and user.role in ('teacher','admin','superadmin')


@login_required
@user_passes_test(is_teacher_or_admin)
def create_quiz_page(request):
    subjects = Subject.objects.select_related('school_class').all()
    return render(request, "exams/create_quiz.html", {"subjects": subjects})

# ---- AJAX JSON create ----
@login_required
@user_passes_test(is_teacher_or_admin)
@require_POST
def create_quiz_ajax(request):
    try:
        payload = json.loads(request.body.decode())
    except Exception:
        return JsonResponse({"ok": False, "error": "Invalid JSON"}, status=400)

    title = payload.get("title")
    subject_id = payload.get("subject_id")
    start_time = payload.get("start_time")
    end_time = payload.get("end_time")
    duration_minutes = payload.get("duration_minutes") or 30
    is_published = bool(payload.get("is_published", False))
    questions = payload.get("questions", [])

    if not title or not subject_id:
        return JsonResponse({"ok": False, "error": "Title and subject are required."}, status=400)
    try:
        subject = Subject.objects.get(id=subject_id)
    except Subject.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Subject not found."}, status=404)

    # parse datetimes (accept ISO or 'YYYY-MM-DDTHH:MM' from datetime-local)
    def parse_dt(s):
        if not s:
            return None
        try:
            if "T" in s:
                s = s.replace("T", " ")
            return timezone.make_aware(datetime.strptime(s, "%Y-%m-%d %H:%M"))
        except Exception:
            try:
                return timezone.make_aware(datetime.fromisoformat(s))
            except Exception:
                return None

    st = parse_dt(start_time)
    et = parse_dt(end_time)
    if not st or not et:
        return JsonResponse({"ok": False, "error": "Invalid start_time or end_time format. Use YYYY-MM-DD HH:MM"}, status=400)

    # Build quiz within transaction
    try:
        with transaction.atomic():
            quiz = Quiz.objects.create(
                title=title,
                subject=subject,
                created_by=request.user,
                start_time=st,
                end_time=et,
                duration_minutes=int(duration_minutes),
                is_published=is_published
            )
            for qidx, q in enumerate(questions):
                qtext = q.get("text")
                qtype = q.get("question_type")
                qmarks = q.get("marks", 1)
                if not qtext or qtype not in ("objective","subjective"):
                    raise ValueError(f"Invalid question at index {qidx}")

                question = Question.objects.create(
                    quiz=quiz,
                    text=qtext,
                    question_type=qtype,
                    marks=int(qmarks)
                )

                if qtype == "objective":
                    choices = q.get("choices", [])
                    if not choices or not isinstance(choices, list):
                        raise ValueError(f"Objective question requires choices at index {qidx}")
                    correct_present = False
                    for cidx, c in enumerate(choices):
                        ctext = c.get("text")
                        cis = bool(c.get("is_correct", False))
                        if not ctext:
                            raise ValueError(f"Choice text missing for question {qidx} choice {cidx}")
                        Choice.objects.create(question=question, text=ctext, is_correct=cis)
                        if cis:
                            correct_present = True
                    if not correct_present:
                        raise ValueError(f"At least one correct choice required for question {qidx}")
            # success
            return JsonResponse({"ok": True, "quiz_id": quiz.id, "message": "Quiz created."})
    except ValueError as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=400)
    except Exception as e:
        return JsonResponse({"ok": False, "error": "Server error: " + str(e)}, status=500)

# ---- Excel import ----
@login_required
@user_passes_test(is_teacher_or_admin)
@require_POST
def import_quiz_excel(request):
    """
    Expect FormData with 'excel_file' and optionally 'subject_id' (or subject/class declared in file).
    Excel format (first sheet):
      - Row 1..6: metadata key/value in column A/B:
         A1: quiz_title  B1: My Quiz Title
         A2: class_name  B2: JSS1
         A3: subject_name B3: Mathematics
         A4: start_time  B4: 2025-09-13 14:00
         A5: end_time    B5: 2025-09-13 15:00
         A6: duration_minutes B6: 60
         A7: is_published B7: True
      - Row 9 header then rows from 10:
         Columns: question_text | question_type | marks | choice_1 | choice_1_correct (0/1) | choice_2 | choice_2_correct | ...
    """
    f = request.FILES.get('excel_file')
    if not f:
        return JsonResponse({"ok": False, "error": "No file uploaded"}, status=400)

    # save to temp location (openpyxl can read file-like objects but safer to store)
    try:
        wb = load_workbook(filename=f, data_only=True)
    except Exception as e:
        return JsonResponse({"ok": False, "error": "Invalid Excel file: " + str(e)}, status=400)

    sheet = wb.active

    def cell_value(r,c):
        return sheet.cell(row=r, column=c).value

    # read metadata
    try:
        meta = {}
        for r in range(1, 9):
            key = cell_value(r,1)
            val = cell_value(r,2)
            if key:
                meta[str(key).strip().lower()] = val
    except Exception:
        return JsonResponse({"ok": False, "error": "Failed to read metadata"}, status=400)

    title = meta.get("quiz_title") or meta.get("title")
    class_name = meta.get("class_name")
    subject_name = meta.get("subject_name")
    start_time_s = meta.get("start_time")
    end_time_s = meta.get("end_time")
    duration = int(meta.get("duration_minutes") or meta.get("duration") or 30)
    published = bool(meta.get("is_published")) if meta.get("is_published") is not None else False

    # validate subject/class
    if not (class_name and subject_name and title):
        return JsonResponse({"ok": False, "error": "Metadata must include class_name, subject_name and quiz_title"}, status=400)

    try:
        school_class = Class.objects.get(name__iexact=str(class_name).strip())
    except Class.DoesNotExist:
        return JsonResponse({"ok": False, "error": f"Class '{class_name}' not found"}, status=404)
    try:
        subject = Subject.objects.get(name__iexact=str(subject_name).strip(), school_class=school_class)
    except Subject.DoesNotExist:
        return JsonResponse({"ok": False, "error": f"Subject '{subject_name}' not found for class {class_name}"}, status=404)

    # parse datetimes (support datetime objects too)
    def parse_dt_obj(v):
        if v is None:
            return None
        if isinstance(v, datetime):
            return timezone.make_aware(v) if timezone.is_naive(v) else v
        try:
            s = str(v)
            if "T" in s: s = s.replace("T"," ")
            return timezone.make_aware(datetime.strptime(s, "%Y-%m-%d %H:%M"))
        except Exception:
            try:
                return timezone.make_aware(datetime.fromisoformat(str(v)))
            except Exception:
                return None

    st = parse_dt_obj(start_time_s)
    et = parse_dt_obj(end_time_s)
    if not st or not et:
        return JsonResponse({"ok": False, "error": "Invalid start_time or end_time in metadata. Use 'YYYY-MM-DD HH:MM' or Excel datetime."}, status=400)

    # find header row (we expect header at row 9 or row with 'question_text')
    header_row = None
    for r in range(1, 30):
        first_col = cell_value(r,1)
        if first_col and str(first_col).strip().lower() in ("question_text","question","q_text"):
            header_row = r
            break
    if header_row is None:
        # assume header at row 9
        header_row = 9

    # parse questions starting from header_row+1 to last row with question_text
    questions = []
    r = header_row + 1
    while True:
        q_text = cell_value(r, 1)
        if q_text is None:
            break
        q_type = cell_value(r, 2) or 'objective'
        q_marks = int(cell_value(r, 3) or 1)

        # choices start at col 4, every pair: text, correct
        choices = []
        col = 4
        while True:
            c_text = cell_value(r, col)
            c_flag = cell_value(r, col+1)
            if c_text is None:
                break
            is_corr = False
            if c_flag in (1, '1', True, 'TRUE', 'true'):
                is_corr = True
            choices.append({"text": str(c_text).strip(), "is_correct": bool(is_corr)})
            col += 2

        questions.append({
            "text": str(q_text).strip(),
            "question_type": str(q_type).strip().lower(),
            "marks": q_marks,
            "choices": choices
        })
        r += 1

    # Now create quiz
    try:
        with transaction.atomic():
            quiz = Quiz.objects.create(
                title=title,
                subject=subject,
                created_by=request.user,
                start_time=st,
                end_time=et,
                duration_minutes=duration,
                is_published=published
            )
            # create questions
            for q in questions:
                qtext = q["text"]
                qtype = q["question_type"]
                qmarks = q["marks"]
                question = Question.objects.create(quiz=quiz, text=qtext, question_type=qtype, marks=qmarks)
                if qtype == "objective":
                    if not q["choices"]:
                        raise ValueError("Objective question without choices found in Excel.")
                    correct_found = False
                    for c in q["choices"]:
                        Choice.objects.create(question=question, text=c["text"], is_correct=c["is_correct"])
                        if c["is_correct"]:
                            correct_found = True
                    if not correct_found:
                        raise ValueError("Objective question must have at least one correct choice.")
            return JsonResponse({"ok": True, "quiz_id": quiz.id, "message": "Quiz imported from Excel."})
    except ValueError as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=400)
    except Exception as e:
        return JsonResponse({"ok": False, "error": "Import failed: " + str(e)}, status=500)


# ---- Manage quizzes page ----
@login_required
@user_passes_test(is_teacher_or_admin)
def manage_quizzes_page(request):
    if request.user.role == 'teacher':
        quizzes = Quiz.objects.filter(created_by=request.user).order_by('-created_at')
    else:
        quizzes = Quiz.objects.all().order_by('-created_at')
    return render(request, "exams/manage_quizzes.html", {"quizzes": quizzes})

# ---- AJAX publish toggle ---old first----#
@login_required
@user_passes_test(is_teacher_or_admin)
@require_POST
def publish_toggle_ajax(request, quiz_id):
    quiz = get_object_or_404(Quiz, id=quiz_id)
    # only creator or admin can toggle
    if request.user != quiz.created_by and request.user.role not in ('admin','superadmin'):
        return JsonResponse({"ok": False, "error": "Permission denied."}, status=403)
    quiz.is_published = not quiz.is_published
    quiz.save()
    return JsonResponse({"ok": True, "is_published": quiz.is_published})

# ---- AJAX delete ----
@login_required
@user_passes_test(is_teacher_or_admin)
@require_POST
def delete_quiz_ajax(request, quiz_id):
    quiz = get_object_or_404(Quiz, id=quiz_id)
    if request.user != quiz.created_by and request.user.role not in ('admin','superadmin'):
        return JsonResponse({"ok": False, "error": "Permission denied."}, status=403)
    quiz.delete()
    return JsonResponse({"ok": True})



def is_teacher_or_admin(user):
    return user.is_authenticated and user.role in ('teacher','admin','superadmin')

@login_required
@user_passes_test(is_teacher_or_admin)
def edit_quiz_page(request, quiz_id):
    quiz = get_object_or_404(Quiz, id=quiz_id)
    # permission: only creator or admin allowed to edit
    if request.user != quiz.created_by and request.user.role not in ('admin','superadmin'):
        return HttpResponse("Permission denied", status=403)
    subjects = Subject.objects.select_related('school_class').all()
    # We'll render a page similar to create_quiz but include a small script that fetches quiz JSON to prefill
    return render(request, "exams/edit_quiz.html", {"quiz": quiz, "subjects": subjects})

@login_required
@user_passes_test(is_teacher_or_admin)
@require_POST
def edit_quiz_ajax(request, quiz_id):
    quiz = get_object_or_404(Quiz, id=quiz_id)
    if request.user != quiz.created_by and request.user.role not in ('admin','superadmin'):
        return JsonResponse({"ok": False, "error": "Permission denied"}, status=403)

    try:
        payload = json.loads(request.body.decode())
    except Exception:
        return JsonResponse({"ok": False, "error": "Invalid JSON"}, status=400)

    title = payload.get("title")
    subject_id = payload.get("subject_id")
    start_time = payload.get("start_time")
    end_time = payload.get("end_time")
    duration_minutes = payload.get("duration_minutes") or 30
    is_published = bool(payload.get("is_published", False))
    questions = payload.get("questions", [])

    if not title or not subject_id:
        return JsonResponse({"ok": False, "error": "Title and subject are required."}, status=400)

    try:
        subject = Subject.objects.get(id=subject_id)
    except Subject.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Subject not found."}, status=404)

    # Update within transaction. We'll replace existing questions/choices with new ones.
    try:
        with transaction.atomic():
            quiz.title = title
            quiz.subject = subject
            # parse start/end strings same as in create; expecting ISO or "YYYY-MM-DD HH:MM"
            from datetime import datetime
            from django.utils import timezone
            def parse_dt(s):
                if not s: return None
                try:
                    if "T" in s: s = s.replace("T"," ")
                    return timezone.make_aware(datetime.strptime(s, "%Y-%m-%d %H:%M"))
                except Exception:
                    try:
                        return timezone.make_aware(datetime.fromisoformat(s))
                    except Exception:
                        return None
            st = parse_dt(start_time)
            et = parse_dt(end_time)
            if not st or not et:
                return JsonResponse({"ok": False, "error": "Invalid start/end time format."}, status=400)
            quiz.start_time = st
            quiz.end_time = et
            quiz.duration_minutes = int(duration_minutes)
            quiz.is_published = is_published
            quiz.save()

            # delete old questions & choices, then recreate
            quiz.questions.all().delete()
            for qidx, q in enumerate(questions):
                qtext = q.get("text")
                qtype = q.get("question_type")
                qmarks = q.get("marks", 1)
                if not qtext or qtype not in ("objective","subjective"):
                    raise ValueError(f"Invalid question at index {qidx}")
                question = Question.objects.create(
                    quiz=quiz, text=qtext, question_type=qtype, marks=int(qmarks)
                )
                if qtype == "objective":
                    choices = q.get("choices", [])
                    if not choices or not isinstance(choices, list):
                        raise ValueError(f"Objective question requires choices at index {qidx}")
                    correct_found = False
                    for cidx, c in enumerate(choices):
                        ctext = c.get("text")
                        cis = bool(c.get("is_correct", False))
                        if not ctext:
                            raise ValueError(f"Choice text missing for question {qidx} choice {cidx}")
                        Choice.objects.create(question=question, text=ctext, is_correct=cis)
                        if cis:
                            correct_found = True
                    if not correct_found:
                        raise ValueError(f"At least one correct choice required for question {qidx}")
        return JsonResponse({"ok": True, "quiz_id": quiz.id, "message": "Quiz updated."})
    except ValueError as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=400)
    except Exception as e:
        return JsonResponse({"ok": False, "error": "Server error: " + str(e)}, status=500)

# endpoint to return quiz JSON (for prefill)
@login_required
@user_passes_test(is_teacher_or_admin)
def quiz_json(request, quiz_id):
    quiz = get_object_or_404(Quiz, id=quiz_id)
    # permission check as above
    if request.user != quiz.created_by and request.user.role not in ('admin','superadmin'):
        return JsonResponse({"ok": False, "error": "Permission denied"}, status=403)
    data = {
        "id": quiz.id,
        "title": quiz.title,
        "subject_id": quiz.subject.id,
        "start_time": quiz.start_time.strftime("%Y-%m-%dT%H:%M"),
        "end_time": quiz.end_time.strftime("%Y-%m-%dT%H:%M"),
        "duration_minutes": quiz.duration_minutes,
        "is_published": quiz.is_published,
        "questions": []
    }
    for q in quiz.questions.all():
        qd = {"text": q.text, "question_type": q.question_type, "marks": q.marks}
        if q.question_type == "objective":
            qd["choices"] = [{"text": c.text, "is_correct": c.is_correct} for c in q.choices.all()]
        data["questions"].append(qd)
    return JsonResponse({"ok": True, "quiz": data})



@require_POST
def toggle_quiz_publish(request, quiz_id):
    quiz = get_object_or_404(Quiz, id=quiz_id)
    quiz.is_published = not quiz.is_published
    quiz.save()
    return JsonResponse({"ok": True, "new_status": quiz.is_published})

def quiz_detail_api(request, quiz_id):
    quiz = get_object_or_404(Quiz, id=quiz_id)
    return JsonResponse({
        "ok": True,
        "quiz": {
            "id": quiz.id,
            "title": quiz.title,
            "subject": str(quiz.subject),
            "class_name": str(quiz.subject.school_class),
            "duration_minutes": quiz.duration_minutes,
            "is_published": quiz.is_published,
        }
    })


@login_required
@user_passes_test(is_teacher_or_admin)
def quiz_details_page(request, quiz_id):
    quiz = get_object_or_404(Quiz, id=quiz_id)
    # permission: only creator or admin allowed to view details
    if request.user != quiz.created_by and request.user.role not in ('admin','superadmin'):
        return HttpResponse("Permission denied", status=403)
    if quiz.DoesNotExist:
        attempts = StudentQuizAttempt.objects.filter(quiz=quiz).select_related('student').order_by('-started_at')
        return redirect('quiz_closed_detail', quiz.id)
    
    attempts = StudentQuizAttempt.objects.filter(quiz=quiz).select_related('student').order_by('-started_at')

    return render(request, "exams/quiz_details.html", {"quiz": quiz, "attempts": attempts})




def quiz_closed_detail(request, quiz_id):
    quiz = get_object_or_404(Quiz, id=quiz_id)
    
    # Make sure quiz is actually closed
    if quiz.end_time > timezone.now():
        # If not yet closed, you can redirect to quiz detail or show error
        return render(request, "exams/not_closed.html", {"quiz": quiz})
    
    # Get all attempts
    attempts = StudentQuizAttempt.objects.filter(quiz=quiz).select_related("student").order_by("-started_at")
    context = {
        "quiz": quiz,
        "attempts": attempts,
    }
    return render(request, "exams/quiz_closed_detail.html", context)




# -------------------------
# @login_required
# def start_attempt(request, quiz_id):
#     quiz = get_object_or_404(Quiz, id=quiz_id, is_published=True)
#     now = timezone.now()
#     if not (quiz.start_time <= now <= quiz.end_time):
#         return JsonResponse({"ok": False, "error": "Quiz not active."}, status=400)

#     # If student already has an unsubmitted attempt and time hasn't elapsed => resume it
#     existing = StudentQuizAttempt.objects.filter(student=request.user, quiz=quiz, is_submitted=False).order_by('-started_at').first()
#     if existing:
#         # compute end_time based on started_at + duration
#         end_time = existing.started_at + timezone.timedelta(minutes=quiz.duration_minutes)
#         if timezone.now() > end_time:
#             # time elapsed -> auto-submit or mark submitted
#             # attempt auto-grade objective answers here, mark submitted
#             auto_grade_attempt(existing)
#             existing.is_submitted = True
#             existing.completed_at = timezone.now()
#             existing.save()
#             return JsonResponse({"ok": False, "error": "Previous attempt timed out and was auto-submitted."}, status=400)
#         else:
#             return JsonResponse({
#                 "ok": True,
#                 "attempt_id": existing.id,
#                 "end_time": end_time.isoformat(),
#                 "resume": True
#             })
#     # else create new attempt
#     attempt = StudentQuizAttempt.objects.create(student=request.user, quiz=quiz, started_at=timezone.now(), is_submitted=False)
#     end_time = attempt.started_at + timezone.timedelta(minutes=quiz.duration_minutes)
#     return JsonResponse({"ok": True, "attempt_id": attempt.id, "end_time": end_time.isoformat(), "resume": False})

# def auto_grade_attempt(attempt):
#     """
#     Simple auto-grade: iterate objective answers, award question.marks if chosen choice.is_correct.
#     We assume ObjectiveAnswer entries exist (from autosaves). If not, they will be treated as unanswered (0).
#     """
#     total_score = 0
#     total_marks = 0
#     for q in attempt.quiz.questions.filter(question_type='objective'):
#         total_marks += q.marks
#         obj = ObjectiveAnswer.objects.filter(attempt=attempt, question=q).select_related('choice').first()
#         if obj and obj.choice and obj.choice.is_correct:
#             total_score += q.marks
#     # Subjective marks are added later when graded — compute total_marks to include subjectives
#     subj_total = sum(q.marks for q in attempt.quiz.questions.filter(question_type='subjective'))
#     attempt.score = total_score
#     attempt.total_marks = total_marks + subj_total
#     attempt.save()

# @require_POST
# @login_required
# def autosave_attempt(request, attempt_id):
#     attempt = get_object_or_404(StudentQuizAttempt, id=attempt_id, student=request.user, is_submitted=False)
#     try:
#         payload = json.loads(request.body.decode())
#     except Exception:
#         return JsonResponse({"ok": False, "error": "Invalid JSON"}, status=400)
#     answers = payload.get('answers', [])  # list of {question_id, choice_id/text}
#     # Save each answer (create or update)
#     for a in answers:
#         qid = a.get('question_id')
#         if not qid:
#             continue
#         q = Question.objects.get(id=qid)
#         if q.question_type == 'objective':
#             choice_id = a.get('choice_id')
#             if choice_id:
#                 # update or create ObjectiveAnswer
#                 oa, _ = ObjectiveAnswer.objects.get_or_create(attempt=attempt, question=q)
#                 oa.choice_id = choice_id
#                 oa.save()
#             else:
#                 # unanswered -> remove existing maybe
#                 ObjectiveAnswer.objects.filter(attempt=attempt, question=q).delete()
#         else:
#             text = a.get('text', '')
#             sa, _ = SubjectiveAnswer.objects.get_or_create(attempt=attempt, question=q)
#             sa.answer_text = text
#             sa.save()
#     return JsonResponse({"ok": True})

# @require_POST
# @login_required
# def submit_attempt(request, attempt_id):
#     attempt = get_object_or_404(StudentQuizAttempt, id=attempt_id, student=request.user, is_submitted=False)
#     # server-side check: time
#     quiz = attempt.quiz
#     end_time = attempt.started_at + timezone.timedelta(minutes=quiz.duration_minutes)
#     now = timezone.now()
#     if now > end_time:
#         # time elapsed: auto-grade & finalize
#         auto_grade_attempt(attempt)
#         attempt.is_submitted = True
#         attempt.completed_at = now
#         attempt.save()
#         return JsonResponse({"ok": True, "auto_submitted": True, "message": "Time elapsed — attempt auto-submitted."})

#     # otherwise grade objectives now
    # auto_grade_attempt(attempt)
    # attempt.is_submitted = True
    # attempt.completed_at = now
    # attempt.save()

    # # optionally create Notification for teacher that subjectives need grading
    # from .models import Notification
    # if attempt.quiz.created_by:
    #     Notification.objects.create(title=f"New attempt by {request.user.username}", message=f"{request.user.username} submitted {attempt.quiz.title}", sender=request.user, target_role='teachers')

    # return JsonResponse({"ok": True, "message": "Submitted", "score_so_far": attempt.score})
 

from openpyxl import Workbook
from django.http import HttpResponse

@login_required
@user_passes_test(is_teacher_or_admin)
def download_excel_template(request):
    wb = Workbook()
    ws = wb.active
    ws.title = "QuizTemplate"

    # metadata rows
    ws['A1'] = 'quiz_title'; ws['B1'] = 'My Exam Title'
    ws['A2'] = 'class_name'; ws['B2'] = 'JSS1'
    ws['A3'] = 'subject_name'; ws['B3'] = 'Mathematics'
    ws['A4'] = 'start_time'; ws['B4'] = timezone.now()
    ws['A5'] = 'end_time'; ws['B5'] = timezone.now()
    ws['A6'] = 'duration_minutes'; ws['B6'] = 60
    ws['A7'] = 'is_published'; ws['B7'] = 'True'

    # header row at row 9
    headers = ['question_text','question_type','marks']
    # allow up to 6 choices (choice_x, choice_x_correct)
    for i in range(1,7):
        headers.append(f'choice_{i}')
        headers.append(f'choice_{i}_correct')
    for col_idx, header in enumerate(headers, start=1):
        ws.cell(row=9, column=col_idx, value=header)

    # example question row
    ws.cell(row=10, column=1, value='What is 2+2?')
    ws.cell(row=10, column=2, value='objective')
    ws.cell(row=10, column=3, value=1)
    ws.cell(row=10, column=4, value='3')
    ws.cell(row=10, column=5, value='0')
    ws.cell(row=10, column=6, value='4')
    ws.cell(row=10, column=7, value='1')

    # prepare response
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename=quiz_template.xlsx'
    wb.save(response)
    return response
