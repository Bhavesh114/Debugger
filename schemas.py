"""
schemas.py

Pydantic models for all request and response validation.

This is the contract. If the input doesn't match these shapes,
FastAPI returns a 422 before the request ever reaches the AI layer.
If the output doesn't match, it fails before reaching the caller.

This is the first file to update when adding a new signal source.
"""

from datetime import datetime
from pydantic import BaseModel, Field


# ------------------------------------------------------------------ #
# Signal source models — one per source                               #
# ------------------------------------------------------------------ #

class CloudWatchLog(BaseModel):
    log_group: str = Field(..., description="CloudWatch log group name e.g. /ecs/payments-service")
    timestamp: datetime
    message: str


class CloudWatchMetric(BaseModel):
    metric_name: str = Field(..., description="e.g. MemoryUtilization")
    namespace: str = Field(..., description="e.g. ECS/ContainerInsights")
    value: float
    unit: str = Field(..., description="e.g. Percent, Count, Bytes")
    timestamp: datetime
    alarm_state: str | None = Field(None, description="ALARM | OK | INSUFFICIENT_DATA")


class KubernetesEvent(BaseModel):
    namespace: str
    pod: str
    reason: str = Field(..., description="e.g. OOMKilled, CrashLoopBackOff, Evicted")
    message: str
    timestamp: datetime


# ------------------------------------------------------------------ #
# Signals container                                                    #
# ------------------------------------------------------------------ #

class Signals(BaseModel):
    cloudwatch_logs: list[CloudWatchLog] = Field(
        default_factory=list,
        description="Log entries from CloudWatch Logs"
    )
    cloudwatch_metrics: list[CloudWatchMetric] = Field(
        default_factory=list,
        description="Metric data points and alarm states from CloudWatch"
    )
    kubernetes_events: list[KubernetesEvent] = Field(
        default_factory=list,
        description="Events from kubectl or Kubernetes event streams"
    )


# ------------------------------------------------------------------ #
# API request / response models                                        #
# ------------------------------------------------------------------ #

class CorrelateRequest(BaseModel):
    incident_id: str = Field(..., description="Unique identifier for this incident")
    triggered_at: datetime = Field(..., description="When the incident was first detected")
    signals: Signals

    class Config:
        json_schema_extra = {
            "example": {
                "incident_id": "inc-20250302-001",
                "triggered_at": "2025-03-02T14:37:00Z",
                "signals": {
                    "cloudwatch_logs": [
                        {
                            "log_group": "/ecs/payments-service",
                            "timestamp": "2025-03-02T14:35:12Z",
                            "message": "OutOfMemoryError: Java heap space"
                        }
                    ],
                    "cloudwatch_metrics": [
                        {
                            "metric_name": "MemoryUtilization",
                            "namespace": "ECS/ContainerInsights",
                            "value": 94.2,
                            "unit": "Percent",
                            "timestamp": "2025-03-02T14:35:00Z",
                            "alarm_state": "ALARM"
                        }
                    ],
                    "kubernetes_events": [
                        {
                            "namespace": "production",
                            "pod": "payments-service-7d9f8b-xkp2m",
                            "reason": "OOMKilled",
                            "message": "Container killed due to memory limit",
                            "timestamp": "2025-03-02T14:33:45Z"
                        }
                    ]
                }
            }
        }


class CorrelateResponse(BaseModel):
    incident_id: str
    probable_cause: str
    affected_services: list[str]
    confidence: float = Field(..., ge=0.0, le=1.0)
    supporting_evidence: list[str]
    recommended_action: str
    severity: str = Field(..., description="critical | high | medium | low")
    correlated_at: datetime


class HealthResponse(BaseModel):
    status: str
    model_id: str
    region: str