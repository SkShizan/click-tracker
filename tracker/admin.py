from django.contrib import admin
from .models import Project, ButtonTracker, ClickEvent


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'created_at')
    list_filter = ('user',)
    search_fields = ('name', 'description')
    readonly_fields = ('created_at',)


@admin.register(ButtonTracker)
class ButtonTrackerAdmin(admin.ModelAdmin):
    list_display = ('title', 'project', 'created_at')
    list_filter = ('project__user',)
    search_fields = ('title', 'description')
    readonly_fields = ('id', 'created_at')


@admin.register(ClickEvent)
class ClickEventAdmin(admin.ModelAdmin):
    list_display = ('tracker', 'ip_address', 'city', 'country', 'clicked_at')
    list_filter = ('country', 'city')
    search_fields = ('ip_address', 'city', 'country', 'page_url')
    readonly_fields = ('clicked_at',)
