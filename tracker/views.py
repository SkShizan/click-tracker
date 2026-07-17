import json
import requests
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages
from django.db.models import Count
from .models import Project, ButtonTracker, ClickEvent


# --- Authentication ---
def register(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Account created successfully! Welcome aboard.')
            return redirect('dashboard')
    else:
        form = UserCreationForm()
    return render(request, 'registration/register.html', {'form': form})


# --- LEVEL 1: Main Dashboard ---
@login_required
def main_dashboard(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        if name:
            Project.objects.create(user=request.user, name=name, description=description)
            messages.success(request, f'Project "{name}" created successfully.')
            return redirect('dashboard')
        else:
            messages.error(request, 'Project name cannot be empty.')

    projects = request.user.projects.annotate(
        button_count=Count('buttons'),
        click_count=Count('buttons__clicks')
    ).order_by('-created_at')

    total_projects = projects.count()
    total_buttons = ButtonTracker.objects.filter(project__user=request.user).count()
    total_clicks = ClickEvent.objects.filter(tracker__project__user=request.user).count()

    context = {
        'projects': projects,
        'total_projects': total_projects,
        'total_buttons': total_buttons,
        'total_clicks': total_clicks,
    }
    return render(request, 'tracker/main_dashboard.html', context)


@login_required
def delete_project(request, project_id):
    project = get_object_or_404(Project, id=project_id, user=request.user)
    if request.method == 'POST':
        name = project.name
        project.delete()
        messages.success(request, f'Project "{name}" deleted.')
    return redirect('dashboard')


# --- LEVEL 2: Project Dashboard ---
@login_required
def project_dashboard(request, project_id):
    project = get_object_or_404(Project, id=project_id, user=request.user)

    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        description = request.POST.get('description', '').strip()
        if title:
            ButtonTracker.objects.create(project=project, title=title, description=description)
            messages.success(request, f'Button tracker "{title}" created.')
            return redirect('project_dashboard', project_id=project.id)
        else:
            messages.error(request, 'Button name cannot be empty.')

    buttons = project.buttons.annotate(click_count=Count('clicks')).order_by('-created_at')
    total_clicks = ClickEvent.objects.filter(tracker__project=project).count()

    context = {
        'project': project,
        'buttons': buttons,
        'total_clicks': total_clicks,
    }
    return render(request, 'tracker/project_dashboard.html', context)


@login_required
def delete_button(request, tracker_id):
    tracker = get_object_or_404(ButtonTracker, id=tracker_id, project__user=request.user)
    project_id = tracker.project.id
    if request.method == 'POST':
        title = tracker.title
        tracker.delete()
        messages.success(request, f'Button tracker "{title}" deleted.')
    return redirect('project_dashboard', project_id=project_id)


# --- LEVEL 3: Button Analytics ---
@login_required
def button_analytics(request, tracker_id):
    tracker = get_object_or_404(ButtonTracker, id=tracker_id, project__user=request.user)
    clicks = tracker.clicks.all().order_by('-clicked_at')

    # Aggregate stats
    total = clicks.count()
    unique_countries = clicks.exclude(country='').values('country').distinct().count()
    unique_ips = clicks.exclude(ip_address=None).values('ip_address').distinct().count()

    return render(request, 'tracker/button_analytics.html', {
        'tracker': tracker,
        'project': tracker.project,
        'clicks': clicks,
        'total': total,
        'unique_countries': unique_countries,
        'unique_ips': unique_ips,
    })


# --- API ENDPOINTS ---
def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


@csrf_exempt
def track_click(request, tracker_id):
    if request.method == 'POST':
        try:
            tracker = get_object_or_404(ButtonTracker, id=tracker_id)
            data = json.loads(request.body)
            page_url = data.get('url', '')
            user_agent = request.META.get('HTTP_USER_AGENT', '')

            ip_address = data.get('ip') or get_client_ip(request)
            city = data.get('city', '')
            country = data.get('country', '')

            if not city and ip_address and ip_address not in ('127.0.0.1', '::1'):
                try:
                    geo = requests.get(f'http://ip-api.com/json/{ip_address}', timeout=2).json()
                    city = geo.get('city', '')
                    country = geo.get('country', '')
                except Exception:
                    pass

            ClickEvent.objects.create(
                tracker=tracker,
                ip_address=ip_address,
                city=city,
                country=country,
                page_url=page_url,
                user_agent=user_agent,
            )
            return JsonResponse({'status': 'success'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'invalid method'}, status=405)
