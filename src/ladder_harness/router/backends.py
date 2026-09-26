"""Live model backends on Google Cloud: Gemini (google-genai, Vertex mode) and Claude (anthropic[vertex]).

Both use the caller's Application Default Credentials. Nothing here stores or accepts keys. On a
credential problem the error names the exact command the human must run — it never works around auth.
"""
from __future__ import annotations

import json
import os
import time

from .types import BackendUnavailable, ModelCall, ModelRefused, ModelResult, OutputTruncated, Usage

AUTH_HINT = ("Google Cloud credentials are missing or expired. Run in your own terminal:\n"
             "    gcloud auth application-default login\n"
             "then retry. (The harness never uses key files or other credential workarounds.)")


def project_id() -> str:
    pid = os.environ.get("LADDER_GCP_PROJECT") or os.environ.get("GOOGLE_CLOUD_PROJECT")
    if not pid:
        raise BackendUnavailable("Set LADDER_GCP_PROJECT (or GOOGLE_CLOUD_PROJECT) to your Google Cloud project id.")
    return pid


def _is_auth_error(e: Exception) -> bool:
    text = f"{type(e).__name__} {e}".lower()
    return any(s in text for s in ("defaultcredentialserror", "reauth", "refresh", "invalid_grant",
                                   "could not automatically determine credentials", "unauthenticated", "401"))


class VertexGemini:
    """Gemini on Vertex. Effort maps to thinking level (LOW / MEDIUM / HIGH)."""

    LEVELS = {"low": "LOW", "medium": "MEDIUM", "high": "HIGH"}

    def __init__(self, location: str = "global"):
        self.location = location
        self._client = None

    def _get(self):
        if self._client is None:
            from google import genai
            self._client = genai.Client(vertexai=True, project=project_id(), location=self.location)
        return self._client

    def call(self, c: ModelCall) -> ModelResult:
        from google.genai import types
        config = types.GenerateContentConfig(
            system_instruction=c.system,
            response_mime_type="application/json",
            response_json_schema=c.schema,
            thinking_config=types.ThinkingConfig(thinking_level=self.LEVELS[c.effort]),
            max_output_tokens=65536,          # Gemini counts thinking against this cap; bill is per actual token
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        )
        t0 = time.monotonic()
        try:
            resp = self._get().models.generate_content(model=c.model, contents=c.prompt, config=config)
        except Exception as e:  # noqa: BLE001 — classify, then re-raise with a precise message
            if _is_auth_error(e):
                raise BackendUnavailable(AUTH_HINT) from e
            raise
        latency = time.monotonic() - t0
        text = resp.text or ""
        um = resp.usage_metadata
        finish = str(getattr(resp.candidates[0], "finish_reason", "")) if resp.candidates else ""
        if "MAX_TOKENS" in finish:
            raise OutputTruncated(f"{c.model}/{c.effort} hit the output limit ({um.thoughts_token_count} thinking tokens)")
        usage = Usage(input=um.prompt_token_count or 0, output=um.candidates_token_count or 0,
                      thinking=um.thoughts_token_count or 0, cached=um.cached_content_token_count or 0)
        return ModelResult(json.loads(text) if text else {}, text, usage, latency, c.model, c.effort, "vertex")


class VertexClaude:
    """Claude on Vertex. Thinking is always on for Opus 5.5; effort is the only control."""

    def __init__(self, region: str = "global"):
        self.region = region
        self._client = None

    def _get(self):
        if self._client is None:
            from anthropic import AnthropicVertex
            self._client = AnthropicVertex(project_id=project_id(), region=self.region)
        return self._client

    def call(self, c: ModelCall) -> ModelResult:
        t0 = time.monotonic()
        try:
            with self._get().messages.stream(
                model=c.model,
                max_tokens=c.max_output_tokens,
                system=[{"type": "text", "text": c.system, "cache_control": {"type": "ephemeral"}}],
                messages=[{"role": "user", "content": c.prompt}],
                output_config={"effort": c.effort, "format": {"type": "json_schema", "schema": c.schema}},
            ) as stream:
                resp = stream.get_final_message()
        except Exception as e:  # noqa: BLE001
            if _is_auth_error(e):
                raise BackendUnavailable(AUTH_HINT) from e
            raise
        latency = time.monotonic() - t0
        if resp.stop_reason == "max_tokens":
            raise OutputTruncated(f"{c.model}/{c.effort} hit max_tokens={c.max_output_tokens}")
        if resp.stop_reason == "refusal":
            details = getattr(resp, "stop_details", None)
            raise ModelRefused(f"{c.model} declined: {getattr(details, 'category', None)} {getattr(details, 'explanation', '')}")
        text = next((b.text for b in resp.content if b.type == "text"), "")
        u = resp.usage
        cached = int(getattr(u, "cache_read_input_tokens", 0) or 0)
        written = int(getattr(u, "cache_creation_input_tokens", 0) or 0)
        usage = Usage(input=int(u.input_tokens) + cached + written, output=int(u.output_tokens), thinking=0,
                      cached=cached, cache_write=written)
        return ModelResult(json.loads(text) if text else {}, text, usage, latency, c.model, c.effort, "vertex")


def default_backends() -> dict[str, object]:
    return {"vertex-gemini": VertexGemini(), "vertex-claude": VertexClaude()}
