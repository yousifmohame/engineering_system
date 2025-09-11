# engineering_office/back-end/core/migrations/XXXX_populate_initial_data.py
# (استبدل XXXX بالرقم الصحيح)

from django.db import migrations

def populate_initial_data(apps, schema_editor):
    # Get models from the app registry
    TransactionMainCategory = apps.get_model('core', 'TransactionMainCategory')
    TransactionSubCategory = apps.get_model('core', 'TransactionSubCategory')
    CompetentAuthority = apps.get_model('core', 'CompetentAuthority')

    # --- 1. Populate TransactionMainCategory ---
    main_categories_data = [
        {'name': 'مشروع', 'code': 'PROJ'},
        {'name': 'طلب', 'code': 'REQ'},
        {'name': 'استشارة', 'code': 'CONC'},
    ]
    main_categories = {}
    for data in main_categories_data:
        obj, created = TransactionMainCategory.objects.get_or_create(code=data['code'], defaults={'name': data['name']})
        main_categories[data['code']] = obj

    # --- 2. Populate TransactionSubCategory ---
    sub_categories_data = [
        # Sub-categories for "مشروع"
        {'main': 'PROJ', 'name': 'رخصة بناء', 'code': 'BUILD-LIC'},
        {'main': 'PROJ', 'name': 'رخصة تصحيح وضع مبنى قائم', 'code': 'CORR-LIC'},
        {'main': 'PROJ', 'name': 'رخصة هدم', 'code': 'DEMO-LIC'},
        {'main': 'PROJ', 'name': 'رخصة تسوير', 'code': 'FENCE-LIC'},
        # Sub-categories for "طلب"
        {'main': 'REQ', 'name': 'طلب إشراف', 'code': 'SUPER-REQ'},
        {'main': 'REQ', 'name': 'طلب استخراج شهادة إشغال', 'code': 'OCCUP-CERT'},
        {'main': 'REQ', 'name': 'طلب متابعة معاملة لدى الجهات', 'code': 'FOLLOW-REQ'},
        {'main': 'REQ', 'name': 'طلب تحديث صك', 'code': 'DEED-UPDATE'},
        {'main': 'REQ', 'name': 'طلب تعديل بيانات صك', 'code': 'DEED-MODIFY'},
        {'main': 'REQ', 'name': 'رفع إيقاف عن قطعة أرض', 'code': 'LIFT-SUSP'},
        {'main': 'REQ', 'name': 'أخرى', 'code': 'OTHER-REQ'},
    ]
    for data in sub_categories_data:
        TransactionSubCategory.objects.get_or_create(
            code=data['code'],
            defaults={
                'name': data['name'],
                'main_category': main_categories[data['main']]
            }
        )
    
    # --- 3. Populate CompetentAuthority ---
    authorities_data = [
        {'name': 'الهيئة الملكية لتطوير مدينة الرياض', 'code': 'RCRC'},
        {'name': 'هيئة تطوير الدرعية', 'code': 'DDA'},
        {'name': 'وزارة الإسكان والبلديات', 'code': 'MHUC'},
        {'name': 'أمانة منطقة الرياض', 'code': 'RMA'},
        {'name': 'قطاع وسط الرياض', 'code': 'CENTER'},
        {'name': 'قطاع جنوب الرياض', 'code': 'SOUTH'},
        {'name': 'قطاع شمال الرياض', 'code': 'NORTH'},
        {'name': 'قطاع شرق الرياض', 'code': 'EAST'},
        {'name': 'قطاع غرب الرياض', 'code': 'WEST'},
    ]
    for data in authorities_data:
        CompetentAuthority.objects.get_or_create(code=data['code'], defaults={'name': data['name']})


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_initial'), # This should be the name of your first migration file
    ]

    operations = [
        migrations.RunPython(populate_initial_data),
    ]