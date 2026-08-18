import json
import requests
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages
from django.db.models import Count, Min, Max, Avg
from .models import PageClickEvent, Project, ButtonTracker, ClickEvent, SiteTracker
import requests
import time
from django.db.models import Q

def get_client_ip(request):
    """Safely extract the user's real IP address."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        # Proxies can append multiple IPs; the first one is the client.
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

def get_ip_location(ip_address):
    """Fetch location data for a given IP."""
    # 1. Handle empty or None IP addresses immediately
    if not ip_address:
        return {"city": "Unknown", "country": "Unknown", "isp": "Unknown"}

    # 2. Localhost won't return geolocation data
    if ip_address in ['127.0.0.1', 'localhost', '::1']:
        return {"city": "Localhost", "country": "Localhost", "isp": "Local Network"}

    try:
        clean_ip = str(ip_address).strip()
        # Switched to ip-api.com over HTTP to bypass hosting proxy restrictions
        response = requests.get(f"http://ip-api.com/json/{clean_ip}", timeout=5)
        data = response.json()

        # 3. If the API successfully finds the IP (ip-api uses 'status': 'success')
        if data.get("status") == "success":
            return {
                "city": data.get("city", "Unknown"),
                "country": data.get("country", "Unknown"),
                "isp": data.get("isp", "Unknown"),
                "lat": data.get("lat"),
                "lon": data.get("lon"),
            }
        else:
            print(f"API Error for IP {clean_ip}: {data.get('message', 'No message provided')}")

    except requests.exceptions.RequestException as e:
        print(f"Network error while fetching IP location: {e}")

    return {"city": "Unknown", "country": "Unknown", "isp": "Unknown"}

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

    # Public share link
    public_link = None
    try:
        from .models import PublicShareLink
        public_link = project.public_link
    except Exception:
        pass

    context = {
        'project': project,
        'buttons': buttons,
        'site_trackers': site_trackers,
        'total_clicks': total_clicks,
        'public_link': public_link,
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
        clicks.exclude(ip_address=None)
        .values('ip_address')
        .annotate(
            count=Count('id'),
            first_seen=Min('clicked_at'),
            last_seen=Max('clicked_at'),
        )
        .order_by('-count')
    )

    # Also count clicks where IP could not be resolved (null) and add as Unknown group
    unknown_count = clicks.filter(ip_address=None).count()
    if unknown_count > 0:
        from django.db.models import Min as _Min, Max as _Max
        unk_qs = clicks.filter(ip_address=None)
        unk_agg = unk_qs.aggregate(first_seen=_Min('clicked_at'), last_seen=_Max('clicked_at'))
        sample = unk_qs.values('city', 'country', 'user_agent').first() or {}
        groups.append({
            'ip_address': None,
            'count': unknown_count,
            'first_seen': unk_agg['first_seen'],
            'last_seen': unk_agg['last_seen'],
            'city': sample.get('city', ''),
            'country': sample.get('country', ''),
            'user_agent': sample.get('user_agent', ''),
        })

    if not groups:
        return groups

    ips = [g['ip_address'] for g in groups if g['ip_address']]
    # One sample row per IP for city/country/user_agent
    ip_meta = {}
    for row in clicks.filter(ip_address__in=ips).values('ip_address', 'city', 'country', 'user_agent'):
        ip = row['ip_address']
        if ip not in ip_meta:
            ip_meta[ip] = {'city': row['city'], 'country': row['country'], 'user_agent': row['user_agent']}

    for g in groups:
        if g['ip_address'] is None:
            continue  # already enriched above
        meta = ip_meta.get(g['ip_address'], {})
        g['city'] = meta.get('city', '')
        g['country'] = meta.get('country', '')
        g['user_agent'] = meta.get('user_agent', '')

    return groups


# ── LEVEL 3a: Button Analytics ───────────────────────────────────────────────

@login_required
def button_analytics(request, tracker_id):
    tracker = get_object_or_404(ButtonTracker, id=tracker_id, project__user=request.user)

    # Date range filtering
    date_from, date_to = parse_date_range(request)
    clicks = tracker.clicks.all().order_by('-clicked_at')
    clicks = filter_clicks_by_date(clicks, date_from, date_to)

    total = clicks.count()
    unique_countries = clicks.exclude(country='').values('country').distinct().count()
    unique_ips = clicks.exclude(ip_address=None).values('ip_address').distinct().count()
    ip_groups = build_ip_groups(clicks)

    # Chart data
    daily_clicks = json.dumps(compute_daily_clicks(clicks))
    country_data = json.dumps(compute_country_distribution(clicks))
    country_map_json = json.dumps(compute_country_map_data(clicks))
    city_map_json = json.dumps(compute_city_map_data(clicks))

    return render(request, 'tracker/button_analytics.html', {
        'tracker': tracker,
        'project': tracker.project,
        'total': total,
        'unique_countries': unique_countries,
        'unique_ips': unique_ips,
        'ip_groups': ip_groups,
        'daily_clicks': daily_clicks,
        'country_data': country_data,
        'country_map_json': country_map_json,
        'city_map_json': city_map_json,
        'date_from': date_from.strftime('%Y-%m-%d') if date_from else '',
        'date_to': date_to.strftime('%Y-%m-%d') if date_to else '',
    })


# ── LEVEL 3a-detail: Button IP Detail ────────────────────────────────────────

@login_required
def button_ip_detail(request, tracker_id):
    tracker = get_object_or_404(ButtonTracker, id=tracker_id, project__user=request.user)
    ip = request.GET.get('ip', '')
    unknown = (ip == '__unknown__')
    if unknown:
        clicks = tracker.clicks.filter(ip_address=None).order_by('-clicked_at')
    else:
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
        'unknown': unknown,
        'clicks': clicks,
        'location': location,
        'user_agent': sample.user_agent if sample else '',
        'total': clicks.count(),
    })


# ── Helpers: chart data ───────────────────────────────────────────────────────

from datetime import datetime, timedelta
from django.db.models.functions import TruncDate
from collections import Counter
import re as _re

def parse_date_range(request):
    """Parse from/to date query params. Returns (date_from, date_to) or (None, None)."""
    date_from = request.GET.get('from', '')
    date_to = request.GET.get('to', '')
    try:
        date_from = datetime.strptime(date_from, '%Y-%m-%d').date() if date_from else None
    except ValueError:
        date_from = None
    try:
        date_to = datetime.strptime(date_to, '%Y-%m-%d').date() if date_to else None
    except ValueError:
        date_to = None
    return date_from, date_to


def filter_clicks_by_date(clicks, date_from, date_to):
    """Apply date range filter to a queryset."""
    if date_from:
        clicks = clicks.filter(clicked_at__date__gte=date_from)
    if date_to:
        clicks = clicks.filter(clicked_at__date__lte=date_to)
    return clicks


def compute_daily_clicks(clicks):
    """Return list of {date: 'YYYY-MM-DD', count: N} for chart."""
    daily = (
        clicks.annotate(day=TruncDate('clicked_at'))
        .values('day')
        .annotate(count=Count('id'))
        .order_by('day')
    )
    return [{'date': d['day'].strftime('%Y-%m-%d'), 'count': d['count']} for d in daily if d['day']]


def compute_country_distribution(clicks):
    """Return list of {country: str, count: N} for doughnut chart."""
    countries = (
        clicks.exclude(country='')
        .values('country')
        .annotate(count=Count('id'))
        .order_by('-count')[:10]
    )
    return [{'country': c['country'], 'count': c['count']} for c in countries]


def parse_browser(ua):
    """Extract browser name from user agent string."""
    if not ua:
        return 'Unknown'
    ua_lower = ua.lower()
    if 'edg' in ua_lower:
        return 'Edge'
    if 'chrome' in ua_lower and 'chromium' not in ua_lower:
        return 'Chrome'
    if 'firefox' in ua_lower:
        return 'Firefox'
    if 'safari' in ua_lower and 'chrome' not in ua_lower:
        return 'Safari'
    if 'opera' in ua_lower or 'opr' in ua_lower:
        return 'Opera'
    return 'Other'


def parse_device(ua):
    """Extract device type from user agent string."""
    if not ua:
        return 'Unknown'
    ua_lower = ua.lower()
    if 'mobile' in ua_lower or 'android' in ua_lower and 'tablet' not in ua_lower:
        return 'Mobile'
    if 'tablet' in ua_lower or 'ipad' in ua_lower:
        return 'Tablet'
    return 'Desktop'


def compute_browser_breakdown(clicks):
    """Return browser distribution from user agents."""
    agents = clicks.exclude(user_agent='').values_list('user_agent', flat=True)
    counter = Counter(parse_browser(ua) for ua in agents)
    return [{'name': k, 'count': v} for k, v in counter.most_common(6)]


def compute_device_breakdown(clicks):
    """Return device type distribution."""
    agents = clicks.exclude(user_agent='').values_list('user_agent', flat=True)
    counter = Counter(parse_device(ua) for ua in agents)
    return [{'name': k, 'count': v} for k, v in counter.most_common(5)]


def compute_city_distribution(clicks):
    """Return list of {city, country, count} for city-level bar chart."""
    cities = (
        clicks.exclude(city='')
        .values('city', 'country')
        .annotate(count=Count('id'))
        .order_by('-count')[:15]
    )
    return [{'city': c['city'], 'country': c['country'] or '', 'count': c['count']} for c in cities]


def compute_location_points(clicks):
    """Return unique IP locations for map/location visualization."""
    # Group by city+country and count
    locations = (
        clicks.exclude(city='').exclude(country='')
        .values('city', 'country')
        .annotate(count=Count('id'))
        .order_by('-count')[:50]
    )
    return [{'city': l['city'], 'country': l['country'], 'count': l['count']} for l in locations]


def compute_country_map_data(clicks):
    """Return map data aggregated by country with approx center lat/lon."""
    locations = (
        clicks.exclude(country='').exclude(latitude__isnull=True)
        .values('country')
        .annotate(count=Count('id'), lat=Avg('latitude'), lon=Avg('longitude'))
        .order_by('-count')[:50]
    )
    return [{'country': l['country'], 'lat': l['lat'], 'lon': l['lon'], 'count': l['count']} for l in locations]


def compute_city_map_data(clicks):
    """Return map data aggregated by city exact lat/lon."""
    locations = (
        clicks.exclude(city='').exclude(latitude__isnull=True)
        .values('city', 'country', 'latitude', 'longitude')
        .annotate(count=Count('id'))
        .order_by('-count')[:100]
    )
    return [{'city': l['city'], 'country': l['country'], 'lat': l['latitude'], 'lon': l['longitude'], 'count': l['count']} for l in locations]


# ── LEVEL 3b: Site Tracker Analytics ─────────────────────────────────────────

@login_required
def site_analytics(request, tracker_id):
    tracker = get_object_or_404(SiteTracker, id=tracker_id, project__user=request.user)

    # Date range filtering
    date_from, date_to = parse_date_range(request)
    clicks = tracker.clicks.all().order_by('-clicked_at')
    clicks = filter_clicks_by_date(clicks, date_from, date_to)

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

    # Chart data (JSON-safe)
    daily_clicks = json.dumps(compute_daily_clicks(clicks))
    country_data = json.dumps(compute_country_distribution(clicks))
    browser_data = json.dumps(compute_browser_breakdown(clicks))
    device_data = json.dumps(compute_device_breakdown(clicks))
    city_data = json.dumps(compute_city_distribution(clicks))
    location_data = json.dumps(compute_location_points(clicks))
    country_map_json = json.dumps(compute_country_map_data(clicks))
    city_map_json = json.dumps(compute_city_map_data(clicks))

    # Table sort
    sort_by = request.GET.get('sort', 'recent')  # 'recent' or 'clicks'

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
        'daily_clicks': daily_clicks,
        'country_data': country_data,
        'browser_data': browser_data,
        'device_data': device_data,
        'city_data': city_data,
        'location_data': location_data,
        'country_map_json': country_map_json,
        'city_map_json': city_map_json,
        'sort_by': sort_by,
        'date_from': date_from.strftime('%Y-%m-%d') if date_from else '',
        'date_to': date_to.strftime('%Y-%m-%d') if date_to else '',
    })


# ── LEVEL 3b-detail: Site IP Detail ──────────────────────────────────────────

@login_required
def site_ip_detail(request, tracker_id):
    tracker = get_object_or_404(SiteTracker, id=tracker_id, project__user=request.user)
    ip = request.GET.get('ip', '')
    unknown = (ip == '__unknown__')
    if unknown:
        clicks = tracker.clicks.filter(ip_address=None).order_by('-clicked_at')
    else:
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
        'unknown': unknown,
        'clicks': clicks,
        'location': location,
        'user_agent': sample.user_agent if sample else '',
        'total': clicks.count(),
    })


# ── MASTER PROJECT DASHBOARD ─────────────────────────────────────────────────

@login_required
def master_project_dashboard(request, project_id):
    project = get_object_or_404(Project, id=project_id, user=request.user)
    date_from, date_to = parse_date_range(request)

    # Gather all clicks from both tracker types
    btn_clicks = ClickEvent.objects.filter(tracker__project=project)
    site_clicks = PageClickEvent.objects.filter(tracker__project=project)
    btn_clicks = filter_clicks_by_date(btn_clicks, date_from, date_to)
    site_clicks = filter_clicks_by_date(site_clicks, date_from, date_to)

    total_btn = btn_clicks.count()
    total_site = site_clicks.count()
    total_clicks = total_btn + total_site

    # Unique visitors (IPs across both)
    btn_ips = set(btn_clicks.exclude(ip_address=None).values_list('ip_address', flat=True).distinct())
    site_ips = set(site_clicks.exclude(ip_address=None).values_list('ip_address', flat=True).distinct())
    all_ips = btn_ips | site_ips
    unique_visitors = len(all_ips)

    # Unique countries
    btn_countries = set(btn_clicks.exclude(country='').values_list('country', flat=True).distinct())
    site_countries = set(site_clicks.exclude(country='').values_list('country', flat=True).distinct())
    all_countries = btn_countries | site_countries
    unique_countries = len(all_countries)

    # Unique pages (site trackers only)
    unique_pages = site_clicks.exclude(page_url='').values('page_url').distinct().count()

    # Avg clicks per day
    btn_daily = compute_daily_clicks(btn_clicks)
    site_daily = compute_daily_clicks(site_clicks)
    # Merge daily counts
    daily_map = {}
    for d in btn_daily:
        daily_map[d['date']] = daily_map.get(d['date'], 0) + d['count']
    for d in site_daily:
        daily_map[d['date']] = daily_map.get(d['date'], 0) + d['count']
    merged_daily = sorted([{'date': k, 'count': v} for k, v in daily_map.items()], key=lambda x: x['date'])
    avg_clicks_day = round(sum(d['count'] for d in merged_daily) / max(len(merged_daily), 1), 1)

    # Trackers count
    total_btn_trackers = project.buttons.count()
    total_site_trackers = project.site_trackers.count()

    # Chart data: daily trend (separate series for button vs site)
    daily_btn_json = json.dumps(btn_daily)
    daily_site_json = json.dumps(site_daily)
    daily_total_json = json.dumps(merged_daily)

    # Country distribution (merge)
    btn_country = compute_country_distribution(btn_clicks)
    site_country = compute_country_distribution(site_clicks)
    country_map = {}
    for c in btn_country:
        country_map[c['country']] = country_map.get(c['country'], 0) + c['count']
    for c in site_country:
        country_map[c['country']] = country_map.get(c['country'], 0) + c['count']
    merged_countries = sorted([{'country': k, 'count': v} for k, v in country_map.items()], key=lambda x: -x['count'])[:10]
    country_json = json.dumps(merged_countries)

    # Browser / Device breakdown (from site clicks which have user_agent)
    browser_json = json.dumps(compute_browser_breakdown(site_clicks))
    device_json = json.dumps(compute_device_breakdown(site_clicks))

    # City distribution (merge btn + site)
    btn_city = compute_city_distribution(btn_clicks)
    site_city = compute_city_distribution(site_clicks)
    city_map = {}
    for c in btn_city:
        key = f"{c['city']}|{c['country']}"
        city_map[key] = {'city': c['city'], 'country': c['country'], 'count': city_map.get(key, {}).get('count', 0) + c['count']}
    for c in site_city:
        key = f"{c['city']}|{c['country']}"
        city_map[key] = {'city': c['city'], 'country': c['country'], 'count': city_map.get(key, {}).get('count', 0) + c['count']}
    merged_cities = sorted(city_map.values(), key=lambda x: -x['count'])[:15]
    city_json = json.dumps(merged_cities)

    # Location points for map
    location_json = json.dumps(compute_location_points(site_clicks))

    # Leaflet Maps JSON data (merge btn + site)
    btn_country_map = compute_country_map_data(btn_clicks)
    site_country_map = compute_country_map_data(site_clicks)
    country_map_dict = {}
    for c in btn_country_map + site_country_map:
        key = c['country']
        if key not in country_map_dict:
            country_map_dict[key] = {'country': key, 'lat': c['lat'], 'lon': c['lon'], 'count': 0}
        country_map_dict[key]['count'] += c['count']
    country_map_json = json.dumps(list(country_map_dict.values()))

    btn_city_map = compute_city_map_data(btn_clicks)
    site_city_map = compute_city_map_data(site_clicks)
    city_map_dict = {}
    for c in btn_city_map + site_city_map:
        key = f"{c['city']}|{c['country']}"
        if key not in city_map_dict:
            city_map_dict[key] = {'city': c['city'], 'country': c['country'], 'lat': c['lat'], 'lon': c['lon'], 'count': 0}
        city_map_dict[key]['count'] += c['count']
    city_map_json = json.dumps(list(city_map_dict.values()))

    # Top pages (site only)
    top_pages = list(
        site_clicks.exclude(page_url='')
        .values('page_url')
        .annotate(count=Count('id'))
        .order_by('-count')[:10]
    )

    # Top elements (site only)
    top_elements = list(
        site_clicks.exclude(element_text='')
        .values('element_tag', 'element_text')
        .annotate(count=Count('id'))
        .order_by('-count')[:10]
    )

    # Recent visitors (site clicks, grouped by IP)
    ip_groups = build_ip_groups(site_clicks)

    # Public share link
    public_link = None
    try:
        from .models import PublicShareLink
        public_link = project.public_link
    except Exception:
        pass

    context = {
        'project': project,
        'total_clicks': total_clicks,
        'total_btn': total_btn,
        'total_site': total_site,
        'unique_visitors': unique_visitors,
        'unique_countries': unique_countries,
        'unique_pages': unique_pages,
        'avg_clicks_day': avg_clicks_day,
        'total_btn_trackers': total_btn_trackers,
        'total_site_trackers': total_site_trackers,
        'daily_btn_json': daily_btn_json,
        'daily_site_json': daily_site_json,
        'daily_total_json': daily_total_json,
        'country_json': country_json,
        'browser_json': browser_json,
        'device_json': device_json,
        'city_json': city_json,
        'location_json': location_json,
        'country_map_json': country_map_json,
        'city_map_json': city_map_json,
        'top_pages': top_pages,
        'top_elements': top_elements,
        'ip_groups': ip_groups,
        'date_from': date_from.strftime('%Y-%m-%d') if date_from else '',
        'date_to': date_to.strftime('%Y-%m-%d') if date_to else '',
        'public_link': public_link,
    }
    return render(request, 'tracker/master_dashboard.html', context)

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

        # --- STEP 3: NEW IP TRACKING LOGIC ---
        ip_address = get_client_ip(request)
        location_data = get_ip_location(ip_address)

        ClickEvent.objects.create(
            tracker=tracker,
            ip_address=ip_address or None,
            city=location_data.get('city', ''),
            country=location_data.get('country', ''),
            latitude=location_data.get('lat'),
            longitude=location_data.get('lon'),
            page_url=page_url,
            referrer=referrer,
            user_agent=user_agent,
            # Uncomment the line below ONLY if you added 'isp' to your ClickEvent model
            # isp=location_data.get('isp', ''),
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

        # --- STEP 3: NEW IP TRACKING LOGIC ---
        ip_address = get_client_ip(request)
        location_data = get_ip_location(ip_address)

        PageClickEvent.objects.create(
            tracker=tracker,
            ip_address=ip_address or None,
            city=location_data.get('city', ''),
            country=location_data.get('country', ''),
            latitude=location_data.get('lat'),
            longitude=location_data.get('lon'),
            page_url=page_url,
            referrer=referrer,
            element_tag=element_tag,
            element_text=element_text,
            element_id=element_id,
            element_class=element_class,
            element_href=element_href,
            user_agent=user_agent,
            # Uncomment the line below ONLY if you added 'isp' to your PageClickEvent model
            # isp=location_data.get('isp', ''),
        )
        return cors_response({'status': 'success', 'message': 'Click recorded'})

    except Exception as e:
        return cors_response({'status': 'error', 'message': str(e)}, 400)


# ── UTILITY: Sync Old Locations ──────────────────────────────────────────────

@login_required
def sync_old_locations(request, tracker_type, tracker_id):
    """Batch updates old clicks that have missing location data."""

    # 1. Get the correct tracker
    if tracker_type == 'site':
        tracker = get_object_or_404(SiteTracker, id=tracker_id, project__user=request.user)
    else:
        tracker = get_object_or_404(ButtonTracker, id=tracker_id, project__user=request.user)

    # 2. Find clicks where the city is missing or Unknown
    missing_clicks = tracker.clicks.filter(Q(city__exact='') | Q(city__exact='Unknown') | Q(city__isnull=True))

    # 3. Get up to 20 UNIQUE IP addresses to avoid hitting the API rate limit (45/min)
    unique_ips = missing_clicks.exclude(ip_address=None).values_list('ip_address', flat=True).distinct()[:20]

    if not unique_ips:
        messages.success(request, "✅ All click locations are already fully synced!")
    else:
        synced_count = 0
        for ip in unique_ips:
            # Fetch the location using our existing function
            location_data = get_ip_location(ip)

            # Update EVERY click that shares this IP address all at once
            tracker.clicks.filter(ip_address=ip).update(
                city=location_data.get('city', ''),
                country=location_data.get('country', '')
                # isp=location_data.get('isp', '') # Uncomment if ISP is in your model
            )

            synced_count += 1
            time.sleep(1.3) # Pause for 1.3 seconds so the API doesn't block us

        messages.success(request, f"🔄 Successfully synced locations for {synced_count} unique IP addresses.")

    # Redirect back to the correct analytics page
    if tracker_type == 'site':
        return redirect('site_analytics', tracker_id=tracker.id)
    return redirect('button_analytics', tracker_id=tracker.id)


# ── PUBLIC DASHBOARD (no login required) ─────────────────────────────────────

def public_dashboard(request, token):
    """Read-only public dashboard for clients — no login required."""
    from .models import PublicShareLink
    link = get_object_or_404(PublicShareLink, token=token, is_active=True)
    project = link.project
    date_from, date_to = parse_date_range(request)

    btn_clicks = ClickEvent.objects.filter(tracker__project=project)
    site_clicks = PageClickEvent.objects.filter(tracker__project=project)
    btn_clicks = filter_clicks_by_date(btn_clicks, date_from, date_to)
    site_clicks = filter_clicks_by_date(site_clicks, date_from, date_to)

    total_btn = btn_clicks.count()
    total_site = site_clicks.count()
    total_clicks = total_btn + total_site

    btn_ips = set(btn_clicks.exclude(ip_address=None).values_list('ip_address', flat=True).distinct())
    site_ips = set(site_clicks.exclude(ip_address=None).values_list('ip_address', flat=True).distinct())
    unique_visitors = len(btn_ips | site_ips)

    btn_countries = set(btn_clicks.exclude(country='').values_list('country', flat=True).distinct())
    site_countries = set(site_clicks.exclude(country='').values_list('country', flat=True).distinct())
    unique_countries = len(btn_countries | site_countries)

    unique_pages = site_clicks.exclude(page_url='').values('page_url').distinct().count()

    btn_daily = compute_daily_clicks(btn_clicks)
    site_daily = compute_daily_clicks(site_clicks)
    daily_map = {}
    for d in btn_daily:
        daily_map[d['date']] = daily_map.get(d['date'], 0) + d['count']
    for d in site_daily:
        daily_map[d['date']] = daily_map.get(d['date'], 0) + d['count']
    merged_daily = sorted([{'date': k, 'count': v} for k, v in daily_map.items()], key=lambda x: x['date'])
    avg_clicks_day = round(sum(d['count'] for d in merged_daily) / max(len(merged_daily), 1), 1)

    country_map = {}
    for c in compute_country_distribution(btn_clicks):
        country_map[c['country']] = country_map.get(c['country'], 0) + c['count']
    for c in compute_country_distribution(site_clicks):
        country_map[c['country']] = country_map.get(c['country'], 0) + c['count']
    merged_countries = sorted([{'country': k, 'count': v} for k, v in country_map.items()], key=lambda x: -x['count'])[:10]

    top_pages = list(
        site_clicks.exclude(page_url='').values('page_url').annotate(count=Count('id')).order_by('-count')[:10]
    )
    top_elements = list(
        site_clicks.exclude(element_text='').values('element_tag', 'element_text').annotate(count=Count('id')).order_by('-count')[:10]
    )
    ip_groups = build_ip_groups(site_clicks)

    context = {
        'project': project,
        'token': token,
        'total_clicks': total_clicks,
        'total_btn': total_btn,
        'total_site': total_site,
        'unique_visitors': unique_visitors,
        'unique_countries': unique_countries,
        'unique_pages': unique_pages,
        'avg_clicks_day': avg_clicks_day,
        'daily_btn_json': json.dumps(btn_daily),
        'daily_site_json': json.dumps(site_daily),
        'daily_total_json': json.dumps(merged_daily),
        'country_json': json.dumps(merged_countries),
        'browser_json': json.dumps(compute_browser_breakdown(site_clicks)),
        'device_json': json.dumps(compute_device_breakdown(site_clicks)),
        'top_pages': top_pages,
        'top_elements': top_elements,
        'ip_groups': ip_groups,
        'date_from': date_from.strftime('%Y-%m-%d') if date_from else '',
        'date_to': date_to.strftime('%Y-%m-%d') if date_to else '',
    }
    return render(request, 'tracker/public_dashboard.html', context)


# ── TOGGLE PUBLIC LINK ───────────────────────────────────────────────────────

@login_required
def toggle_public_link(request, project_id):
    """Create or toggle the public share link for a project."""
    project = get_object_or_404(Project, id=project_id, user=request.user)
    from .models import PublicShareLink

    if request.method == 'POST':
        link, created = PublicShareLink.objects.get_or_create(project=project)
        if not created:
            link.is_active = not link.is_active
            link.save()
            if link.is_active:
                messages.success(request, '🔗 Public link enabled!')
            else:
                messages.info(request, '🔒 Public link disabled.')
        else:
            messages.success(request, '🔗 Public share link created!')

    return redirect('project_dashboard', project_id=project.id)
