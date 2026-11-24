from django.contrib.auth import views as auth_views
from django.urls import reverse_lazy


class LoginView(auth_views.LoginView):
    template_name = "users/login.html"
    redirect_authenticated_user = True

    def get_success_url(self):
        if self.request.user.is_driver:
            return reverse_lazy("deliveries:driver_dashboard")
        return reverse_lazy("deliveries:dashboard")


class LogoutView(auth_views.LogoutView):
    next_page = reverse_lazy("users:login")


from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, redirect
from django import forms
from .forms import ProfileForm

@login_required
def profile(request):
    if request.method == "POST":
        form = ProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Your profile has been updated.")
            return redirect("users:profile")
    else:
        form = ProfileForm(instance=request.user)
    return render(request, "users/profile.html", {"form": form})
