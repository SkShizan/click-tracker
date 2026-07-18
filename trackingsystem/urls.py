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
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),

    # Dashboards
    path('dashboard/', tracker_views.main_dashboard, name='dashboard'),
    path('dashboard/project/<int:project_id>/', tracker_views.project_dashboard, name='project_dashboard'),
    path('dashboard/project/<int:project_id>/delete/', tracker_views.delete_project, name='delete_project'),

    # Button trackers
    path('dashboard/button/<uuid:tracker_id>/', tracker_views.button_analytics, name='button_analytics'),
    path('dashboard/button/<uuid:tracker_id>/delete/', tracker_views.delete_button, name='delete_button'),
    path('dashboard/button/<uuid:tracker_id>/ip/', tracker_views.button_ip_detail, name='button_ip_detail'),

    # Site trackers
    path('dashboard/site/<uuid:tracker_id>/', tracker_views.site_analytics, name='site_analytics'),
    path('dashboard/site/<uuid:tracker_id>/delete/', tracker_views.delete_site_tracker, name='delete_site_tracker'),
    path('dashboard/site/<uuid:tracker_id>/ip/', tracker_views.site_ip_detail, name='site_ip_detail'),

    # API
    path('api/track/<uuid:tracker_id>/', tracker_views.track_click, name='track_click'),
    path('api/autotrack/<uuid:tracker_id>/', tracker_views.track_auto_click, name='track_auto_click'),
]
