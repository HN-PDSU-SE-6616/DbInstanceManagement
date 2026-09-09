"""观测层：读取 Prometheus 注册表并输出人可读的运行指标快照"""
import logging

from prometheus_client import REGISTRY, generate_latest
from prometheus_client.parser import text_string_to_metric_families

logger = logging.getLogger("app")

_REQUESTS_FAMILIES = (
    "django_http_requests_total_by_view_method",
    "django_http_requests_total_by_transport",
)
_LATENCY_FAMILY = "django_http_requests_latency_seconds_by_view_method"
_STATUS_FAMILY = "django_http_responses_total_by_status_code"


def _collect():
    """导出 Prometheus 注册表文本并按指标族名组织样本"""
    families = {}
    try:
        text = generate_latest(REGISTRY).decode("utf-8")
        for family in text_string_to_metric_families(text):
            families[family.name] = list(family.samples)
    except Exception:
        logger.exception("读取 Prometheus registry 失败")
    return families


def metrics_snapshot():
    """汇总核心运行指标供页面展示"""
    snapshot = {
        "available": False,
        "requests_total": 0,
        "avg_latency_ms": None,
        "status_codes": {},
    }
    families = _collect()
    if not families:
        return snapshot
    snapshot["available"] = True

    req_name = next((name for name in _REQUESTS_FAMILIES if name in families), None)
    if req_name:
        samples = families[req_name]
        totals = [s.value for s in samples if s.name.endswith("_total")]
        snapshot["requests_total"] = int(
            sum(totals)
            if totals
            else sum(s.value for s in samples if not s.name.endswith("_created"))
        )

    latency_samples = families.get(_LATENCY_FAMILY)
    if latency_samples:
        latency_sum = next(
            (s.value for s in latency_samples if s.name.endswith("_sum")), 0.0
        )
        latency_count = next(
            (s.value for s in latency_samples if s.name.endswith("_count")), 0.0
        )
        if latency_count:
            snapshot["avg_latency_ms"] = round(latency_sum / latency_count * 1000, 2)

    status_samples = families.get(_STATUS_FAMILY)
    if status_samples:
        codes = {}
        for sample in status_samples:
            if sample.name.endswith("_created"):
                continue
            code = sample.labels.get("status_code") or sample.labels.get("code") or "unknown"
            codes[str(code)] = int(codes.get(str(code), 0) + sample.value)
        snapshot["status_codes"] = dict(sorted(codes.items()))
    return snapshot
