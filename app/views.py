from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.shortcuts import render
from django.views.decorators.http import require_http_methods
from rest_framework import status, viewsets
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Cluster, Department, Instance, InstanceDailyStat
from .serializers import (
    ClusterSerializer,
    DepartmentSerializer,
    InstanceSerializer,
    PortProbeSerializer,
    ProbeTaskQuerySerializer
)
from .tasks import probe_port
from .utils import check_port_reachable
from .monitoring import metrics_snapshot


# Create your views here.

class DepartmentViewSet(viewsets.ModelViewSet):
    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer
    permission_classes = [IsAuthenticated]


class ClusterViewSet(viewsets.ModelViewSet):
    queryset = Cluster.objects.all()
    serializer_class = ClusterSerializer
    permission_classes = [IsAuthenticated]


class InstanceViewSet(viewsets.ModelViewSet):
    serializer_class = InstanceSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = Instance.objects.select_related("department", "cluster").all()
        department = self.request.query_params.get("department")
        cluster = self.request.query_params.get("cluster")
        status_value = self.request.query_params.get("status")
        if department:
            queryset = queryset.filter(department_id=department)
        if cluster:
            queryset = queryset.filter(cluster_id=cluster)
        if status_value:
            queryset = queryset.filter(status=status_value)
        return queryset


class InstanceProbeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = PortProbeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        task = probe_port.delay(data["host"], data["port"], data.get("timeout", 3.0))
        return Response(
            {"task_id": task.id, "state": task.state},
            status=status.HTTP_202_ACCEPTED,
        )


class ProbeResultView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, task_id):
        task = probe_port.AsyncResult(task_id)
        payload = {"task_id": task_id, "state": task.state, "ready": task.ready()}
        if task.successful():
            payload["reachable"] = task.result
        elif task.ready() and task.failed():
            payload["error"] = str(task.result)
        return Response(payload)


@login_required(login_url="/admin/login/")
@require_http_methods(["GET", "POST"])
def dashboard(request):
    probe_result = None
    if request.method == "POST":
        host = request.POST.get("host", "").strip()
        try:
            port = int(request.POST.get("port", ""))
        except (TypeError, ValueError):
            port = 0
        if host and 1 <= port <= 65535:
            reachable = check_port_reachable(host, port, timeout=3.0)
            probe_result = {
                "host": host,
                "port": port,
                "reachable": reachable,
                "text": "可达" if reachable else "不可达或超时",
            }
        else:
            probe_result = {
                "host": host or "-",
                "port": port,
                "reachable": False,
                "text": "参数不合法，请检查 host/port",
            }

    instances = Instance.objects.select_related("department", "cluster").order_by(
        "-created_at"
    )
    status_counts = {
        row["status"]: row["count"]
        for row in Instance.objects.values("status").annotate(count=Count("id"))
    }
    status_cards = [
        {"label": label, "count": status_counts.get(value, 0)}
        for value, label in Instance.Status.choices
    ]
    db_counts = {
        row["db_type"]: row["count"]
        for row in Instance.objects.values("db_type").annotate(count=Count("id"))
    }
    db_type_cards = [
        {"label": label, "count": db_counts.get(value, 0)}
        for value, label in Instance.DbType.choices
    ]

    context = {
        "probe_result": probe_result,
        "metrics": metrics_snapshot(),
        "status_cards": status_cards,
        "db_type_cards": db_type_cards,
        "totals": {
            "department": Department.objects.count(),
            "cluster": Cluster.objects.count(),
            "instance": instances.count(),
        },
        "recent_instances": instances[:10],
        "recent_stats": InstanceDailyStat.objects.select_related(
            "department", "cluster"
        ).order_by("-stat_date", "-updated_at")[:10],
    }
    return render(request, "dashboard/index.html", context)


class InstanceProbeView(GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = PortProbeSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        task = probe_port.delay(data["host"], data["port"], data.get("timeout", 3.0))
        return Response(
            {"task_id": task.id, "state": task.state},
            status=status.HTTP_202_ACCEPTED,
        )


class ProbeResultView(GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ProbeTaskQuerySerializer

    def get(self, request, task_id):
        task = probe_port.AsyncResult(task_id)
        payload = {"task_id": task_id, "state": task.state, "ready": task.ready()}
        if task.successful():
            payload["reachable"] = task.result
        elif task.ready() and task.failed():
            payload["error"] = str(task.result)
        return Response(payload)
