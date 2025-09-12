# exams/models.py
from django.conf import settings
from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model

User = get_user_model()


class SchoolClass(models.Model):
    name = models.CharField(max_length=100)  # e.g. JSS1
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name


class Subject(models.Model):
    name = models.CharField(max_length=200)
    school_class = models.ForeignKey(SchoolClass, on_delete=models.CASCADE, related_name='subjects')

    def __str__(self):
        return f"{self.name} - {self.school_class.name}"


class Quiz(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='quizzes')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_quizzes')
    duration_minutes = models.PositiveIntegerField(help_text="Duration in minutes")
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    published = models.BooleanField(default=False)
    shuffle_questions = models.BooleanField(default=False)

    def __str__(self):
        return self.title


QUESTION_TYPE_CHOICES = [
    ('objective', 'Objective'),
    ('subjective', 'Subjective'),
]


class Question(models.Model):
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='questions')
    text = models.TextField()
    type = models.CharField(max_length=20, choices=QUESTION_TYPE_CHOICES)
    marks = models.FloatField(default=1.0)
    order = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"Q{self.id} ({self.type})"


class Choice(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='choices')
    text = models.CharField(max_length=1000)
    is_correct = models.BooleanField(default=False)  # only used for objectives

    def __str__(self):
        return self.text[:80]


class StudentQuizAttempt(models.Model):
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='quiz_attempts')
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='attempts')
    started_at = models.DateTimeField(auto_now_add=True)
    submitted_at = models.DateTimeField(blank=True, null=True)
    auto_submitted = models.BooleanField(default=False)
    total_score = models.FloatField(default=0.0)
    graded = models.BooleanField(default=False)  # becomes True when all subjectives graded
    approved = models.BooleanField(default=False) 
    
    class Meta:
        ordering = ['-started_at']

    def __str__(self):
        return f"{self.student.username} - {self.quiz.title}"


class Answer(models.Model):
    attempt = models.ForeignKey(StudentQuizAttempt, on_delete=models.CASCADE, related_name='answers')
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    selected_choice = models.ForeignKey(Choice, on_delete=models.SET_NULL, null=True, blank=True)
    text_answer = models.TextField(blank=True, null=True)
    obtained_marks = models.FloatField(default=0.0)
    graded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='graded_answers')
    graded_at = models.DateTimeField(null=True, blank=True)
    feedback = models.TextField(blank=True, null=True)
    is_pending = models.BooleanField(default=False)  # True for subjective until graded

    def __str__(self):
        return f"Answer by {self.attempt.student} for Q{self.question.id}"


# quizzes/models.py (append or create)
from django.db import models
from django.conf import settings
from django.utils import timezone

User = settings.AUTH_USER_MODEL

class Notification(models.Model):
    """Broadcast messages sent by admin/teacher to users (target: all/teachers/students/specific)"""
    title = models.CharField(max_length=255)
    message = models.TextField()
    sender = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='sent_notifications')
    created_at = models.DateTimeField(auto_now_add=True)
    target_role = models.CharField(max_length=20, choices=[
        ('all','All'),
        ('teachers','Teachers'),
        ('students','Students'),
        ('admins','Admins'),
    ], default='all')

    def __str__(self):
        return f"{self.title} → {self.target_role}"

class ActionLog(models.Model):
    """Log significant actions performed by admins/teachers for audit"""
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=255)
    model_name = models.CharField(max_length=100, blank=True, null=True)
    object_id = models.CharField(max_length=255, blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    details = models.JSONField(blank=True, null=True)  # optional

    def __str__(self):
        return f"{self.user} {self.action} @ {self.timestamp}"

# Leaderboard helper: you might compute on the fly, but store computed ranking if you want caching.
# No separate model needed — we compute ranking from StudentQuizAttempt totals.
