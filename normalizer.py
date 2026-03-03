"""
normalizer.py

Transforms raw signal arrays from each source into clean, structured text
that an LLM can reason about effectively.

Each source has its own normalizer function. Adding a new signal source
means adding one new function here — nothing else changes.
"""

from schemas import CloudWatchLog, CloudWatchMetric, KubernetesEvent


def normalize_cloudwatch_logs(logs: list[CloudWatchLog]) -> str:
    """
    Converts raw CloudWatch log entries into a chronologically sorted,
    readable block of text. Deduplicates identical messages to reduce
    prompt noise.
    """
    if not logs:
        return "No CloudWatch log signals provided."

    # Sort chronologically
    sorted_logs = sorted(logs, key=lambda x: x.timestamp)

    # Deduplicate identical messages (repeated errors add noise, not signal)
    seen = set()
    unique_logs = []
    for log in sorted_logs:
        key = (log.log_group, log.message)
        if key not in seen:
            seen.add(key)
            unique_logs.append(log)

    lines = ["[CloudWatch Logs]"]
    for log in unique_logs:
        lines.append(f"  [{log.timestamp}] {log.log_group}: {log.message}")

    return "\n".join(lines)


def normalize_cloudwatch_metrics(metrics: list[CloudWatchMetric]) -> str:
    """
    Converts CloudWatch metric data points into a readable summary.
    Highlights any metrics that are in ALARM state — these are the
    most signal-rich data points for root cause analysis.
    """
    if not metrics:
        return "No CloudWatch metric signals provided."

    sorted_metrics = sorted(metrics, key=lambda x: x.timestamp)

    lines = ["[CloudWatch Metrics]"]
    for m in sorted_metrics:
        alarm_flag = " ⚠ ALARM" if m.alarm_state == "ALARM" else ""
        lines.append(
            f"  [{m.timestamp}] {m.namespace}/{m.metric_name}: "
            f"{m.value} {m.unit}{alarm_flag}"
        )

    return "\n".join(lines)


def normalize_kubernetes_events(events: list[KubernetesEvent]) -> str:
    """
    Converts Kubernetes events into a readable block.
    OOMKilled, CrashLoopBackOff, Evicted are flagged as high-signal
    events — they directly indicate container-level failures.
    """
    if not events:
        return "No Kubernetes event signals provided."

    HIGH_SIGNAL_REASONS = {
        "OOMKilled",
        "CrashLoopBackOff",
        "Evicted",
        "BackOff",
        "Failed",
        "FailedScheduling",
        "FailedMount",
    }

    sorted_events = sorted(events, key=lambda x: x.timestamp)

    lines = ["[Kubernetes Events]"]
    for e in sorted_events:
        flag = " ⚠ HIGH SIGNAL" if e.reason in HIGH_SIGNAL_REASONS else ""
        lines.append(
            f"  [{e.timestamp}] {e.namespace}/{e.pod} "
            f"— {e.reason}: {e.message}{flag}"
        )

    return "\n".join(lines)


def normalize_all(signals) -> str:
    """
    Master normalizer. Combines all signal sources into a single
    structured context block ready to be injected into the prompt.

    The order matters — logs first (what happened), then metrics
    (how bad), then Kubernetes events (container-level impact).
    """
    sections = [
        normalize_cloudwatch_logs(signals.cloudwatch_logs),
        normalize_cloudwatch_metrics(signals.cloudwatch_metrics),
        normalize_kubernetes_events(signals.kubernetes_events),
    ]

    return "\n\n".join(sections)