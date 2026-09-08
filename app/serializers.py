from rest_framework import serializers

from .models import Cluster, Department, Instance


class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = "__all__"
        read_only_fields = ("created_at", "updated_at")


class ClusterSerializer(serializers.ModelSerializer):
    environment_display = serializers.CharField(
        source="get_environment_display", read_only=True
    )

    class Meta:
        model = Cluster
        fields = "__all__"
        read_only_fields = ("created_at", "updated_at")


class InstanceSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True,
        style={"input_type": "password"},
        help_text="实例账号密码，仅写入不回显；留空则自动生成随机强密码",
    )
    department_code = serializers.CharField(source="department.code", read_only=True)
    cluster_code = serializers.CharField(source="cluster.code", read_only=True)
    db_type_display = serializers.CharField(source="get_db_type_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = Instance
        exclude = ("_password",)
        read_only_fields = ("last_password_rotate", "created_at", "updated_at")

    def create(self, validated_data):
        password = validated_data.pop("password", None) or ""
        instance = Instance(**validated_data)
        if password:
            instance.password = password
        instance.save()
        return instance

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.password = password
        instance.save()
        return instance


class PortProbeSerializer(serializers.Serializer):
    host = serializers.CharField(max_length=255, help_text="IP 或域名")
    port = serializers.IntegerField(min_value=1, max_value=65535)
    timeout = serializers.FloatField(
        min_value=0.5, max_value=30.0, default=3.0, required=False
    )


class ProbeTaskQuerySerializer(serializers.Serializer):
    task_id = serializers.CharField(max_length=255, help_text="Celery 任务 ID")
