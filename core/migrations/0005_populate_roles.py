from django.db import migrations

# قائمة بجميع الأدوار الوظيفية الـ 25 كما في دليل النظام
ROLES_LIST = [
    # الإدارة العليا
    "ملاك المكتب (OWNER)",
    "مدير النظام (ADMIN)",
    "مدير عام (GM)",
    # الإدارة التنفيذية
    "مدير (MGR)",
    "مدير المشاريع (PM)",
    "مسؤول المحاسبة (FIN)",
    "مسؤول الموارد البشرية (HR)",
    # الفنيون والمهندسون
    "مشرف مهندسين (ENGS)",
    "مهندس معماري (ARCH)",
    "مهندس إنشائي (STRUC)",
    "مهندس كهرباء (ELEC)",
    "مهندس ميكانيكا (MECH)",
    "مهندس أنظمة الأمن والسلامة (SAFE)",
    "رسام هندسي (DRAFT)",
    # الموظفون التشغيليون
    "مدخل بيانات (DATA)",
    "موظف استقبال (RECEP)",
    "موظف أرشفة (ARCH)",
    "معقب (FOLLOW)",
    "موظف إداري (CLERK)",
    "موظف عمل حر (FREEL)",
    # الأدوار المتخصصة
    "مسؤول التسويق (MKT)",
    "الدعم الفني (IT)",
    "موظف أمن (SEC)",
    "المدقق (AUD)",
    "زائر (GUEST)"
]

def populate_roles(apps, schema_editor):
    Role = apps.get_model('core', 'Role')
    for role_name in ROLES_LIST:
        Role.objects.get_or_create(name=role_name)

class Migration(migrations.Migration):

    dependencies = [
        ('core', '0004_merge_20250903_1127'), # تأكد أن هذا هو اسم آخر ملف ترحيل لديك
    ]

    operations = [
        migrations.RunPython(populate_roles),
    ]