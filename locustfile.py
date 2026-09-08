import os
import random
import uuid

from locust import HttpUser, between, task

USERNAME = os.getenv("LOCUST_USERNAME", "loadtest")
PASSWORD = os.getenv("LOCUST_PASSWORD", "Load@12345")


class DbInstanceUser(HttpUser):
    wait_time = between(0.3, 1.5)

    def on_start(self):
        resp = self.client.post(
            "/api/token/", json={"username": USERNAME, "password": PASSWORD}
        )
        if resp.status_code != 200:
            raise RuntimeError(f"登录失败: {resp.status_code} {resp.text}")
        token = resp.json()["access"]
        self.client.headers.update({"Authorization": f"Bearer {token}"})

    @task(6)
    def list_instances(self):
        self.client.get("/api/instances/")

    @task(3)
    def list_departments(self):
        self.client.get("/api/departments/")

    @task(2)
    def list_clusters(self):
        self.client.get("/api/clusters/")

    @task(2)
    def create_instance(self):
        departments = self.client.get("/api/departments/").json()
        clusters = self.client.get("/api/clusters/").json()
        if not departments or not clusters:
            return
        uid = uuid.uuid4().hex[:8]
        payload = {
            "name": f"load-{uid}",
            "host": f"10.{random.randint(0, 200)}.{random.randint(0, 200)}.{random.randint(1, 254)}",
            "port": random.randint(20000, 60000),
            "db_type": "postgresql",
            "username": "load",
            "department": random.choice(departments)["id"],
            "cluster": random.choice(clusters)["id"],
        }
        self.client.post("/api/instances/", json=payload)

    @task(1)
    def submit_probe(self):
        self.client.post(
            "/api/instances/probe/",
            json={"host": "127.0.0.1", "port": 5432, "timeout": 2.0},
        )
