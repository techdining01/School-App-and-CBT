from django.contrib import admin
from .models import Class, Subject, Quiz, Question, Choice, StudentQuizAttempt, Answer


class ChoiceInline(admin.TabularInline):
    model = Choice
    extra = 2


class QuestionAdmin(admin.ModelAdmin):
    inlines = [ChoiceInline]
    list_display = ('text', 'quiz', 'question_type', 'marks')


class QuizAdmin(admin.ModelAdmin):
    list_display = ('title', 'subject', 'is_published')
    list_filter = ('subject', 'is_published')


class AnswerAdmin(admin.ModelAdmin):
    list_display = ('attempt', 'question', 'obtained_marks', 'is_pending')


admin.site.register(Class)
admin.site.register(Subject)
admin.site.register(Quiz, QuizAdmin)
admin.site.register(Question, QuestionAdmin)
admin.site.register(Choice)
admin.site.register(StudentQuizAttempt)
admin.site.register(Answer, AnswerAdmin)
