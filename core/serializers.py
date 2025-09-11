# core/serializers.py

from rest_framework import serializers
from .models import Account, Attendance, Budget, BudgetItem, ChatMessage, ChatRoom, Client, CompetentAuthority, GeneratedReport, JournalEntry, JournalEntryItem, LeaveRequest, CustomUser, Department, Document, DocumentType, Invoice, InvoiceItem, LandBoundary, MessageReadStatus, Notification, Payment, PermissionRequest, Project, ReportTemplate, Role, Permission, Task, Transaction, TransactionDistribution, TransactionDocument, TransactionMainCategory, TransactionSubCategory
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.db import transaction

class PermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Permission
        fields = ['code', 'name_en', 'name_ar']

class RoleSerializer(serializers.ModelSerializer):
    # عند عرض الأدوار، سنعرض الصلاحيات المرتبطة بها كقائمة من الأكواد
    permissions = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Permission.objects.all()
    )

    class Meta:
        model = Role
        fields = ['id', 'name', 'permissions']

class UserSerializer(serializers.ModelSerializer):
    # عند عرض المستخدم، سنعرض اسم الدور بدلاً من رقمه لسهولة القراءة
    role_name = serializers.CharField(source='role.name', read_only=True)

    class Meta:
        model = CustomUser
        # الحقول التي ستظهر في الـ API
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'user_code', 'full_name_ar', 'employee_type',
            'role', # هذا الحقل يستخدم عند الإنشاء والتعديل (نرسل ID)
            'role_name' # هذا الحقل للقراءة فقط
        ]
        # جعل بعض الحقول للقراءة فقط لأنها تُدار تلقائيًا
        read_only_fields = ['id', 'role_name']

class LandBoundarySerializer(serializers.ModelSerializer):
    class Meta:
        model = LandBoundary
        fields = [
            'north_desc_nature', 'north_length_nature',
            'east_desc_nature', 'east_length_nature',
            'south_desc_nature', 'south_length_nature',
            'west_desc_nature', 'west_length_nature',
        ]

class DocumentTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentType
        fields = ['code', 'name_ar']

class DocumentSerializer(serializers.ModelSerializer):
    uploaded_by_name = serializers.CharField(source='uploaded_by.username', read_only=True)
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = Document
        fields = ['id', 'file', 'file_url', 'description', 'uploaded_at', 'uploaded_by_name', 'transaction_document']
        read_only_fields = ['id', 'uploaded_at', 'uploaded_by_name', 'file_url']

    def get_file_url(self, obj):
        request = self.context.get('request')
        # ---  هذا هو التصحيح ---
        # 1. تأكد من وجود كائن الطلب (request)
        # 2. تأكد من وجود ملف فعلي مرتبط بالسجل (obj.file)
        if request and hasattr(obj.file, 'url'):
            return request.build_absolute_uri(obj.file.url)
        # إذا لم يتحقق الشرط، أرجع قيمة فارغة بدلاً من التسبب في انهيار الخادم
        return None

class TransactionDocumentSerializer(serializers.ModelSerializer):
    document_type = DocumentTypeSerializer(read_only=True)
    # --- [هذا هو التعديل] ---
    # سنعرض قائمة الملفات المرتبطة بهذا البند
    files = DocumentSerializer(many=True, read_only=True)

    class Meta:
        model = TransactionDocument
        fields = ['id', 'document_type', 'status', 'files'] # تم استبدال uploaded_file بـ files

    def get_uploaded_file_url(self, obj):
        # هذه الدالة تتأكد من وجود الملف والرابط قبل محاولة الوصول إليهما
        request = self.context.get('request')
        if obj.uploaded_file and hasattr(obj.uploaded_file.file, 'url') and request:
            return request.build_absolute_uri(obj.uploaded_file.file.url)
        return None


class TransactionSerializer(serializers.ModelSerializer):
    assigned_to_name = serializers.CharField(source='assigned_to.username', read_only=True, allow_null=True)
    client_name = serializers.CharField(source='client.name_ar', read_only=True)
    main_category_name = serializers.CharField(source='main_category.name', read_only=True, allow_null=True)
    sub_category_name = serializers.CharField(source='sub_category.name', read_only=True, allow_null=True)
    competent_authority_name = serializers.CharField(source='competent_authority.name', read_only=True, allow_null=True)
    boundaries = LandBoundarySerializer(required=False, allow_null=True)
    required_documents = TransactionDocumentSerializer(many=True, read_only=True)

    

    class Meta:
        model = Transaction
        fields = [
            'id', 'short_code', 'long_code', 'client', 'client_name',
            'status', 'assigned_to', 'assigned_to_name', 'created_at',
            'updated_at', 'main_category', 'main_category_name', 'sub_category',
            'sub_category_name', 'competent_authority', 'competent_authority_name',
            'doc_type', 'doc_classification', 'doc_number', 'doc_date', 'area_sq_meters',
            'piece_number', 'plan_number', 'neighborhood', 'city',
            'boundaries', 'required_documents'
        ]
        # --- [هذا هو التصحيح] ---
        # قمنا بإزالة 'status' من قائمة الحقول للقراءة فقط للسماح بتحديثها
        read_only_fields = [
            'long_code', 'created_at', 'updated_at', 'client_name', 
            'main_category_name', 'sub_category_name', 'competent_authority_name',
            'required_documents' 
        ]
    def update(self, instance, validated_data):
        """
        Override the update method to automatically update the status
        to 'assigned' when a user is assigned to a 'new' transaction.
        """
        # Check if a user is being assigned in this update request
        if 'assigned_to' in validated_data and validated_data.get('assigned_to') is not None:
            # Check if the transaction's current status is 'new'
            if instance.status == 'new':
                # Automatically set the status to 'assigned'
                validated_data['status'] = 'assigned'
        
        # Call the original update method to save the instance
        return super().update(instance, validated_data)
    # === END: التعديل الاحتياطي هنا ===    


class MyTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)

        # Add custom claims
        token['username'] = user.username
        token['first_name'] = user.first_name
        token['last_name'] = user.last_name
        
        # === START: الإضافة المهمة هنا ===
        token['is_superuser'] = user.is_superuser
        token['is_staff'] = user.is_staff
        # === END: الإضافة المهمة هنا ===

        # Get permissions from the user's assigned role
        if hasattr(user, 'role') and user.role and hasattr(user.role, 'permissions'):
            permissions = user.role.permissions.all().values_list('code', flat=True)
            token['permissions'] = list(permissions)
        else:
            token['permissions'] = []
            
        # Add role and department info
        if hasattr(user, 'role') and user.role:
            token['role_name'] = user.role.name
        if hasattr(user, 'department') and user.department:
            token['department_name'] = user.department.name

        return token
    
class ClientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Client
        fields = ['id', 'client_code', 'name_ar', 'client_type', 'phone_number', 'email', 'created_at']


    
class TaskSerializer(serializers.ModelSerializer):
    assigned_to_name = serializers.CharField(source='assigned_to.username', read_only=True, default='')
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    transaction_code = serializers.CharField(source='transaction.short_code', read_only=True, default='')

    assigned_to = serializers.PrimaryKeyRelatedField(
        queryset=CustomUser.objects.all(), allow_null=True, required=False
    )
    transaction = serializers.PrimaryKeyRelatedField(
        queryset=Transaction.objects.all(), allow_null=True, required=False
    )

    class Meta:
        model = Task
        fields = [
            'id', 'title', 'description', 'status', 'assigned_to', 
            'created_by', 'transaction', 'created_at', 'due_date',
            'assigned_to_name', 'created_by_name', 'transaction_code'
        ]
        # --- هذا هو التعديل ---
        # قمنا بإزالة 'status' من قائمة القراءة فقط للسماح بتحديثها
        read_only_fields = [
            'id', 'created_at', 'created_by', 'assigned_to_name', 
            'created_by_name', 'transaction_code'
        ]

class StaffSerializer(serializers.ModelSerializer):
    role_name = serializers.CharField(source='role.name', read_only=True, default='')
    department_name = serializers.CharField(source='department.name', read_only=True, default='')
    active_transactions = serializers.SerializerMethodField()
    active_tasks = serializers.SerializerMethodField()

    # --- [هذا هو التطوير] ---
    # ١. تعريف الحقول القابلة للكتابة بشكل صريح
    role = serializers.PrimaryKeyRelatedField(
        queryset=Role.objects.all(), required=True # الدور مطلوب
    )
    department = serializers.PrimaryKeyRelatedField(
        queryset=Department.objects.all(), required=False, allow_null=True # القسم اختياري
    )
    password = serializers.CharField(
        write_only=True, 
        required=True, 
        style={'input_type': 'password'}
    )

    class Meta:
        model = CustomUser
        # ٢. تنظيف قائمة الحقول لتجنب التكرار
        fields = [
            'id', 'username', 'user_code', 'full_name_ar', 
            'email', 'phone_number_1', 'employee_type', 'is_active',
            'department', 'department_name', 'role', 'role_name',
            'active_transactions', 'active_tasks', 'password'
        ]
        read_only_fields = ['id', 'role_name', 'department_name', 'is_active', 'active_transactions', 'active_tasks']

    # ٣. تصحيح دالة الإنشاء (Create)
    def create(self, validated_data):
        # فصل حقول العلاقات قبل إنشاء المستخدم
        role_data = validated_data.pop('role')
        department_data = validated_data.pop('department', None)
        
        # استخدام create_user لضمان تشفير كلمة المرور بشكل آمن
        user = CustomUser.objects.create_user(**validated_data)
        
        # ربط العلاقات بعد إنشاء المستخدم
        user.role = role_data
        if department_data:
            user.department = department_data
        
        user.save()
        return user

    def get_active_transactions(self, obj):
        return obj.transactions.exclude(status__in=['completed', 'cancelled']).count()

    def get_active_tasks(self, obj):
        return obj.tasks.exclude(status__in=['approved', 'cancelled']).count()

class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = ['id', 'name']

class InvoiceItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceItem
        fields = ['id', 'description', 'quantity', 'unit_price', 'total_price']
        read_only_fields = ['id', 'total_price']

class InvoiceSerializer(serializers.ModelSerializer):
    # عند عرض الفاتورة، سيتم عرض تفاصيل البنود
    # جعلناه للقراءة فقط لأن منطق الإنشاء يتم التعامل معه في views.py
    items = InvoiceItemSerializer(many=True, read_only=True)
    
    # حقول إضافية للقراءة فقط لتسهيل العرض في الواجهة الأمامية
    client_name = serializers.CharField(source='client.name_ar', read_only=True)
    transaction_code = serializers.CharField(source='transaction.short_code', read_only=True, default='', allow_null=True)

    class Meta:
        model = Invoice
        fields = [
            'id', 'invoice_number', 'client', 'client_name', 'transaction', 
            'transaction_code', 'status', 'issue_date', 'due_date', 
            'total_amount', 'qr_code_image', 'items'
        ]
        # الحقول التي يتم حسابها تلقائيًا أو جلبها من نماذج أخرى يجب أن تكون للقراءة فقط
        read_only_fields = ['id', 'total_amount', 'client_name', 'transaction_code', 'qr_code_image']

class RoleSerializer(serializers.ModelSerializer):
    # عند عرض الأدوار، سنعرض التفاصيل الكاملة لكل صلاحية
    permissions = PermissionSerializer(many=True, read_only=True)
    # حقل جديد لاستقبال قائمة من أكواد الصلاحيات عند التحديث
    permission_codes = serializers.ListField(
        child=serializers.CharField(), write_only=True, required=False
    )

    class Meta:
        model = Role
        fields = ['id', 'name', 'permissions', 'permission_codes']

    def update(self, instance, validated_data):
        # إذا تم إرسال قائمة بأكواد الصلاحيات
        if 'permission_codes' in validated_data:
            permission_codes = validated_data.pop('permission_codes')
            # ابحث عن كل الصلاحيات المطابقة للأكواد
            permissions = Permission.objects.filter(code__in=permission_codes)
            # قم بتعيينها للدور
            instance.permissions.set(permissions)
        
        # قم بتحديث باقي الحقول (مثل الاسم)
        return super().update(instance, validated_data)
    
class TransactionMainCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = TransactionMainCategory
        fields = ['id', 'name', 'code']

class TransactionSubCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = TransactionSubCategory
        fields = ['id', 'name', 'code', 'main_category']

class CompetentAuthoritySerializer(serializers.ModelSerializer):
    class Meta:
        model = CompetentAuthority
        fields = ['id', 'name', 'code']

class PaymentSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    class Meta:
        model = Payment
        fields = '__all__'
        read_only_fields = ['created_by']

class BudgetItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = BudgetItem
        fields = '__all__'

class BudgetSerializer(serializers.ModelSerializer):
    items = BudgetItemSerializer(many=True, read_only=True)
    
    class Meta:
        model = Budget
        fields = ['id', 'project', 'total_amount', 'version', 'created_at', 'updated_at', 'items']
        # === START: أضف هذا السطر لجعل حقل المبلغ اختيارياً عند الإنشاء ===
        extra_kwargs = {
            'total_amount': {'required': False}
        }
        # === END: الإضافة هنا ===

class ProjectSerializer(serializers.ModelSerializer):
    # حقول إضافية لجلب الأسماء بدلاً من الأرقام التعريفية (IDs)
    client_name = serializers.CharField(source='client.name', read_only=True)
    project_manager_name = serializers.CharField(source='project_manager.get_full_name', read_only=True, default=None)

    class Meta:
        model = Project
        fields = '__all__'
        fields = [
            'id', 'name', 'description', 'client', 'client_name', 
            'transaction', 'start_date', 'end_date', 'status', 
            'project_manager', 'project_manager_name', 'created_at'
        ]




class PermissionRequestSerializer(serializers.ModelSerializer):
    # === START: أضف هذه الأسطر ===
    # حقل جديد لجلب اسم مقدم الطلب
    requester_name = serializers.CharField(source='requester.full_name_ar', read_only=True)
    # حقل جديد لجلب اسم الصلاحية المطلوبة
    permission_name = serializers.CharField(source='permission.name_ar', read_only=True)
    # حقل جديد لجلب كود الصلاحية
    permission_code = serializers.CharField(source='permission.code', read_only=True)
    # === END: الإضافة تنتهي هنا ===
    reviewed_by_name = serializers.CharField(source='reviewed_by.get_full_name', read_only=True, default=None)

    class Meta:
        model = PermissionRequest
        fields = [
            'id', 'requester', 'requester_name', 'permission', 'permission_name','permission_code',
            'justification', 'status', 'reviewed_by', 'reviewed_by_name',
            'reviewed_at', 'created_at'
        ]
        read_only_fields = ['requester', 'status', 'reviewed_by', 'reviewed_at']

class AttendanceSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.get_full_name', read_only=True)
    # === التصحيح المهم: إضافة اسم الموظف بالعربية ===
    employee_name_ar = serializers.CharField(source='employee.full_name_ar', read_only=True)
    employee_department = serializers.CharField(source='employee.department.name', read_only=True, allow_null=True)
    employee_username = serializers.CharField(source='employee.username', read_only=True)

    class Meta:
        model = Attendance
        fields = ['id', 'employee', 'employee_name', 'employee_name_ar', 'employee_department', 
                 'employee_username', 'date', 'check_in', 'check_out', 'notes']
        read_only_fields = ['employee', 'date', 'check_in', 'check_out']

class LeaveRequestSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.get_full_name', read_only=True)
    reviewed_by_name = serializers.CharField(source='reviewed_by.get_full_name', read_only=True, allow_null=True)
    leave_type_display = serializers.CharField(source='get_leave_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    # === التصحيح المهم: إضافة اسم الموظف بالعربية ===
    employee_name_ar = serializers.CharField(source='employee.full_name_ar', read_only=True)
    employee_department = serializers.CharField(source='employee.department.name', read_only=True, allow_null=True)

    class Meta:
        model = LeaveRequest
        fields = '__all__'
        read_only_fields = ['employee', 'status', 'reviewed_by']

class RecursiveField(serializers.Serializer):
    def to_representation(self, value):
        serializer = self.parent.parent.__class__(value, context=self.context)
        return serializer.data

class AccountSerializer(serializers.ModelSerializer):
    # حقل لعرض الحسابات الفرعية بشكل متداخل
    children = RecursiveField(many=True, read_only=True)

    class Meta:
        model = Account
        fields = [
            'id', 'name', 'code', 'parent', 'account_type', 
            'is_active', 'balance', 'children'
        ]

class JournalEntryItemSerializer(serializers.ModelSerializer):
    account_name = serializers.CharField(source='account.name', read_only=True)

    class Meta:
        model = JournalEntryItem
        fields = ['id', 'account', 'account_name', 'amount', 'entry_type']


class JournalEntrySerializer(serializers.ModelSerializer):
    items = JournalEntryItemSerializer(many=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)

    class Meta:
        model = JournalEntry
        fields = ['id', 'date', 'description', 'created_by', 'created_by_name', 'created_at', 'items']

    def create(self, validated_data):
        items_data = validated_data.pop('items')
        
        # التحقق من توازن القيد
        total_debit = sum(item['amount'] for item in items_data if item['entry_type'] == 'DEBIT')
        total_credit = sum(item['amount'] for item in items_data if item['entry_type'] == 'CREDIT')

        if total_debit != total_credit:
            raise serializers.ValidationError("القيد غير متوازن: مجموع المدين لا يساوي مجموع الدائن.")
        
        if total_debit == 0:
            raise serializers.ValidationError("لا يمكن إنشاء قيد بقيمة صفر.")

        # استخدام transaction لضمان حفظ القيد وأطرافه معاً
        with transaction.atomic():
            entry = JournalEntry.objects.create(**validated_data)
            for item_data in items_data:
                # تحديث رصيد الحساب
                account = item_data['account']
                amount = item_data['amount']
                if item_data['entry_type'] == 'DEBIT':
                    if account.account_type in ['ASSET', 'EXPENSE']:
                        account.balance += amount
                    else:
                        account.balance -= amount
                else: # CREDIT
                    if account.account_type in ['LIABILITY', 'EQUITY', 'REVENUE']:
                        account.balance += amount
                    else:
                        account.balance -= amount
                account.save()
                JournalEntryItem.objects.create(entry=entry, **item_data)
        
        return entry
    

class ReportTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReportTemplate
        fields = '__all__'

class GeneratedReportSerializer(serializers.ModelSerializer):
    template_name = serializers.CharField(source='template.name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)

    class Meta:
        model = GeneratedReport
        fields = ['id', 'transaction', 'template', 'template_name', 'generated_file', 'created_by', 'created_by_name', 'created_at']

class NotificationSerializer(serializers.ModelSerializer):
    """
    Serializer الخاص بموديل الإشعارات.
    """
    class Meta:
        model = Notification
        fields = ['id', 'message', 'event_type', 'link', 'is_read', 'created_at']



class TransactionDistributionSerializer(serializers.ModelSerializer):
    # حقول إضافية لعرض الأسماء بدلاً من الأرقام فقط
    assigned_from_name = serializers.CharField(source='assigned_from.full_name_ar', read_only=True)
    assigned_to_name = serializers.CharField(source='assigned_to.full_name_ar', read_only=True)
    transaction_code = serializers.CharField(source='transaction.short_code', read_only=True)

    class Meta:
        model = TransactionDistribution
        fields = '__all__'
        read_only_fields = ['assigned_from', 'assigned_at', 'responded_at']


class ChatUserSerializer(serializers.ModelSerializer):
    """Serializer مختصر لعرض بيانات المستخدم في المحادثات"""
    department_name = serializers.CharField(source='department.name', read_only=True)
    is_online = serializers.SerializerMethodField()
    
    class Meta:
        model = CustomUser
        fields = ['id', 'username', 'full_name_ar', 'department', 'department_name', 'is_online']
    
    def get_is_online(self, obj):
        try:
            return obj.presence.is_online
        except:
            return False

class ChatMessageSerializer(serializers.ModelSerializer):
    sender = UserSerializer(read_only=True)  # نعرض معلومات المرسل فقط، ولا نسمح بإرسالها من الـ frontend

    class Meta:
        model = ChatMessage
        fields = ['id', 'room', 'sender', 'content', 'message_type', 'created_at']
        read_only_fields = ['id', 'sender', 'created_at']  # هذه الحقول يتم توليدها تلقائيًا

    def create(self, validated_data):
        request = self.context.get('request')
        room = validated_data.get('room')

        # تحقق من أن المستخدم جزء من الغرفة
        if not room.participants.filter(id=request.user.id).exists():
            raise serializers.ValidationError("You are not a participant in this room")

        # إزالة أي sender أُرسل من الـ frontend حتى لا يتكرر
        validated_data.pop('sender', None)

        # إنشاء الرسالة
        message = ChatMessage.objects.create(
            **validated_data,
            sender=request.user
        )

        # إنشاء حالات القراءة للمشاركين الآخرين
        participants = room.participants.exclude(id=request.user.id)
        for participant in participants:
            MessageReadStatus.objects.get_or_create(
                message=message,
                user=participant,
                defaults={'is_read': False}
            )

        return message


class ChatRoomSerializer(serializers.ModelSerializer):
    """Serializer لغرف المحادثة"""
    participants = ChatUserSerializer(many=True, read_only=True)
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()
    participants_count = serializers.IntegerField(source='get_participants_count', read_only=True)
    
    class Meta:
        model = ChatRoom
        fields = [
            'id', 'name', 'room_type', 'participants', 'created_by', 'created_at',
            'is_active', 'department', 'last_message', 'unread_count', 'participants_count'
        ]
        read_only_fields = ['created_by', 'created_at']
    
    def get_last_message(self, obj):
        last_msg = obj.messages.last()
        return ChatMessageSerializer(last_msg, context=self.context).data if last_msg else None
    
    def get_unread_count(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.messages.filter(
                read_status__user=request.user,
                read_status__is_read=False
            ).exclude(sender=request.user).count()
        return 0

class CreateChatRoomSerializer(serializers.ModelSerializer):
    """Serializer لإنشاء غرف محادثة جديدة"""
    participant_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False
    )
    
    class Meta:
        model = ChatRoom
        fields = ['id', 'name', 'room_type', 'participant_ids', 'department']
    
    def create(self, validated_data):
        participant_ids = validated_data.pop('participant_ids', [])
        request = self.context.get('request')
        
        # إنشاء الغرفة بدون تمرير created_by في validated_data
        room = ChatRoom.objects.create(
            name=validated_data.get('name'),
            room_type=validated_data.get('room_type'),
            department=validated_data.get('department'),
            created_by=request.user  # تمرير created_by هنا فقط
        )
        
        # إضافة المشاركين
        participants = CustomUser.objects.filter(id__in=participant_ids)
        room.participants.add(request.user)
        if participants:
            room.participants.add(*participants)
        
        return room