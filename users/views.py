from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.contrib.auth import get_user_model
from .models import Notification
from django.urls import reverse
from .forms import TeacherAdminForm, EditUserRegistrationForm, EditTeacherAdminForm, UserRegistrationForm, loginForm

User = get_user_model()


def signup_view(request):
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save()
            user_id = user.id
            role = user.role
            if role in ['admin', 'teacher']:
                messages.success(request, f'{user.role.title()} account created successfully. Awaiting approval.')
                url = reverse('teacheradminprofile', kwargs={'user_id': user_id})
                return redirect(url)
            else:
                messages.success(request, "Registration successful. Please wait for approval.")
            return redirect("login")
    else:
        form = UserRegistrationForm()
    return render(request, 'users/signup.html', {'form': form})


def login_view(request):
    if request.method == 'POST':
        form = loginForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                messages.success(request, f"Welcome back, {user.username} 👋")
                return redirect('dashboard')
        messages.error(request, "Invalid username or password.")
    else:
        form = loginForm()
    return render(request, 'users/login.html', {'form': form})

def logout_view(request):
    logout(request)
    messages.info(request, "You have been logged out.")
    return redirect('login')



def teacheradminprofile(request, user_id):
    user = get_object_or_404(User, id=user_id)
    
    if request.method == 'POST':
        form = TeacherAdminForm(request.POST, request.FILES, instance=user)
        if form.is_valid():
            profile = form.save(commit=False)
            profile.user = user
            profile.save()
            messages.success(request, f'{user.role.title()} profile created successfully.')
            return redirect('dashboard')
    else:
        form = TeacherAdminForm()


    context = {'form': form, 'user': user}

    return render(request, "users/teacheradminprofile.html", context )


@login_required
def view_profile(request):
    """Read-only profile page for Student, Teacher, Admin."""
    return render(request, "users/view_profile.html", {"user": request.user})



@login_required
def edit_profile(request):
    """Allow Student, Teacher, or Admin to update their profile."""
    user = request.user

    # Select correct form by role
    if user.role == "student":
        form_class = EditUserRegistrationForm
    else:  # teacher or admin
        form_class = EditTeacherAdminForm

    if request.method == "POST":
        form = form_class(request.POST, request.FILES, instance=user)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated successfully!")

            # Redirect back to dashboard
            if user.role == "student":
                return redirect("student_dashboard")
            elif user.role == "teacher":
                return redirect("teacher_dashboard")
            else:
                return redirect("admin_dashboard")
    else:
        form = form_class(instance=user)

    return render(request, "users/edit_profile.html", {"form": form, "user": user})


@login_required
def send_broadcast(request):
    if request.method == "POST":
        message = request.POST.get("message")
        sender = request.user

        # Decide recipients
        if sender.role == "admin":
            recipients = User.objects.filter(role__in=["teacher", "student"])
        elif sender.role == "teacher":
            recipients = User.objects.filter(role="student")
        else:
            messages.error(request, "You cannot send broadcasts.")
            return redirect("dashboard")

        # Create notifications
        for recipient in recipients:
            Notification.objects.create(
                sender=sender,
                recipient=recipient,
                message=message,
                role=recipient.role,
            )

        messages.success(request, "Broadcast sent successfully ✅")
    return redirect("dashboard")


@login_required
def dashboard_redirect(request):
    if request.user.role == "superadmin":
        return redirect("superadmin_dashboard")
    elif request.user.role == "admin" or request.user.role == "superadmin":
        return redirect("admin_dashboard")
    elif request.user.role == "teacher":
        return redirect("teacher_dashboard")
    elif request.user.role == "student":
        return redirect("student_dashboard")
    else:
        messages.error(request, "Unknown role. Contact SuperAdmin.")
        return redirect("login")


@login_required
def mark_notification_read(request, pk):
    notif = get_object_or_404(Notification, pk=pk, recipient=request.user)
    notif.is_read = True
    notif.save()
    messages.success(request, "Notification marked as read ✅")
    return redirect("dashboard")