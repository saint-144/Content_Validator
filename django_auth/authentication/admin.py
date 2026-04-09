from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User

class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'name', 'position', 'role', 'is_staff')
    fieldsets = UserAdmin.fieldsets + (
        (None, {'fields': ('name', 'position', 'role')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        (None, {'fields': ('name', 'position', 'role')}),
    )

admin.site.register(User, CustomUserAdmin)
