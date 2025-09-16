# engineering_office/back-end/core/models.py

from django.utils import timezone
import os
import qrcode
import base64
from io import BytesIO
from django.db import models
from django.contrib.auth.models import AbstractUser
from decimal import Decimal
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

# ===============================================
# نموذج الصلاحيات (Permissions)
# ===============================================
# في نموذج Permission، أضف صلاحية جديدة
class Permission(models.Model):
    code = models.CharField(max_length=20, unique=True, primary_key=True)  # زدنا الطول
    name_en = models.CharField(max_length=100)
    name_ar = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.code} - {self.name_ar}"

# أو يمكنك إضافتها عبر admin interface

# ===============================================
# نموذج الأدوار (فئات المستخدمين)
# ===============================================
class Role(models.Model):
    name = models.CharField(max_length=100, unique=True)
    permissions = models.ManyToManyField(Permission, blank=True)

    def __str__(self):
        return self.name

class Department(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name="اسم القسم")

    def __str__(self):
        return self.name


class CustomUser(AbstractUser):
    user_code = models.CharField(max_length=6, unique=True, null=True, blank=True)
    
    class EmployeeType(models.TextChoices):
        LOCAL = 'local', 'محلي'
        REMOTE = 'remote', 'عن بعد'

    employee_type = models.CharField(
        max_length=10,
        choices=EmployeeType.choices,
        default=EmployeeType.LOCAL
    )
    full_name_ar = models.CharField(max_length=255)
    nationality = models.CharField(max_length=100, null=True, blank=True)
    phone_number_1 = models.CharField(max_length=20)
    phone_number_2 = models.CharField(max_length=20, null=True, blank=True)
    whatsapp_number = models.CharField(max_length=20, null=True, blank=True)
    role = models.ForeignKey(Role, on_delete=models.SET_NULL, null=True, blank=True)
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True, related_name='employees', verbose_name="القسم")

    def __str__(self):
        return self.username

# ===============================================
# تم وضع نموذج العميل قبل نموذج المعاملة لحل الخطأ
# ===============================================
class Client(models.Model):
    class ClientType(models.TextChoices):
        ENG_OFFICE = 'ENG_OFFICE', 'مكتب هندسي'
        CLIENT = 'CLIENT', 'عميل'

    client_type = models.CharField(max_length=20, choices=ClientType.choices, default=ClientType.CLIENT)
    client_code = models.CharField(max_length=20, unique=True, help_text="مثل: EO-000001 أو CL-000001")
    name_ar = models.CharField(max_length=255)
    phone_number = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True, null=True)
    commercial_register = models.CharField(max_length=100, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.client_code} - {self.name_ar}"

# ===============================================
# النماذج الجديدة التي اقترحتها للتطوير
# ===============================================
class TransactionMainCategory(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20, unique=True)

    def __str__(self):
        return self.name

class TransactionSubCategory(models.Model):
    main_category = models.ForeignKey(TransactionMainCategory, on_delete=models.CASCADE, related_name='sub_categories')
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20, unique=True)

    def __str__(self):
        return f"{self.main_category.name} - {self.name}"

class CompetentAuthority(models.Model):
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=20, unique=True)

    def __str__(self):
        return self.name



class Transaction(models.Model):
    class StatusChoices(models.TextChoices):
        NEW = 'new', 'جديد'
        UNDER_REVIEW = 'under_review', 'قيد المراجعة'
        DOCS_REQUIRED = 'docs_required', 'مطلوب مستندات إضافية'
        PROCESSING = 'processing', 'تحت المعالجة'
        APPROVED = 'approved', 'معتمد'
        COMPLETED = 'completed', 'منتهي'
        CANCELLED = 'cancelled', 'ملغى'
        SUSPENDED = 'suspended', 'موقوف مؤقتاً'

    class DisciplineChoices(models.TextChoices):
        ARCH = 'ARCH', 'معماري'
        STRU = 'STRU', 'إنشائي'
        ELEC = 'ELEC', 'كهربائي'
        MECH = 'MECH', 'ميكانيكي'
        CIVL = 'CIVL', 'مدني'
        ENV = 'ENV', 'بيئي'

    short_code = models.CharField(max_length=30, unique=True, editable=False, blank=True, verbose_name="رمز المعاملة")
    long_code = models.CharField(max_length=255, unique=True, blank=True, null=True)
    client = models.ForeignKey(Client, on_delete=models.PROTECT,null=True, blank=True, related_name='transactions')
    status = models.CharField(max_length=20, choices=StatusChoices.choices, default=StatusChoices.NEW)
    assigned_to = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='transactions')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    title = models.CharField(max_length=255, verbose_name="عنوان المعاملة")
    description = models.TextField(blank=True, null=True, verbose_name="وصف المعاملة")
    engineering_discipline = models.CharField(
        max_length=10,
        choices=DisciplineChoices.choices,
        default=DisciplineChoices.ARCH,
        verbose_name="التخصص الهندسي"
    )
    location = models.CharField(max_length=255, blank=True, null=True, verbose_name="الموقع الجغرافي")
    expected_start_date = models.DateField(null=True, blank=True, verbose_name="تاريخ البدء المتوقع")
    expected_duration = models.PositiveIntegerField(null=True, blank=True, help_text="المدة بالأيام", verbose_name="المدة الزمنية المتوقعة")

    main_category = models.ForeignKey('TransactionMainCategory', on_delete=models.SET_NULL, null=True, blank=True)
    sub_category = models.ForeignKey('TransactionSubCategory', on_delete=models.SET_NULL, null=True, blank=True)
    competent_authority = models.ForeignKey('CompetentAuthority', on_delete=models.SET_NULL, null=True, blank=True)

    # === START: التصحيح هنا - إضافة null=True للحقول النصية ===
    doc_type = models.CharField(max_length=100, blank=True, null=True)
    doc_classification = models.CharField(max_length=100, blank=True, null=True)
    doc_number = models.CharField(max_length=50, blank=True, null=True)
    doc_date = models.DateField(null=True, blank=True)
    area_sq_meters = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    piece_number = models.CharField(max_length=50, blank=True, null=True)
    plan_number = models.CharField(max_length=50, blank=True, null=True)
    neighborhood = models.CharField(max_length=100, blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    # === END: التصحيح ===

    def __str__(self):
        display_name = self.short_code if self.short_code else self.title
        return f"{display_name}"

    def save(self, *args, **kwargs):
        if not self.pk:
            now = timezone.now()
            year = now.year
            month = now.month
            last_transaction = Transaction.objects.filter(
                created_at__year=year,
                created_at__month=month
            ).order_by('-short_code').first()
            sequence = 1
            if last_transaction and last_transaction.short_code:
                try:
                    last_sequence_str = last_transaction.short_code.split('-')[-1]
                    sequence = int(last_sequence_str) + 1
                except (IndexError, ValueError):
                    pass
            self.short_code = (
                f"PROJ-{self.engineering_discipline}"
                f"-{year}-{str(month).zfill(2)}"
                f"-{str(sequence).zfill(4)}"
            )
        super().save(*args, **kwargs)


def transaction_directory_path(instance, filename):
    transaction_id = instance.transaction.id
    return f'transaction_{transaction_id}/{filename}'

class Document(models.Model):
    transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE, related_name='documents')
    
    transaction_document = models.ForeignKey('TransactionDocument', on_delete=models.CASCADE, related_name='files', null=True, blank=True)
    
    file = models.FileField(upload_to=transaction_directory_path)
    description = models.CharField(max_length=255, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True)
    # === START: أضف الحقلين التاليين ===
    stamped_file = models.FileField(upload_to='documents/stamped/', null=True, blank=True, verbose_name="الملف المختوم")
    is_stamped = models.BooleanField(default=False, verbose_name="هل تم الختم؟")
    # === END: الإضافة هنا ===


    def __str__(self):
        return os.path.basename(self.file.name)

class Task(models.Model):
    class TaskTypeChoices(models.TextChoices):
        PLAN_REVIEW = 'PLAN_REVIEW', 'تدقيق مخطط'
        DOC_REVIEW = 'DOC_REVIEW', 'مراجعة مستندات'
        TECH_REPORT = 'TECH_REPORT', 'إعداد تقرير فني'
        EXT_FOLLOW = 'EXT_FOLLOW', 'متابعة معاملة خارجية'
        ACC_AUDIT = 'ACC_AUDIT', 'تدقيق حسابات'
        QUOTE_PREP = 'QUOTE_PREP', 'إعداد عرض سعر'
        DATA_UPDATE = 'DATA_UPDATE', 'تحديث بيانات'
        GENERAL_TASK = 'GENERAL_TASK', 'مهمة عامة'

    class StatusChoices(models.TextChoices):
        NEW = 'new', 'جديد'
        IN_PROGRESS = 'in_progress', 'قيد التنفيذ'
        COMPLETED_PENDING = 'completed_pending', 'مكتمل - بانتظار المراجعة'
        APPROVED = 'approved', 'معتمد'
        REJECTED = 'rejected', 'مرفوض - يحتاج تعديل'
        CANCELLED = 'cancelled', 'ملغي'

    task_type = models.CharField(
        max_length=20, 
        choices=TaskTypeChoices.choices, 
        default=TaskTypeChoices.GENERAL_TASK,
        verbose_name="نوع المهمة"
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=StatusChoices.choices, default=StatusChoices.NEW)
    assigned_to = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='tasks')
    created_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, related_name='created_tasks')
    transaction = models.ForeignKey(Transaction, on_delete=models.SET_NULL, null=True, blank=True, related_name='tasks')
    created_at = models.DateTimeField(auto_now_add=True)
    due_date = models.DateField(null=True, blank=True)

    def clean(self):
        super().clean()
        if self.pk: # التحقق فقط عند التحديث وليس الإنشاء
            old_instance = Task.objects.get(pk=self.pk)
            old_status = old_instance.status
            new_status = self.status

            # تعريف مسارات العمل المسموح بها
            allowed_transitions = {
                'new': ['in_progress', 'cancelled'],
                'in_progress': ['completed_pending', 'cancelled'],
                'completed_pending': ['approved', 'rejected'],
                'rejected': ['in_progress', 'cancelled'],
                'approved': [], # حالة نهائية
                'cancelled': [], # حالة نهائية
            }
            
            if new_status != old_status and new_status not in allowed_transitions.get(old_status, []):
                raise models.ValidationError(f"لا يمكن تغيير حالة المهمة من '{old_status}' إلى '{new_status}'.")

    def save(self, *args, **kwargs):
        self.full_clean() # استدعاء دالة التحقق قبل الحفظ
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title

class Invoice(models.Model):
    class StatusChoices(models.TextChoices):
        DRAFT = 'draft', 'مسودة'
        SENT = 'sent', 'مرسلة'
        PAID = 'paid', 'مدفوعة'
        CANCELLED = 'cancelled', 'ملغاة'

    invoice_number = models.CharField(max_length=50, unique=True)
    client = models.ForeignKey(Client, on_delete=models.PROTECT, related_name='invoices')
    transaction = models.ForeignKey(Transaction, on_delete=models.SET_NULL, null=True, blank=True, related_name='invoices')
    status = models.CharField(max_length=20, choices=StatusChoices.choices, default=StatusChoices.DRAFT)
    issue_date = models.DateField()
    due_date = models.DateField()
    notes = models.TextField(blank=True)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    
    # --- هذا هو الحقل الجديد لتخزين صورة QR Code ---
    qr_code_image = models.TextField(blank=True, null=True, verbose_name="QR Code Image (Base64)")

    def __str__(self):
        return f"Invoice {self.invoice_number} for {self.client.name_ar}"

    def _generate_qr_code_data(self):
        """
        تنسيق بيانات الفاتورة لتشفيرها في QR Code (متوافق مع متطلبات الزكاة والضريبة في السعودية - TLV format).
        """
        seller_name = "المكتب الهندسي للاستشارات".encode('utf-8')
        vat_number = "300000000000003".encode('utf-8') # رقم ضريبي تجريبي
        timestamp = self.issue_date.isoformat() + "T00:00:00Z"
        invoice_total = str(self.total_amount)
        vat_total = str(round(self.total_amount * Decimal('0.15'), 2)) # حساب 15% ضريبة

        def to_tlv(tag, value):
            tag_bytes = tag.to_bytes(1, 'big')
            len_bytes = len(value).to_bytes(1, 'big')
            return tag_bytes + len_bytes + value.encode('utf-8')

        tlv_tags = [
            to_tlv(1, "المكتب الهندسي للاستشارات"),
            to_tlv(2, "300000000000003"),
            to_tlv(3, timestamp),
            to_tlv(4, invoice_total),
            to_tlv(5, vat_total),
        ]
        
        tlv_string = b''.join(tlv_tags)
        return base64.b64encode(tlv_string).decode('utf-8')

    def save(self, *args, **kwargs):
        # إنشاء وتحديث QR Code قبل الحفظ
        qr_data = self._generate_qr_code_data()
        qr_img = qrcode.make(qr_data)
        buffer = BytesIO()
        qr_img.save(buffer, format="PNG")
        self.qr_code_image = base64.b64encode(buffer.getvalue()).decode('utf-8')
        
        super().save(*args, **kwargs)

class InvoiceItem(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='items')
    description = models.CharField(max_length=255)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('1.00'))
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)

    @property
    def total_price(self):
        return self.quantity * self.unit_price

    def __str__(self):
        return self.description
    
class LandBoundary(models.Model):
    # علاقة واحد لواحد تضمن أن كل معاملة لها جدول حدود واحد فقط
    transaction = models.OneToOneField(Transaction, on_delete=models.CASCADE, related_name='boundaries')
    
    # حدود جهة الشمال
    north_desc_nature = models.CharField(max_length=255, blank=True, verbose_name="وصف الحد الشمالي طبيعة")
    north_length_nature = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True, verbose_name="طول الحد الشمالي طبيعة")

    # حدود جهة الشرق
    east_desc_nature = models.CharField(max_length=255, blank=True, verbose_name="وصف الحد الشرقي طبيعة")
    east_length_nature = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True, verbose_name="طول الحد الشرقي طبيعة")
    
    # حدود جهة الجنوب
    south_desc_nature = models.CharField(max_length=255, blank=True, verbose_name="وصف الحد الجنوبي طبيعة")
    south_length_nature = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True, verbose_name="طول الحد الجنوبي طبيعة")
    
    # حدود جهة الغرب
    west_desc_nature = models.CharField(max_length=255, blank=True, verbose_name="وصف الحد الغربي طبيعة")
    west_length_nature = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True, verbose_name="طول الحد الغربي طبيعة")

    def __str__(self):
        return f"حدود المعاملة رقم {self.transaction.short_code}"

class Payment(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_date = models.DateField()
    payment_method = models.CharField(max_length=100, default='Bank Transfer')
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return f"Payment of {self.amount} for Invoice {self.invoice.invoice_number}"


class DocumentType(models.Model):
    """
    يخزن القائمة الرئيسية لجميع أنواع المستندات الممكنة في النظام.
    """
    code = models.CharField(max_length=20, unique=True, primary_key=True) # DOC001, DOC002, etc.
    name_ar = models.CharField(max_length=255)
    
    def __str__(self):
        return f"{self.code} - {self.name_ar}"

class TransactionDocument(models.Model):
    """
    هذا هو النموذج المحوري الذي يمثل كل مستند مطلوب لكل معاملة.
    """
    class StatusChoices(models.TextChoices):
        MISSING = 'missing', 'مطلوب'
        UPLOADED = 'uploaded', 'تم الرفع'
        APPROVED = 'approved', 'معتمد'
        REJECTED = 'rejected', 'مرفوض'

    transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE, related_name='required_documents')
    document_type = models.ForeignKey(DocumentType, on_delete=models.PROTECT)
    status = models.CharField(max_length=20, choices=StatusChoices.choices, default=StatusChoices.MISSING)
    
    
    class Meta:
        unique_together = ('transaction', 'document_type')

    def __str__(self):
        return f"{self.transaction.short_code}: {self.document_type.name_ar} ({self.status})"



class Project(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'معلق'),
        ('IN_PROGRESS', 'قيد التنفيذ'),
        ('COMPLETED', 'مكتمل'),
        ('CANCELLED', 'ملغي'),
    ]
    name = models.CharField(max_length=200, verbose_name="اسم المشروع")
    description = models.TextField(blank=True, null=True, verbose_name="وصف المشروع")
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='projects', verbose_name="العميل")
    transaction = models.OneToOneField(Transaction, on_delete=models.SET_NULL, null=True, blank=True, related_name='project', verbose_name="المعاملة المرتبطة")
    start_date = models.DateField(verbose_name="تاريخ البدء")
    end_date = models.DateField(blank=True, null=True, verbose_name="تاريخ الانتهاء")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING', verbose_name="حالة المشروع")
    project_manager = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='managed_projects', verbose_name="مدير المشروع")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "مشروع"
        verbose_name_plural = "المشاريع"
        ordering = ['-created_at']


class Budget(models.Model):
    project = models.OneToOneField(Project, on_delete=models.CASCADE, related_name='budget', verbose_name="المشروع")
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, verbose_name="المبلغ الإجمالي للميزانية")
    version = models.PositiveIntegerField(default=1, verbose_name="الإصدار")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاريخ الإنشاء")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="تاريخ آخر تحديث")

    def __str__(self):
        return f"ميزانية مشروع {self.project.name} - إصدار {self.version}"

    class Meta:
        verbose_name = "ميزانية"
        verbose_name_plural = "الميزانيات"
        ordering = ['-created_at']

class BudgetItem(models.Model):
    CATEGORY_CHOICES = [
        ('LABOR', 'أعمال'),
        ('MATERIALS', 'مواد'),
        ('PERMITS', 'تراخيص ورسوم'),
        ('EQUIPMENT', 'معدات'),
        ('SUBCONTRACTOR', 'مقاول باطن'),
        ('OTHER', 'أخرى'),
    ]
    budget = models.ForeignKey(Budget, on_delete=models.CASCADE, related_name='items', verbose_name="الميزانية")
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, verbose_name="فئة البند")
    description = models.CharField(max_length=255, verbose_name="وصف البند")
    estimated_cost = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="التكلفة التقديرية")
    actual_cost = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, verbose_name="التكلفة الفعلية")
    
    def __str__(self):
        return f"{self.description} - {self.estimated_cost}"

    class Meta:
        verbose_name = "بند ميزانية"
        verbose_name_plural = "بنود الميزانية"


class PermissionRequest(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'معلق'),
        ('APPROVED', 'مقبول'),
        ('REJECTED', 'مرفوض'),
    ]

    requester = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="permission_requests", verbose_name="مقدم الطلب")
    permission = models.ForeignKey(Permission, on_delete=models.CASCADE, verbose_name="الصلاحية المطلوبة")
    justification = models.TextField(verbose_name="المبرر")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING', verbose_name="حالة الطلب")
    
    reviewed_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name="reviewed_permission_requests", verbose_name="تمت المراجعة بواسطة")
    reviewed_at = models.DateTimeField(null=True, blank=True, verbose_name="تاريخ المراجعة")
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاريخ الطلب")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="تاريخ آخر تحديث")

    def __str__(self):
        return f"طلب صلاحية '{self.permission.name}' من قِبل {self.requester.username}"

    class Meta:
        verbose_name = "طلب صلاحية"
        verbose_name_plural = "طلبات الصلاحيات"
        ordering = ['-created_at']


class Attendance(models.Model):
    """
    Represents a single attendance record for an employee on a specific day.
    """
    employee = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='attendance_records', verbose_name="الموظف")
    date = models.DateField(default=timezone.now, verbose_name="التاريخ")
    check_in = models.DateTimeField(verbose_name="وقت الحضور")
    check_out = models.DateTimeField(null=True, blank=True, verbose_name="وقت الانصراف")
    notes = models.TextField(blank=True, null=True, verbose_name="ملاحظات")

    def __str__(self):
        return f"حضور الموظف {self.employee.username} في تاريخ {self.date}"

    class Meta:
        verbose_name = "سجل حضور"
        verbose_name_plural = "سجلات الحضور"
        # يضمن عدم تكرار سجل الحضور للموظف في نفس اليوم
        unique_together = ('employee', 'date')
        ordering = ['-date', '-check_in']

class LeaveRequest(models.Model):
    LEAVE_TYPE_CHOICES = [
        ('ANNUAL', 'إجازة سنوية'),
        ('SICK', 'إجازة مرضية'),
        ('EMERGENCY', 'إجازة طارئة'),
        ('UNPAID', 'إجازة بدون راتب'),
        ('OTHER', 'أخرى'),
    ]

    STATUS_CHOICES = [
        ('PENDING', 'معلق'),
        ('APPROVED', 'مقبول'),
        ('REJECTED', 'مرفوض'),
    ]

    employee = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='leave_requests', verbose_name="الموظف")
    leave_type = models.CharField(max_length=20, choices=LEAVE_TYPE_CHOICES, verbose_name="نوع الإجازة")
    start_date = models.DateField(verbose_name="تاريخ البدء")
    end_date = models.DateField(verbose_name="تاريخ الانتهاء")
    reason = models.TextField(verbose_name="السبب")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING', verbose_name="الحالة")
    reviewed_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_leaves', verbose_name="تمت المراجعة بواسطة")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"طلب إجازة للموظف {self.employee.username} من {self.start_date} إلى {self.end_date}"

    class Meta:
        verbose_name = "طلب إجازة"
        verbose_name_plural = "طلبات الإجازات"
        ordering = ['-created_at']


class Account(models.Model):
    ACCOUNT_TYPE_CHOICES = [
        ('ASSET', 'أصول'),
        ('LIABILITY', 'خصوم'),
        ('EQUITY', 'حقوق ملكية'),
        ('REVENUE', 'إيرادات'),
        ('EXPENSE', 'مصروفات'),
    ]

    name = models.CharField(max_length=100, verbose_name="اسم الحساب")
    code = models.CharField(max_length=20, unique=True, verbose_name="رمز الحساب")
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='children', verbose_name="الحساب الأصلي")
    account_type = models.CharField(max_length=20, choices=ACCOUNT_TYPE_CHOICES, verbose_name="نوع الحساب")
    is_active = models.BooleanField(default=True, verbose_name="نشط")
    balance = models.DecimalField(max_digits=15, decimal_places=2, default=0.00, verbose_name="الرصيد")

    def __str__(self):
        return f"{self.code} - {self.name}"

    class Meta:
        verbose_name = "حساب"
        verbose_name_plural = "دليل الحسابات"
        ordering = ['code']


class JournalEntry(models.Model):
    date = models.DateField(default=timezone.now, verbose_name="تاريخ القيد")
    description = models.CharField(max_length=255, verbose_name="البيان / الوصف")
    created_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, related_name="journal_entries")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"قيد يومية بتاريخ {self.date} - {self.description}"

    class Meta:
        verbose_name = "قيد يومية"
        verbose_name_plural = "قيود اليومية"
        ordering = ['-date']


class JournalEntryItem(models.Model):
    ENTRY_TYPE_CHOICES = [
        ('DEBIT', 'مدين'),
        ('CREDIT', 'دائن'),
    ]

    entry = models.ForeignKey(JournalEntry, on_delete=models.CASCADE, related_name='items')
    account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name='journal_items')
    amount = models.DecimalField(max_digits=15, decimal_places=2, verbose_name="المبلغ")
    entry_type = models.CharField(max_length=6, choices=ENTRY_TYPE_CHOICES, verbose_name="نوع الطرف")

    def __str__(self):
        return f"{self.get_entry_type_display()} بقيمة {self.amount} على حساب {self.account.name}"
    


class ReportTemplate(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name="اسم القالب")
    description = models.TextField(blank=True, null=True, verbose_name="وصف القالب")
    # سنخزن محتوى القالب كـ HTML مع متغيرات Jinja2
    template_content = models.TextField(verbose_name="محتوى القالب (HTML)")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "قالب تقرير"
        verbose_name_plural = "قوالب التقارير"
        ordering = ['-created_at']

def generated_report_upload_path(instance, filename):
    return f'reports/{instance.transaction.id}/{filename}'

class GeneratedReport(models.Model):
    transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE, related_name='generated_reports')
    template = models.ForeignKey(ReportTemplate, on_delete=models.PROTECT, related_name='generated_reports')
    generated_file = models.FileField(upload_to=generated_report_upload_path, verbose_name="الملف المُنشأ")
    created_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"تقرير '{self.template.name}' للمعاملة {self.transaction.short_code}"

    class Meta:
        verbose_name = "تقرير مُنشأ"
        verbose_name_plural = "التقارير المُنشأة"
        ordering = ['-created_at']


class Notification(models.Model):
    """
    موديل الإشعارات الموسع.
    """
    class EventType(models.TextChoices):
        NEW_TASK = 'NEW_TASK', 'مهمة جديدة'
        STATUS_CHANGE = 'STATUS_CHANGE', 'تغيير حالة'
        NEW_MESSAGE = 'NEW_MESSAGE', 'رسالة جديدة'
        PERMISSION_REQUEST = 'PERMISSION_REQUEST', 'طلب صلاحية'
        PERMISSION_RESPONSE = 'PERMISSION_RESPONSE', 'رد على طلب صلاحية'
        TRANSACTION_ASSIGNED = 'TRANSACTION_ASSIGNED', 'إسناد معاملة'
        GENERIC_NOTIFICATION = 'GENERIC_NOTIFICATION', 'إشعار عام'

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications', verbose_name="المستخدم")
    message = models.TextField(verbose_name="الرسالة")
    event_type = models.CharField(max_length=50, choices=EventType.choices, default=EventType.GENERIC_NOTIFICATION, verbose_name="نوع الحدث")
    link = models.URLField(max_length=200, blank=True, null=True, verbose_name="الرابط")
    is_read = models.BooleanField(default=False, verbose_name="مقروء")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاريخ الإنشاء")

    # حقول لربط الإشعار بأي موديل آخر (مهمة، معاملة، إلخ)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True, blank=True)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    related_object = GenericForeignKey('content_type', 'object_id')

    class Meta:
        ordering = ['-created_at']
        verbose_name = "إشعار"
        verbose_name_plural = "الإشعارات"

    def __str__(self):
        return f"إشعار لـ {self.user.username}: {self.message[:20]}"

    
class TransactionDistribution(models.Model):
    """
    يسجل هذا الموديل كل عملية توزيع لمعاملة من مدير إلى موظف.
    """
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('ACCEPTED', 'Accepted'),
        ('REJECTED', 'Rejected'),
    ]
    
    transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE, related_name='distributions')
    assigned_from = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, related_name='made_assignments')
    assigned_to = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='received_assignments')
    assigned_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='PENDING')
    manager_notes = models.TextField(blank=True, null=True)
    employee_notes = models.TextField(blank=True, null=True)
    responded_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ['-assigned_at']

    def __str__(self):
        return f'{self.transaction.short_code} assigned to {self.assigned_to.username}'
    

class ChatRoom(models.Model):
    """نموذج لغرف المحادثة"""
    class RoomType(models.TextChoices):
        PRIVATE = 'private', 'محادثة خاصة'
        GROUP = 'group', 'مجموعة'
        DEPARTMENT = 'department', 'قسم'
        GENERAL = 'general', 'عام'

    name = models.CharField(max_length=255, verbose_name="اسم الغرفة")
    room_type = models.CharField(max_length=20, choices=RoomType.choices, default=RoomType.PRIVATE)
    participants = models.ManyToManyField(CustomUser, related_name='chat_rooms', verbose_name="المشاركون")
    created_by = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='created_rooms')
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True, 
                                  verbose_name="القسم المرتبط")

    class Meta:
        verbose_name = "غرفة محادثة"
        verbose_name_plural = "غرف المحادثات"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.get_room_type_display()})"

    def get_participants_count(self):
        return self.participants.count()

class ChatMessage(models.Model):
    """نموذج للرسائل في المحادثات"""
    room = models.ForeignKey(ChatRoom, on_delete=models.CASCADE, related_name='messages', verbose_name="الغرفة")
    sender = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='chat_messages', verbose_name="المرسل")
    content = models.TextField(verbose_name="محتوى الرسالة")
    message_type = models.CharField(max_length=20, default='text', choices=[
        ('text', 'نص'),
        ('file', 'ملف'),
        ('image', 'صورة'),
        ('system', 'نظام')
    ])
    file = models.FileField(upload_to='chat_files/', null=True, blank=True, verbose_name="ملف مرفق")
    is_read = models.BooleanField(default=False, verbose_name="تم القراءة")
    created_at = models.DateTimeField(auto_now_add=True)
    parent_message = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, 
                                     related_name='replies', verbose_name="رد على")

    class Meta:
        verbose_name = "رسالة محادثة"
        verbose_name_plural = "رسائل المحادثات"
        ordering = ['created_at']

    def __str__(self):
        return f"{self.sender.username}: {self.content[:50]}"

class MessageReadStatus(models.Model):
    """تتبع حالة قراءة الرسائل"""
    message = models.ForeignKey(ChatMessage, on_delete=models.CASCADE, related_name='read_status')
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='message_reads')
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('message', 'user')
        verbose_name = "حالة قراءة الرسالة"
        verbose_name_plural = "حالات قراءة الرسائل"

class UserPresence(models.Model):
    """تتبع حالة الاتصال للمستخدمين"""
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='presence')
    is_online = models.BooleanField(default=False)
    last_seen = models.DateTimeField(auto_now=True)
    device_token = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        verbose_name = "حالة الاتصال"
        verbose_name_plural = "حالات الاتصال"

    def __str__(self):
        return f"{self.user.username} - {'Online' if self.is_online else 'Offline'}"

