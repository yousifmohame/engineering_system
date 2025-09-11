from django.urls import path, include
from rest_framework_nested import routers
from .views import *

# === المسجل الرئيسي ===
router = routers.DefaultRouter()

# وحدات الإدارة الأساسية
router.register(r'users', UserViewSet, basename='user')
router.register(r'roles', RoleViewSet, basename='role')
router.register(r'permissions', PermissionViewSet, basename='permission')
router.register(r'staff', StaffViewSet, basename='staff')

# وحدات العمل الرئيسية
router.register(r'transactions', TransactionViewSet, basename='transaction')
router.register(r'clients', ClientViewSet, basename='client')
router.register(r'tasks', TaskViewSet, basename='task')
router.register(r'invoices', InvoiceViewSet, basename='invoice')

# وحدات البيانات المساعدة
router.register(r'transaction-main-categories', TransactionMainCategoryViewSet, basename='maincategory')
router.register(r'transaction-sub-categories', TransactionSubCategoryViewSet, basename='subcategory')
router.register(r'competent-authorities', CompetentAuthorityViewSet, basename='authority')
router.register(r'transaction-documents', TransactionDocumentViewSet, basename='transactiondocument')
router.register(r'documents', DocumentViewSet, basename='document')
router.register(r'departments', DepartmentViewSet, basename='department')
router.register(r'budgets', BudgetViewSet, basename='budget')
router.register(r'budget-items', BudgetItemViewSet, basename='budget-item')
router.register(r'projects', ProjectViewSet, basename='project')
router.register(r'permission-requests', PermissionRequestViewSet, basename='permission-request')
router.register(r'attendance', AttendanceViewSet, basename='attendance')
router.register(r'leave-requests', LeaveRequestViewSet, basename='leaverequest')
router.register(r'accounts', AccountViewSet, basename='account')
router.register(r'journal-entries', JournalEntryViewSet, basename='journalentry')
router.register(r'report-templates', ReportTemplateViewSet, basename='report-template')
router.register(r'notifications', NotificationViewSet, basename='notification')
router.register(r'transaction-distributions', TransactionDistributionViewSet, basename='transactiondistribution')
router.register(r'chat/rooms', ChatRoomViewSet, basename='chat-room')

# === المسجلات المتداخلة ===
transactions_router = routers.NestedSimpleRouter(router, r'transactions', lookup='transaction')
transactions_router.register(r'documents', DocumentViewSet, basename='transaction-documents')

transaction_docs_router = routers.NestedSimpleRouter(router, r'transaction-documents', lookup='transaction_document')
transaction_docs_router.register(r'documents', DocumentViewSet, basename='transaction-document-files')

chat_router = routers.NestedSimpleRouter(router, r'chat/rooms', lookup='room')
chat_router.register(r'messages', ChatMessageViewSet, basename='chat-message')

# === أنماط URL ===
urlpatterns = [
    path('dashboard-stats/', DashboardStatsView.as_view(), name='dashboard-stats'),
    path('', include(router.urls)),
    path('', include(transactions_router.urls)),
    path('', include(transaction_docs_router.urls)),
    path('', include(chat_router.urls)),
    path('accounting/trial-balance/', TrialBalanceView.as_view(), name='trial-balance'),
    path('reports/generate/', GenerateReportView.as_view(), name='generate-report'),
    path('chat/users/', UserListView.as_view(), name='chat-users'),
    path('chat/presence/', UserPresenceView.as_view(), name='user-presence'),
    path('pusher/auth/', PusherAuthView.as_view(), name='pusher-auth'),
  
]
