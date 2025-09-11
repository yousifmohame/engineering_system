# core/admin.py

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, Role, Permission

# تخصيص عرض نموذج المستخدم في لوحة التحكم
class CustomUserAdmin(UserAdmin):
    # إضافة الحقول المخصصة إلى شاشة إنشاء وتعديل المستخدم
    fieldsets = UserAdmin.fieldsets + (
        ('Custom Fields', {'fields': ('user_code', 'employee_type', 'full_name_ar', 'role')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Custom Fields', {'fields': ('user_code', 'employee_type', 'full_name_ar', 'role')}),
    )

# تسجيل النماذج
admin.site.register(CustomUser, CustomUserAdmin)
admin.site.register(Role)
admin.site.register(Permission)