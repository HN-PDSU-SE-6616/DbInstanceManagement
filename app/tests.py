import socket
import threading
from contextlib import contextmanager
from datetime import date
from unittest import mock

from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, TestCase

from rest_framework import status
from rest_framework.test import APITestCase

from .middleware import RequestTimingMiddleware
from .models import Cluster, Department, Instance, InstanceDailyStat
from .tasks import (
    generate_daily_instance_stats,
    rotate_instance_passwords,
    rotate_single_instance_password,
)
from .utils import check_port_reachable, decrypt_password, encrypt_password

# Create your tests here.
User = get_user_model()


@contextmanager
def listening_socket():
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    port = srv.getsockname()[1]
    stop = False

    def serve():
        while not stop:
            try:
                conn, _ = srv.accept()
            except OSError:
                break
            conn.close()

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    try:
        yield port
    finally:
        stop = True
        srv.close()


class ModelTests(TestCase):
    def setUp(self):
        self.department = Department.objects.create(name="研发部", code="RD")
        self.cluster = Cluster.objects.create(name="生产集群", code="PROD", environment="prod")

    def test_password_encrypted_at_rest(self):
        instance = Instance.objects.create(
            name="pg1",
            host="10.0.0.1",
            port=5432,
            username="admin",
            password="Plain@123",
            department=self.department,
            cluster=self.cluster,
        )
        instance.refresh_from_db()
        self.assertNotEqual(instance._password, "Plain@123")
        self.assertTrue(instance._password.startswith("gAAAAA"))
        self.assertEqual(instance.password, "Plain@123")

    def test_password_auto_generated(self):
        instance = Instance.objects.create(
            name="pg2",
            host="10.0.0.2",
            port=5432,
            username="admin",
            department=self.department,
            cluster=self.cluster,
        )
        instance.refresh_from_db()
        self.assertTrue(instance._password.startswith("gAAAAA"))
        self.assertTrue(instance.password)

    def test_rotate_password(self):
        instance = Instance.objects.create(
            name="pg3",
            host="10.0.0.3",
            port=5432,
            username="admin",
            password="Old@123",
            department=self.department,
            cluster=self.cluster,
        )
        old = instance.password
        instance.rotate_password()
        instance.refresh_from_db()
        self.assertNotEqual(instance.password, old)
        self.assertIsNotNone(instance.last_password_rotate)

    def test_encrypt_decrypt_roundtrip(self):
        plain = "Round@Trip#9"
        self.assertEqual(decrypt_password(encrypt_password(plain)), plain)


class UtilsTests(TestCase):
    def test_open_port_reachable(self):
        with listening_socket() as port:
            self.assertTrue(check_port_reachable("127.0.0.1", port, timeout=2))

    def test_closed_port_unreachable(self):
        with listening_socket() as port:
            pass
        self.assertFalse(check_port_reachable("127.0.0.1", port, timeout=2))

    def test_invalid_port_rejected(self):
        self.assertFalse(check_port_reachable("127.0.0.1", 70000))
        self.assertFalse(check_port_reachable("127.0.0.1", -1))


class MiddlewareTests(SimpleTestCase):
    def test_duration_header_added(self):
        request = RequestFactory().get("/api/departments/")
        middleware = RequestTimingMiddleware(lambda req: HttpResponse("ok"))
        response = middleware(request)
        self.assertIn("X-Request-Duration-Ms", response)
        self.assertGreater(float(response["X-Request-Duration-Ms"]), 0)


class TaskTests(TestCase):
    def setUp(self):
        self.department = Department.objects.create(name="研发部", code="RD")
        self.cluster_a = Cluster.objects.create(name="集群A", code="A")
        self.cluster_b = Cluster.objects.create(name="集群B", code="B")

    def _instance(self, cluster, status_value, seq):
        return Instance.objects.create(
            name=f"pg{seq}",
            host=f"10.1.1.{seq}",
            port=5432 + seq,
            username="admin",
            status=status_value,
            department=self.department,
            cluster=cluster,
        )

    def test_rotate_only_active(self):
        active = self._instance(self.cluster_a, Instance.Status.ACTIVE, 1)
        maintenance = self._instance(self.cluster_b, Instance.Status.MAINTENANCE, 2)
        old_active = active.password
        old_maint = maintenance.password

        count = rotate_instance_passwords()

        self.assertEqual(count, 1)
        active.refresh_from_db()
        maintenance.refresh_from_db()
        self.assertNotEqual(active.password, old_active)
        self.assertIsNotNone(active.last_password_rotate)
        self.assertEqual(maintenance.password, old_maint)
        self.assertIsNone(maintenance.last_password_rotate)

    def test_rotate_single_missing_returns_none(self):
        self.assertIsNone(rotate_single_instance_password(999999))

    def test_generate_daily_stats_and_idempotent(self):
        stat_date = date(2026, 9, 8)
        self._instance(self.cluster_a, Instance.Status.ACTIVE, 1)
        self._instance(self.cluster_a, Instance.Status.MAINTENANCE, 2)
        self._instance(self.cluster_b, Instance.Status.INACTIVE, 3)

        first = generate_daily_instance_stats(stat_date)
        self.assertEqual(first, 2)

        rows = InstanceDailyStat.objects.filter(stat_date=stat_date)
        self.assertEqual(rows.count(), 2)

        row_a = rows.get(cluster=self.cluster_a)
        self.assertEqual(row_a.total_count, 2)
        self.assertEqual(row_a.active_count, 1)
        self.assertEqual(row_a.maintenance_count, 1)

        row_b = rows.get(cluster=self.cluster_b)
        self.assertEqual(row_b.total_count, 1)
        self.assertEqual(row_b.inactive_count, 1)

        second = generate_daily_instance_stats(stat_date)
        self.assertEqual(second, 2)
        self.assertEqual(rows.count(), 2)


class ApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="tester", password="Pass@123")
        self.client.force_authenticate(self.user)

    def test_auth_required(self):
        anon = self.client_class()
        self.assertEqual(anon.get("/api/departments/").status_code, status.HTTP_401_UNAUTHORIZED)

    def test_jwt_token_endpoint(self):
        resp = self.client.post(
            "/api/token/",
            {"username": "tester", "password": "Pass@123"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("access", resp.data)
        self.assertIn("refresh", resp.data)

    def test_department_crud(self):
        created = self.client.post(
            "/api/departments/", {"name": "财务部", "code": "FIN"}, format="json"
        )
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        dept_id = created.data["id"]

        listed = self.client.get("/api/departments/")
        self.assertEqual(listed.status_code, status.HTTP_200_OK)
        self.assertEqual(len(listed.data), 1)
        self.assertEqual(listed.data[0]["code"], "FIN")

        updated = self.client.patch(
            f"/api/departments/{dept_id}/", {"name": "财务共享中心"}, format="json"
        )
        self.assertEqual(updated.data["name"], "财务共享中心")

        deleted = self.client.delete(f"/api/departments/{dept_id}/")
        self.assertEqual(deleted.status_code, status.HTTP_204_NO_CONTENT)

    def test_instance_create_password_write_only(self):
        department = Department.objects.create(name="研发部", code="RD")
        cluster = Cluster.objects.create(name="生产集群", code="PROD")
        payload = {
            "name": "pg-main",
            "host": "10.2.2.1",
            "port": 5432,
            "db_type": "postgresql",
            "username": "dba",
            "password": "Secret@123",
            "department": department.id,
            "cluster": cluster.id,
        }
        resp = self.client.post("/api/instances/", payload, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertNotIn("password", resp.data)
        self.assertNotIn("_password", resp.data)

        instance = Instance.objects.get(pk=resp.data["id"])
        self.assertEqual(instance.password, "Secret@123")
        self.assertTrue(instance._password.startswith("gAAAAA"))

    def test_probe_submit_and_result(self):
        fake_task = mock.Mock(id="fake-task-id", state="PENDING")
        with mock.patch("app.views.probe_port.delay", return_value=fake_task) as delay:
            submitted = self.client.post(
                "/api/instances/probe/",
                {"host": "127.0.0.1", "port": 5432},
                format="json",
            )
            delay.assert_called_once_with("127.0.0.1", 5432, 3.0)
        self.assertEqual(submitted.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(submitted.data["task_id"], "fake-task-id")

        fake_result = mock.Mock(
            state="SUCCESS", ready=lambda: True, successful=lambda: True, result=True
        )
        with mock.patch("app.views.probe_port") as proxy:
            proxy.AsyncResult.return_value = fake_result
            result = self.client.get("/api/instances/probe/fake-task-id/")
        self.assertEqual(result.status_code, status.HTTP_200_OK)
        self.assertTrue(result.data["reachable"])

    def test_probe_validation(self):
        resp = self.client.post(
            "/api/instances/probe/", {"host": "", "port": 99999}, format="json"
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
