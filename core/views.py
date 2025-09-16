# core/views.py

from decimal import Decimal
from django.conf import settings
import pusher
from rest_framework import viewsets, status, mixins
from rest_framework.views import APIView
from rest_framework.response import Response
from django.db.models import Count
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q
from django.utils import timezone
from django.db.models import Max
from io import BytesIO
from xhtml2pdf import pisa
from django.template import Context, Template
from django.core.files.base import ContentFile
from .models import *
from .serializers import *
from rest_framework.decorators import action
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters
from asgiref.sync import async_to_sync # <-- إضافة استيراد جديد
from channels.layers import get_channel_layer
from django.db.models import Sum, Case, When, Value, DecimalField
from .services import create_and_send_notification # استيراد الدالة الجديدة
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework_simplejwt.views import TokenObtainPairView



class UserViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows users to be viewed or edited.
    """
    queryset = CustomUser.objects.all().order_by('-date_joined')
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

class RoleViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows roles to be viewed or edited.
    """
    queryset = Role.objects.all()
    serializer_class = RoleSerializer
    permission_classes = [IsAuthenticated]

class PermissionViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows permissions to be viewed.
    """
    # الصلاحيات للقراءة فقط من خلال الـ API
    queryset = Permission.objects.all()
    serializer_class = PermissionSerializer
    permission_classes = [IsAuthenticated]

class TransactionViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows transactions to be viewed or edited,
    with permission-based filtering and custom actions.
    """
    serializer_class = TransactionSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    # --- فلاتر البحث والترتيب ---
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter, filters.SearchFilter]
    filterset_fields = ['client', 'status', 'assigned_to', 'main_category']
    search_fields = ['short_code', 'title', 'client__name_ar']
    ordering_fields = ['created_at', 'updated_at']

    def get_queryset(self):
        """
        يقوم بإرجاع قائمة المعاملات مع تطبيق الصلاحيات والفلاتر وتحسينات الأداء.
        """
        user = self.request.user
        
        # 1. نبدأ بالـ QuerySet الأساسي مع تحسينات الأداء
        queryset = Transaction.objects.all().select_related(
            'client', 'assigned_to', 'main_category', 'sub_category'
        ).prefetch_related(
            'distributions', 'required_documents'
        ).order_by('-created_at')

        # 2. نطبق فلترة الصلاحيات
        if not (user.is_superuser or (user.role and user.role.permissions.filter(code='PERM039').exists())):
            # إذا لم يكن المستخدم مشرفًا أو لديه صلاحية عرض الكل،
            # فإنه يرى فقط المعاملات المسندة إليه
            queryset = queryset.filter(assigned_to=user)
        
        # 3. نطبق فلتر "المعاملات النشطة" (is_active)
        is_active_param = self.request.query_params.get('is_active')
        if is_active_param in ['true', 'True', '1']:
            queryset = queryset.exclude(status__in=['completed', 'cancelled'])

        return queryset

    def perform_create(self, serializer):
        """
        إنشاء معاملة جديدة وتوليد قائمة المستندات المطلوبة لها تلقائيًا.
        """
        transaction = serializer.save()
        
        required_docs_codes = []
        sub_category_code = transaction.sub_category.code if transaction.sub_category else None

        if sub_category_code == 'BUILD-LIC': # رخصة بناء جديدة
            required_docs_codes = [
                "DOC001", "DOC002", "DOC003", "DOC004", "DOC005", "DOC006", 
                "DOC007", "DOC008", "DOC009", "DOC010", "DOC011", "DOC012",
                "DOC013", "DOC014", "DOC015", "DOC016", "DOC017", "DOC018",
                "DOC019", "DOC020", "DOC021", "DOC022"
            ]
        else: # قائمة افتراضية
            required_docs_codes = ["DOC001", "DOC005"]

        for code in required_docs_codes:
            try:
                doc_type = DocumentType.objects.get(code=code)
                TransactionDocument.objects.create(
                    transaction=transaction,
                    document_type=doc_type
                )
            except DocumentType.DoesNotExist:
                print(f"Warning: DocumentType with code {code} not found.")

    def perform_update(self, serializer):
        boundaries_data = serializer.validated_data.pop('boundaries', None)
        transaction = serializer.save()
        if boundaries_data:
            LandBoundary.objects.update_or_create(transaction=transaction, defaults=boundaries_data)

    # --- الإجراءات المخصصة لتغيير حالة المعاملة ---
    # === START: إعادة إضافة الإجراء المخصص الذي تم حذفه ===
    @action(detail=False, methods=['get'], url_path='my-work')
    def my_work(self, request):
        """
        إرجاع قائمة بالمعاملات المسندة إلى المستخدم الحالي.
        هذا الإجراء يطبق نفس منطق الفلترة الموجود في get_queryset الرئيسي.
        """
        queryset = self.get_queryset() # يعيد استخدام منطق الفلترة بالصلاحيات
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    # === END: الإضافة هنا ===

    def _check_permission(self, user, transaction):
        """دالة مساعدة للتحقق مما إذا كان المستخدم هو المسند إليه المعاملة."""
        return user.is_superuser or transaction.assigned_to == user

    @action(detail=True, methods=['post'], url_path='start-processing')
    def start_processing(self, request, pk=None):
        """تغيير حالة المعاملة إلى 'تحت المعالجة'."""
        transaction = self.get_object()
        if not self._check_permission(request.user, transaction):
            return Response({'detail': 'Action forbidden.'}, status=status.HTTP_403_FORBIDDEN)
        
        if transaction.status == 'under_review':
            transaction.status = 'processing'
            transaction.save()
            return Response({'status': 'Transaction processing started'})
        return Response({'detail': 'Invalid current status for this action.'}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], url_path='request-documents')
    def request_documents(self, request, pk=None):
        """تغيير حالة المعاملة إلى 'مطلوب مستندات'."""
        transaction = self.get_object()
        if not self._check_permission(request.user, transaction):
            return Response({'detail': 'Action forbidden.'}, status=status.HTTP_403_FORBIDDEN)

        transaction.status = 'docs_required'
        transaction.save()
        return Response({'status': 'Transaction status updated to docs_required'})

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """تغيير حالة المعاملة إلى 'منتهي'."""
        transaction = self.get_object()
        if not self._check_permission(request.user, transaction):
            return Response({'detail': 'Action forbidden.'}, status=status.HTTP_403_FORBIDDEN)
        
        transaction.status = 'completed'
        transaction.save()
        return Response({'status': 'Transaction marked as completed'})

    

class MyTokenObtainPairView(TokenObtainPairView):
    serializer_class = MyTokenObtainPairSerializer

class DashboardStatsView(APIView):
    """
    A view to retrieve aggregated statistics for the main dashboard.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, format=None):
        status_counts = Transaction.objects.values('status').annotate(count=Count('status'))
        
        stats = {item['status']: item['count'] for item in status_counts}

        recent_transactions = Transaction.objects.order_by('-created_at')[:5]
        
        # FIX: Pass the request context to the serializer so it can build full URLs for files if needed.
        recent_transactions_serializer = TransactionSerializer(recent_transactions, many=True, context={'request': request})

        # FIX: Updated to use the new, more detailed status fields from the model
        data = {
            'total_transactions': Transaction.objects.count(),
            'new_transactions': stats.get('new', 0) + stats.get('under_review', 0),
            'in_progress_transactions': stats.get('processing', 0) + stats.get('docs_required', 0),
            'completed_transactions': stats.get('completed', 0),
            'recent_transactions': recent_transactions_serializer.data,
        }
        return Response(data)

class ClientViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows clients to be viewed or edited.
    """
    serializer_class = ClientSerializer
    permission_classes = [IsAuthenticated]

    # --- [هذا هو التطوير] ---
    # إضافة منطق للتحقق من الصلاحيات قبل عرض البيانات
    def get_queryset(self):
        """
        Filters clients based on user permissions:
        - Superusers or users with 'PERM054' (Clients_View_All) can see all clients.
        - Other users will see an empty list.
        """
        user = self.request.user

        # تحقق إذا كان المستخدم هو مدير خارق أو يملك صلاحية عرض كل العملاء
        if user.is_superuser or (user.role and user.role.permissions.filter(code='PERM054').exists()):
            return Client.objects.all().order_by('-created_at')
        
        # في المستقبل، يمكنك إضافة منطق لعرض العملاء المسندين لموظف معين هنا
        # if user.role and user.role.permissions.filter(code='PERM055').exists():
        #     return Client.objects.filter(assigned_to=user).order_by('-created_at')

        # إذا لم يكن لدى المستخدم أي من الصلاحيات السابقة، قم بإرجاع قائمة فارغة
        return Client.objects.none()

# في ملف core/views.py

class DocumentViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing documents for a specific transaction.
    """
    serializer_class = DocumentSerializer
    permission_classes = [IsAuthenticated]

    # === START: التصحيح الكامل هنا ===
    def get_queryset(self):
        """
        This view dynamically filters documents based on the nested URL.
        - Returns documents for a specific transaction (/transactions/{pk}/documents/).
        - Returns documents for a specific checklist item (/transaction-documents/{pk}/documents/).
        """
        # التحقق من وجود 'transaction_pk' في الرابط
        if 'transaction_pk' in self.kwargs:
            transaction_id = self.kwargs['transaction_pk']
            # إرجاع المستندات المرتبطة مباشرة بالمعاملة (المستندات الإضافية)
            return Document.objects.filter(transaction_id=transaction_id, transaction_document__isnull=True).order_by('-uploaded_at')

        # التحقق من وجود 'transaction_document_pk' في الرابط
        if 'transaction_document_pk' in self.kwargs:
            transaction_document_id = self.kwargs['transaction_document_pk']
            # إرجاع الملفات المرفوعة لبند معين في قائمة المتطلبات
            return Document.objects.filter(transaction_document_id=transaction_document_id).order_by('-uploaded_at')

        # كإجراء أمني، لا تقم بإرجاع أي شيء إذا لم يتم تحديد معاملة
        return Document.objects.none()
    # === END: التصحيح الكامل هنا ===

    def perform_create(self, serializer):
        transaction = None
        transaction_document = None

        if 'transaction_document_pk' in self.kwargs:
            transaction_document_pk = self.kwargs.get('transaction_document_pk')
            try:
                transaction_document = TransactionDocument.objects.get(pk=transaction_document_pk)
                transaction = transaction_document.transaction
                if transaction_document.status == 'missing':
                    transaction_document.status = 'uploaded'
                    transaction_document.save()
            except TransactionDocument.DoesNotExist:
                pass
        
        elif 'transaction_pk' in self.kwargs:
            transaction_pk = self.kwargs.get('transaction_pk')
            try:
                transaction = Transaction.objects.get(pk=transaction_pk)
            except Transaction.DoesNotExist:
                pass

        if not transaction:
            # منع إنشاء مستند بدون معاملة مرتبطة
            from rest_framework.exceptions import ValidationError
            raise ValidationError("A transaction must be specified to upload a document.")

        serializer.save(
            uploaded_by=self.request.user, 
            transaction=transaction,
            transaction_document=transaction_document
        )

class ProjectViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows projects to be viewed or edited.
    """
    queryset = Project.objects.select_related('client', 'project_manager').all()
    serializer_class = ProjectSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    
    # تحديد الحقول التي يمكن الفلترة من خلالها
    filterset_fields = ['client', 'status', 'project_manager']
    search_fields = ['name', 'description', 'client__name']
    ordering_fields = ['start_date', 'end_date', 'created_at']
# === END: أضف الكلاس المفقود هنا ===

class TaskViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing internal tasks.
    """
    serializer_class = TaskSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """
        Filters tasks based on user permissions:
        - PERM141 (Tasks_View): Can see all tasks.
        - Regular User: Sees tasks assigned to them OR created by them.
        """
        user = self.request.user
        
        # Superuser or user with "View All Tasks" permission
        if user.is_superuser or (user.role and user.role.permissions.filter(code='PERM141').exists()):
            return Task.objects.all().order_by('-created_at')
            
        # Regular user sees only their own tasks (assigned or created)
        return Task.objects.filter(Q(assigned_to=user) | Q(created_by=user)).distinct().order_by('-created_at')

    def perform_create(self, serializer):
        """
        عند إنشاء مهمة جديدة، قم بحفظها وإرسال إشعار للموظف المسندة إليه.
        """
        # أولاً، احفظ المهمة مع تحديد منشئها (المستخدم الحالي)
        task = serializer.save(created_by=self.request.user)

        # تحقق مما إذا كانت المهمة قد تم إسنادها إلى شخص ما
        if task.assigned_to:
            try:
                # --- >> هذا هو الإصلاح << ---
                # بدلاً من استخدام task.assigned_to مباشرة،
                # نحصل على كائن المستخدم الكامل من قاعدة البيانات لضمان أنه جاهز.
                assigned_user = CustomUser.objects.get(id=task.assigned_to.id)

                print(f"سيتم إرسال إشعار للموظف {assigned_user.username} بخصوص المهمة الجديدة.")
                
                # الآن نرسل كائن المستخدم الجاهز إلى خدمة الإشعارات
                create_and_send_notification(
                    user=assigned_user,
                    message=f"تم إسناد مهمة جديدة لك: {task.title}",
                    event_type=Notification.EventType.NEW_TASK,
                    link=f'/tasks/{task.id}',
                    related_object=task
                )
            except CustomUser.DoesNotExist:
                print(f"خطأ: المستخدم المسندة إليه المهمة (ID: {task.assigned_to.id}) غير موجود.")
            except Exception as e:
                print(f"حدث خطأ غير متوقع أثناء إرسال الإشعار: {e}")



class StaffViewSet(viewsets.ModelViewSet):
    """
    API endpoint for HR to view and manage staff members.
    """
    serializer_class = StaffSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        
        # المديرون والمشرفون يمكنهم رؤية جميع الموظفين
        if user.is_superuser or (user.role and user.role.permissions.filter(code='PERM084').exists()):
            return CustomUser.objects.filter(is_active=True).order_by('full_name_ar')
        
        # الموظفون العاديون يمكنهم رؤية زملائهم في القسم أو جميع الموظفين حسب الصلاحية
        if user.role and user.role.permissions.filter(code='PERM_CHAT_VIEW_COLLEAGUES').exists():
            if user.department:
                return CustomUser.objects.filter(
                    is_active=True, 
                    department=user.department
                ).exclude(id=user.id).order_by('full_name_ar')
            else:
                return CustomUser.objects.filter(is_active=True).exclude(id=user.id).order_by('full_name_ar')
        
        # إذا لم يكن لديه صلاحية، لا يرى أي موظفين
        return CustomUser.objects.none()

    @action(detail=False, methods=['get'])
    def assignable(self, request):
        """
        Returns a list of staff members who are eligible to be assigned tasks/transactions.
        """
        user = request.user
        queryset = CustomUser.objects.filter(is_active=True).exclude(id=user.id)
        
        # المديرون يرون الجميع
        if not (user.is_superuser or (user.role and user.role.permissions.filter(code='PERM084').exists())):
            # الموظفون العاديون يرون زملاء القسم فقط
            if user.department:
                queryset = queryset.filter(department=user.department)
            else:
                # إذا لم يكن لديه قسم، لا يرى أحداً
                queryset = queryset.none()
        
        department_id = request.query_params.get('department')
        if department_id:
            queryset = queryset.filter(department_id=department_id)
            
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class InvoiceViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing invoices.
    """
    serializer_class = InvoiceSerializer
    permission_classes = [IsAuthenticated]

    # --- هذا هو التعديل ---
    def get_queryset(self):
        """
        Filters invoices based on user permissions:
        - PERM064 (Invoices_View_All): Can see all invoices.
        - Otherwise, sees nothing.
        """
        user = self.request.user
        if user.is_superuser or (user.role and user.role.permissions.filter(code='PERM064').exists()):
            return Invoice.objects.all().order_by('-issue_date')
        return Invoice.objects.none()
    @action(detail=True, methods=['post'])
    def record_payment(self, request, pk=None):
        invoice = self.get_object()
        serializer = PaymentSerializer(data=request.data)
        if serializer.is_valid():
            # إنشاء دفعة جديدة وربطها بالمستخدم الحالي والفاتورة
            serializer.save(invoice=invoice, created_by=request.user)

            # التحقق من إجمالي المدفوعات
            total_paid = invoice.payments.aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')
            if total_paid >= invoice.total_amount:
                invoice.status = 'paid'
                invoice.save()

            return Response({'status': 'payment recorded', 'invoice_status': invoice.status}, status=status.HTTP_201_CREATED)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


    def perform_create(self, serializer):
        # ... (الكود يبقى كما هو)
        items_data = self.request.data.get('items', [])
        invoice = serializer.save()
        total_amount = Decimal('0.00')
        for item_data in items_data:
            quantity = Decimal(str(item_data.get('quantity', 0)))
            unit_price = Decimal(str(item_data.get('unit_price', 0)))
            InvoiceItem.objects.create(
                invoice=invoice,
                description=item_data.get('description', ''),
                quantity=quantity,
                unit_price=unit_price
            )
            total_amount += quantity * unit_price
        invoice.total_amount = total_amount
        invoice.save()

class TransactionMainCategoryViewSet(viewsets.ModelViewSet):
    """
    API endpoint for transaction main categories.
    """
    queryset = TransactionMainCategory.objects.all()
    serializer_class = TransactionMainCategorySerializer
    permission_classes = [IsAuthenticated]

class TransactionSubCategoryViewSet(viewsets.ModelViewSet):
    """
    API endpoint for transaction sub-categories.
    """
    queryset = TransactionSubCategory.objects.all()
    serializer_class = TransactionSubCategorySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = TransactionSubCategory.objects.all()
        main_category_id = self.request.query_params.get('main_category')
        if main_category_id is not None:
            queryset = queryset.filter(main_category_id=main_category_id)
        return queryset

class CompetentAuthorityViewSet(viewsets.ModelViewSet):
    """
    API endpoint for competent authorities.
    """
    queryset = CompetentAuthority.objects.all()
    serializer_class = CompetentAuthoritySerializer
    permission_classes = [IsAuthenticated]

class TransactionDocumentViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing the status and linking of required documents.
    """
    queryset = TransactionDocument.objects.all()
    serializer_class = TransactionDocumentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """
        Ensure users can only access checklist items related to transactions they can see.
        """
        user = self.request.user
        
        # Superuser or user with "View All Transactions" permission can see all
        if user.is_superuser or (user.role and user.role.permissions.filter(code='PERM039').exists()):
            return TransactionDocument.objects.all()
        
        # User with "View Assigned Transactions" can see checklist items for their transactions
        if user.role and user.role.permissions.filter(code='PERM040').exists():
            return TransactionDocument.objects.filter(transaction__assigned_to=user)
        
        return TransactionDocument.objects.none()
    @action(detail=True, methods=['post'])
    def stamp(self, request, pk=None):
        """
        An action to stamp a document. This version is robust and matches the DB schema.
        """
        # 1. نحصل على "حاوية المستند" التي تم طلب ختمها
        document_container = self.get_object()

        # 2. من الحاوية، نستخرج "الملف الفعلي" المرتبط بها
        #    نستخدم .files.first() لأن العلاقة قد تحتوي على عدة ملفات
        actual_document = document_container.files.first()

        # 3. طبقة حماية للتأكد من وجود ملف فعلي قبل المتابعة
        if not actual_document or not actual_document.file:
            return Response(
                {'detail': 'خطأ: لا يوجد ملف فعلي مرتبط بهذا السجل ليتم ختمه.'}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        # 4. الآن نتعامل مع الملف الفعلي (actual_document)
        if not actual_document.file.name.lower().endswith('.pdf'):
            return Response(
                {'detail': 'فقط ملفات PDF يمكن ختمها.'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if actual_document.is_stamped:
            return Response(
                {'detail': 'هذا المستند تم ختمه بالفعل.'}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        # 5. نرسل "الملف الفعلي" إلى خدمة الختم
        success, message = stamp_document(actual_document)

        if success:
            # نرجع بيانات "الحاوية" بعد نجاح العملية لتحديث الواجهة
            serializer = self.get_serializer(document_container)
            return Response(serializer.data)
        else:
            return Response(
                {'detail': f'فشل في ختم المستند: {message}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    # === END: الاستبدال ينتهي هنا ===


class DepartmentViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows departments to be viewed or edited.
    """
    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer
    permission_classes = [IsAuthenticated]

class BudgetViewSet(viewsets.ModelViewSet):
    queryset = Budget.objects.all()
    serializer_class = BudgetSerializer
    permission_classes = [IsAuthenticated]
    
    # فلترة النتائج لعرض ميزانية المشروع المطلوب فقط
    def get_queryset(self):
        queryset = super().get_queryset()
        project_id = self.request.query_params.get('project_id')
        if project_id:
            queryset = queryset.filter(project_id=project_id)
        return queryset

class BudgetItemViewSet(viewsets.ModelViewSet):
    queryset = BudgetItem.objects.all()
    serializer_class = BudgetItemSerializer
    permission_classes = [IsAuthenticated]



class PermissionRequestViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing permission requests.
    """
    queryset = PermissionRequest.objects.all()
    serializer_class = PermissionRequestSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        
        # === START: التصحيح الكامل هنا ===
        # استخدام الطريقة الصحيحة للتحقق من الصلاحية من خلال الدور المخصص
        # الصلاحية المطلوبة هي 'HR_Manage_PermissionRequests'
        if user.is_superuser or (user.role and user.role.permissions.filter(code='HR_Manage_PermissionRequests').exists()):
            status_filter = self.request.query_params.get('status')
            if status_filter:
                return PermissionRequest.objects.filter(status=status_filter.upper()).select_related('requester', 'permission')
            return PermissionRequest.objects.all().select_related('requester', 'permission')
        # === END: التصحيح الكامل هنا ===
        
        # المستخدم العادي يرى طلباته فقط
        return PermissionRequest.objects.filter(requester=user).select_related('requester', 'permission')

    def perform_create(self, serializer):
        serializer.save(requester=self.request.user)

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        # التصحيح هنا أيضاً
        if not (request.user.is_superuser or (request.user.role and request.user.role.permissions.filter(code='HR_Manage_PermissionRequests').exists())):
             return Response({'detail': 'Action forbidden.'}, status=status.HTTP_403_FORBIDDEN)

        permission_request = self.get_object()
        user_to_grant = permission_request.requester
        permission_to_grant = permission_request.permission

        if user_to_grant.role:
            user_to_grant.role.permissions.add(permission_to_grant)
        else:
            return Response({'detail': 'User does not have a role.'}, status=status.HTTP_400_BAD_REQUEST)
        
        permission_request.status = 'APPROVED'
        permission_request.reviewed_by = request.user
        permission_request.reviewed_at = timezone.now()
        permission_request.save()
        return Response({'status': 'Permission granted'})

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        # التصحيح هنا أيضاً
        if not (request.user.is_superuser or (request.user.role and request.user.role.permissions.filter(code='HR_Manage_PermissionRequests').exists())):
             return Response({'detail': 'Action forbidden.'}, status=status.HTTP_403_FORBIDDEN)

        permission_request = self.get_object()
        permission_request.status = 'REJECTED'
        permission_request.reviewed_by = request.user
        permission_request.reviewed_at = timezone.now()
        permission_request.save()
        return Response({'status': 'Request rejected'})


    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated]) # Add appropriate admin permission
    def approve(self, request, pk=None):
        """
        Approves a permission request.
        """
        permission_request = self.get_object()
        user_to_grant = permission_request.requester
        permission_to_grant = permission_request.permission

        # إضافة الصلاحية لدور المستخدم
        if user_to_grant.role:
            user_to_grant.role.permissions.add(permission_to_grant)
            user_to_grant.role.save()
        else:
            return Response({'detail': 'User does not have a role to add permissions to.'}, status=status.HTTP_400_BAD_REQUEST)
        
        permission_request.status = 'APPROVED'
        permission_request.reviewed_by = request.user
        permission_request.reviewed_at = timezone.now()
        permission_request.save()

        return Response({'status': 'Permission granted and request approved'})

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated]) # Add appropriate admin permission
    def reject(self, request, pk=None):
        """
        Rejects a permission request.
        """
        permission_request = self.get_object()
        permission_request.status = 'REJECTED'
        permission_request.reviewed_by = request.user
        permission_request.reviewed_at = timezone.now()
        permission_request.save()
        
        return Response({'status': 'Request rejected'})
    

class AttendanceViewSet(
    mixins.ListModelMixin, 
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet
):
    """
    ViewSet for listing attendance records and handling check-in/out actions.
    """
    serializer_class = AttendanceSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['employee', 'date']

    def get_queryset(self):
        user = self.request.user
        
        # التحقق من صلاحية عرض جميع سجلات الحضور
        if user.is_superuser or (user.role and user.role.permissions.filter(code='PERM004').exists()):
            return Attendance.objects.select_related(
                'employee', 'employee__department'
            ).all().order_by('-date', '-check_in')
        
        # إذا لم يكن لديه صلاحية، لا تعرض أي شيء
        return Attendance.objects.none()

    @action(detail=False, methods=['post'])
    def check_in(self, request):
        user = request.user
        today = timezone.now().date()
        if Attendance.objects.filter(employee=user, date=today).exists():
            return Response({'detail': 'لقد قمت بتسجيل الحضور بالفعل لهذا اليوم.'}, status=status.HTTP_400_BAD_REQUEST)
        Attendance.objects.create(employee=user, check_in=timezone.now())
        return Response({'status': 'تم تسجيل الحضور بنجاح'}, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'])
    def check_out(self, request):
        user = request.user
        today = timezone.now().date()
        try:
            attendance_record = Attendance.objects.get(employee=user, date=today, check_out__isnull=True)
        except Attendance.DoesNotExist:
            return Response({'detail': 'لم يتم العثور على سجل حضور مفتوح لهذا اليوم.'}, status=status.HTTP_404_NOT_FOUND)
        attendance_record.check_out = timezone.now()
        attendance_record.save()
        return Response({'status': 'تم تسجيل الانصراف بنجاح'}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'])
    def my_status(self, request):
        user = request.user
        today = timezone.now().date()
        try:
            record = Attendance.objects.get(employee=user, date=today)
            status_data = {
                'checked_in': True,
                'check_in_time': record.check_in,
                'checked_out': record.check_out is not None,
                'check_out_time': record.check_out
            }
            return Response(status_data)
        except Attendance.DoesNotExist:
            return Response({'checked_in': False})

# في ملف core/views.py

class LeaveRequestViewSet(viewsets.ModelViewSet):
    serializer_class = LeaveRequestSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        # المدراء ومن لديهم صلاحية يرون طلبات القسم أو كل الطلبات
        if user.is_superuser or (user.role and user.role.permissions.filter(code='HR_LeaveRequests_View').exists()):
            return LeaveRequest.objects.all().order_by('-start_date')
        
        if user.role and user.role.permissions.filter(code='HR_DepartmentLeaves_View').exists() and user.department:
            return LeaveRequest.objects.filter(employee__department=user.department).order_by('-start_date')

        # الخيار الافتراضي الآمن هو إرجاع لا شيء
        return LeaveRequest.objects.none()

    # === START: التصحيح الكامل هنا ===
    def perform_create(self, serializer):
        """
        هذه الدالة تضمن أن أي طلب إجازة جديد يتم إنشاؤه
        يتم ربطه تلقائيًا بالموظف الذي قام بتسجيل الدخول.
        """
        serializer.save(employee=self.request.user)
    # === END: التصحيح الكامل هنا ===

    @action(detail=False, methods=['get'])
    def my_requests(self, request):
        """
        Returns a list of leave requests for the currently authenticated user.
        """
        queryset = LeaveRequest.objects.filter(employee=request.user).order_by('-start_date')
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approve a leave request."""
        if not (request.user.is_superuser or (request.user.role and request.user.role.permissions.filter(code='HR_LeaveRequests_Manage').exists())):
            return Response({'detail': 'Action forbidden.'}, status=status.HTTP_403_FORBIDDEN)
        
        leave_request = self.get_object()
        leave_request.status = 'APPROVED'
        leave_request.save()
        return Response({'status': 'Leave request approved'})

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """Reject a leave request."""
        if not (request.user.is_superuser or (request.user.role and request.user.role.permissions.filter(code='HR_LeaveRequests_Manage').exists())):
            return Response({'detail': 'Action forbidden.'}, status=status.HTTP_403_FORBIDDEN)
            
        leave_request = self.get_object()
        leave_request.status = 'REJECTED'
        leave_request.save()
        return Response({'status': 'Leave request rejected'})

class AccountViewSet(viewsets.ModelViewSet):
    """
    ViewSet for the Chart of Accounts.
    Provides list (tree structure), retrieve, create, update operations.
    """
    queryset = Account.objects.filter(is_active=True)
    serializer_class = AccountSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # نعرض فقط الحسابات الرئيسية (التي ليس لها حساب أصلي)
        # الـ Serializer سيتكفل بعرض الحسابات الفرعية
        return Account.objects.filter(parent__isnull=True, is_active=True)

class JournalEntryViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Journal Entries.
    Handles creation of balanced entries and updates account balances.
    """
    queryset = JournalEntry.objects.prefetch_related('items__account').all()
    serializer_class = JournalEntrySerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

class TrialBalanceView(APIView):
    """
    A view to generate the trial balance report.
    Calculates debit and credit balances for all accounts.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        accounts = Account.objects.filter(is_active=True)

        # === START: التصحيح هنا ===
        # أضفنا output_field=DecimalField() لتحديد نوع بيانات الخرج
        trial_balance_data = accounts.annotate(
            total_debit=Sum(
                Case(
                    When(journal_items__entry_type='DEBIT', then='journal_items__amount'),
                    default=Value(0, output_field=DecimalField()),
                    output_field=DecimalField()
                )
            ),
            total_credit=Sum(
                Case(
                    When(journal_items__entry_type='CREDIT', then='journal_items__amount'),
                    default=Value(0, output_field=DecimalField()),
                    output_field=DecimalField()
                )
            )
        ).values(
            'code',
            'name',
            'account_type',
            'total_debit',
            'total_credit'
        )
        # === END: التصحيح هنا ===

        report = []
        grand_total_debit = 0
        grand_total_credit = 0

        for acc in trial_balance_data:
            debit = acc['total_debit'] or 0
            credit = acc['total_credit'] or 0
            balance = debit - credit
            
            debit_balance = 0
            credit_balance = 0

            if acc['account_type'] in ['ASSET', 'EXPENSE']:
                if balance > 0:
                    debit_balance = balance
                else:
                    credit_balance = -balance
            else: # LIABILITY, EQUITY, REVENUE
                if balance < 0:
                    credit_balance = -balance
                else:
                    debit_balance = balance
            
            if debit_balance > 0 or credit_balance > 0:
                report.append({
                    'code': acc['code'],
                    'name': acc['name'],
                    'debit': debit_balance,
                    'credit': credit_balance,
                })
                grand_total_debit += debit_balance
                grand_total_credit += credit_balance

        return Response({
            'report_lines': report,
            'total_debit': grand_total_debit,
            'total_credit': grand_total_credit,
            'is_balanced': abs(grand_total_debit - grand_total_credit) < 0.001
        })
    
class ReportTemplateViewSet(viewsets.ModelViewSet):
    """ViewSet for managing Report Templates."""
    queryset = ReportTemplate.objects.all()
    serializer_class = ReportTemplateSerializer
    permission_classes = [IsAuthenticated] # يجب تخصيص صلاحية للمدراء فقط

class GenerateReportView(APIView):
    """A view to generate a PDF report from a template and transaction data."""
    permission_classes = [IsAuthenticated]

    def check_permissions(self, request):
        """
        Custom permission check to ensure user can generate reports.
        """
        super().check_permissions(request)
        user = request.user
        # PERM144 = Reports_Generate
        if not (user.is_superuser or (user.role and user.role.permissions.filter(code='PERM144').exists())):
            self.permission_denied(
                request, message='You do not have permission to generate reports.'
            )

    def post(self, request, *args, **kwargs):
        template_id = request.data.get('template_id')
        transaction_id = request.data.get('transaction_id')

        try:
            template_obj = ReportTemplate.objects.get(id=template_id)
            transaction_obj = Transaction.objects.get(id=transaction_id)
        except (ReportTemplate.DoesNotExist, Transaction.DoesNotExist):
            return Response({'detail': 'القالب أو المعاملة غير موجود.'}, status=status.HTTP_404_NOT_FOUND)

        # تجهيز البيانات التي ستُستخدم في القالب
        context_data = {
            'transaction': transaction_obj,
            'client': transaction_obj.client,
            'project': getattr(transaction_obj, 'project', None),
            'today': timezone.now().date(),
        }
        
        # تحويل قالب HTML إلى PDF
        template = Template(template_obj.template_content)
        context = Context(context_data)
        html = template.render(context)
        
        result = BytesIO()
        pdf = pisa.pisaDocument(BytesIO(html.encode("UTF-8")), result)
        
        if not pdf.err:
            file_name = f"report_{transaction_obj.short_code}_{template_obj.name}.pdf"
            generated_report = GeneratedReport.objects.create(
                transaction=transaction_obj,
                template=template_obj,
                created_by=request.user,
            )
            generated_report.generated_file.save(file_name, ContentFile(result.getvalue()))
            
            serializer = GeneratedReportSerializer(generated_report)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        
        return Response({'detail': 'فشل في إنشاء ملف PDF.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet لعرض الإشعارات و التفاعل معها.
    """
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """

        ترجع فقط إشعارات المستخدم الحالي.
        """
        print(f"المستخدم {self.request.user} يطلب قائمة إشعاراته.")
        return Notification.objects.filter(user=self.request.user)

    @action(detail=False, methods=['post'])
    def mark_all_as_read(self, request):
        """
        تحديد كل إشعارات المستخدم كـ 'مقروءة'.
        """
        print(f"المستخدم {request.user} يطلب تحديد كل إشعاراته كمقروءة.")
        try:
            updated_count = Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
            print(f"تم تحديث {updated_count} إشعار.")
            return Response({'status': 'success', 'updated_count': updated_count}, status=status.HTTP_200_OK)
        except Exception as e:
            print(f"خطأ أثناء تحديد الإشعارات كمقروءة: {e}")
            return Response({'status': 'error', 'message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class TransactionDistributionViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing transaction distributions.
    """
    queryset = TransactionDistribution.objects.all()
    serializer_class = TransactionDistributionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        # المدراء ومن لديهم صلاحية التوزيع يرون كل عمليات التوزيع
        if user.is_superuser or (user.role and user.role.permissions.filter(code='Transactions_Assign').exists()):
            return TransactionDistribution.objects.select_related('transaction', 'assigned_from', 'assigned_to').all()
        
        # الموظف العادي يرى فقط المعاملات الموجهة إليه
        return TransactionDistribution.objects.filter(assigned_to=user).select_related('transaction', 'assigned_from', 'assigned_to')

    def perform_create(self, serializer):
        # عند إنشاء توزيع جديد
        assigned_to_user = serializer.validated_data.get('assigned_to')

        # 1. تعيين المدير الذي قام بالتوزيع ليكون المستخدم الحالي
        distribution = serializer.save()
        assigned_user = distribution.assigned_to
        transaction = distribution.transaction
        
        if assigned_user:
            try:
                print(f"سيتم إرسال إشعار للموظف {assigned_user.username} بخصوص إسناد المعاملة.")
                
                create_and_send_notification(
                    user=assigned_user,
                    message=f"تم إسناد المعاملة رقم {transaction.short_code} إليك.",
                    event_type=Notification.EventType.TRANSACTION_ASSIGNED,
                    link=f'/transactions/{transaction.id}',
                    related_object=transaction
                )
            except Exception as e:
                print(f"حدث خطأ أثناء إرسال إشعار إسناد المعاملة: {e}")

        # 2. تحديث المعاملة نفسها وتعيين الموظف وحالتها
        transaction.assigned_to = assigned_to_user
        transaction.status = 'under_review' # تغيير الحالة إلى "قيد المراجعة"
        transaction.save()


class ChatRoomViewSet(viewsets.ModelViewSet):
    """ViewSet لإدارة غرف المحادثة - متاح للجميع"""
    serializer_class = ChatRoomSerializer
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action in ['create', 'update']:
            return CreateChatRoomSerializer
        return ChatRoomSerializer
    
    def get_queryset(self):
        """جميع المستخدمين يمكنهم رؤية الغرف التي هم مشاركون فيها"""
        user = self.request.user
        room_type = self.request.query_params.get('room_type')
        
        queryset = ChatRoom.objects.filter(
            participants=user,
            is_active=True
        ).prefetch_related('participants', 'messages')
        
        if room_type:
            queryset = queryset.filter(room_type=room_type)
        
        return queryset.order_by('-created_at')
    
    def perform_create(self, serializer):
        # لا حاجة لتمرير created_by هنا، لأن الـ serializer يتعامل معه
        serializer.save()
    
    @action(detail=True, methods=['post'])
    def add_participants(self, request, pk=None):
        """إضافة مشاركين جدد للغرفة"""
        room = self.get_object()
        participant_ids = request.data.get('participant_ids', [])
        
        if room.room_type == 'private' and len(participant_ids) > 1:
            return Response(
                {'detail': 'لا يمكن إضافة أكثر من مشارك في المحادثة الخاصة'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        participants = CustomUser.objects.filter(id__in=participant_ids)
        room.participants.add(*participants)
        
        # إرسال إشعار للمشاركين الجدد
        for participant in participants:
            Notification.objects.create(
                user=participant,
                message=f'تمت إضافتك إلى غرفة المحادثة: {room.name}',
                link=f'/chat/{room.id}'
            )
        
        return Response({'status': 'تمت إضافة المشاركين بنجاح'})
    
    @action(detail=True, methods=['post'])
    def leave(self, request, pk=None):
        """مغادرة غرفة المحادثة"""
        room = self.get_object()
        room.participants.remove(request.user)
        
        # إذا كانت غرفة خاصة وأصبحت فارغة، قم بإلغاء تنشيطها
        if room.room_type == 'private' and room.participants.count() < 2:
            room.is_active = False
            room.save()
        
        return Response({'status': 'تم مغادرة الغرفة بنجاح'})

class ChatMessageViewSet(viewsets.ModelViewSet):
    """ViewSet لإدارة الرسائل"""
    serializer_class = ChatMessageSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        room_id = self.kwargs.get('room_pk')
        user = self.request.user
        
        # التحقق من أن المستخدم مشارك في الغرفة
        if not ChatRoom.objects.filter(id=room_id, participants=user, is_active=True).exists():
            return ChatMessage.objects.none()
        
        return ChatMessage.objects.filter(room_id=room_id).select_related(
            'sender', 'sender__department'
        ).order_by('created_at')
    
    @action(detail=False, methods=['post'])
    def mark_all_read(self, request, room_pk=None):
        """تحديد جميع الرسائل في الغرفة كمقروءة"""
        room_id = room_pk
        user = request.user
        
        # تحديث حالة القراءة للرسائل
        messages = ChatMessage.objects.filter(
            room_id=room_id
        ).exclude(sender=user)
        
        for message in messages:
            MessageReadStatus.objects.update_or_create(
                message=message,
                user=user,
                defaults={'is_read': True, 'read_at': timezone.now()}
            )
        
        return Response({'status': 'تم تحديد جميع الرسائل كمقروءة'})
    
    def perform_create(self, serializer):
        room_id = self.kwargs.get('room_pk')
        room = ChatRoom.objects.get(id=room_id)
        
        message = serializer.save(
            sender=self.request.user,
            room=room
        )
        
        # إنشاء سجلات حالة القراءة للمشاركين الآخرين
        participants = room.participants.exclude(id=self.request.user.id)
        print(f"سيتم إرسال إشعار رسالة جديدة إلى {participants.count()} مشارك.")
        for participant in participants:
            # 1. إرسال الإشعار الفوري
            create_and_send_notification(
                user=participant,
                message=f"لديك رسالة جديدة من {message.sender.username} في '{room.name}'.",
                event_type=Notification.EventType.NEW_MESSAGE,
                link=f'/chat?room={room.id}',
                related_object=message
            )

            # 2. تسجيل حالة الرسالة كـ "غير مقروءة" لنفس المشارك
            MessageReadStatus.objects.get_or_create(
                message=message,
                user=participant,
                defaults={'is_read': False}
            )
    

    
    @action(detail=True, methods=['post'])
    def mark_as_read(self, request, room_pk=None, pk=None):
        """تحديد الرسالة كمقروءة"""
        message = self.get_object()
        
        MessageReadStatus.objects.update_or_create(
            message=message,
            user=request.user,
            defaults={'is_read': True, 'read_at': timezone.now()}
        )
        
        return Response({'status': 'تم تحديد الرسالة كمقروءة'})
    
    @action(detail=False, methods=['post'])
    def mark_all_read(self, request, room_pk=None):
        """تحديد جميع الرسائل في الغرفة كمقروءة"""
        room_id = room_pk
        user = request.user

        # تحقق أن المستخدم مشارك في الغرفة
        if not ChatRoom.objects.filter(id=room_id, participants=user, is_active=True).exists():
            return Response({'detail': 'You are not a participant in this room.'},
                            status=status.HTTP_403_FORBIDDEN)

        # تحديث أو إنشاء حالات القراءة لجميع الرسائل في الغرفة
        messages = ChatMessage.objects.filter(
            room_id=room_id
        ).exclude(
            sender=user
        )

        for message in messages:
            MessageReadStatus.objects.update_or_create(
                message=message,
                user=user,
                defaults={
                    'is_read': True,
                    'read_at': timezone.now()
                }
            )

        return Response({'status': 'تم تحديد جميع الرسائل كمقروءة'})


class UserListView(APIView):
    """عرض قائمة المستخدمين المتاحين للمحادثة"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        users = CustomUser.objects.filter(
            is_active=True
        ).exclude(
            id=request.user.id
        ).select_related('department', 'presence')
        
        serializer = ChatUserSerializer(users, many=True, context={'request': request})
        return Response(serializer.data)

class UserPresenceView(APIView):
    """إدارة حالة الاتصال للمستخدم"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        is_online = request.data.get('is_online', True)
        device_token = request.data.get('device_token')
        
        UserPresence.objects.update_or_create(
            user=request.user,
            defaults={
                'is_online': is_online,
                'device_token': device_token,
                'last_seen': timezone.now()
            }
        )
        
        return Response({'status': 'تم تحديث حالة الاتصال'})
    
    def get(self, request):
        try:
            presence = UserPresence.objects.get(user=request.user)
            return Response({
                'is_online': presence.is_online,
                'last_seen': presence.last_seen
            })
        except UserPresence.DoesNotExist:
            return Response({
                'is_online': False,
                'last_seen': None
            })
        
class PusherAuthView(APIView):
    """
    View to authenticate users for private Pusher channels.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        print("--- Pusher authentication request received ---")
        
        pusher_client = pusher.Pusher(
            app_id=settings.PUSHER_APP_ID,
            key=settings.PUSHER_KEY,
            secret=settings.PUSHER_SECRET,
            cluster=settings.PUSHER_CLUSTER,
            ssl=True
        )

        channel_name = request.data.get('channel_name')
        socket_id = request.data.get('socket_id')

        # Basic validation
        if not channel_name or not socket_id:
            print("!!! Pusher Auth Error: Missing channel_name or socket_id")
            return Response({'error': 'channel_name and socket_id are required'}, status=400)

        # Check if the user is authorized for this channel
        # The channel name should be 'private-user-{user.id}'
        expected_channel = f'private-user-{request.user.id}'
        if channel_name != expected_channel:
            print(f"!!! Pusher Auth Error: User {request.user.id} not authorized for channel {channel_name}")
            return Response({'error': 'Forbidden'}, status=403)

        try:
            auth = pusher_client.authenticate(
                channel=channel_name,
                socket_id=socket_id,
                custom_data={
                    'user_id': request.user.id,
                    'user_info': {'username': request.user.username}
                }
            )
            print(f"--- Successfully authenticated user {request.user.id} for Pusher channel {channel_name} ---")
            return Response(auth)

        except Exception as e:
            print(f"!!! Pusher Auth Exception: {e}")
            return Response({'error': 'Authentication failed'}, status=500)
