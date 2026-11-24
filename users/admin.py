from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import UserCreationForm
from .models import User


class DMTSUserCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email", "first_name", "last_name", "role", "phone_number")


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    add_form = DMTSUserCreationForm
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("username", "email", "first_name", "last_name", "role", "phone_number", "password1", "password2")}),
    )
    fieldsets = BaseUserAdmin.fieldsets + (("DMTS profile", {"fields": ("role", "phone_number")}),)
    list_display = ("username", "first_name", "last_name", "email", "role", "is_active", "is_staff")
    list_filter = ("role", "is_active", "is_staff")
