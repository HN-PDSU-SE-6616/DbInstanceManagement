from django.core.management.base import BaseCommand

from app.tasks import rotate_instance_passwords


class Command(BaseCommand):
    help = "手动轮换所有运行中实例的密码（无需 Celery）"

    def handle(self, *args, **options):
        rotated = rotate_instance_passwords()
        self.stdout.write(self.style.SUCCESS(f"已轮换 {rotated} 个实例的密码"))
