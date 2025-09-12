from django.contrib import admin
from .models import SchoolClass, Subject, Quiz, Question, Choice, StudentQuizAttempt, Answer


class ChoiceInline(admin.TabularInline):
    model = Choice
    extra = 2


class QuestionAdmin(admin.ModelAdmin):
    inlines = [ChoiceInline]
    list_display = ('text', 'quiz', 'type', 'marks')


class QuizAdmin(admin.ModelAdmin):
    list_display = ('title', 'subject', 'start_time', 'end_time', 'published')
    list_filter = ('subject', 'published')


class AnswerAdmin(admin.ModelAdmin):
    list_display = ('attempt', 'question', 'obtained_marks', 'is_pending')


admin.site.register(SchoolClass)
admin.site.register(Subject)
admin.site.register(Quiz, QuizAdmin)
admin.site.register(Question, QuestionAdmin)
admin.site.register(Choice)
admin.site.register(StudentQuizAttempt)
admin.site.register(Answer, AnswerAdmin)
