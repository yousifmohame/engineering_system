# engineering_office/back-end/create_super_admin.py

import os
import django

# --- Setup Django Environment ---
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'engineering_office.settings')
django.setup()
# --------------------------------

from core.models import Role, Permission, CustomUser

def create_super_admin():
    """
    This script creates a 'Super Admin' role, assigns all permissions to it,
    and then creates a new user with this role.
    """
    # 1. Create a new Role or get it if it already exists
    role_name = "Super Admin"
    super_admin_role, created = Role.objects.get_or_create(name=role_name)

    if created:
        print(f"✅ تم إنشاء الدور بنجاح: '{role_name}'")
    else:
        print(f"🔹 الدور '{role_name}' موجود بالفعل.")

    # 2. Get all permissions
    all_permissions = Permission.objects.all()
    if not all_permissions.exists():
        print("⚠️ لم يتم العثور على أي صلاحيات. يرجى التأكد من تشغيل ملف ترحيل الصلاحيات أولاً.")
        return
        
    print(f"🔍 تم العثور على عدد {all_permissions.count()} صلاحية.")

    # 3. Add all permissions to the role
    super_admin_role.permissions.set(all_permissions)
    print(f"✅ تم إسناد جميع الصلاحيات لدور '{role_name}'.")

    # 4. Create a new Super User
    # !!! الرجاء تغيير هذه البيانات قبل تشغيل السكربت !!!
    username = 'admin'
    email = 'admin@example.com'
    password = 'admin123' # استخدم كلمة مرور قوية
    full_name_ar = 'مدير النظام'

    if not CustomUser.objects.filter(username=username).exists():
        super_user = CustomUser.objects.create_user(
            username=username,
            email=email,
            password=password,
            full_name_ar=full_name_ar,
            is_staff=True,
            is_superuser=True # هذا يمنحه صلاحيات كاملة على لوحة تحكم Django
        )
        
        # 5. Assign the role to the user
        super_user.role = super_admin_role
        super_user.save()
        
        print("\n🎉 نجحت العملية! 🎉")
        print("===================================")
        print(f"تم إنشاء المستخدم الخارق بنجاح:")
        print(f"  - اسم المستخدم: {username}")
        print(f"  - كلمة المرور: {password}")
        print("===================================")

    else:
        # If user exists, just ensure they have the Super Admin role
        user = CustomUser.objects.get(username=username)
        user.role = super_admin_role
        user.is_superuser = True
        user.is_staff = True
        user.save()
        print(f"\n🔹 المستخدم '{username}' موجود بالفعل. تم التأكد من أنه يمتلك دور وصلاحيات مدير النظام.")


if __name__ == '__main__':
    create_super_admin()