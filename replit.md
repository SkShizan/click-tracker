# ClickTrack — Button Click Analytics

A Django web application for tracking button click events across multiple websites. Create projects, add trackable buttons, embed a JavaScript snippet on any external site, and view real-time analytics (clicks, geo-location, IP, device).

## Stack

| Layer | Technology |
|-------|-----------|
| Backend | Django 6.0.7 (Python 3.12) |
| Database | SQLite (`db.sqlite3`) |
| Auth | Django built-in auth |
| CORS | django-cors-headers |
| Geo lookup | ip-api.com (client-side + server fallback) |

## How to Run

The app is configured to start automatically via the **Start application** workflow.

Manual start:
```bash
python manage.py runserver 0.0.0.0:5000
```

## Architecture

Three-level dashboard hierarchy:
1. **Main Dashboard** (`/dashboard/`) — global stats, all projects
2. **Project Dashboard** (`/dashboard/project/<id>/`) — project stats, button trackers + embed code
3. **Button Analytics** (`/dashboard/button/<uuid>/`) — click history table

## API

`POST /api/track/<uuid>/` — records a click event. Accepts JSON body:
```json
{ "url": "...", "ip": "...", "city": "...", "country": "..." }
```
No authentication required (CSRF-exempt, for external embeds).

## Dependencies

Install with:
```bash
pip install django django-cors-headers requests
```

## Environment Secrets

| Secret | Purpose |
|--------|---------|
| `SESSION_SECRET` | Django SECRET_KEY |

## Admin

Access Django admin at `/admin/`. Create a superuser with:
```bash
python manage.py createsuperuser
```

## User Preferences

- Dark-mode SaaS design (dark background #0f1117, indigo accent #6366f1)
- Inter font throughout
- Professional dashboard layout with sidebar navigation
- Toast notifications for all user actions
- Confirm modal before destructive deletes
