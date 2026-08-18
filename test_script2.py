import os
import django
import traceback
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'trackingsystem.settings')
django.setup()

from tracker.models import Project, SiteTracker, ButtonTracker, PageClickEvent, ClickEvent
from django.contrib.auth.models import User
from django.test import Client

try:
    user = User.objects.first()
    if not user:
        user = User.objects.create_user(username='test_debug2', password='password')

    proj = Project.objects.create(name='Test Proj 2', user=user)
    st = SiteTracker.objects.create(project=proj, name='Test Site 2')
    bt = ButtonTracker.objects.create(project=proj, title='Test Btn 2')

    PageClickEvent.objects.create(
        tracker=st, ip_address='8.8.8.8', city='Mountain View', country='United States',
        latitude=37.386, longitude=-122.0838, page_url='http://test.com'
    )

    ClickEvent.objects.create(
        tracker=bt, ip_address='8.8.8.8', city='Mountain View', country='United States',
        latitude=37.386, longitude=-122.0838, page_url='http://test.com'
    )

    c = Client()
    c.force_login(user)

    print("Testing with valid lat/lon...")
    r1 = c.get(f'/dashboard/project/{proj.id}/master/')
    print("Master:", r1.status_code)
    if r1.status_code == 500:
        print(r1.content.decode('utf-8')[:1000])

    r2 = c.get(f'/dashboard/site/{st.id}/')
    print("Site:", r2.status_code)
    if r2.status_code == 500:
        print(r2.content.decode('utf-8')[:1000])

    r3 = c.get(f'/dashboard/button/{bt.id}/')
    print("Button:", r3.status_code)
    if r3.status_code == 500:
        print(r3.content.decode('utf-8')[:1000])
        
    print("\nTesting with NULL lat/lon...")
    PageClickEvent.objects.create(
        tracker=st, ip_address='127.0.0.1', city='Unknown', country='Unknown',
        latitude=None, longitude=None, page_url='http://localhost'
    )
    
    r4 = c.get(f'/dashboard/site/{st.id}/')
    print("Site (Null Lat/Lon):", r4.status_code)
    if r4.status_code == 500:
        print(r4.content.decode('utf-8')[:1000])

except Exception as e:
    traceback.print_exc()

