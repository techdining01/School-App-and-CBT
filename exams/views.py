from django.contrib import messages
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from .models import Quiz, Question, Choice, StudentQuizAttempt, ActionLog, Answer, Class, Subject, ObjectiveAnswer, SubjectiveAnswer
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse, HttpResponse, HttpResponseBadRequest, HttpResponseForbidden
from django.db.models import Sum, Avg, Count
from django.template.loader import render_to_string
from .utils import log_action
from .forms import QuizCreateForm, QuestionForm, ChoiceForm
from django.conf import settings
import json, os
from django.views.decorators.http import require_POST
from .models import Quiz, Question, Choice, Subject

from django.http import HttpResponse
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from reportlab.lib.units import inch
from .models import StudentQuizAttempt

# continuing from above
from django.views.decorators.http import require_POST
from django.contrib import messages
from users.models import Notification
from django.contrib.auth import get_user_model


import json, os
from django.http import JsonResponse, HttpResponseBadRequest, HttpResponse
from django.db import transaction
from django.utils import timezone
from django.conf import settings
from .models import Quiz, Question, Choice, Subject, Class as SchoolClass

# Excel parser
from openpyxl import load_workbook
from datetime import datetime
import json
from django.db import transaction

import json
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from django.http import JsonResponse
from .models import Quiz, StudentQuizAttempt, Question


User = get_user_model()

def home(request):
    return render(request, "exams/home.html")


@login_required
def take_quiz(request, quiz_id):
    quiz = get_object_or_404(Quiz, id=quiz_id, published=True)
    now = timezone.now()

    # Check if quiz is active
    if not (quiz.start_time <= now <= quiz.end_time):
        return render(request, "exams/quiz_closed.html", {"quiz": quiz})

    # Get or create attempt
    attempt, created = StudentQuizAttempt.objects.get_or_create(
        student=request.user, quiz=quiz, submitted_at__isnull=True
    )

    if request.method == "POST":
        # Process answers
        for question in quiz.questions.all():
            qid = str(question.id)

            if question.type == "objective":
                choice_id = request.POST.get(f"question_{qid}")
                if choice_id:
                    choice = Choice.objects.get(id=choice_id)
                    ans, _ = Answer.objects.get_or_create(attempt=attempt, question=question)
                    ans.selected_choice = choice
                    ans.text_answer = ""
                    # Auto-grade
                    ans.obtained_marks = question.marks if choice.is_correct else 0
                    ans.is_pending = False
                    ans.save()

            elif question.type == "subjective":
                text = request.POST.get(f"question_{qid}")
                if text:
                    ans, _ = Answer.objects.get_or_create(attempt=attempt, question=question)
                    ans.text_answer = text
                    ans.selected_choice = None
                    ans.obtained_marks = 0  # to be graded later
                    ans.is_pending = True
                    ans.save()

        attempt.submitted_at = timezone.now()
        attempt.auto_submitted = False
        attempt.save()
        log_action(request.user, f"attempted {"title": quiz.title}")

        messages.success(request, "Quiz submitted successfully!")
        return redirect("quiz_result", attempt_id=attempt.id)

    context = {
        "quiz": quiz,
        "attempt": attempt,
        "questions": quiz.questions.prefetch_related("choices"),
        "end_time": quiz.start_time + timezone.timedelta(minutes=quiz.duration_minutes),
    }
    return render(request, "exams/take_quiz.html", context)


def take_quiz(request, quiz_id):
    quiz = get_object_or_404(Quiz, id=quiz_id)

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

    return render(request, "quizzes/take_quiz.html", {
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
    approved = User.objects.exclude(role='superadmin',approved=True).count()
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

    notifications = Notification.objects.filter(role='admin').order_by('-created_at')[:10]
    

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



@login_required
@user_passes_test(is_admin)
def admin_dashboard(request):
    # counts
    approved = User.objects.filter(approved=True).count()
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

    notifications = Notification.objects.filter(role='admin').order_by('-created_at')[:10]
    

    context = {
        "approved": approved,
        "pended": pended,
        "teachers": teachers,
        "students": students,
        "leaderboard": leaderboard,
        "actions": actions,
        "notifications": notifications,
    }
    return render(request, "exams/admin_dashboard.html", context)

  
@login_required
def admin_dashboard_data(request):
    if request.user.role not in ("admin", "superadmin"):
        return JsonResponse({"error": "forbidden"}, status=403)

    # Stats
    stats = {
        "total_users": User.objects.filter(role__in=["admin", "teacher", "student"]).count(),
        "admins": User.objects.filter(role="admin", approved=True).count(),
        "teachers": User.objects.filter(role="teacher", approved=True).count(),
        "students": User.objects.filter(role="student", approved=True).count(),
        "pending_users": User.objects.filter(approved=False).count(),
        "classes": Class.objects.count(),
        "subjects": Subject.objects.count(),
        "quizzes": Quiz.objects.count(),
    }

    
    # Pending users list (serialize to list of dicts)
    pending_list = list(User.objects.filter(approved=False).values("id","username", "email", "role", "date_joined"))

    # Activity log entries (adapt field names of your ActivityLog model)
    logs_qs = ActionLog.objects.order_by("-timestamp")[:10]
    logs = [
        {
            "action": l.action,
            "user": (l.user.username if getattr(l, "user", None) else getattr(l, "performed_by__username", None)),
            "timestamp": l.timestamp.isoformat()
        }
        for l in logs_qs
    ]

    # Leaderboard (top students by avg score). Adjust Result model fields
    leaderboard_qs = Answer.objects.values("attempt__student__username").annotate(avg_score=Avg("obtained_marks")).order_by("-avg_score")[:10]

    leaderboard = [{"username": r["attempt__student__username"], "avg_score": float(r["avg_score"] or 0)} for r in leaderboard_qs]

    # Class performance (avg score per class); adjust keys to your schema
    class_perf_qs = Answer.objects.values("attempt__quiz__subject__school_class__name").annotate(avg_score=Avg("obtained_marks")).order_by("attempt__quiz__subject__school_class__name")
    
    class_performance = [
        {"class_name": row["attempt__quiz__subject__school_class__name"] or "Unknown", "avg_score": float(row["avg_score"] or 0)}
        for row in class_perf_qs
    ]

    # Notifications for the admin user (last 10) - adapt Notification model fields
    notifications_qs = Notification.objects.filter(recipient=request.user).order_by("-created_at")[:10]
    notifications = [
        {"id": n.id, "message": n.message, "sender": (n.sender.username if n.sender else None), "created_at": n.created_at.isoformat(), "is_read": n.is_read}
        for n in notifications_qs
    ]

    return JsonResponse({
        "stats": stats,
        "pending_list": pending_list,
        "logs": logs, 
        "leaderboard": leaderboard,
        "class_performance": class_performance,
        "notifications": notifications,
    })



@login_required
@user_passes_test(is_teacher)
def teacher_dashboard(request):
    user = request.user
    # list classes teacher handles: depends on your data model. Here we take subjects created_by teacher
    teacher_subjects = request.user.student_class  # adapt: this is quizzes created_by teacher
    # For performance chart we aggregate attempts by quiz or subject
    # Example: average score per quiz created by teacher
    performance = StudentQuizAttempt.objects.filter(quiz__subject__school_class=user.student_class).values('quiz__title').annotate(avg_score=Avg('score'), attempts=Count('id')).order_by('-avg_score')

    # subjectives pending for this teacher's quizzes
    pending_subjectives = SubjectiveAnswer.objects.filter(question__quiz__subject__school_class=user.student_class, graded=False).select_related('attempt','question').order_by('attempt__started_at')

    # recent action logs
    actions = ActionLog.objects.order_by('-timestamp')[:20]

    # notifications visible to teachers or all
    notifications = Notification.objects.filter(role='teacher').order_by('-created_at')[:10]


    context = {
        "performance": performance,
        "pending_subjectives": pending_subjectives,
        "notifications": notifications,
        'actions': actions
    }
    return render(request, "exams/teacher_dashboard.html", context)


  
@login_required
def student_dashboard(request):
    user = request.user
    # summary: total attempts, avg score, pending subjectives count
    attempts = StudentQuizAttempt.objects.filter(student=user)
    total_attempts = attempts.count()
    avg_score = attempts.aggregate(avg=Avg('score'))['avg'] or 0
    pending_count = Answer.objects.filter(attempt__student=user, is_pending=True).count()

    # available quizzes for student's classes (assumes you have relationship)
    # adapt: if User has class field, e.g., profile_class
    # For this example, we assume user.profile_class exists (adjust accordingly).
    available = []
    # if user has class, fetch quizzes for that class's subjects
    try:
        user_class = user.student_class  # user.profile_class must exist in your User model or related profile
        available = Quiz.objects.filter(subject__school_class=user.student_class, start_time__lte=timezone.now(), end_time__gte=timezone.now(),).order_by('start_time')
    except Exception:
        available = None

    # recent attempts with ability to review wrong answers
    recent_attempts = attempts.select_related('quiz').order_by('-started_at')[:5]

    # recent action logs
    actions = ActionLog.objects.order_by('-timestamp')[:20]

    # notifications for students or all
    notifications = Notification.objects.filter(role='students').order_by('-created_at')[:5]
    

    context = {
        "total_attempts": total_attempts,
        "avg_score": avg_score,
        "pending_count": pending_count,
        "available_quizzes": available,
        "recent_attempts": recent_attempts,
        "notifications": notifications,
        'actions': actions
    }
    return render(request, "exams/student_dashboard.html", context)


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

def consolidated_results_pdf(request):
    # response
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="consolidated_results.pdf"'

    # setup doc
    doc = SimpleDocTemplate(response, pagesize=A4)
    styles = getSampleStyleSheet()
    elements = []

    # === HEADER SECTION ===
    # static school logo
    school_logo_path = os.path.join(settings.BASE_DIR, "static/images/school_logo.png")
    # user profile picture (from your User model)
    profile_pic_path = None
    if request.user.profile_picture:
        try:
            profile_pic_path = request.user.profile_picture.path
        except Exception:
            profile_pic_path = None

    # header row (logo | school name | profile picture)
    header_data = []

    logo_img = Image(school_logo_path, width=1*inch, height=1*inch) if os.path.exists(school_logo_path) else ""
    profile_img = Image(profile_pic_path, width=1*inch, height=1*inch) if profile_pic_path and os.path.exists(profile_pic_path) else ""

    school_name = getattr(settings, "SCHOOL_NAME", "My School")

    header_data.append([
        logo_img,
        Paragraph(f"<b>{school_name}</b>", styles["Title"]),
        profile_img
    ])

    header_table = Table(header_data, colWidths=[1.5*inch, 3.5*inch, 1.5*inch])
    header_table.setStyle(TableStyle([
        ("ALIGN", (0, 0), (0, 0), "LEFT"),
        ("ALIGN", (1, 0), (1, 0), "CENTER"),
        ("ALIGN", (2, 0), (2, 0), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))

    elements.append(header_table)
    elements.append(Spacer(1, 20))

    # subtitle
    elements.append(Paragraph("Consolidated Quiz Results", styles["Heading2"]))
    elements.append(Spacer(1, 12))

    # === RESULTS TABLE ===
    attempts = StudentQuizAttempt.objects.filter(student=request.user)

    data = [["Quiz", "Score", "Total", "Completed At"]]
    for attempt in attempts:
        data.append([
            attempt.quiz.title,
            attempt.score,
            attempt.total_marks,
            attempt.completed_at.strftime("%d-%m-%Y %H:%M") if attempt.completed_at else "In Progress",
        ])

    # create table
    table = Table(data, colWidths=[200, 70, 70, 120])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
        ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
        ("GRID", (0, 0), (-1, -1), 1, colors.black),
    ]))

    elements.append(table)

    # build pdf
    doc.build(elements)
    return response



@login_required
def student_consolidated_results_pdf(request):
    student = request.user
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{student.username}_results.pdf"'

    p = canvas.Canvas(response, pagesize=A4)
    width, height = A4

    # Header: logo + profile
    p.drawImage("static/images/school_logo.png", 40, height - 100, width=60, height=60, mask='auto')
    if student.profile_picture:
        try:
            p.drawImage(student.profile_picture.path, width - 100, height - 100, width=60, height=60, mask='auto')
        except Exception:
            pass

    p.setFont("Helvetica-Bold", 16)
    p.drawCentredString(width/2, height - 50, "SCHOOL NAME")
    p.setFont("Helvetica", 12)
    p.drawCentredString(width/2, height - 70, f"Student: {student.get_full_name()}")

    y = height - 150

    attempts = StudentQuizAttempt.objects.filter(student=student).select_related("quiz")

    for attempt in attempts:
        quiz = attempt.quiz

        # Score computation
        total_obj = ObjectiveAnswer.objects.filter(attempt=attempt).count()
        correct_obj = ObjectiveAnswer.objects.filter(attempt=attempt, choice__is_correct=True).count()
        graded_subj = SubjectiveAnswer.objects.filter(attempt=attempt, marks_awarded__isnull=False)
        subj_score = sum(ans.marks_awarded for ans in graded_subj)
        subj_total = sum(ans.question.marks for ans in graded_subj)

        pending_subj = SubjectiveAnswer.objects.filter(attempt=attempt, marks_awarded__isnull=True).count()

        total_score = correct_obj + subj_score
        total_marks = total_obj + subj_total + pending_subj  # pending ones reserved, no awarded marks yet

        # Print quiz title & result
        p.setFont("Helvetica-Bold", 13)
        p.drawString(50, y, f"Quiz: {quiz.title} ({quiz.subject.name})")
        y -= 20
        p.setFont("Helvetica", 11)
        p.drawString(70, y, f"Score: {total_score}/{total_marks} | Pending: {pending_subj}")
        y -= 20

        # List wrongly answered objective questions (review)
        wrong_obj = ObjectiveAnswer.objects.filter(attempt=attempt, choice__is_correct=False)
        if wrong_obj.exists():
            p.setFont("Helvetica-Oblique", 11)
            p.drawString(70, y, "Review of Wrong Answers:")
            y -= 20
            for obj in wrong_obj:
                q_text = obj.question.text[:60] + ("..." if len(obj.question.text) > 60 else "")
                p.drawString(90, y, f"- {q_text}")
                y -= 15
                if y < 100:
                    p.showPage()
                    y = height - 100

        y -= 15
        if y < 100:
            p.showPage()
            y = height - 100

    p.showPage()
    p.save()
    return response



@login_required
def teacher_class_results_pdf(request):
    teacher = request.user
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="class_results.pdf"'

    p = canvas.Canvas(response, pagesize=A4)
    width, height = A4

    # Header
    p.drawImage("static/images/school_logo.png", 40, height - 100, width=60, height=60, mask='auto')
    if teacher.profile_picture:
        p.drawImage(teacher.profile_picture.path, width - 100, height - 100, width=60, height=60, mask='auto')

    p.setFont("Helvetica-Bold", 16)
    p.drawCentredString(width/2, height - 50, "SCHOOL NAME")
    p.setFont("Helvetica", 12)
    p.drawCentredString(width/2, height - 70, f"Teacher: {teacher.get_full_name()}")

    y = height - 150
    quizzes = Quiz.objects.filter(created_by=teacher)

    for quiz in quizzes:
        p.setFont("Helvetica-Bold", 13)
        p.drawString(50, y, f"Quiz: {quiz.title}")
        y -= 20

        attempts = StudentQuizAttempt.objects.filter(quiz=quiz).select_related("student")
        for attempt in attempts:
            # Compute score
            total_obj = ObjectiveAnswer.objects.filter(attempt=attempt).count()
            correct_obj = ObjectiveAnswer.objects.filter(attempt=attempt, is_correct=True).count()
            pending_subj = SubjectiveAnswer.objects.filter(attempt=attempt, score__isnull=True).count()
            graded_subj = SubjectiveAnswer.objects.filter(attempt=attempt, score__isnull=False)

            subj_score = sum(ans.score for ans in graded_subj)
            subj_total = sum(ans.question.max_marks for ans in graded_subj)

            total_score = correct_obj + subj_score
            total_marks = total_obj + subj_total + (pending_subj * 0)  # pending not graded yet

            p.setFont("Helvetica", 11)
            p.drawString(70, y, f"Student: {attempt.student.get_full_name()} | Score: {total_score}/{total_marks} | Pending: {pending_subj}")
            y -= 20

            if y < 100:
                p.showPage()
                y = height - 100

        y -= 10

    p.showPage()
    p.save()
    return response


@login_required
def admin_overall_results_pdf(request):
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="admin_results.pdf"'

    p = canvas.Canvas(response, pagesize=A4)
    width, height = A4

    # Header
    p.drawImage("static/images/school_logo.png", 40, height - 100, width=60, height=60, mask='auto')
    if request.user.profile_picture:
        p.drawImage(request.user.profile_picture.path, width - 100, height - 100, width=60, height=60, mask='auto')

    p.setFont("Helvetica-Bold", 16)
    p.drawCentredString(width/2, height - 50, "SCHOOL NAME")
    p.setFont("Helvetica", 12)
    p.drawCentredString(width/2, height - 70, f"Admin: {request.user.get_full_name()}")

    y = height - 150

    # Leaderboard (top 10 students by computed score)
    leaderboard = []
    attempts = StudentQuizAttempt.objects.select_related("student")
    for attempt in attempts:
        total_obj = ObjectiveAnswer.objects.filter(attempt=attempt).count()
        correct_obj = ObjectiveAnswer.objects.filter(attempt=attempt, is_correct=True).count()
        graded_subj = SubjectiveAnswer.objects.filter(attempt=attempt, score__isnull=False)
        subj_score = sum(ans.score for ans in graded_subj)

        score = correct_obj + subj_score
        leaderboard.append((attempt.student, score))

    # sort by score
    leaderboard = sorted(leaderboard, key=lambda x: x[1], reverse=True)[:10]

    p.setFont("Helvetica-Bold", 13)
    p.drawString(50, y, "Leaderboard (Top Students)")
    y -= 20

    for idx, (student, score) in enumerate(leaderboard, start=1):
        p.setFont("Helvetica", 11)
        p.drawString(70, y, f"{idx}. {student.get_full_name()} - {score} points")
        y -= 20
        if y < 100:
            p.showPage()
            y = height - 100

    y -= 30

    # Users summary
    total_users = User.objects.count()
    students = User.objects.filter(role="student").count()
    teachers = User.objects.filter(role="teacher").count()
    admins = User.objects.filter(role="admin").count()

    p.setFont("Helvetica-Bold", 13)
    p.drawString(50, y, "Users Summary")
    y -= 20
    p.setFont("Helvetica", 11)
    p.drawString(70, y, f"Total Users: {total_users}")
    y -= 20
    p.drawString(70, y, f"Students: {students}")
    y -= 20
    p.drawString(70, y, f"Teachers: {teachers}")
    y -= 20
    p.drawString(70, y, f"Admins: {admins}")

    p.showPage()
    p.save()
    return response


# --------------------------------------------------------------#


# @login_required
# @user_passes_test(is_admin)
# @require_POST
# def broadcast(request):
#     title = request.POST.get('title')
#     message = request.POST.get('message')
#     target_role = request.POST.get('target_role', 'all')
#     Notification.objects.create(title=title, message=message, sender=request.user, target_role=target_role)
#     log_action(request.user, "Broadcast", details={"title": title, "target": target_role})
#     messages.success(request, "Broadcast sent.")
#     return redirect('admin_dashboard')


@login_required
@user_passes_test(is_teacher)
def grade_answer(request, answer_id):
    # simple grade form: GET shows form, POST submits grade and feedback
    ans = get_object_or_404(Answer, id=answer_id, question__quiz__created_by=request.user)
    if request.method == 'POST':
        marks = float(request.POST.get('marks') or 0)
        feedback = request.POST.get('feedback', '')
        ans.obtained_marks = marks
        ans.feedback = feedback
        ans.graded_by = request.user
        ans.graded_at = timezone.now()
        ans.is_pending = False
        ans.save()
        # update attempt total if all subjectives graded
        attempt = ans.attempt
        if not attempt.answers.filter(is_pending=True).exists():
            # sum marks objective + subjective into attempt.total_score
            total = attempt.answers.aggregate(total=Sum('obtained_marks'))['total'] or 0
            attempt.total_score = total
            attempt.graded = True
            attempt.save()
        log_action(request.user, "Graded answer", "Answer", ans.id, {"marks": marks})
        messages.success(request, "Answer graded.")
        return redirect('teacher_dashboard')
    return render(request, 'quizzes/grade_answer.html', {'ans': ans})



def is_teacher_or_admin(user):
    return user.is_authenticated and user.role in ('teacher', 'admin', 'superadmin')


@login_required
@user_passes_test(is_teacher_or_admin)
def create_quiz_page(request):
    """
    Renders the page with the create quiz UI (dynamic JS will handle adding questions & choices).
    """
    subjects = Subject.objects.all()
    return render(request, "quizzes/create_quiz.html", {"subjects": subjects})


@login_required
@user_passes_test(is_teacher_or_admin)
@require_POST
def create_quiz_ajax(request):
    """
    Expects JSON payload like:
    {
      "title": "Midterm 1",
      "subject_id": 1,
      "duration_minutes": 30,
      "is_published": true,
      "questions": [
        {
          "text": "What is 2+2?",
          "question_type": "objective",
          "marks": 2,
          "choices": [
            {"text": "3", "is_correct": false},
            {"text": "4", "is_correct": true}
          ]
        },
        {
          "text": "Explain photosynthesis",
          "question_type": "subjective",
          "marks": 5
        }
      ]
    }
    """
    try:
        payload = json.loads(request.body.decode('utf-8'))
    except Exception as e:
        return HttpResponseBadRequest("Invalid JSON")

    # Basic quiz data validation
    quiz_data = {
        "title": payload.get("title"),
        "subject_id": payload.get("subject_id"),
        "duration_minutes": payload.get("duration_minutes"),
        "is_published": payload.get("is_published", False),
    }
    if not quiz_data["title"] or not quiz_data["subject_id"]:
        return JsonResponse({"ok": False, "error": "Title and subject are required."}, status=400)

    subject = get_object_or_404(Subject, id=quiz_data["subject_id"])

    # Create the quiz
    quiz = Quiz.objects.create(
        title=quiz_data["title"],
        subject=subject,
        created_by=request.user,
        duration_minutes=int(quiz_data.get("duration_minutes") or 30),
        is_published=bool(quiz_data.get("is_published", False))
    )

    questions = payload.get("questions", [])
    created_questions = []
    for q_idx, q in enumerate(questions):
        q_text = q.get("text")
        q_type = q.get("question_type")
        q_marks = q.get("marks", 1)
        if not q_text or q_type not in ("objective", "subjective"):
            # rollback: delete quiz and return error
            quiz.delete()
            return JsonResponse({"ok": False, "error": f"Invalid question data at index {q_idx}"}, status=400)

        question = Question.objects.create(
            quiz=quiz,
            text=q_text,
            question_type=q_type,
            marks=float(q_marks)
        )
        created_questions.append(question)

        # If objective, create choices
        if q_type == "objective":
            choices = q.get("choices", [])
            if not choices or not isinstance(choices, list):
                quiz.delete()
                return JsonResponse({"ok": False, "error": f"Objective question must have choices at index {q_idx}"}, status=400)

            # create choices
            correct_exists = False
            for c_idx, choice in enumerate(choices):
                c_text = choice.get("text")
                c_is_correct = bool(choice.get("is_correct", False))
                if not c_text:
                    quiz.delete()
                    return JsonResponse({"ok": False, "error": f"Choice text missing for question {q_idx} choice {c_idx}"}, status=400)
                Choice.objects.create(question=question, text=c_text, is_correct=c_is_correct)
                if c_is_correct:
                    correct_exists = True

            if not correct_exists:
                quiz.delete()
                return JsonResponse({"ok": False, "error": f"At least one correct choice required for objective question {q_idx}"}, status=400)

    # Log action
    log_action(request.user, "Created quiz", "Quiz", quiz.id, {"title": quiz.title, "questions": len(created_questions)})

    return JsonResponse({"ok": True, "quiz_id": quiz.id, "message": "Quiz created successfully."})


@require_POST
@login_required
def attempt_submit(request, attempt_id):
    attempt = get_object_or_404(StudentQuizAttempt, id=attempt_id, student=request.user, is_submitted=False)
    # mark submitted
    attempt.is_submitted = True
    attempt.completed_at = timezone.now()

    # grade objective answers
    total_score = 0
    total_marks = 0
    for obj in attempt.objective_answers.select_related('choice','question'):
        q = obj.question
        total_marks += q.marks
        if obj.choice and obj.choice.is_correct:
            total_score += q.marks

    # subjectives remain pending - teacher will grade later.
    # compute partial score now and store totals
    attempt.score = total_score
    attempt.total_marks = total_marks + sum(q.marks for q in attempt.subjective_answers.values_list('question__marks', flat=True))
    attempt.save()

    # Optionally notify teacher(s) that new subjectives need grading (create Notification)
    # log action
    log_action(request.user, "Submitted attempt", "StudentQuizAttempt", attempt.id, {"score_so_far": total_score})

    return JsonResponse({"ok": True, "score": total_score})



def is_teacher_or_admin(user):
    return user.is_authenticated and user.role in ('teacher','admin','superadmin')

# ---- Page: create quiz (manual + excel upload) ----
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
        school_class = SchoolClass.objects.get(name__iexact=str(class_name).strip())
    except SchoolClass.DoesNotExist:
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

# ---- AJAX publish toggle ----
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


import json
from django.utils import timezone
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST
from .models import Quiz, StudentQuizAttempt, Question, Choice, ObjectiveAnswer, SubjectiveAnswer, Answer

@login_required
def start_attempt(request, quiz_id):
    quiz = get_object_or_404(Quiz, id=quiz_id, is_published=True)
    now = timezone.now()
    if not (quiz.start_time <= now <= quiz.end_time):
        return JsonResponse({"ok": False, "error": "Quiz not active."}, status=400)

    # If student already has an unsubmitted attempt and time hasn't elapsed => resume it
    existing = StudentQuizAttempt.objects.filter(student=request.user, quiz=quiz, is_submitted=False).order_by('-started_at').first()
    if existing:
        # compute end_time based on started_at + duration
        end_time = existing.started_at + timezone.timedelta(minutes=quiz.duration_minutes)
        if timezone.now() > end_time:
            # time elapsed -> auto-submit or mark submitted
            # attempt auto-grade objective answers here, mark submitted
            auto_grade_attempt(existing)
            existing.is_submitted = True
            existing.completed_at = timezone.now()
            existing.save()
            return JsonResponse({"ok": False, "error": "Previous attempt timed out and was auto-submitted."}, status=400)
        else:
            return JsonResponse({
                "ok": True,
                "attempt_id": existing.id,
                "end_time": end_time.isoformat(),
                "resume": True
            })
    # else create new attempt
    attempt = StudentQuizAttempt.objects.create(student=request.user, quiz=quiz, started_at=timezone.now(), is_submitted=False)
    end_time = attempt.started_at + timezone.timedelta(minutes=quiz.duration_minutes)
    return JsonResponse({"ok": True, "attempt_id": attempt.id, "end_time": end_time.isoformat(), "resume": False})

def auto_grade_attempt(attempt):
    """
    Simple auto-grade: iterate objective answers, award question.marks if chosen choice.is_correct.
    We assume ObjectiveAnswer entries exist (from autosaves). If not, they will be treated as unanswered (0).
    """
    total_score = 0
    total_marks = 0
    for q in attempt.quiz.questions.filter(question_type='objective'):
        total_marks += q.marks
        obj = ObjectiveAnswer.objects.filter(attempt=attempt, question=q).select_related('choice').first()
        if obj and obj.choice and obj.choice.is_correct:
            total_score += q.marks
    # Subjective marks are added later when graded — compute total_marks to include subjectives
    subj_total = sum(q.marks for q in attempt.quiz.questions.filter(question_type='subjective'))
    attempt.score = total_score
    attempt.total_marks = total_marks + subj_total
    attempt.save()

@require_POST
@login_required
def autosave_attempt(request, attempt_id):
    attempt = get_object_or_404(StudentQuizAttempt, id=attempt_id, student=request.user, is_submitted=False)
    try:
        payload = json.loads(request.body.decode())
    except Exception:
        return JsonResponse({"ok": False, "error": "Invalid JSON"}, status=400)
    answers = payload.get('answers', [])  # list of {question_id, choice_id/text}
    # Save each answer (create or update)
    for a in answers:
        qid = a.get('question_id')
        if not qid:
            continue
        q = Question.objects.get(id=qid)
        if q.question_type == 'objective':
            choice_id = a.get('choice_id')
            if choice_id:
                # update or create ObjectiveAnswer
                oa, _ = ObjectiveAnswer.objects.get_or_create(attempt=attempt, question=q)
                oa.choice_id = choice_id
                oa.save()
            else:
                # unanswered -> remove existing maybe
                ObjectiveAnswer.objects.filter(attempt=attempt, question=q).delete()
        else:
            text = a.get('text', '')
            sa, _ = SubjectiveAnswer.objects.get_or_create(attempt=attempt, question=q)
            sa.answer_text = text
            sa.save()
    return JsonResponse({"ok": True})

@require_POST
@login_required
def submit_attempt(request, attempt_id):
    attempt = get_object_or_404(StudentQuizAttempt, id=attempt_id, student=request.user, is_submitted=False)
    # server-side check: time
    quiz = attempt.quiz
    end_time = attempt.started_at + timezone.timedelta(minutes=quiz.duration_minutes)
    now = timezone.now()
    if now > end_time:
        # time elapsed: auto-grade & finalize
        auto_grade_attempt(attempt)
        attempt.is_submitted = True
        attempt.completed_at = now
        attempt.save()
        return JsonResponse({"ok": True, "auto_submitted": True, "message": "Time elapsed — attempt auto-submitted."})

    # otherwise grade objectives now
    auto_grade_attempt(attempt)
    attempt.is_submitted = True
    attempt.completed_at = now
    attempt.save()

    # optionally create Notification for teacher that subjectives need grading
    from .models import Notification
    if attempt.quiz.created_by:
        Notification.objects.create(title=f"New attempt by {request.user.username}", message=f"{request.user.username} submitted {attempt.quiz.title}", sender=request.user, target_role='teachers')

    return JsonResponse({"ok": True, "message": "Submitted", "score_so_far": attempt.score})
 

from openpyxl import Workbook
from django.http import HttpResponse

@login_required
@user_passes_test(is_teacher_or_admin)
def download_excel_template(request):
    wb = Workbook()
    ws = wb.active
    ws.title = "QuizTemplate"

    # metadata rows
    ws['A1'] = 'quiz_title'; ws['B1'] = 'My Quiz Title'
    ws['A2'] = 'class_name'; ws['B2'] = 'JSS1'
    ws['A3'] = 'subject_name'; ws['B3'] = 'Mathematics'
    ws['A4'] = 'start_time'; ws['B4'] = '2025-09-13 14:00'
    ws['A5'] = 'end_time'; ws['B5'] = '2025-09-13 15:00'
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
