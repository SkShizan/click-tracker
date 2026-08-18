import os
import django
import traceback
import re
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
    
    match = re.search(r'const mapDataCountry = (.*?);', html)
    if match:
        print("====== JAVASCRIPT CONTEXT IN HTML ======")
        print("mapDataCountry:", match.group(1))
    else:
        print("Could not find mapDataCountry in html")
        
    match2 = re.search(r'const mapDataCity = (.*?);', html)
    if match2:
        print("mapDataCity:", match2.group(1))
        
except Exception as e:
    traceback.print_exc()
