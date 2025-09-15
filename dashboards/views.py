from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from quizzes.models import StudentQuizAttempt

def grant_retake(request, attempt_id):
    attempt = get_object_or_404(StudentQuizAttempt, id=attempt_id)
    attempt.retake_allowed = True
    attempt.save()
    messages.success(request, f"{attempt.student} can now retake {attempt.quiz}.")
    return redirect("admin_dashboard")
