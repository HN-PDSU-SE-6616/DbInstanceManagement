"""中间件层"""
import logging
import time

logger = logging.getLogger("app.access")


class RequestTimingMiddleware:
    """请求计时中间件"""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        """处理请求：计时、调用后续处理、写响应头与访问日志。

        :param request: 请求对象。
        :Return: HttpResponse。
        """
        start = time.perf_counter()
        response = self.get_response(request)
        duration_ms = (time.perf_counter() - start) * 1000
        response["X-Request-Duration-Ms"] = f"{duration_ms:.2f}"

        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated:
            username = user.username
        else:
            username = "anonymous"
        logger.info(
            "%s %s -> %s %.2fms user=%s",
            request.method,
            request.get_full_path(),
            response.status_code,
            duration_ms,
            username,
        )
        if duration_ms >= 1000:
            logger.warning(
                "Slow request: %s %s took %.0f ms",
                request.method,
                request.get_full_path(),
                duration_ms,
            )
        return response