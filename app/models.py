from datetime import date

from django.db import models
from django.utils import timezone

from .utils import decrypt_password, encrypt_password, generate_strong_password


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Department(TimeStampedModel):
    name = models.CharField(max_length=128)
    code = models.CharField(max_length=64, unique=True)
    description = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        ordering = ["code"]
        verbose_name = "部门"

    def __str__(self):
        return f"{self.name} ({self.code})"


class Cluster(TimeStampedModel):
    class Environment(models.TextChoices):
        DEVELOPMENT = "dev", "开发"
        TEST = "test", "测试"
        PRODUCTION = "prod", "生产"

    name = models.CharField(max_length=128)
    code = models.CharField(max_length=64, unique=True)
    environment = models.CharField(
        max_length=16, choices=Environment.choices, default=Environment.DEVELOPMENT
    )
    description = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        ordering = ["code"]
        verbose_name = "集群"

    def __str__(self):
        return f"{self.name} ({self.code})"


class Instance(TimeStampedModel):
    class DbType(models.TextChoices):
        POSTGRESQL = "postgresql", "PostgreSQL"
        MYSQL = "mysql", "MySQL"
        REDIS = "redis", "Redis"
        MONGODB = "mongodb", "MongoDB"
        ORACLE = "oracle", "Oracle"
        SQLSERVER = "sqlserver", "SQL Server"
        OTHER = "other", "其他"

    class Status(models.TextChoices):
        ACTIVE = "active", "运行中"
        MAINTENANCE = "maintenance", "维护中"
        INACTIVE = "inactive", "已停用"
        DEPRECATED = "deprecated", "已废弃"

    name = models.CharField(max_length=128)
    host = models.CharField(max_length=255)
    port = models.IntegerField()
    db_type = models.CharField(
        max_length=20, choices=DbType.choices, default=DbType.POSTGRESQL
    )
    username = models.CharField(max_length=128)
    _password = models.TextField(blank=True, default="")
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.ACTIVE, db_index=True
    )
    department = models.ForeignKey(
        Department, on_delete=models.PROTECT, related_name="instances"
    )
    cluster = models.ForeignKey(
        Cluster, on_delete=models.PROTECT, related_name="instances"
    )
    last_password_rotate = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "数据库实例"
        constraints = [
            models.UniqueConstraint(
                fields=["host", "port"], name="uniq_instance_host_port"
            )
        ]

    def __str__(self):
        return f"{self.name} ({self.host}:{self.port})"

    @property
    def password(self) -> str:
        return decrypt_password(self._password)

    @password.setter
    def password(self, value: str) -> None:
        self._password = encrypt_password(value)

    def save(self, *args, **kwargs):
        if not self._password:
            self.password = generate_strong_password()
        super().save(*args, **kwargs)

    def rotate_password(self) -> None:
        self.password = generate_strong_password()
        self.last_password_rotate = timezone.now()
        self.save(update_fields=["_password", "last_password_rotate", "updated_at"])


class InstanceDailyStat(models.Model):
    stat_date = models.DateField(default=date.today, db_index=True)
    department = models.ForeignKey(
        Department, on_delete=models.PROTECT, related_name="daily_stats"
    )
    cluster = models.ForeignKey(
        Cluster, on_delete=models.PROTECT, related_name="daily_stats"
    )
    total_count = models.PositiveIntegerField(default=0)
    active_count = models.PositiveIntegerField(default=0)
    maintenance_count = models.PositiveIntegerField(default=0)
    inactive_count = models.PositiveIntegerField(default=0)
    deprecated_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "实例每日统计"
        ordering = ["-stat_date", "department", "cluster"]
        constraints = [
            models.UniqueConstraint(
                fields=["stat_date", "department", "cluster"],
                name="uniq_daily_stat_department_cluster",
            )
        ]

    def __str__(self):
        return f"{self.stat_date} | {self.department.code} | {self.cluster.code}: {self.total_count}"
