"""管理命令：一键生成演示数据（部门/集群/实例）并生成当日统计。"""
from django.core.management.base import BaseCommand

from app.models import Cluster, Department, Instance
from app.tasks import generate_daily_instance_stats


class Command(BaseCommand):
    help = "生成演示数据：部门/集群/实例，并顺带生成当日统计"

    def handle(self, *args, **options):
        """创建或更新演示数据并打印汇总"""
        rd, _ = Department.objects.get_or_create(code="RD", defaults={"name": "研发部"})
        fin, _ = Department.objects.get_or_create(code="FIN", defaults={"name": "财务部"})
        prod, _ = Cluster.objects.get_or_create(
            code="PROD", defaults={"name": "生产集群", "environment": "prod"}
        )
        test, _ = Cluster.objects.get_or_create(
            code="TEST", defaults={"name": "测试集群", "environment": "test"}
        )
        dev, _ = Cluster.objects.get_or_create(
            code="DEV", defaults={"name": "开发集群", "environment": "dev"}
        )

        specs = [
            (rd, prod, "pg-prod", "postgresql", Instance.Status.ACTIVE, 3),
            (rd, test, "pg-test", "postgresql", Instance.Status.MAINTENANCE, 2),
            (fin, prod, "pg-fin", "postgresql", Instance.Status.ACTIVE, 2),
            (fin, dev, "redis-dev", "redis", Instance.Status.INACTIVE, 2),
        ]
        seq = 10
        for department, cluster, prefix, db_type, instance_status, amount in specs:
            for _ in range(amount):
                seq += 1
                Instance.objects.update_or_create(
                    name=f"{prefix}-{seq}",
                    defaults={
                        "host": f"10.1.1.{seq}",
                        "port": 15432 + seq,
                        "db_type": db_type,
                        "username": "admin",
                        "department": department,
                        "cluster": cluster,
                        "status": instance_status,
                    },
                )

        affected = generate_daily_instance_stats()
        self.stdout.write(
            self.style.SUCCESS(
                f"演示数据就绪：实例 {Instance.objects.count()} 个，"
                f"当日统计 {affected} 行"
            )
        )
