from django.contrib import admin

from .models import Cluster, Department, Instance, InstanceDailyStat

# Register your models here.

@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "description", "created_at")
    search_fields = ("name", "code")


@admin.register(Cluster)
class ClusterAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "environment", "created_at")
    list_filter = ("environment",)
    search_fields = ("name", "code")


@admin.register(Instance)
class InstanceAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "host",
        "port",
        "db_type",
        "status",
        "department",
        "cluster",
        "last_password_rotate",
    )
    list_filter = ("status", "db_type", "department", "cluster")
    search_fields = ("name", "host", "username")
    exclude = ("_password",)
    readonly_fields = ("last_password_rotate", "created_at", "updated_at")


@admin.register(InstanceDailyStat)
class InstanceDailyStatAdmin(admin.ModelAdmin):
    list_display = (
        "stat_date",
        "department",
        "cluster",
        "total_count",
        "active_count",
        "maintenance_count",
        "inactive_count",
        "deprecated_count",
    )
    list_filter = ("stat_date", "department", "cluster")
    date_hierarchy = "stat_date"
