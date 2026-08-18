import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'trackingsystem.settings')
django.setup()

from django.test import Client
from django.contrib.auth.models import User
from tracker.models import Project, SiteTracker, ButtonTracker
import sys

c = Client()
user = User.objects.first()
if not user:
    print("No user.")
    sys.exit()

c.force_login(user)
proj = Project.objects.filter(user=user).first()

if proj:
    r = c.get(f'/project/{proj.id}/')
    print(f"Master Dashboard: {r.status_code}")
    if r.status_code == 500:
        print(r.content.decode('utf-8')[:2000])
        
    st = SiteTracker.objects.filter(project=proj).first()
    if st:
        r = c.get(f'/analytics/site/{st.id}/')
        print(f"Site Analytics: {r.status_code}")
        if r.status_code == 500:
            print(r.content.decode('utf-8')[:2000])

    bt = ButtonTracker.objects.filter(project=proj).first()
    if bt:
        r = c.get(f'/analytics/button/{bt.id}/')
        print(f"Button Analytics: {r.status_code}")
        if r.status_code == 500:
            print(r.content.decode('utf-8')[:2000])

