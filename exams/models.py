from django.db import models
from django.conf import settings
from django.utils import timezone

User = settings.AUTH_USER_MODEL



class Class(models.Model):
    name = models.CharField(max_length=50, unique=True)  # e.g. JSS1, JSS2

    def __str__(self):
        return self.name


class Subject(models.Model):
    name = models.CharField(max_length=100)
    school_class = models.ForeignKey(Class, on_delete=models.CASCADE, related_name="subjects")

    def __str__(self):
        return f"{self.name} ({self.school_class})"


class Quiz(models.Model):
    title = models.CharField(max_length=200)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name="quizzes")
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name="created_quizzes")
    created_at = models.DateTimeField(default=timezone.now)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    duration_minutes = models.PositiveIntegerField(default=30)  # Timer
    is_published = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.title} - {self.subject}"


class Question(models.Model):
    QUESTION_TYPES = (
        ('objective', 'Objective'),
        ('subjective', 'Subjective'),
    )

    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name="questions")
    text = models.TextField()
    question_type = models.CharField(max_length=20, choices=QUESTION_TYPES)
    marks = models.PositiveIntegerField(default=1)

    def __str__(self):
        return f"{self.text[:50]} ({self.get_question_type_display()})"


class Choice(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="choices")
    text = models.CharField(max_length=255)
    is_correct = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.text} ({'Correct' if self.is_correct else 'Wrong'})"


class StudentQuizAttempt(models.Model):
    student = models.ForeignKey(User, on_delete=models.CASCADE)
    quiz = models.ForeignKey("Quiz", on_delete=models.CASCADE)
    started_at = models.DateTimeField(auto_now_add=True)
    end_time = models.DateTimeField(null=True, blank=True)  # quiz expiry
    completed = models.BooleanField(default=False)  # submitted or not
    retake_allowed = models.BooleanField(default=False)  # admin override
    retake_count = models.PositiveIntegerField(default=0)  # how many times student retook
    score = models.FloatField(default=0.0)  # total score for the attempt

    def can_resume(self):
        """Allow resume if attempt still within time and not submitted."""
        return not self.completed and (self.end_time is None or timezone.now() < self.end_time)

    def can_retake(self):
        """Allow retake if admin has granted it."""
        return self.retake_allowed

    def __str__(self):
        return f"{self.student} - {self.quiz} (Retakes: {self.retake_count})"


class ObjectiveAnswer(models.Model):
    attempt = models.ForeignKey(StudentQuizAttempt, on_delete=models.CASCADE, related_name="objective_answers")
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    choice = models.ForeignKey(Choice, on_delete=models.SET_NULL, null=True, blank=True)

    def is_correct(self):
        return self.choice and self.choice.is_correct


class SubjectiveAnswer(models.Model):
    attempt = models.ForeignKey(StudentQuizAttempt, on_delete=models.CASCADE, related_name="subjective_answers")
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    answer_text = models.TextField()
    marks_awarded = models.FloatField(null=True, blank=True)  # null until teacher marks
    graded = models.BooleanField(default=False)
    graded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="graded_subjectives")
    graded_at = models.DateTimeField(null=True, blank=True)

    def is_graded(self):
        return self.marks_awarded is not None


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

