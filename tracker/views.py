import json
import requests
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages
from django.db.models import Count, Min, Max
from .models import Project, ButtonTracker, ClickEvent, SiteTracker, PageClickEvent


# ── Helpers ──────────────────────────────────────────────────────────────────

def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '')


def geo_lookup(ip):
    """Server-side geo lookup. Returns (city, country) or ('', '')."""
    if not ip or ip in ('127.0.0.1', '::1', ''):
        return '', ''
    # Skip RFC-1918 / link-local addresses
    private_prefixes = ('10.', '192.168.', '172.16.', '172.17.', '172.18.',
                        '172.19.', '172.20.', '172.21.', '172.22.', '172.23.',
                        '172.24.', '172.25.', '172.26.', '172.27.', '172.28.',
                        '172.29.', '172.30.', '172.31.', '169.254.', 'fc', 'fd')
    if any(ip.startswith(p) for p in private_prefixes):
        return '', ''
    try:
        geo = requests.get(f'https://ip-api.com/json/{ip}', timeout=3).json()
        if geo.get('status') == 'success':
            return geo.get('city', ''), geo.get('country', '')
    except Exception:
        pass
    return '', ''


def cors_response(data, status=200):
    r = JsonResponse(data, status=status)
    r['Access-Control-Allow-Origin'] = '*'
    r['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
    r['Access-Control-Allow-Headers'] = 'Content-Type'
    return r


def cors_preflight():
    r = JsonResponse({'status': 'ok'})
    r['Access-Control-Allow-Origin'] = '*'
    r['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
    r['Access-Control-Allow-Headers'] = 'Content-Type'
    return r


# ── Authentication ────────────────────────────────────────────────────────────

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


# ── LEVEL 1: Main Dashboard ───────────────────────────────────────────────────

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
    total_site_clicks = PageClickEvent.objects.filter(tracker__project__user=request.user).count()

    context = {
        'projects': projects,
        'total_projects': total_projects,
        'total_buttons': total_buttons,
        'total_clicks': total_clicks + total_site_clicks,
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


# ── LEVEL 2: Project Dashboard ────────────────────────────────────────────────

@login_required
def project_dashboard(request, project_id):
    project = get_object_or_404(Project, id=project_id, user=request.user)

    if request.method == 'POST':
        tracker_type = request.POST.get('tracker_type', 'button')
        title = request.POST.get('title', '').strip()
        description = request.POST.get('description', '').strip()

        if not title:
            messages.error(request, 'Name cannot be empty.')
            return redirect('project_dashboard', project_id=project.id)

        if tracker_type == 'site':
            SiteTracker.objects.create(project=project, name=title, description=description)
            messages.success(request, f'Site tracker "{title}" created.')
        else:
            ButtonTracker.objects.create(project=project, title=title, description=description)
            messages.success(request, f'Button tracker "{title}" created.')

        return redirect('project_dashboard', project_id=project.id)

    buttons = project.buttons.annotate(click_count=Count('clicks')).order_by('-created_at')
    site_trackers = project.site_trackers.annotate(click_count=Count('clicks')).order_by('-created_at')

    total_btn_clicks = ClickEvent.objects.filter(tracker__project=project).count()
    total_site_clicks = PageClickEvent.objects.filter(tracker__project=project).count()
    total_clicks = total_btn_clicks + total_site_clicks

    context = {
        'project': project,
        'buttons': buttons,
        'site_trackers': site_trackers,
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


@login_required
def delete_site_tracker(request, tracker_id):
    tracker = get_object_or_404(SiteTracker, id=tracker_id, project__user=request.user)
    project_id = tracker.project.id
    if request.method == 'POST':
        name = tracker.name
        tracker.delete()
        messages.success(request, f'Site tracker "{name}" deleted.')
    return redirect('project_dashboard', project_id=project_id)


# ── Helpers: IP grouping ──────────────────────────────────────────────────────

def build_ip_groups(clicks):
    """Return list of dicts, one per unique IP, with count/location/ua/times."""
    groups = list(
        clicks.exclude(ip_address=None).exclude(ip_address='')
        .values('ip_address')
        .annotate(
            count=Count('id'),
            first_seen=Min('clicked_at'),
            last_seen=Max('clicked_at'),
        )
        .order_by('-count')
    )
    if not groups:
        return groups

    ips = [g['ip_address'] for g in groups]
    # One sample row per IP for city/country/user_agent
    ip_meta = {}
    for row in clicks.filter(ip_address__in=ips).values('ip_address', 'city', 'country', 'user_agent'):
        ip = row['ip_address']
        if ip not in ip_meta:
            ip_meta[ip] = {'city': row['city'], 'country': row['country'], 'user_agent': row['user_agent']}

    for g in groups:
        meta = ip_meta.get(g['ip_address'], {})
        g['city'] = meta.get('city', '')
        g['country'] = meta.get('country', '')
        g['user_agent'] = meta.get('user_agent', '')

    return groups


# ── LEVEL 3a: Button Analytics ───────────────────────────────────────────────

@login_required
def button_analytics(request, tracker_id):
    tracker = get_object_or_404(ButtonTracker, id=tracker_id, project__user=request.user)
    clicks = tracker.clicks.all().order_by('-clicked_at')

    total = clicks.count()
    unique_countries = clicks.exclude(country='').values('country').distinct().count()
    unique_ips = clicks.exclude(ip_address=None).values('ip_address').distinct().count()
    ip_groups = build_ip_groups(clicks)

    return render(request, 'tracker/button_analytics.html', {
        'tracker': tracker,
        'project': tracker.project,
        'total': total,
        'unique_countries': unique_countries,
        'unique_ips': unique_ips,
        'ip_groups': ip_groups,
    })


# ── LEVEL 3a-detail: Button IP Detail ────────────────────────────────────────

@login_required
def button_ip_detail(request, tracker_id):
    tracker = get_object_or_404(ButtonTracker, id=tracker_id, project__user=request.user)
    ip = request.GET.get('ip', '')
    clicks = tracker.clicks.filter(ip_address=ip).order_by('-clicked_at')

    sample = clicks.first()
    location = ''
    if sample:
        if sample.city and sample.country:
            location = f"{sample.city}, {sample.country}"
        elif sample.country:
            location = sample.country

    return render(request, 'tracker/button_ip_detail.html', {
        'tracker': tracker,
        'project': tracker.project,
        'ip': ip,
        'clicks': clicks,
        'location': location,
        'user_agent': sample.user_agent if sample else '',
        'total': clicks.count(),
    })


# ── LEVEL 3b: Site Tracker Analytics ─────────────────────────────────────────

@login_required
def site_analytics(request, tracker_id):
    tracker = get_object_or_404(SiteTracker, id=tracker_id, project__user=request.user)
    clicks = tracker.clicks.all().order_by('-clicked_at')

    total = clicks.count()
    unique_pages = clicks.exclude(page_url='').values('page_url').distinct().count()
    unique_countries = clicks.exclude(country='').values('country').distinct().count()
    unique_ips = clicks.exclude(ip_address=None).values('ip_address').distinct().count()
    ip_groups = build_ip_groups(clicks)

    top_pages = (
        clicks.exclude(page_url='')
        .values('page_url')
        .annotate(count=Count('id'))
        .order_by('-count')[:10]
    )
    top_elements = (
        clicks.exclude(element_text='')
        .values('element_tag', 'element_text')
        .annotate(count=Count('id'))
        .order_by('-count')[:10]
    )

    return render(request, 'tracker/site_analytics.html', {
        'tracker': tracker,
        'project': tracker.project,
        'total': total,
        'unique_pages': unique_pages,
        'unique_countries': unique_countries,
        'unique_ips': unique_ips,
        'ip_groups': ip_groups,
        'top_pages': top_pages,
        'top_elements': top_elements,
    })


# ── LEVEL 3b-detail: Site IP Detail ──────────────────────────────────────────

@login_required
def site_ip_detail(request, tracker_id):
    tracker = get_object_or_404(SiteTracker, id=tracker_id, project__user=request.user)
    ip = request.GET.get('ip', '')
    clicks = tracker.clicks.filter(ip_address=ip).order_by('-clicked_at')

    sample = clicks.first()
    location = ''
    if sample:
        if sample.city and sample.country:
            location = f"{sample.city}, {sample.country}"
        elif sample.country:
            location = sample.country

    return render(request, 'tracker/site_ip_detail.html', {
        'tracker': tracker,
        'project': tracker.project,
        'ip': ip,
        'clicks': clicks,
        'location': location,
        'user_agent': sample.user_agent if sample else '',
        'total': clicks.count(),
    })


# ── API: Button Click Tracking ────────────────────────────────────────────────

@csrf_exempt
def track_click(request, tracker_id):
    if request.method == 'OPTIONS':
        return cors_preflight()

    if request.method != 'POST':
        return cors_response({'status': 'invalid method'}, 405)

    try:
        tracker = get_object_or_404(ButtonTracker, id=tracker_id)

        body = request.body
        try:
            data = json.loads(body) if body else {}
        except (json.JSONDecodeError, ValueError):
            data = {}

        page_url = data.get('url', '') or data.get('page_url', '')
        referrer = data.get('referrer', '')
        user_agent = request.META.get('HTTP_USER_AGENT', '')

        # Always resolve IP server-side — don't trust client-supplied geo
        ip_address = get_client_ip(request)
        city, country = geo_lookup(ip_address)

        ClickEvent.objects.create(
            tracker=tracker,
            ip_address=ip_address or None,
            city=city,
            country=country,
            page_url=page_url,
            referrer=referrer,
            user_agent=user_agent,
        )
        return cors_response({'status': 'success', 'message': 'Click recorded'})

    except Exception as e:
        return cors_response({'status': 'error', 'message': str(e)}, 400)


# ── API: Site / Auto-Click Tracking ──────────────────────────────────────────

@csrf_exempt
def track_auto_click(request, tracker_id):
    if request.method == 'OPTIONS':
        return cors_preflight()

    if request.method != 'POST':
        return cors_response({'status': 'invalid method'}, 405)

    try:
        tracker = get_object_or_404(SiteTracker, id=tracker_id)

        body = request.body
        try:
            data = json.loads(body) if body else {}
        except (json.JSONDecodeError, ValueError):
            data = {}

        page_url = data.get('page_url', '')
        referrer = data.get('referrer', '')
        element_tag = (data.get('element_tag', '') or '').upper()[:50]
        element_text = (data.get('element_text', '') or '')[:300]
        element_id = (data.get('element_id', '') or '')[:200]
        element_class = (data.get('element_class', '') or '')[:300]
        element_href = (data.get('element_href', '') or '')[:500]
        user_agent = request.META.get('HTTP_USER_AGENT', '')

        ip_address = get_client_ip(request)
        city, country = geo_lookup(ip_address)

        PageClickEvent.objects.create(
            tracker=tracker,
            ip_address=ip_address or None,
            city=city,
            country=country,
            page_url=page_url,
            referrer=referrer,
            element_tag=element_tag,
            element_text=element_text,
            element_id=element_id,
            element_class=element_class,
            element_href=element_href,
            user_agent=user_agent,
        )
        return cors_response({'status': 'success', 'message': 'Click recorded'})

    except Exception as e:
        return cors_response({'status': 'error', 'message': str(e)}, 400)
