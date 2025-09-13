from django.contrib import messages
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from .models import Quiz, Question, Choice, StudentQuizAttempt, ActionLog, Answer, Class, Subject
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
        log_action(request.user, f"attempted {"title": quiz.subject}")


        return redirect("quiz_result", attempt_id=attempt.id)

    context = {
        "quiz": quiz,
        "attempt": attempt,
        "questions": quiz.questions.prefetch_related("choices"),
        "end_time": quiz.start_time + timezone.timedelta(minutes=quiz.duration_minutes),
    }
    return render(request, "exams/take_quiz.html", context)


@login_required
def quiz_result(request, attempt_id):
    attempt = get_object_or_404(StudentQuizAttempt, id=attempt_id, student=request.user)
    answers = attempt.answers.select_related("question", "selected_choice")
    total_objective = sum(ans.obtained_marks for ans in answers if ans.question.type == "objective")
    total_subjective = sum(ans.obtained_marks for ans in answers if ans.question.type == "subjective")

    context = {
        "attempt": attempt,
        "answers": answers,
        "total_objective": total_objective,
        "total_subjective": total_subjective,
        "final_score": total_objective + total_subjective,
    }
    return render(request, "exams/quiz_result.html", context)


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
     
    context = {
        "total_admins": User.objects.filter(role="admin", approved=True).count(),
        "total_teachers": User.objects.filter(role="teacher", approved=True).count(),
        "total_students": User.objects.filter(role="student", approved=True).count(),
        "total_quizzes": Quiz.objects.count(),
        "total_classes": Class.objects.count(),
        'total_subjects': Subject.objects.count(),
        "total_pending_users": User.objects.filter(approved=False).count(),
        "pending_users": User.objects.filter(approved=False),   
    }

    # # Leaderboard (Top 10 students overall)
    # leaderboard = (
    #     Answer.objects.values("attempt__student__id", "attempt__student__first_name", "attempt__student__last_name")
    #     .annotate(obtained_marks=Sum("score"))
    #     .order_by("-obtained_marks")[:10]
    # )
    # context["leaderboard"] = leaderboard

    # # Class performance (average score per class)
    # class_performance = (
    #     Answer.objects.values("attempt__quiz__class_assigned__name")
    #     .annotate(avg_score=Avg("score"), num_students=Count("attempt__student", distinct=True))
    #     .order_by("attempt__quiz__class_assigned__name")
    # )
    # context["class_performance"] = class_performance

    # Notifications for the admin user (last 10) - adapt Notification model fields
    notifications_qs = Notification.objects.filter(recipient=request.user).order_by("-created_at")[:10]
    notifications = [
        {"id": n.id, "message": n.message, "sender": (n.sender.username if n.sender else None), "created_at": n.created_at.isoformat(), "is_read": n.is_read}
        for n in notifications_qs
    ]

    context['notifications'] = notifications

    # Activity log entries (adapt field names of your ActivityLog model)
    # logs_qs = ActivityLog.objects.order_by("-timestamp")[:10]
    # logs = [
    #     {
    #         "action": l.action,
    #         "user": (l.user.username if getattr(l, "user", None) else getattr(l, "performed_by__username", None)),
    #         "timestamp": l.timestamp.isoformat()
    #     }
    #     for l in logs_qs
    # ]

    # context['logs'] = logs

    # context['messages'] = messages

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse(context)

    return render(request, "admins/superadmin_dashboard.html", context)


@login_required
@user_passes_test(is_admin)
def admin_dashboard(request):
    # counts
    from django.contrib.auth import get_user_model
    User = get_user_model()
    approved = User.objects.filter(is_active=True).count()
    pended = User.objects.filter(is_active=False).count()
    teachers = User.objects.filter(role='teacher').count()
    students = User.objects.filter(role='student').count()

    # leaderboard: top students by average total_score (only graded attempts)
    leaderboard = StudentQuizAttempt.objects.filter(is_submitted=True).values('student__id','student__username').annotate(avg_score=Avg('total_marks')).order_by('-avg_score')[:10]

    # recent action logs
    actions = ActionLog.objects.order_by('-timestamp')[:20]

    notifications = Notification.objects.filter(target_role__in=['all','admins']).order_by('-created_at')[:10]

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
@user_passes_test(is_teacher)
def teacher_dashboard(request):
    user = request.user
    # list classes teacher handles: depends on your data model. Here we take subjects created_by teacher
    teacher_subjects = request.user.quizzes_created.all()  # adapt: this is quizzes created_by teacher
    # For performance chart we aggregate attempts by quiz or subject
    # Example: average score per quiz created by teacher
    performance = StudentQuizAttempt.objects.filter(quiz__created_by=user).values('quiz__title').annotate(avg_score=Avg('total_score'), attempts=Count('id')).order_by('-avg_score')

    # subjectives pending for this teacher's quizzes
    pending_subjectives = Answer.objects.filter(question__quiz__created_by=user, is_pending=True).select_related('attempt','question').order_by('attempt__started_at')

    # notifications visible to teachers or all
    notifications = Notification.objects.filter(target_role__in=['all','teachers']).order_by('-created_at')[:10]

    context = {
        "performance": performance,
        "pending_subjectives": pending_subjectives,
        "notifications": notifications,
    }
    return render(request, "exams/teacher_dashboard.html", context)


  
@login_required
def student_dashboard(request):
    user = request.user
    # summary: total attempts, avg score, pending subjectives count
    attempts = StudentQuizAttempt.objects.filter(student=user)
    total_attempts = attempts.count()
    avg_score = attempts.aggregate(avg=Avg('total_marks'))['avg'] or 0
    pending_count = Answer.objects.filter(attempt__student=user, is_pending=True).count()

    # available quizzes for student's classes (assumes you have relationship)
    # adapt: if User has class field, e.g., profile_class
    # For this example, we assume user.profile_class exists (adjust accordingly).
    available = []
    # if user has class, fetch quizzes for that class's subjects
    try:
        user_class = user.profile_class  # user.profile_class must exist in your User model or related profile
        available = Quiz.objects.filter(subject__class_assigned=user_class, start_time__lte=timezone.now(), end_time__gte=timezone.now(),).order_by('start_time')
    except Exception:
        available = Quiz.objects.filter(start_time__lte=timezone.now(), end_time__gte=timezone.now()).order_by('start_time')[:10]

    # recent attempts with ability to review wrong answers
    recent_attempts = attempts.select_related('quiz').order_by('-started_at')[:5]

    # notifications for students or all
    notifications = Notification.objects.filter(target_role__in=['all','students']).order_by('-created_at')[:5]

    context = {
        "total_attempts": total_attempts,
        "avg_score": avg_score,
        "pending_count": pending_count,
        "available_quizzes": available,
        "recent_attempts": recent_attempts,
        "notifications": notifications,
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
            attempt.completed_at.strftime("%Y-%m-%d %H:%M") if attempt.completed_at else "In Progress",
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
@user_passes_test(is_admin)
@require_POST
def broadcast(request):
    title = request.POST.get('title')
    message = request.POST.get('message')
    target_role = request.POST.get('target_role', 'all')
    Notification.objects.create(title=title, message=message, sender=request.user, target_role=target_role)
    log_action(request.user, "Broadcast", details={"title": title, "target": target_role})
    messages.success(request, "Broadcast sent.")
    return redirect('admin_dashboard')


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


