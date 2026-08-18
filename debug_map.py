import os
import django
import traceback
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'trackingsystem.settings')
django.setup()

from django.test import Client
from django.contrib.auth.models import User
from tracker.models import Project

try:
    user = User.objects.first()
    proj = Project.objects.filter(user=user).first()
    c = Client()
    c.force_login(user)

    r = c.get(f'/dashboard/project/{proj.id}/master/')
    html = r.content.decode('utf-8')
    
    start_idx = html.find('const mapDataCountry')
    end_idx = html.find('const mapDataCity') + 200
    if start_idx != -1:
        print("====== JAVASCRIPT CONTEXT IN HTML ======")
        print(html[start_idx:end_idx])
    else:
        print("Could not find mapDataCountry in html")
        
except Exception as e:
    traceback.print_exc()
