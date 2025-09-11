from django.db import migrations

# القائمة الكاملة لجميع أنواع المستندات المطلوبة في النظام
DOCUMENT_TYPES = [
    {"code": "DOC001", "name_ar": "وثيقة الملكية"},
    {"code": "DOC002", "name_ar": "تعهد إزالة المخلفات ونواتج الحفر"},
    {"code": "DOC003", "name_ar": "تعهد المالك بتنفيذ الضوابط والشروط"},
    {"code": "DOC004", "name_ar": "تعهد المكتب الهندسي المصمم"},
    {"code": "DOC005", "name_ar": "صورة الهوية / السجل التجاري"},
    {"code": "DOC006", "name_ar": "وثيقة التأمين"},
    {"code": "DOC007", "name_ar": "بيانات وثائق المشروع"},
    {"code": "DOC008", "name_ar": "المخططات المعمارية"},
    {"code": "DOC009", "name_ar": "المخططات الإنشائية"},
    {"code": "DOC010", "name_ar": "مخططات الأمن والسلامة"},
    {"code": "DOC011", "name_ar": "المخططات الميكانيكية"},
    {"code": "DOC012", "name_ar": "مخططات الأعمال الكهربائية"},
    {"code": "DOC013", "name_ar": "خطاب طلب المكتب الهندسي"},
    {"code": "DOC014", "name_ar": "تعهد تغطية الخزانات أثناء الأعمال الإنشائية"},
    {"code": "DOC015", "name_ar": "تعهد تنفيذ التسوير المؤقت"},
    {"code": "DOC016", "name_ar": "صور من الطبيعة"},
    {"code": "DOC017", "name_ar": "صورة الواجهة"},
    {"code": "DOC018", "name_ar": "صورة الموقع العام"},
    {"code": "DOC019", "name_ar": "الرفع المساحي"},
    {"code": "DOC020", "name_ar": "خطاب المناسيب"},
    {"code": "DOC021", "name_ar": "تقرير مساحي إلكتروني"},
    {"code": "DOC022", "name_ar": "قرار لجنة مفوضة"},
]

def populate_document_types(apps, schema_editor):
    DocumentType = apps.get_model('core', 'DocumentType')
    for doc_type in DOCUMENT_TYPES:
        DocumentType.objects.get_or_create(code=doc_type['code'], defaults={'name_ar': doc_type['name_ar']})

class Migration(migrations.Migration):
    dependencies = [
        # تأكد من أن هذا هو اسم ملف الترحيل الذي ينشئ نماذج المستندات
        ('core', '0009_documenttype_transactiondocument'), 
    ]
    operations = [
        migrations.RunPython(populate_document_types),
    ]
