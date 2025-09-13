# quizzes/forms.py
from django import forms
from .models import Quiz, Question, Choice, Subject

class QuizCreateForm(forms.ModelForm):
    class Meta:
        model = Quiz
        fields = ['title', 'subject', 'duration_minutes', 'is_published']

class QuestionForm(forms.ModelForm):
    class Meta:
        model = Question
        fields = ['text', 'question_type', 'marks']

class ChoiceForm(forms.ModelForm):
    class Meta:
        model = Choice
        fields = ['text', 'is_correct']
