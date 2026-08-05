"""SigNoz observability service using OpenTelemetry."""

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter as HTTPOTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export import ConsoleSpanExporter

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def setup_opentelemetry(app=None, engine=None, redis_client=None) -> None:
    """Initialize OpenTelemetry with SigNoz exporter."""
    if not settings.SIGNOZ_ENABLED:
        logger.info("SigNoz instrumentation disabled")
        return

    try:
        resource = Resource.create(
            {
                "service.name": settings.SIGNOZ_SERVICE_NAME,
                "service.version": settings.SIGNOZ_SERVICE_VERSION,
                "deployment.environment": settings.SIGNOZ_DEPLOYMENT_ENVIRONMENT,
            }
        )

        trace_provider = TracerProvider(resource=resource)

        # Use gRPC exporter by default, fallback to HTTP
        try:
            otlp_exporter = OTLPSpanExporter(
                endpoint=settings.SIGNOZ_OTLP_ENDPOINT,
                insecure=True,
            )
            trace_provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
            logger.info("SigNoz gRPC exporter configured", endpoint=settings.SIGNOZ_OTLP_ENDPOINT)
        except Exception as exc:
            logger.warning("Failed to configure gRPC exporter, falling back to HTTP", error=str(exc))
            # Fallback to HTTP exporter
            http_endpoint = settings.SIGNOZ_OTLP_ENDPOINT.replace("4317", "4318")
            otlp_exporter = HTTPOTLPSpanExporter(endpoint=http_endpoint)
            trace_provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
            logger.info("SigNoz HTTP exporter configured", endpoint=http_endpoint)

        trace.set_tracer_provider(trace_provider)

        # Instrument HTTPX
        HTTPXClientInstrumentor().instrument()
        logger.info("HTTPX instrumentation enabled")

        # Instrument SQLAlchemy
        if engine is not None:
            SQLAlchemyInstrumentor().instrument(engine=engine)
            logger.info("SQLAlchemy instrumentation enabled")

        # Instrument Redis
        if redis_client is not None:
            RedisInstrumentor().instrument(redis_client=redis_client)
            logger.info("Redis instrumentation enabled")

        # Instrument logging
        LoggingInstrumentor().instrument()
        logger.info("Logging instrumentation enabled")

        logger.info(
            "SigNoz OpenTelemetry setup complete",
            service=settings.SIGNOZ_SERVICE_NAME,
            environment=settings.SIGNOZ_DEPLOYMENT_ENVIRONMENT,
            ui_url=settings.SIGNOZ_UI_URL,
        )

    except Exception as exc:
        logger.error("Failed to setup SigNoz instrumentation", error=str(exc))


def shutdown_opentelemetry() -> None:
    """Shutdown OpenTelemetry and flush remaining spans."""
    if not settings.SIGNOZ_ENABLED:
        return

    try:
        tracer_provider = trace.get_tracer_provider()
        if hasattr(tracer_provider, "shutdown"):
            tracer_provider.shutdown()
            logger.info("SigNoz OpenTelemetry shutdown complete")
    except Exception as exc:
        logger.error("Error during SigNoz shutdown", error=str(exc))
