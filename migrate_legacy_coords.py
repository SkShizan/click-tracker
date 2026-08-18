import os, django, time, requests
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'trackingsystem.settings')
django.setup()

from tracker.models import ClickEvent, PageClickEvent

def geocode_location(city, country):
    query = ""
    if city and city != "Unknown" and city != "Localhost":
        query += f"{city},"
    if country and country != "Unknown" and country != "Localhost":
        query += f"{country}"
        
    query = query.strip(',')
    if not query:
        return None, None
        
    url = f"https://nominatim.openstreetmap.org/search?format=json&q={query}&limit=1"
    headers = {'User-Agent': 'ClickTracker-DataMigration/1.0'}
    try:
        r = requests.get(url, headers=headers, timeout=5)
        data = r.json()
        if data and len(data) > 0:
            return float(data[0]['lat']), float(data[0]['lon'])
    except Exception as e:
        print(f"Error geocoding {query}: {e}")
    return None, None

cache = {}

for Model in [ClickEvent, PageClickEvent]:
    missing = Model.objects.filter(latitude__isnull=True).exclude(country='')
    count = missing.count()
    if count == 0:
        continue
    
    # We will process in batches of identical country/city pairs without querying the DB repeatedly
    print(f"Found {count} {Model.__name__} records missing latitude/longitude.")
    
    places = missing.values_list('city', 'country').distinct()
    for city, country in places:
        key = f"{city}|{country}"
        if key not in cache:
            print(f"Geocoding {city}, {country}...")
            lat, lon = geocode_location(city, country)
            cache[key] = (lat, lon)
            time.sleep(1.1) # respect Nominatim rate limit
        else:
            lat, lon = cache[key]
            
        if lat is not None and lon is not None:
            updated = Model.objects.filter(city=city, country=country, latitude__isnull=True).update(latitude=lat, longitude=lon)
            print(f" -> Updated {updated} records for {city}, {country} to {lat}, {lon}")

print("Migration complete!")
