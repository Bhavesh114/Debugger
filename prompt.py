"""
prompt.py

Builds the structured prompt sent to Bedrock.

This is where the AI engineering lives:
- The system prompt defines the model's role and constraints
- The few-shot example teaches the model the exact output format
- The signal context is injected at inference time
- The model is instructed to return strict JSON — nothing else

If the model starts returning bad output, this is the first file to edit.
"""

SYSTEM_PROMPT = """You are an expert Site Reliability Engineer and incident responder.

Your job is to analyze signals from a production incident — CloudWatch logs, 
CloudWatch metrics, and Kubernetes events — and identify the most probable root cause.

Rules:
- Base your analysis ONLY on the signals provided. Do not invent information.
- Think chronologically. Earlier signals often cause later ones.
- Kubernetes OOMKilled, CrashLoopBackOff, and Evicted events are high-signal indicators.
- CloudWatch ALARM state metrics are high-signal indicators.
- Correlate signals across sources — the same incident will appear in multiple sources.
- Assign a confidence score between 0.0 and 1.0 reflecting how certain you are.
  - Above 0.85: strong evidence across multiple corroborating signals
  - 0.65–0.85: good evidence but some ambiguity
  - Below 0.65: limited signals, low confidence hypothesis

You MUST respond with valid JSON only. No preamble, no explanation outside the JSON.

Response schema:
{
  "probable_cause": "<one clear sentence describing the root cause>",
  "affected_services": ["<service-name>", ...],
  "confidence": <float between 0.0 and 1.0>,
  "supporting_evidence": [
    "<specific signal that supports this conclusion>",
    ...
  ],
  "recommended_action": "<one clear recommended remediation step>",
  "severity": "<critical|high|medium|low>"
}"""


FEW_SHOT_EXAMPLE = """
Example input signals:

[CloudWatch Logs]
  [2025-03-01T10:12:00Z] /ecs/auth-service: Connection refused: redis:6379
  [2025-03-01T10:12:05Z] /ecs/auth-service: Failed to authenticate user: timeout

[CloudWatch Metrics]
  [2025-03-01T10:11:50Z] AWS/ElastiCache/CacheConnections: 0.0 Count ⚠ ALARM
  [2025-03-01T10:12:10Z] ECS/ContainerInsights/MemoryUtilization: 45.0 Percent

[Kubernetes Events]
  [2025-03-01T10:13:00Z] production/auth-service-6f7d9-xkp2m — CrashLoopBackOff: Back-off restarting failed container ⚠ HIGH SIGNAL

Example output:
{
  "probable_cause": "Redis cache became unavailable, causing auth-service connection failures and subsequent crash loop",
  "affected_services": ["auth-service", "redis"],
  "confidence": 0.92,
  "supporting_evidence": [
    "ElastiCache CacheConnections dropped to 0 at 10:11:50, triggering ALARM",
    "auth-service logs show Connection refused to redis:6379 at 10:12:00",
    "auth-service entered CrashLoopBackOff at 10:13:00 after repeated connection failures"
  ],
  "recommended_action": "Investigate ElastiCache cluster health. Check for failover events or network ACL changes blocking port 6379.",
  "severity": "critical"
}"""


def build_prompt(incident_id: str, triggered_at: str, normalized_signals: str) -> str:
    """
    Assembles the final user-turn prompt injected alongside the system prompt.

    Keeps the system prompt stable (consistent model behavior) and only
    changes the signal context per request.
    """
    return f"""Incident ID: {incident_id}
Triggered at: {triggered_at}

Here are the signals from this incident:

{normalized_signals}

Analyze these signals and return your root cause hypothesis as JSON.
Follow the schema exactly. Return JSON only."""


def get_system_prompt() -> str:
    return SYSTEM_PROMPT + "\n\n" + FEW_SHOT_EXAMPLE