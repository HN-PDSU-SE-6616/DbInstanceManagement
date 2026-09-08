from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Cluster, Department, Instance
from .serializers import (
    ClusterSerializer,
    DepartmentSerializer,
    InstanceSerializer,
    PortProbeSerializer,
)
from .tasks import probe_port

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
