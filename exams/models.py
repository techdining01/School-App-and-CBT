from django.db import models
from django.conf import settings
from django.utils import timezone



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
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="created_quizzes")
    created_at = models.DateTimeField(default=timezone.now)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    duration_minutes = models.PositiveIntegerField(default=30)  # Timer
    is_published = models.BooleanField(default=False)
    allow_retake = models.BooleanField(default=False)  # ✅ new field you asked for

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
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    quiz = models.ForeignKey("Quiz", on_delete=models.CASCADE)
    started_at = models.DateTimeField(auto_now_add=True)
    end_time = models.DateTimeField(null=True, blank=True)  # quiz expiry
    completed = models.BooleanField(default=False)  # submitted or not
    retake_allowed = models.BooleanField(default=False)  # ✅ admin/superadmin override
    retake_count = models.PositiveIntegerField(default=0)  # how many times student retook
    score = models.FloatField(default=0.0)  # total score for the attempt

    def can_resume(self):
        """Allow resume if attempt still within time and not submitted."""
        return not self.completed and (self.end_time is None or timezone.now() < self.end_time)

    def can_retake(self):
        """Allow retake if admin has granted it, or quiz allows retakes globally."""
        return self.retake_allowed 

    def __str__(self):
        return f"{self.student} - {self.quiz} (Retakes: {self.retake_count})"



class Answer(models.Model):
    attempt = models.ForeignKey(StudentQuizAttempt, on_delete=models.CASCADE, related_name='answers')
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    selected_choice = models.ForeignKey(Choice, on_delete=models.SET_NULL, null=True, blank=True)
    text_answer = models.TextField(blank=True, null=True)
    obtained_marks = models.FloatField(default=0.0)
    graded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='graded_answers')
    graded_at = models.DateTimeField(null=True, blank=True)
    feedback = models.TextField(blank=True, null=True)
    is_pending = models.BooleanField(default=False)  # True for subjective until graded

    @classmethod
    def objective_score(cls, attempt):
        """Return total objective marks for a given attempt."""
        return cls.objects.filter(
            attempt=attempt,
            question__question_type="objective"
        ).aggregate(total=models.Sum("obtained_marks"))["total"] or 0

    @classmethod
    def subjective_score(cls, attempt):
        """Return total subjective marks for a given attempt (graded only)."""
        return cls.objects.filter(
            attempt=attempt,
            question__question_type="subjective",
            is_pending=False
        ).aggregate(total=models.Sum("obtained_marks"))["total"] or 0

    @classmethod
    def total_score(cls, attempt):
        """Return grand total (objective + graded subjective)."""
        return cls.objective_score(attempt) + cls.subjective_score(attempt)


    def __str__(self):
        return f"Answer by {self.attempt.student} for Q{self.question.id}"



# class ActionLog(models.Model):
#     """Log significant actions performed by admins/teachers for audit"""
#     user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
#     action = models.CharField(max_length=255)
#     model_name = models.CharField(max_length=100, blank=True, null=True)
#     object_id = models.CharField(max_length=255, blank=True, null=True)
#     timestamp = models.DateTimeField(auto_now_add=True)
#     details = models.JSONField(blank=True, null=True)  # optional

#     def __str__(self):
#         return f"{self.user} {self.action} @ {self.timestamp}"
    

class ActionLog(models.Model):
    ACTION_TYPES = (
        ('download', 'Download'),
        ('retake_request', 'Retake Request'),
        ('grade', 'Grade'),
        ('review', 'Review'),
        ('notification', 'Notification'),
        ('pended', 'Pended'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    )
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="action_logs")
    action_type = models.CharField(max_length=50, choices=ACTION_TYPES)
    description = models.TextField()
    created_at = models.DateTimeField(default=timezone.now)
    model_name = models.CharField(max_length=100, blank=True, null=True)
    object_id = models.CharField(max_length=255, blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    details = models.JSONField(blank=True, null=True)  # optional
    
    def __str__(self):
        return f"{self.user} {self.action} @ {self.timestamp}"


class RetakeRequest(models.Model):
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, limit_choices_to={"role": "student"})
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE)
    reason = models.TextField(blank=True, null=True)
    status = models.CharField(
        max_length=20,
        choices=(("pending", "Pending"), ("approved", "Approved"), ("denied", "Denied")),
        default="pending"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(blank=True, null=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="retake_reviews")

    def __str__(self):
        return f"{self.student.username} → {self.quiz.title} ({self.status})"




# class Answer(models.Model):
#     """
#     Represents a student's answer to a quiz question.
    
#     - For **Objective questions**:
#         * `selected_choice` stores the chosen option.
#         * `obtained_marks` is set immediately (auto-graded).
    
#     - For **Subjective questions**:
#         * `text_answer` stores the free-text response.
#         * `obtained_marks` remains 0 until graded.
#         * `is_pending=True` until a teacher/admin grades it.
    
#     Common fields:
#         * `feedback` can be used to explain grading.
#         * `graded_by` + `graded_at` track manual grading history.
#     """

#     attempt = models.ForeignKey("StudentQuizAttempt", on_delete=models.CASCADE, related_name='answers')
#     question = models.ForeignKey("Question", on_delete=models.CASCADE)

#     # Objective
#     selected_choice = models.ForeignKey("Choice", on_delete=models.SET_NULL, null=True, blank=True)

#     # Subjective
#     text_answer = models.TextField(blank=True, null=True)

#     # Common
#     obtained_marks = models.FloatField(default=0.0)
#     graded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='graded_answers')
#     graded_at = models.DateTimeField(null=True, blank=True)
#     feedback = models.TextField(blank=True, null=True)
#     is_pending = models.BooleanField(default=False)  # True for subjective until graded

#     def __str__(self):
#         return f"Answer by {self.attempt.student} for Q{self.question.id}"

#     # -----------------------------
#     # 🔹 Helper methods
#     # -----------------------------

#     def is_objective(self):
#         return self.question.question_type == "objective"

#     def is_subjective(self):
#         return self.question.question_type == "subjective"

#     def is_correct(self):
#         """For objective questions only."""
#         return self.is_objective() and self.selected_choice and self.selected_choice.is_correct

#     @classmethod
#     def objective_score(cls, attempt):
#         """Return total objective marks for a given attempt."""
#         return cls.objects.filter(
#             attempt=attempt,
#             question__question_type="objective"
#         ).aggregate(total=models.Sum("obtained_marks"))["total"] or 0

#     @classmethod
#     def subjective_score(cls, attempt):
#         """Return total subjective marks for a given attempt (graded only)."""
#         return cls.objects.filter(
#             attempt=attempt,
#             question__question_type="subjective",
#             is_pending=False
#         ).aggregate(total=models.Sum("obtained_marks"))["total"] or 0

#     @classmethod
#     def total_score(cls, attempt):
#         """Return grand total (objective + graded subjective)."""
#         return cls.objective_score(attempt) + cls.subjective_score(attempt)
