from django.contrib import admin
from django.urls import path
from django.contrib.auth import views as auth_views
from django.views.generic import RedirectView
from tracker import views as tracker_views

urlpatterns = [
    path('', RedirectView.as_view(pattern_name='dashboard'), name='home'),
    path('admin/', admin.site.urls),
    
    # Auth
    path('register/', tracker_views.register, name='register'),
    path('login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    
    # 3 Levels of Dashboards
    path('dashboard/', tracker_views.main_dashboard, name='dashboard'),
    path('dashboard/project/<int:project_id>/', tracker_views.project_dashboard, name='project_dashboard'),
    path('dashboard/button/<uuid:tracker_id>/', tracker_views.button_analytics, name='button_analytics'),
    
    # API
    path('api/track/<uuid:tracker_id>/', tracker_views.track_click, name='track_click'),
]