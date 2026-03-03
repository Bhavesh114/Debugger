"""
bedrock.py

Amazon Bedrock client. Sends the prompt to Claude Sonnet and parses
the JSON response back into a structured Python dict.

This is the only file that knows about Bedrock. Swapping to a different
model or provider means changing this file only — nothing else.
"""

import json
import logging
import boto3
from botocore.exceptions import ClientError, BotoCoreError

logger = logging.getLogger(__name__)

# Claude Sonnet on Bedrock — best balance of quality and latency for this task
MODEL_ID = "anthropic.claude-3-5-sonnet-20241022-v2:0"

# Keep responses focused — root cause analysis doesn't need long outputs
MAX_TOKENS = 1024


class BedrockClientError(Exception):
    """Raised when Bedrock returns an error or an unparseable response."""
    pass


class BedrockClient:
    def __init__(self, region: str = "us-east-1"):
        self.client = boto3.client("bedrock-runtime", region_name=region)

    def correlate(self, system_prompt: str, user_prompt: str) -> dict:
        """
        Sends the prompt to Bedrock and returns the parsed JSON response.

        Raises BedrockClientError if:
        - Bedrock returns an API error
        - The response is not valid JSON
        - The response is missing required fields
        """
        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": MAX_TOKENS,
            "system": system_prompt,
            "messages": [
                {"role": "user", "content": user_prompt}
            ],
            # Nudge the model to start its response with JSON
            "temperature": 0.1,  # Low temp = more deterministic, less creative
        }

        try:
            response = self.client.invoke_model(
                modelId=MODEL_ID,
                contentType="application/json",
                accept="application/json",
                body=json.dumps(body),
            )
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            raise BedrockClientError(f"Bedrock API error [{error_code}]: {e}") from e
        except BotoCoreError as e:
            raise BedrockClientError(f"Bedrock connection error: {e}") from e

        raw = json.loads(response["body"].read())
        text = raw["content"][0]["text"].strip()

        return self._parse_response(text)

    def _parse_response(self, text: str) -> dict:
        """
        Parses the model's text output into a structured dict.

        Handles two cases:
        1. Clean JSON — model followed instructions perfectly
        2. JSON wrapped in markdown code fences — model added ```json ... ```
        """
        # Strip markdown code fences if present
        if text.startswith("```"):
            lines = text.split("\n")
            # Remove first line (```json or ```) and last line (```)
            text = "\n".join(lines[1:-1]).strip()

        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as e:
            logger.error(f"Model returned non-JSON response: {text[:200]}")
            raise BedrockClientError(
                f"Model returned invalid JSON: {e}. Raw response: {text[:200]}"
            ) from e

        # Validate required fields are present
        required_fields = {
            "probable_cause",
            "affected_services",
            "confidence",
            "supporting_evidence",
            "recommended_action",
            "severity",
        }
        missing = required_fields - set(parsed.keys())
        if missing:
            raise BedrockClientError(
                f"Model response missing required fields: {missing}"
            )

        # Clamp confidence to valid range in case model goes out of bounds
        parsed["confidence"] = max(0.0, min(1.0, float(parsed["confidence"])))

        return parsed