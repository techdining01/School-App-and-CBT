from django.contrib import messages
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from .models import Quiz, Question, Choice, StudentQuizAttempt, Answer
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse, HttpResponse
from django.db.models import Sum, Avg, Count
from django.utils import timezone
from .models import Quiz, StudentQuizAttempt, Answer, Notification, ActionLog, Question
from django.template.loader import render_to_string
from .utils import log_action
from django.conf import settings
import weasyprint  # ensure installed in your env if using WeasyPrint# quizzes/views.py


# continuing from above
from django.views.decorators.http import require_POST
from django.contrib import messages


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


@login_required
def dashboard(request):
    return render(request, 'quizzes/dashboard.html')



def is_teacher(user):
    return user.is_authenticated and user.role == 'teacher'

def is_admin(user):
    return user.is_authenticated and user.role in ('admin', 'superadmin')

@login_required
def student_dashboard(request):
    user = request.user
    # summary: total attempts, avg score, pending subjectives count
    attempts = StudentQuizAttempt.objects.filter(student=user)
    total_attempts = attempts.count()
    avg_score = attempts.aggregate(avg=Avg('total_score'))['avg'] or 0
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
    return render(request, "quizzes/student_dashboard.html", context)


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
    return render(request, "quizzes/teacher_dashboard.html", context)


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
    leaderboard = StudentQuizAttempt.objects.filter(graded=True).values('student__id','student__username').annotate(avg_score=Avg('total_score')).order_by('-avg_score')[:10]

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
    return render(request, "quizzes/admin_dashboard.html", context)


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
@login_required
def export_consolidated_pdf(request):
    # export all attempts for current student
    student = request.user
    attempts = StudentQuizAttempt.objects.filter(student=student).order_by('-started_at').select_related('quiz')
    html = render_to_string('quizzes/consolidated_results_pdf.html', {'student': student, 'attempts': attempts, 'request': request})
    # Use WeasyPrint to convert to PDF
    pdf_file = weasyprint.HTML(string=html, base_url=request.build_absolute_uri('/')).write_pdf()
    response = HttpResponse(pdf_file, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{student.username}_consolidated_results.pdf"'
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
