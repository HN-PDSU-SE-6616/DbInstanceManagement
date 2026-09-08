from celery import shared_task
from django.db.models import Count, Q
from django.utils import timezone

from .models import Instance, InstanceDailyStat
from .utils import check_port_reachable, generate_strong_password


@shared_task
def probe_port(host: str, port: int, timeout: float = 3.0) -> bool:
    return check_port_reachable(host, port, timeout)


@shared_task
def rotate_instance_passwords() -> int:
    rotated = 0
    instances = Instance.objects.filter(status=Instance.Status.ACTIVE)
    for instance in instances.iterator():
        instance.password = generate_strong_password()
        instance.last_password_rotate = timezone.now()
        instance.save(update_fields=["_password", "last_password_rotate", "updated_at"])
        rotated += 1
    return rotated


@shared_task
def rotate_single_instance_password(instance_id: int):
    try:
        instance = Instance.objects.get(pk=instance_id)
    except Instance.DoesNotExist:
        return None
    instance.password = generate_strong_password()
    instance.last_password_rotate = timezone.now()
    instance.save(update_fields=["_password", "last_password_rotate", "updated_at"])
    return instance_id


@shared_task
def generate_daily_instance_stats(stat_date=None) -> int:
    if stat_date is None:
        stat_date = timezone.localdate()
    rows = (
        Instance.objects.values("department_id", "cluster_id")
        .annotate(
            total_count=Count("id"),
            active_count=Count("id", filter=Q(status=Instance.Status.ACTIVE)),
            maintenance_count=Count("id", filter=Q(status=Instance.Status.MAINTENANCE)),
            inactive_count=Count("id", filter=Q(status=Instance.Status.INACTIVE)),
            deprecated_count=Count("id", filter=Q(status=Instance.Status.DEPRECATED)),
        )
    )
    defaults_keys = (
        "total_count",
        "active_count",
        "maintenance_count",
        "inactive_count",
        "deprecated_count",
    )
    affected = 0
    for row in rows:
        InstanceDailyStat.objects.update_or_create(
            stat_date=stat_date,
            department_id=row["department_id"],
            cluster_id=row["cluster_id"],
            defaults={key: row[key] for key in defaults_keys},
        )
        affected += 1
    return affected
