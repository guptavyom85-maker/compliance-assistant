from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

app_name = 'qa'

urlpatterns = [
    path('', views.index, name='index'),
    path('ask/', views.ask_question, name='ask'),
    path('documents/', views.document_list, name='document_list'),
    path('documents/upload/', views.document_upload, name='document_upload'),
    path('documents/<int:pk>/index/', views.index_document, name='index_document'),
    path('documents/<int:pk>/delete/', views.delete_document, name='delete_document'),
    path('query-log/', views.query_log, name='query_log'),
    path('eval/', views.eval_dashboard, name='eval_dashboard'),
    path('eval/run/', views.run_eval, name='run_eval'),
    path('login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
]
