"""OpenTelemetry configuration and setup utilities for Strands agents.

This module provides centralized configuration and initialization functionality
for OpenTelemetry components and other telemetry infrastructure shared across Strands applications.
"""

import logging
from importlib.metadata import version

import opentelemetry.trace as trace_api
from opentelemetry import propagate
from opentelemetry.baggage.propagation import W3CBaggagePropagator
from opentelemetry.propagators.composite import CompositePropagator
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider as SDKTracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter, SimpleSpanProcessor
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

logger = logging.getLogger(__name__)


def get_otel_resource() -> Resource:
    """Create a standard OpenTelemetry resource with service information.

    Returns:
        Resource object with standard service information.
    """
    resource = Resource.create(
        {
            "service.name": "strands-agents",
            "service.version": version("strands-agents"),
            "telemetry.sdk.name": "opentelemetry",
            "telemetry.sdk.language": "python",
        }
    )

    return resource


class StrandsTelemetry:
    """OpenTelemetry configuration and setup for Strands applications.

    Automatically initializes a tracer provider with text map propagators.
    Trace exporters (console, OTLP) can be set up individually using dedicated methods
    that support method chaining for convenient configuration.

    Args:
        tracer_provider: Optional pre-configured SDKTracerProvider. If None,
            a new one will be created and set as the global tracer provider.

    Environment Variables:
        Environment variables are handled by the underlying OpenTelemetry SDK:
        - OTEL_EXPORTER_OTLP_ENDPOINT: OTLP endpoint URL
        - OTEL_EXPORTER_OTLP_HEADERS: Headers for OTLP requests

    Examples:
        Quick setup with method chaining:
        >>> StrandsTelemetry().setup_console_exporter().setup_otlp_exporter()

        Using a custom tracer provider:
        >>> StrandsTelemetry(tracer_provider=my_provider).setup_console_exporter()

        Step-by-step configuration:
        >>> telemetry = StrandsTelemetry()
        >>> telemetry.setup_console_exporter()
        >>> telemetry.setup_otlp_exporter()

    Note:
        - The tracer provider is automatically initialized upon instantiation
        - When no tracer_provider is provided, the instance sets itself as the global provider
        - Exporters must be explicitly configured using the setup methods
        - Failed exporter configurations are logged but do not raise exceptions
        - All setup methods return self to enable method chaining
    """

    def __init__(
        self,
        tracer_provider: SDKTracerProvider | None = None,
    ) -> None:
        """Initialize the StrandsTelemetry instance.

        Args:
            tracer_provider: Optional pre-configured tracer provider.
                If None, a new one will be created and set as global.

        The instance is ready to use immediately after initialization, though
        trace exporters must be configured separately using the setup methods.
        """
        if tracer_provider:
            self.tracer_provider = tracer_provider
        else:
            self.resource = get_otel_resource()
            self._initialize_tracer()

    def _initialize_tracer(self) -> None:
        """Initialize the OpenTelemetry tracer."""
        logger.info("initializing tracer")

        # Create tracer provider
        self.tracer_provider = SDKTracerProvider(resource=self.resource)

        # Set as global tracer provider
        trace_api.set_tracer_provider(self.tracer_provider)

        # Set up propagators
        propagate.set_global_textmap(
            CompositePropagator(
                [
                    W3CBaggagePropagator(),
                    TraceContextTextMapPropagator(),
                ]
            )
        )

    def setup_console_exporter(self) -> "StrandsTelemetry":
        """Set up console exporter for the tracer provider."""
        try:
            logger.info("enabling console export")
            console_processor = SimpleSpanProcessor(ConsoleSpanExporter())
            self.tracer_provider.add_span_processor(console_processor)
        except Exception as e:
            logger.exception("error=<%s> | Failed to configure console exporter", e)
        return self

    def setup_otlp_exporter(self) -> "StrandsTelemetry":
        """Set up OTLP exporter for the tracer provider."""
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

        try:
            otlp_exporter = OTLPSpanExporter()
            batch_processor = BatchSpanProcessor(otlp_exporter)
            self.tracer_provider.add_span_processor(batch_processor)
            logger.info("OTLP exporter configured")
        except Exception as e:
            logger.exception("error=<%s> | Failed to configure OTLP exporter", e)
        return self
