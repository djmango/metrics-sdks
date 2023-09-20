import asyncio
import time
from collections.abc import Callable
from datetime import datetime

from django.conf import settings

from readme_metrics import MetricsApiConfig
from readme_metrics.Metrics import Metrics
from readme_metrics.ResponseInfoWrapper import ResponseInfoWrapper


class MetricsMiddleware:
    def __init__(self, get_response: Callable, config=None):
        self.get_response = get_response
        self.config: MetricsApiConfig = config or settings.README_METRICS_CONFIG
        assert isinstance(self.config, MetricsApiConfig)
        self.metrics_core = Metrics(self.config)

    def __call__(self, request):
        if not asyncio.iscoroutinefunction(self.get_response):
            return self.sync_process_request(request)
        else:
            raise NotImplementedError("Async not implemented")

    def sync_process_request(self, request):
        self.preamble(request)
        response = self.get_response(request)
        self.handle_response(request, response)
        return response

    def preamble(self, request):
        try:
            request.rm_start_dt = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
            request.rm_start_ts = int(time.time() * 1000)
            if request.headers.get("Content-Length") or request.body:
                request.rm_content_length = request.headers["Content-Length"] or "0"
                request.rm_body = request.body or ""
        except Exception as e:
            self.config.LOGGER.exception(e)

    def handle_response(self, request, response):
        try:
            try:
                body = response.content.decode("utf-8")
            except UnicodeDecodeError:
                body = "[NOT VALID UTF-8]"
            response_info = ResponseInfoWrapper(
                response.headers,
                response.status_code,
                content_type=None,
                content_length=None,
                body=body,
            )
            self.metrics_core.process(request, response_info)
        except Exception as e:
            self.config.LOGGER.exception(e)
