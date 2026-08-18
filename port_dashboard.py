import os

with open('master_dashboard.html.bak', 'r', encoding='utf-8') as f:
    master_html = f.read()

# Extract exactly what is inside {% block content %}
content_start = master_html.find('{% block content %}') + len('{% block content %}')
content_end = master_html.find('{% endblock %}', content_start)
content = master_html[content_start:content_end].strip()

# Extract exactly what is inside {% block extra_scripts %}
scripts_start = master_html.find('{% block extra_scripts %}') + len('{% block extra_scripts %}')
scripts_end = master_html.find('{% endblock %}', scripts_start)
scripts = master_html[scripts_start:scripts_end].strip()

# Create the standalone HTML structure mapping to the old public_dashboard head but with leaflet
standalone_html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ project.name }} — Analytics Dashboard</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.4/dist/chart.umd.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chartjs-adapter-date-fns@3.0.0/dist/chartjs-adapter-date-fns.bundle.min.js"></script>
    <!-- Leaflet.js for Maps -->
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=" crossorigin=""/>
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js" integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=" crossorigin=""></script>
    <style>
        *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: 'Inter', system-ui, sans-serif; background: #ddeef3; color: #0d2b2e; font-size: 13.5px; line-height: 1.6; }
        .container { max-width: 1280px; margin: 40px auto; padding: 0 24px; }
        
        /* Keep basic button styles for filters */
        .btn { display:inline-flex; align-items:center; gap:7px; padding:8px 16px; border-radius:8px; font-size:13px; font-weight:600; cursor:pointer; border:none; text-decoration:none; font-family:'Inter',sans-serif; transition:all 0.15s; }
        .btn-primary { background:#006d77; color:#fff; }
        .btn-ghost { background:transparent; color:#4a7c83; border:1px solid #dcebee; }
    </style>
</head>
<body>
<div class="container">
"""

# Filter out the "Project Settings" and "Dashboard" private links from the content block
import re
content = re.sub(r'<a.*?href="{% url \'master_dashboard\' project.id %}".*?Clear All Filters.*?</a>', '<a class="btn btn-ghost btn-sm" href="{% url \'public_dashboard\' token %}"><i class="fa-solid fa-xmark"></i> Clear All Filters</a>', content)
content = re.sub(r'<a href="{% url \'project_dashboard\' project\.id %}" class="btn btn-ghost btn-sm">.*?</a>', '', content, flags=re.DOTALL)
content = re.sub(r'{%.*?public_link.*?%}.*?{% endif %}', '', content, flags=re.DOTALL)

# Reassemble
final_html = standalone_html + content + '\n</div>\n' + scripts + '\n</body>\n</html>'

with open(r'tracker\templates\tracker\public_dashboard.html', 'w', encoding='utf-8') as dest:
    dest.write(final_html)

print("public_dashboard.html successfully adapted!")
