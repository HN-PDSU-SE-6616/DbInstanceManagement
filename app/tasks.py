"""Celery 任务层"""
from celery import shared_task
from django.db.models import Count, Q
from django.utils import timezone

from .models import Instance, InstanceDailyStat
from .utils import check_port_reachable, generate_strong_password


@shared_task
def probe_port(host: str, port: int, timeout: float = 3.0) -> bool:
    """探测指定 host:port 的 TCP 可达性。

   :param host: IP 或域名。
   :param port: 端口号（1-65535）。
   :param timeout: 连接超时秒数，默认 3。
   :Return: 可达返回 True，否则返回 False。
   """
    return check_port_reachable(host, port, timeout)


@shared_task
def rotate_instance_passwords() -> int:
    """轮换所有 active 状态实例的密码（每 12 小时由 Beat 触发）。

    :Return: 本次实际轮换的实例数量。
    """
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
    """按 ID 轮换单个实例的密码（供手动精准调用）。

   :param instance_id: 目标 Instance 的主键。
   :Return: 成功返回实例 ID；实例不存在返回 None。
   """
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
    """生成某天按部门×集群维度的实例统计并幂等写入快照表。

   :param stat_date: 统计日期（date 对象）；缺省取当前本地日期。
   :Return: 写入/更新的统计行数。
   """
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
