import os, django, re
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'trackingsystem.settings')
django.setup()

from django.test import RequestFactory
from tracker.views import master_project_dashboard
from tracker.models import Project

rf = RequestFactory()
proj = Project.objects.first()
r = rf.get('/dashboard/project/1/master/')
r.user = proj.user

try:
    response = master_project_dashboard(r, project_id=proj.id)
    html = response.content.decode('utf-8')
    
    start_idx = html.find('const mapDataCountry')
    end_idx = html.find('// Keep maps crisp')
    
    if start_idx != -1:
        print("====== JAVASCRIPT CONTEXT IN HTML ======")
        print(html[start_idx:end_idx].strip())
    else:
        print("Not found.")
except Exception as e:
    import traceback
    traceback.print_exc()
