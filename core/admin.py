from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import Group

from core.models import User

# Register your models here.


@admin.register(User)
class CustomUser(UserAdmin):
    readonly_fields = ('last_login', 'date_joined')
    list_display = ('id', 'username', 'first_name', 'last_name', 'email')
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'email')}),
        (
            'Permissions',
            {
                'fields': (
                    'is_active',
                    'is_staff',
                ),
            },
        ),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )


admin.site.unregister(Group)
