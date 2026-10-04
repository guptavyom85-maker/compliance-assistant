from django.urls import path
from django.contrib.auth import views as auth_views
from . import views
from . import feature_views as features

app_name = 'qa'
urlpatterns = [
    path('', views.index, name='index'),
    path('ask/', views.ask_question, name='ask'),
    path('answers/<int:pk>/', views.answer_detail, name='answer_detail'),
    path('documents/', views.document_list, name='document_list'),
    path('documents/upload/', views.document_upload, name='document_upload'),
    path('documents/<int:pk>/index/', views.index_document, name='index_document'),
    path('documents/<int:pk>/delete/', views.delete_document, name='delete_document'),
    path('documents/<int:pk>/file/', views.document_file, name='document_file'),
    path('query-log/', views.query_log, name='query_log'),
    path('eval/', views.eval_dashboard, name='eval_dashboard'),
    path('eval/run/', views.run_eval, name='run_eval'),
    path('evaluation/', views.eval_dashboard, name='evaluation'),
    path('evaluation/gold/<int:pk>/', views.gold_review, name='gold_review'),
    path('evaluation/results/<int:pk>/review/', features.judge_review, name='judge_review'),
    path('system/index-status/', views.index_status, name='index_status'),
    path('obligations/', features.obligations, name='obligations'),
    path('obligations/extract/<int:pk>/', features.extract, name='extract_obligations'),
    path('obligations/<int:pk>/review/', features.obligation_review, name='obligation_review'),
    path('gap-analyses/new/', features.gap_create, name='gap_create'),
    path('gap-analyses/<int:pk>/', features.gap_detail, name='gap_detail'),
    path('gap-analyses/<int:pk>/pdf/', features.gap_export, name='gap_export'),
    path('gap-findings/<int:pk>/review/', features.gap_review, name='gap_review'),
    path('review/', features.review_queue, name='review_queue'),
    path('review/<str:kind>/<int:pk>/', features.resolve_review, name='resolve_review'),
    path('analytics/', features.analytics, name='analytics'),
    path('trust/', features.trust, name='trust'),
    path('login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
]
