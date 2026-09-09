"""管理命令：手动生成某日部门×集群维度的实例统计。"""
import datetime

from django.core.management.base import BaseCommand

from app.tasks import generate_daily_instance_stats


class Command(BaseCommand):
    help = "手动生成某日部门/集群维度的实例统计（无需 Celery）"

    def add_arguments(self, parser):
        """注册命令行参数"""
        parser.add_argument(
            "--date",
            default=None,
            help="统计日期 YYYY-MM-DD，缺省为今天",
        )

    def handle(self, *args, **options):
        """解析日期并执行统计任务，打印影响行数"""
        raw = options.get("date")
        stat_date = datetime.date.fromisoformat(raw) if raw else None
        affected = generate_daily_instance_stats(stat_date)
        self.stdout.write(self.style.SUCCESS(f"统计完成，写入/更新 {affected} 行"))
