import json
import requests
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .models import Project, ButtonTracker, ClickEvent

# --- Authentication (Keep the same) ---
def register(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('login')
    else:
        form = UserCreationForm()
    return render(request, 'registration/register.html', {'form': form})

# --- LEVEL 1: Main Dashboard (Overall Analytics & Projects) ---
@login_required
def main_dashboard(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description')
        if name:
            Project.objects.create(user=request.user, name=name, description=description)
            return redirect('dashboard')
            
    projects = request.user.projects.all().order_by('-created_at')
    
    # Overall Analytics calculations
    total_projects = projects.count()
    total_buttons = ButtonTracker.objects.filter(project__user=request.user).count()
    total_clicks = ClickEvent.objects.filter(tracker__project__user=request.user).count()
    
    context = {
        'projects': projects,
        'total_projects': total_projects,
        'total_buttons': total_buttons,
        'total_clicks': total_clicks
    }
    return render(request, 'tracker/main_dashboard.html', context)

# --- LEVEL 2: Project Dashboard (Project Analytics & Buttons) ---
@login_required
def project_dashboard(request, project_id):
    project = get_object_or_404(Project, id=project_id, user=request.user)
    
    if request.method == 'POST':
        title = request.POST.get('title')
        description = request.POST.get('description')
        if title:
            ButtonTracker.objects.create(project=project, title=title, description=description)
            return redirect('project_dashboard', project_id=project.id)
            
    buttons = project.buttons.all().order_by('-created_at')
    total_clicks = ClickEvent.objects.filter(tracker__project=project).count()
    
    context = {
        'project': project,
        'buttons': buttons,
        'total_clicks': total_clicks
    }
    return render(request, 'tracker/project_dashboard.html', context)

# --- LEVEL 3: Button Analytics (Specific Click Data) ---
@login_required
def button_analytics(request, tracker_id):
    # Ensure the user actually owns the project this button belongs to
    tracker = get_object_or_404(ButtonTracker, id=tracker_id, project__user=request.user)
    clicks = tracker.clicks.all().order_by('-clicked_at')
    
    return render(request, 'tracker/button_analytics.html', {
        'tracker': tracker, 
        'project': tracker.project,
        'clicks': clicks
    })

# --- API ENDPOINTS (Keep the same) ---
def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for: return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')

@csrf_exempt
def track_click(request, tracker_id):
    if request.method == 'POST':
        try:
            tracker = get_object_or_404(ButtonTracker, id=tracker_id)
            data = json.loads(request.body)
            page_url = data.get('url', '')
            user_agent = request.META.get('HTTP_USER_AGENT', '')
            ip_address = get_client_ip(request)

            city, country = "", ""
            if ip_address and ip_address != '127.0.0.1':
                try:
                    geo = requests.get(f'http://ip-api.com/json/{ip_address}', timeout=2).json()
                    city, country = geo.get('city', ''), geo.get('country', '')
                except: pass

            ClickEvent.objects.create(tracker=tracker, ip_address=ip_address, city=city, country=country, page_url=page_url, user_agent=user_agent)
            return JsonResponse({'status': 'success'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'invalid method'}, status=405)