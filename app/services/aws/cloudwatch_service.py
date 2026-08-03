"""CloudWatch service for monitoring and logging."""

import json
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import Any

import aioboto3
from botocore.exceptions import ClientError

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class CloudWatchService:
    """Service for interacting with AWS CloudWatch."""

    def __init__(self):
        self.session = aioboto3.Session(
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION,
        )
        self.log_group = settings.CLOUDWATCH_LOG_GROUP
        self.log_stream = settings.CLOUDWATCH_LOG_STREAM
        self._client = None

    @asynccontextmanager
    async def get_client(self):
        """Get CloudWatch client context manager."""
        async with self.session.client(
            "cloudwatch",
            endpoint_url=settings.AWS_ENDPOINT_URL,
        ) as client:
            yield client

    @asynccontextmanager
    async def get_logs_client(self):
        """Get CloudWatch Logs client context manager."""
        async with self.session.client(
            "logs",
            endpoint_url=settings.AWS_ENDPOINT_URL,
        ) as client:
            yield client

    async def put_metric_data(
        self,
        namespace: str,
        metric_data: list[dict[str, Any]],
    ) -> bool:
        """Put custom metric data."""
        try:
            async with self.get_client() as client:
                await client.put_metric_data(
                    Namespace=namespace,
                    MetricData=metric_data,
                )
            logger.debug("Metric data sent", namespace=namespace, count=len(metric_data))
            return True
        except ClientError as e:
            logger.error("Failed to put metric data", error=str(e))
            return False

    async def put_metric(
        self,
        namespace: str,
        name: str,
        value: float,
        unit: str = "Count",
        dimensions: list[dict[str, str]] | None = None,
    ) -> bool:
        """Put a single custom metric."""
        metric_data = [
            {
                "MetricName": name,
                "Value": value,
                "Unit": unit,
                "Timestamp": datetime.now(UTC),
            }
        ]

        if dimensions:
            metric_data[0]["Dimensions"] = dimensions

        return await self.put_metric_data(namespace=namespace, metric_data=metric_data)

    async def get_metric_statistics(
        self,
        namespace: str,
        metric_name: str,
        start_time: datetime,
        end_time: datetime,
        period: int = 300,
        statistics: list[str] | None = None,
    ) -> dict[str, Any] | None:
        """Get metric statistics."""
        try:
            async with self.get_client() as client:
                response = await client.get_metric_statistics(
                    Namespace=namespace,
                    MetricName=metric_name,
                    StartTime=start_time,
                    EndTime=end_time,
                    Period=period,
                    Statistics=statistics or ["Average"],
                )
            return response.get("Datapoints", [])
        except ClientError as e:
            logger.error("Failed to get metric statistics", error=str(e))
            return None

    async def create_log_group(self, log_group_name: str | None = None) -> bool:
        """Create a CloudWatch log group."""
        group = log_group_name or self.log_group
        try:
            async with self.get_logs_client() as client:
                await client.create_log_group(logGroupName=group)
            logger.info("Log group created", group=group)
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "ResourceAlreadyOperationException":
                return True
            logger.error("Failed to create log group", error=str(e))
            return False

    async def create_log_stream(
        self,
        log_group_name: str | None = None,
        log_stream_name: str | None = None,
    ) -> bool:
        """Create a CloudWatch log stream."""
        group = log_group_name or self.log_group
        stream = log_stream_name or self.log_stream
        try:
            async with self.get_logs_client() as client:
                await client.create_log_stream(
                    logGroupName=group,
                    logStreamName=stream,
                )
                # Store sequence token
                self._sequence_token = None  # New stream starts fresh
            logger.info("Log stream created", group=group, stream=stream)
            return True
        except ClientError as e:
            logger.error("Failed to create log stream", error=str(e))
            return False

    async def put_log_events(
        self,
        log_events: list[dict[str, Any]],
        log_group_name: str | None = None,
        log_stream_name: str | None = None,
    ) -> bool:
        """Put log events to CloudWatch."""
        group = log_group_name or self.log_group
        stream = log_stream_name or self.log_stream

        # Format log events
        events = []
        for event in log_events:
            events.append(
                {
                    "timestamp": event.get("timestamp")
                    or int(datetime.now(UTC).timestamp() * 1000),
                    "message": event.get("message")
                    if isinstance(event.get("message"), str)
                    else json.dumps(event.get("message")),
                }
            )

        if not events:
            return True

        try:
            async with self.get_logs_client() as client:
                params = {
                    "logGroupName": group,
                    "logStreamName": stream,
                    "logEvents": events,
                }

                # Use sequence token if available
                token = getattr(self, "_sequence_token", None)
                if token:
                    params["sequenceToken"] = token

                response = await client.put_log_events(**params)
                self._sequence_token = response.get("nextSequenceToken")

            return True
        except ClientError as e:
            logger.error("Failed to put log events", error=str(e))
            return False

    async def put_log_event(
        self,
        message: str,
        level: str = "INFO",
        log_group_name: str | None = None,
        log_stream_name: str | None = None,
    ) -> bool:
        """Put a single log event."""
        event = {
            "timestamp": int(datetime.now(UTC).timestamp() * 1000),
            "message": json.dumps(
                {
                    "level": level,
                    "message": message,
                    "timestamp": datetime.now(UTC).isoformat(),
                }
            ),
        }
        return await self.put_log_events(
            log_events=[event],
            log_group_name=log_group_name,
            log_stream_name=log_stream_name,
        )

    async def get_log_events(
        self,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 100,
        log_group_name: str | None = None,
        log_stream_name: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get log events from CloudWatch."""
        group = log_group_name or self.log_group
        stream = log_stream_name or self.log_stream

        start = start_time or (datetime.now(UTC) - timedelta(hours=1))
        end = end_time or datetime.now(UTC)

        try:
            async with self.get_logs_client() as client:
                response = await client.get_log_events(
                    logGroupName=group,
                    logStreamName=stream,
                    startTime=int(start.timestamp() * 1000),
                    endTime=int(end.timestamp() * 1000),
                    limit=limit,
                    startFromHead=False,
                )
            return response.get("events", [])
        except ClientError as e:
            logger.error("Failed to get log events", error=str(e))
            return []

    async def filter_log_events(
        self,
        filter_pattern: str,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 100,
        log_group_name: str | None = None,
    ) -> list[dict[str, Any]]:
        """Filter log events across log streams."""
        group = log_group_name or self.log_group

        start = start_time or (datetime.now(UTC) - timedelta(hours=1))
        end = end_time or datetime.now(UTC)

        try:
            async with self.get_logs_client() as client:
                response = await client.filter_log_events(
                    logGroupName=group,
                    filterPattern=filter_pattern,
                    startTime=int(start.timestamp() * 1000),
                    endTime=int(end.timestamp() * 1000),
                    limit=limit,
                )
            return response.get("events", [])
        except ClientError as e:
            logger.error("Failed to filter log events", error=str(e))
            return []

    async def put_dashboard(
        self,
        name: str,
        dashboard_body: dict[str, Any],
    ) -> bool:
        """Create or update a CloudWatch dashboard."""
        try:
            async with self.get_client() as client:
                await client.put_dashboard(
                    DashboardName=name,
                    DashboardBody=json.dumps(dashboard_body),
                )
            logger.info("Dashboard updated", name=name)
            return True
        except ClientError as e:
            logger.error("Failed to put dashboard", error=str(e))
            return False

    async def list_dashboards(self) -> list[dict[str, str]]:
        """List CloudWatch dashboards."""
        try:
            async with self.get_client() as client:
                response = await client.list_dashboards()
            return response.get("DashboardEntries", [])
        except ClientError as e:
            logger.error("Failed to list dashboards", error=str(e))
            return []

    async def describe_alarms(self) -> list[dict[str, Any]]:
        """Describe CloudWatch alarms."""
        try:
            async with self.get_client() as client:
                response = await client.describe_alarms()

            return response.get("MetricAlarms", [])
        except ClientError as e:
            logger.error("Failed to describe alarms", error=str(e))
            return []

    async def put_alarm(
        self,
        name: str,
        metric_name: str,
        namespace: str,
        threshold: float,
        comparison_operator: str = "GreaterThanThreshold",
        evaluation_periods: int = 1,
        period: int = 300,
        statistic: str = "Average",
        alarm_actions: list[str] | None = None,
    ) -> bool:
        """Create or update a CloudWatch alarm."""
        try:
            async with self.get_client() as client:
                params = {
                    "AlarmName": name,
                    "MetricName": metric_name,
                    "Namespace": namespace,
                    "Threshold": threshold,
                    "ComparisonOperator": comparison_operator,
                    "EvaluationPeriods": evaluation_periods,
                    "Period": period,
                    "Statistic": statistic,
                }

                if alarm_actions:
                    params["AlarmActions"] = alarm_actions

                await client.put_metric_alarm(**params)

            logger.info("Alarm created", name=name)
            return True
        except ClientError as e:
            logger.error("Failed to create alarm", error=str(e))
            return False


# Global CloudWatch service instance
cloudwatch_service = CloudWatchService()
