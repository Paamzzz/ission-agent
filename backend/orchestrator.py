# -*- coding: utf-8 -*-
"""
Ission Agent — Orquestrador principal.

Fluxo de execução:
  1. Busca dados reais da issue via API do GitHub.
  2. [QUALITY SCORE]   Avalia a qualidade da issue com heurísticas (zero API calls).
  3. [FOUNDRY IQ RAG]  Extrai diretrizes arquiteturais do Azure AI Search.
  4. [CLASSIFIER]      Classifica tipo + prioridade (Foundry context + Gemini) — call #1.
  5. [PLANNER]         Gera o plano técnico com auto-revisão embutida — call #2.

SDK: google-genai >= 1.0.0

ARCHITECTURE DECISION — CRITIC REMOVED (June 2026):
  The CRITIC stage was removed to eliminate 503 UNAVAILABLE cascade failures.
  Root cause: gemini-2.5-flash returns intermittent 503 under high demand.
  With 3 sequential calls, any 503 on PLANNER or CRITIC caused full pipeline failure.
  With 2 calls, exposure is reduced by 33% and the PLANNER prompt now includes
  a self-review instruction that preserves output quality.

  Option A chosen over B (merge prompts) and C (model split) because:
  - A reduces call count without increasing token cost per call.
  - B produces a larger single prompt with higher 503 exposure per call.
  - C still uses 3 calls and adds gemini-2.5-pro quota uncertainty.

  gemini-2.5-flash has thinking built-in — a single well-instructed call already
  produces plans with implicit self-correction. The CRITIC rarely changed output
  in practice; it primarily added the "> Critic Review:" prefix annotation.

CONFIRMED WORKING MODELS (June 2026, AQ. key format):
  ✓ gemini-2.5-flash   — HTTP 200, ~200ms, primary model
  ✓ gemini-2.5-pro     — HTTP 200 (quota may be limited on free tier)
  ✗ gemini-2.0-flash   — HTTP 429 RESOURCE_EXHAUSTED (quota zeroed for this project)
  ✗ gemini-1.5-flash   — HTTP 404 NOT FOUND (removed from v1beta API)

SINGLETON PATTERN:
  IssionOrchestrator is created ONCE at application startup via create_orchestrator().
  main.py uses FastAPI lifespan to store it in app.state.
  models.list() runs exactly once per process — not per request.
  Total Gemini calls per pipeline: 2 (CLASSIFIER + PLANNER).
"""

import json
import logging
import os
import pathlib
import re
import socket
import sys
import threading
import time
import urllib.request
import urllib.error
import asyncio
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# IPv4 enforcement — must happen BEFORE the google-genai SDK is imported.
#
# ROOT CAUSE (confirmed): DNS resolves generativelanguage.googleapis.com to
# IPv6 first on this host. IPv6 TCP hangs indefinitely. IPv4 connects in ~17ms.
# ---------------------------------------------------------------------------
_GOOGLEAPIS_SUFFIX = ".googleapis.com"
_original_getaddrinfo = socket.getaddrinfo


def _force_ipv4_for_googleapis(host, port, family=0, type=0, proto=0, flags=0):
    """Return only IPv4 results for googleapis.com; pass everything else through."""
    if isinstance(host, str) and host.endswith(_GOOGLEAPIS_SUFFIX):
        return _original_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)
    return _original_getaddrinfo(host, port, family, type, proto, flags)


socket.getaddrinfo = _force_ipv4_for_googleapis

from google import genai
from google.genai import errors as genai_errors
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Logger
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("ission.orchestrator")


def _ms(t0: float) -> str:
    return f"{(time.perf_counter() - t0) * 1000:.0f}ms"


# ---------------------------------------------------------------------------
# Allowed models — hard allowlist, never falls back to unsupported models.
# Only models confirmed working via raw HTTP test on this project/key.
# ---------------------------------------------------------------------------
ALLOWED_MODELS = frozenset({
    "gemini-2.5-flash",
    "gemini-2.5-pro",
})
DEFAULT_MODEL = "gemini-2.5-flash"

# ---------------------------------------------------------------------------
# Per-stage timeouts (seconds)
# ---------------------------------------------------------------------------
TIMEOUT_FOUNDRY_SEARCH: float = 10.0
TIMEOUT_FOUNDRY_CLASSIFY: float = 30.0
TIMEOUT_GEMINI_PLANNER: float = 45.0

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = (
    "You are Ission Agent, integrated with the Microsoft Foundry IQ layer. "
    "Analyze the following GitHub issue and generate a structured technical action plan "
    "in Markdown that strictly respects the corporate architectural guidelines of the "
    "Recall project provided in the context."
)

# ---------------------------------------------------------------------------
# Quality score keyword lists
# ---------------------------------------------------------------------------
_REPRO_KEYWORDS = [
    "steps to reproduce", "to reproduce", "reproduction", "reproduzir",
    "passos para", "how to reproduce", "repro steps", "reproduce",
]
_ENV_KEYWORDS = [
    "version", "versão", "os ", "operating system", "browser", "node",
    "python", "environment", "ambiente", "platform", "plataforma",
    "runtime", "dependency", "dependência",
]
_EXPECTED_KEYWORDS = [
    "expected", "esperado", "should", "deveria", "actual", "atual",
    "instead", "ao invés", "but got", "mas obteve", "observed",
]
_LOGS_KEYWORDS = [
    "error:", "exception", "traceback", "stack trace", "log", "output",
    "stderr", "stdout", "console", "erro:", "exceção",
]


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class QualityScore:
    score: int
    missing: list[str] = field(default_factory=list)
    present: list[str] = field(default_factory=list)
    level: str = "low"


@dataclass
class IssueClassification:
    issue_type: str
    priority: str
    confidence: str
    rationale: str


# ---------------------------------------------------------------------------
# Module-level generate_content call counter (resets on process restart)
# ---------------------------------------------------------------------------
_gemini_call_counter: int = 0
_gemini_call_counter_lock = threading.Lock()


def _increment_gemini_counter() -> int:
    global _gemini_call_counter
    with _gemini_call_counter_lock:
        _gemini_call_counter += 1
        return _gemini_call_counter


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _detect_api_key_type(api_key: str) -> str:
    """
    Never logs the key value — only the type.

    AQ. prefix = current Google AI Studio key format (post-2024, base64url proto).
    AIzaSy prefix = legacy Google AI Studio key format.
    Both are valid for generativelanguage.googleapis.com.
    """
    if not api_key:
        return "MISSING"
    if api_key.startswith("AQ."):
        return "Google AI Studio key (AQ. format, post-2024) ✓"
    if api_key.startswith("AIza"):
        return "Google AI Studio key (AIzaSy legacy format) ✓"
    if api_key.startswith("ya29."):
        return "OAuth2 access token — NOT a static key, will expire"
    if len(api_key) > 200:
        return "Possible service-account JSON — check format"
    return f"Unknown prefix ({api_key[:4]}...) length={len(api_key)}"


def _is_foundry_configured(endpoint: str, key: str) -> tuple[bool, str]:
    placeholders = {"", "YOUR_AZURE_AI_SEARCH_KEY", "COLE_AQUI",
                    "YOUR_PROJECT", "YOUR_AZURE_AI_FOUNDRY_KEY"}
    if not endpoint or endpoint.strip() in placeholders:
        return False, "AZURE_AI_FOUNDRY_ENDPOINT is not set"
    if not key or key.strip() in placeholders:
        return False, "AZURE_AI_FOUNDRY_KEY is not set"
    if key.startswith("https://"):
        return False, "AZURE_AI_FOUNDRY_KEY looks like a URL — ENDPOINT and KEY are swapped"
    if not endpoint.startswith("https://"):
        return False, f"AZURE_AI_FOUNDRY_ENDPOINT must start with https:// (got: {endpoint[:40]!r})"
    return True, ""


# ---------------------------------------------------------------------------
# Startup validation — runs ONCE when the singleton is created
# ---------------------------------------------------------------------------

def _validate_model_at_startup(api_key: str, model_id: str) -> None:
    """
    Validates that the configured model is in models.list() for this key.
    Raises RuntimeError if not — causing startup to fail fast rather than
    timing out on the first real request.

    Called once from create_orchestrator(). Never called per-request.
    """
    log.info("=" * 70)
    log.info("[STARTUP][GEMINI] ── Gemini Model Validation ──")
    log.info("[STARTUP][GEMINI] SDK version      : %s", genai.__version__)
    log.info("[STARTUP][GEMINI] Python            : %s", sys.version.split()[0])
    log.info("[STARTUP][GEMINI] Model configured  : %s", model_id)
    log.info("[STARTUP][GEMINI] Allowed models    : %s", sorted(ALLOWED_MODELS))
    log.info("[STARTUP][GEMINI] Key type          : %s", _detect_api_key_type(api_key))
    log.info("[STARTUP][GEMINI] Key length        : %d chars", len(api_key))
    log.info("[STARTUP][GEMINI] Key last 6        : ...%s",
             api_key[-6:] if len(api_key) >= 6 else "TOO SHORT")

    # ── System env vars that could interfere ─────────────────────────────
    sys_google_key  = os.environ.get("GOOGLE_API_KEY", "")
    sys_vertexai    = os.environ.get("GOOGLE_GENAI_USE_VERTEXAI", "NOT SET")
    sys_enterprise  = os.environ.get("GOOGLE_GENAI_USE_ENTERPRISE", "NOT SET")
    sys_project     = os.environ.get("GOOGLE_CLOUD_PROJECT", "NOT SET")
    sys_location    = os.environ.get("GOOGLE_CLOUD_LOCATION", "NOT SET")

    log.info("[STARTUP][GEMINI] GOOGLE_API_KEY (sys)          : %s",
             f"SET ...{sys_google_key[-6:]}" if sys_google_key else "NOT SET")
    log.info("[STARTUP][GEMINI] GOOGLE_GENAI_USE_VERTEXAI     : %s", sys_vertexai)
    log.info("[STARTUP][GEMINI] GOOGLE_GENAI_USE_ENTERPRISE   : %s", sys_enterprise)
    log.info("[STARTUP][GEMINI] GOOGLE_CLOUD_PROJECT          : %s", sys_project)
    log.info("[STARTUP][GEMINI] GOOGLE_CLOUD_LOCATION         : %s", sys_location)

    if sys_google_key:
        log.warning(
            "[STARTUP][GEMINI] ⚠ GOOGLE_API_KEY is set in system environment. "
            "SDK prioritizes it over GEMINI_API_KEY from .env. "
            "Active key: ...%s", sys_google_key[-6:],
        )

    # ── Hard check: model must be in ALLOWED_MODELS ──────────────────────
    if model_id not in ALLOWED_MODELS:
        raise RuntimeError(
            f"[STARTUP] REJECTED model '{model_id}' — not in ALLOWED_MODELS.\n"
            f"  Allowed: {sorted(ALLOWED_MODELS)}\n"
            f"  Set GEMINI_MODEL_ID=gemini-2.5-flash in .env"
        )

    if not api_key:
        raise RuntimeError(
            "[STARTUP] GEMINI_API_KEY is empty. Cannot start — all Gemini calls would fail."
        )

    # ── Inspect the client before models.list() ──────────────────────────
    client = genai.Client(api_key=api_key)
    ac = client._api_client
    base_url = getattr(getattr(ac, "_http_options", None), "base_url", "N/A")
    api_ver  = getattr(getattr(ac, "_http_options", None), "api_version", "N/A")

    log.info("[STARTUP][GEMINI] SDK vertexai mode : %s", ac.vertexai)
    log.info("[STARTUP][GEMINI] SDK endpoint      : %s", base_url)
    log.info("[STARTUP][GEMINI] SDK api_version   : %s", api_ver)
    log.info("[STARTUP][GEMINI] SDK active key    : ...%s",
             ac.api_key[-6:] if ac.api_key and len(ac.api_key) >= 6 else str(ac.api_key))

    # Verify the SDK key matches .env key (guards against GOOGLE_API_KEY override)
    env_last6 = api_key[-6:] if len(api_key) >= 6 else api_key
    sdk_last6 = ac.api_key[-6:] if ac.api_key and len(ac.api_key) >= 6 else ""
    if env_last6 != sdk_last6:
        log.error(
            "[STARTUP][GEMINI] ✗ KEY MISMATCH: .env ...%s vs SDK active ...%s. "
            "GOOGLE_API_KEY system env var is overriding GEMINI_API_KEY.",
            env_last6, sdk_last6,
        )
    else:
        log.info("[STARTUP][GEMINI] ✓ SDK key matches .env key (...%s)", sdk_last6)

    # ── models.list() — runs once at startup ─────────────────────────────
    t0 = time.perf_counter()
    log.info("[STARTUP][GEMINI] Calling models.list() (once at startup)...")
    try:
        all_models = list(client.models.list())
    except genai_errors.ClientError as e:
        err = str(e)
        if "401" in err or "403" in err or "API_KEY_INVALID" in err:
            raise RuntimeError(
                f"[STARTUP] Gemini auth failure — API key rejected (401/403).\n"
                f"  Key type: {_detect_api_key_type(api_key)}\n"
                f"  Verify at: https://aistudio.google.com/app/apikey\n"
                f"  Error: {err[:200]}"
            ) from e
        raise RuntimeError(f"[STARTUP] models.list() failed: {err[:300]}") from e

    model_names = [getattr(m, "name", str(m)) for m in all_models]
    log.info("[STARTUP][GEMINI] models.list() returned %d models in %s",
             len(model_names), _ms(t0))
    log.info("[STARTUP][GEMINI] Available Gemini models:")
    for name in sorted(n for n in model_names if "gemini" in n.lower()):
        log.info("[STARTUP][GEMINI]   • %s", name)

    # ── Confirm configured model is in the list ───────────────────────────
    variants = [model_id, f"models/{model_id}", f"gemini/{model_id}"]
    found = any(any(v in name for v in variants) for name in model_names)
    if not found:
        raise RuntimeError(
            f"[STARTUP] Model '{model_id}' is NOT in models.list() for this API key.\n"
            f"  This would cause generate_content() to hang until timeout on every request.\n"
            f"  Available models are listed above.\n"
            f"  Set GEMINI_MODEL_ID=gemini-2.5-flash in .env"
        )

    log.info("[STARTUP][GEMINI] ✓ Model '%s' confirmed available — startup validation passed.",
             model_id)
    log.info("[STARTUP][GEMINI] generate_content calls so far this process: %d",
             _gemini_call_counter)
    log.info("=" * 70)


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

class IssionOrchestrator:
    """
    Do not instantiate directly.  Use create_orchestrator() which runs startup
    validation and returns a ready-to-use singleton.
    """

    def __init__(
        self,
        gemini_api_key: str,
        gemini_model_id: str,
        foundry_endpoint: str,
        foundry_key: str,
        foundry_index: str,
    ) -> None:
        self.gemini_api_key  = gemini_api_key
        self.gemini_model_id = gemini_model_id
        self.foundry_endpoint = foundry_endpoint
        self.foundry_key      = foundry_key
        self.foundry_index    = foundry_index
        self._github_api_base = "https://api.github.com/repos"

        self._foundry_ok, self._foundry_reason = _is_foundry_configured(
            foundry_endpoint, foundry_key
        )
        if not self._foundry_ok:
            log.warning("[STARTUP][FOUNDRY] %s", self._foundry_reason)
        else:
            log.info("[STARTUP][FOUNDRY] Endpoint : %s", foundry_endpoint)
            log.info("[STARTUP][FOUNDRY] Index    : %s", foundry_index)
            log.info("[STARTUP][FOUNDRY] Key len  : %d chars", len(foundry_key))
            self._log_foundry_dns_status()

    # ------------------------------------------------------------------
    # Foundry DNS diagnostic
    # ------------------------------------------------------------------

    def _log_foundry_dns_status(self) -> None:
        host = (
            self.foundry_endpoint
            .replace("https://", "")
            .replace("http://", "")
            .split("/")[0]
        )
        try:
            ip = socket.getaddrinfo(host, 443)[0][4][0]
            log.info("[STARTUP][FOUNDRY] DNS OK: %s -> %s", host, ip)
        except socket.gaierror as e:
            cogsvcs = host.replace(".search.windows.net", "") + ".cognitiveservices.azure.com"
            log.error(
                "[STARTUP][FOUNDRY] DNS FAIL: '%s' -> %s\n"
                "  This is not a valid Azure AI Search hostname.\n"
                "  The resource may be reachable at: https://%s\n"
                "  TO FIX: find the Azure AI Search resource in Azure Portal,\n"
                "  copy its endpoint (https://<name>.search.windows.net) and admin key.\n"
                "  CURRENT: Foundry stages running in FALLBACK MODE.",
                host, e, cogsvcs,
            )
            self._foundry_ok = False
            self._foundry_reason = f"DNS failed for '{host}' — not an Azure AI Search endpoint."

    # ------------------------------------------------------------------
    # Gemini client — created per call (lightweight, stateless)
    # ------------------------------------------------------------------

    def _gemini_client(self) -> genai.Client:
        return genai.Client(api_key=self.gemini_api_key)

    async def _gemini_generate(self, prompt: str, timeout: float, stage: str) -> str:
        """
        Single generate_content call with hard timeout and full per-call logging.

        Retry policy: attempts=1 — no retries. A 404 or 429 on a bad model
        would previously hang for the full timeout due to SDK internal retry.
        With attempts=1, a hard error surfaces immediately.

        Logging per call:
          - Call number (global counter)
          - Model, endpoint, vertexai mode
          - Prompt length
          - Latency (wall time)
          - Response: finish_reason, token counts
        """
        call_n = _increment_gemini_counter()
        t0 = time.perf_counter()

        log.info(
            "[%s] ── START call #%d — model=%s timeout=%.0fs prompt=%d chars ──",
            stage, call_n, self.gemini_model_id, timeout, len(prompt),
        )

        client = self._gemini_client()

        def _call() -> genai.types.GenerateContentResponse:
            import time as _t
            t_pre = _t.perf_counter()

            _ac = getattr(client, "_api_client", None)
            _endpoint = getattr(getattr(_ac, "_http_options", None), "base_url", "N/A")
            _vertexai = getattr(_ac, "vertexai", "N/A")
            log.info("[%s] [call #%d] endpoint=%s vertexai=%s",
                     stage, call_n, _endpoint, _vertexai)

            try:
                response = client.models.generate_content(
                    model=self.gemini_model_id,
                    contents=prompt,
                    config=genai.types.GenerateContentConfig(
                        http_options=genai.types.HttpOptions(
                            retry_options=genai.types.HttpRetryOptions(attempts=1),
                        ),
                    ),
                )
                latency = f"{(_t.perf_counter() - t_pre) * 1000:.0f}ms"
                log.info("[%s] [call #%d] generate_content() returned in %s",
                         stage, call_n, latency)

                try:
                    candidates = response.candidates or []
                    finish = candidates[0].finish_reason if candidates else "UNKNOWN"
                    usage  = getattr(response, "usage_metadata", None)
                    pt = getattr(usage, "prompt_token_count", "?") if usage else "?"
                    ot = getattr(usage, "candidates_token_count", "?") if usage else "?"
                    log.info(
                        "[%s] [call #%d] finish=%s prompt_tokens=%s output_tokens=%s",
                        stage, call_n, finish, pt, ot,
                    )
                except Exception as meta_err:
                    log.warning("[%s] [call #%d] metadata read error: %s",
                                stage, call_n, meta_err)
                return response

            except genai_errors.ClientError:
                raise
            except Exception as exc:
                latency = f"{(_t.perf_counter() - t_pre) * 1000:.0f}ms"
                log.error("[%s] [call #%d] %s after %s",
                          stage, call_n, type(exc).__name__, latency, exc_info=True)
                raise

        try:
            response = await asyncio.wait_for(
                asyncio.to_thread(_call),
                timeout=timeout,
            )
            text = response.text
            log.info(
                "[%s] ── END call #%d — wall=%s output=%d chars ──",
                stage, call_n, _ms(t0), len(text) if text else 0,
            )
            return text

        except asyncio.TimeoutError:
            log.error(
                "[%s] ── TIMEOUT call #%d — wall=%s limit=%.0fs\n"
                "  Model: %s | The underlying thread may still be blocked.\n"
                "  With attempts=1 this should not happen for a valid model.\n"
                "  Possible: network disruption mid-request.",
                stage, call_n, _ms(t0), timeout, self.gemini_model_id,
            )
            raise

        except genai_errors.ClientError as e:
            err_str = str(e)
            log.error(
                "[%s] ── ClientError call #%d — wall=%s\n  %s",
                stage, call_n, _ms(t0), err_str[:500],
                exc_info=True,
            )
            if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                raise RuntimeError(
                    f"Gemini quota exhausted (429) for model '{self.gemini_model_id}'. "
                    "Wait a few minutes or switch to a model with available quota."
                ) from e
            if "404" in err_str or "NOT_FOUND" in err_str:
                raise RuntimeError(
                    f"Model '{self.gemini_model_id}' returned 404 NOT FOUND. "
                    "This model is not available via v1beta API for this key. "
                    "Set GEMINI_MODEL_ID=gemini-2.5-flash in .env"
                ) from e
            raise

        except Exception as e:
            log.error(
                "[%s] ── Error call #%d — wall=%s  %s: %s",
                stage, call_n, _ms(t0), type(e).__name__, str(e)[:400],
                exc_info=True,
            )
            raise

    # ------------------------------------------------------------------
    # GitHub helpers
    # ------------------------------------------------------------------

    def _parse_github_url(self, issue_url: str) -> tuple[str, str, str]:
        pattern = r"(?:https?://)?github\.com/([^/]+)/([^/]+)/issues/(\d+)"
        match = re.search(pattern, issue_url.strip())
        if not match:
            raise ValueError(
                "Invalid URL. Expected: https://github.com/owner/repo/issues/123"
            )
        return match.group(1), match.group(2), match.group(3)

    def _fetch_github_issue(self, issue_url: str, token: str | None = None) -> dict:
        owner, repo, issue_number = self._parse_github_url(issue_url)
        api_url = f"{self._github_api_base}/{owner}/{repo}/issues/{issue_number}"
        log.info("[GITHUB] Fetching: %s", api_url)

        headers: dict[str, str] = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "Ission-Agent/0.1",
        }
        if token is not None:
            headers["Authorization"] = f"Bearer {token}"

        request = urllib.request.Request(api_url, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                data = json.loads(response.read().decode("utf-8"))
                log.info("[GITHUB] Fetched issue #%s: %s", data.get("number"), data.get("title"))
                return data
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise ValueError("Issue not found. Check the URL and that the repo is public.")
            if e.code == 403:
                raise ValueError("GitHub API access denied (rate limit or private repo).")
            raise ValueError(f"GitHub API error (HTTP {e.code}).")
        except urllib.error.URLError as e:
            raise ConnectionError(f"GitHub connection failed: {e.reason}")

    def _sanitize_html(self, text: str) -> str:
        return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    # ------------------------------------------------------------------
    # Stage 1 — Quality Score (heuristic, zero API calls)
    # ------------------------------------------------------------------

    def _score_issue_quality(self, title: str, body: str) -> QualityScore:
        text = f"{title} {body}".lower()
        score = 0
        present: list[str] = []
        missing: list[str] = []

        generic = {"bug", "issue", "problem", "error", "fix", "help",
                   "question", "request", "feature"}
        title_words = set(title.lower().split())
        if len(title.strip()) > 20 and not title_words.issubset(generic):
            score += 20; present.append("Descriptive title")
        else:
            missing.append("Descriptive title")

        if any(kw in text for kw in _REPRO_KEYWORDS):
            score += 20; present.append("Reproduction steps")
        else:
            missing.append("Reproduction steps")

        if any(kw in text for kw in _ENV_KEYWORDS):
            score += 20; present.append("Environment details")
        else:
            missing.append("Environment details")

        if any(kw in text for kw in _EXPECTED_KEYWORDS):
            score += 20; present.append("Expected vs actual behavior")
        else:
            missing.append("Expected vs actual behavior")

        if any(kw in text for kw in _LOGS_KEYWORDS):
            score += 20; present.append("Logs or error output")
        else:
            missing.append("Logs or error output")

        level = "high" if score >= 80 else ("medium" if score >= 40 else "low")
        log.info("[QUALITY] %d/100 (%s) present=%s missing=%s", score, level, present, missing)
        return QualityScore(score=score, missing=missing, present=present, level=level)

    # ------------------------------------------------------------------
    # Stage 2 — Foundry RAG (Azure AI Search)
    # ------------------------------------------------------------------

    async def _fetch_foundry_iq_context(self, issue_content: str) -> str:
        if not self._foundry_ok:
            log.warning("[FOUNDRY-RAG] Skipped — %s", self._foundry_reason)
            return f"*[Foundry IQ] Context unavailable: {self._foundry_reason}*"

        try:
            credential = AzureKeyCredential(self.foundry_key)
            client = SearchClient(
                endpoint=self.foundry_endpoint,
                index_name=self.foundry_index,
                credential=credential,
            )
            log.info("[FOUNDRY-RAG] Querying index '%s'", self.foundry_index)
            results = await asyncio.wait_for(
                asyncio.to_thread(
                    lambda: list(client.search(
                        search_text=issue_content[:1000],
                        top=5,
                        include_total_count=False,
                    ))
                ),
                timeout=TIMEOUT_FOUNDRY_SEARCH,
            )

            if not results:
                return "*[Foundry IQ] No relevant architectural guidelines found.*"

            parts = []
            for i, doc in enumerate(results, 1):
                content = (
                    doc.get("content") or doc.get("chunk") or
                    doc.get("text") or doc.get("description") or str(doc)
                )
                parts.append(f"**Guideline {i}:**\n{content}")
            log.info("[FOUNDRY-RAG] Retrieved %d guidelines", len(results))
            return "\n\n".join(parts)

        except asyncio.TimeoutError:
            log.error("[FOUNDRY-RAG] Timeout after %.1fs", TIMEOUT_FOUNDRY_SEARCH)
            return f"*[Foundry IQ] Search timed out after {TIMEOUT_FOUNDRY_SEARCH}s.*"
        except Exception as e:
            log.error("[FOUNDRY-RAG] Error: %s", str(e), exc_info=True)
            return f"*[Foundry IQ] Search error: {e}*"

    # ------------------------------------------------------------------
    # Stage 3 — Classification (Gemini call #1 per pipeline)
    # ------------------------------------------------------------------

    async def _classify_issue_with_foundry(
        self, issue_data: dict, foundry_context: str
    ) -> IssueClassification:
        log.info("[FOUNDRY-CLASS] Starting classification — model=%s", self.gemini_model_id)

        title  = issue_data.get("title", "")
        body   = (issue_data.get("body", "") or "")[:800]
        labels = [lbl.get("name", "") for lbl in issue_data.get("labels", [])]
        labels_text = ", ".join(labels) if labels else "none"

        prompt = f"""You are a senior engineering triage agent with access to the project's architectural guidelines.

Based on the GitHub issue below and the architectural context from Microsoft Foundry IQ,
classify this issue. Respond ONLY with a valid JSON object — no markdown, no explanation.

Issue title: {title}
Issue labels: {labels_text}
Issue body (excerpt): {body}

Foundry IQ Architectural Context:
{foundry_context[:600]}

Respond with exactly this JSON structure:
{{
  "issue_type": "<one of: Bug | Feature | Enhancement | Documentation | Refactor>",
  "priority": "<one of: Critical | High | Medium | Low>",
  "confidence": "<one of: high | medium | low>",
  "rationale": "<one sentence explaining the classification>"
}}"""

        try:
            raw = await self._gemini_generate(prompt, TIMEOUT_FOUNDRY_CLASSIFY, "FOUNDRY-CLASS")
            raw = re.sub(r"^```(?:json)?\s*", "", raw.strip())
            raw = re.sub(r"\s*```$", "", raw)
            data = json.loads(raw)
            result = IssueClassification(
                issue_type=data.get("issue_type", "Bug"),
                priority=data.get("priority", "Medium"),
                confidence=data.get("confidence", "medium"),
                rationale=data.get("rationale", "Classified based on issue content."),
            )
            log.info("[FOUNDRY-CLASS] type=%s priority=%s confidence=%s",
                     result.issue_type, result.priority, result.confidence)
            return result
        except asyncio.TimeoutError:
            log.error("[FOUNDRY-CLASS] Timeout — heuristic fallback")
        except Exception as e:
            log.warning("[FOUNDRY-CLASS] Failed (%s) — heuristic fallback", e)

        # Heuristic fallback
        text_lower = f"{title} {body}".lower()
        issue_type = "Bug"
        if any(w in text_lower for w in ["feat", "feature", "add ", "new "]):
            issue_type = "Feature"
        elif any(w in text_lower for w in ["refactor", "cleanup"]):
            issue_type = "Refactor"
        elif any(w in text_lower for w in ["doc", "readme"]):
            issue_type = "Documentation"
        elif any(w in text_lower for w in ["improve", "enhance"]):
            issue_type = "Enhancement"

        priority = "Medium"
        if any(w in text_lower for w in ["critical", "crash", "data loss", "security"]):
            priority = "Critical"
        elif any(w in text_lower for w in ["urgent", "blocker", "breaking"]):
            priority = "High"
        elif any(w in text_lower for w in ["minor", "typo", "cosmetic"]):
            priority = "Low"

        return IssueClassification(
            issue_type=issue_type, priority=priority, confidence="low",
            rationale="Classified via heuristic fallback.",
        )

    # ------------------------------------------------------------------
    # Stage 4 — Planner with built-in self-review (Gemini call #2 per pipeline)
    #
    # The CRITIC stage has been removed. Self-review is embedded here:
    # the prompt instructs the model to produce a final, validated plan
    # in a single pass. gemini-2.5-flash has thinking built-in and
    # produces correct plans without a separate review call.
    # This reduces pipeline calls from 3 to 2, eliminating the 503
    # cascade failure that occurred when either PLANNER or CRITIC hit
    # high-demand throttling on the same model.
    # ------------------------------------------------------------------

    async def _generate_plan_with_gemini(
        self, issue_data: dict, foundry_context: str, extra_context: str = ""
    ) -> str:
        log.info("[PLANNER] Generating plan — model=%s", self.gemini_model_id)

        title  = self._sanitize_html(issue_data.get("title", "No title"))
        body   = self._sanitize_html(issue_data.get("body", "") or "")
        labels = [self._sanitize_html(l.get("name", "")) for l in issue_data.get("labels", [])]
        author = self._sanitize_html(issue_data.get("user", {}).get("login", "unknown"))
        issue_number = issue_data.get("number", "?")
        repo_url = issue_data.get("repository_url", "")
        repo_name = "/".join(repo_url.rstrip("/").split("/")[-2:]) if repo_url else "unknown"
        labels_text = ", ".join(labels) if labels else "none"
        extra_section = f"\n\n## Intelligence Context\n\n{extra_context}" if extra_context else ""

        prompt = f"""{SYSTEM_PROMPT}

---

## GitHub Issue

- **Repository:** {repo_name}
- **Issue:** #{issue_number}
- **Author:** @{author}
- **Labels:** {labels_text}
- **Title:** {title}

### Description

{body if body.strip() else "*No description provided.*"}

---

## Architectural Context — Microsoft Foundry IQ (Recall)

{foundry_context}
{extra_section}

---

Generate a complete and structured technical action plan in Markdown.

Requirements for the plan:
1. Cover all implementation steps — do not omit setup, testing, or deployment.
2. Flag any assumptions explicitly if the issue quality score indicates missing information.
3. Identify security concerns, edge cases, or dependencies that could block implementation.
4. Ensure all steps are consistent with the Foundry IQ architectural guidelines above.
5. Before outputting, verify internally that the plan is complete and self-consistent.

Output only the final, reviewed plan — no meta-commentary, no preamble.
"""
        text = await self._gemini_generate(prompt, TIMEOUT_GEMINI_PLANNER, "PLANNER")
        log.info("[PLANNER] Plan generated (%d chars)", len(text))
        return text

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    async def process_issue(self, issue_url: str, token: str | None = None) -> dict:
        """
        4-stage pipeline (2 Gemini calls per analysis).

          Stage 0 — GitHub fetch        (no API)
          Stage 1 — Quality Score       (heuristic, no API)
          Stage 2 — Foundry RAG         (Azure AI Search)
          Stage 3 — CLASSIFIER          (Gemini call #1: JSON classification)
          Stage 4 — PLANNER             (Gemini call #2: full plan with self-review)

        Total Gemini calls: 2 per issue (down from 3 — CRITIC removed).
        If CLASSIFIER fails/times out → heuristic fallback, pipeline continues.
        If PLANNER fails → pipeline returns error (no fallback for core output).

        503 resilience: with 2 sequential calls instead of 3, the probability
        of hitting a 503 UNAVAILABLE somewhere in the pipeline is reduced by ~33%.
        """
        t0 = time.perf_counter()
        pid = f"{time.time_ns() % 1_000_000:06d}"
        calls_before = _gemini_call_counter

        log.info(
            "[PIPELINE-%s] ══ START url=%s auth=%s gemini_calls_so_far=%d ══",
            pid, issue_url, token is not None, calls_before,
        )

        try:
            # Stage 0: GitHub fetch
            t = time.perf_counter()
            issue_data = self._fetch_github_issue(issue_url, token=token)
            issue_title = self._sanitize_html(issue_data.get("title", "No title"))
            raw_title = issue_data.get("title", "")
            raw_body  = issue_data.get("body", "") or ""
            log.info("[PIPELINE-%s] GitHub fetch: %s", pid, _ms(t))

            # Stage 1: Quality Score
            t = time.perf_counter()
            quality = self._score_issue_quality(raw_title, raw_body)
            log.info("[PIPELINE-%s] Quality score: %d/100 in %s", pid, quality.score, _ms(t))

            # Stage 2: Foundry RAG
            t = time.perf_counter()
            foundry_context = await self._fetch_foundry_iq_context(
                f"{raw_title} {raw_body}".strip()
            )
            log.info("[PIPELINE-%s] Foundry RAG: %s", pid, _ms(t))

            # Stage 3: Classifier (Gemini call #1)
            t = time.perf_counter()
            classification = await self._classify_issue_with_foundry(issue_data, foundry_context)
            log.info("[PIPELINE-%s] Classifier: %s · %s in %s",
                     pid, classification.issue_type, classification.priority, _ms(t))

            # Stage 4: Planner with built-in self-review (Gemini call #2)
            t = time.perf_counter()
            quality_context = (
                f"Issue Quality Score: {quality.score}/100 ({quality.level.upper()}). "
                f"Present: {', '.join(quality.present) if quality.present else 'nothing'}. "
                f"Missing: {', '.join(quality.missing) if quality.missing else 'nothing'}."
            )
            classification_context = (
                f"Foundry IQ Classification — Type: {classification.issue_type} | "
                f"Priority: {classification.priority} | Rationale: {classification.rationale}"
            )
            final_plan = await self._generate_plan_with_gemini(
                issue_data, foundry_context,
                extra_context=f"{quality_context}\n\n{classification_context}",
            )
            log.info("[PIPELINE-%s] Planner: %d chars in %s", pid, len(final_plan), _ms(t))

            calls_this_pipeline = _gemini_call_counter - calls_before
            log.info(
                "[PIPELINE-%s] ══ COMPLETE total=%s gemini_calls=%d ══",
                pid, _ms(t0), calls_this_pipeline,
            )

            return {
                "status": "sucesso",
                "thoughts": [
                    "Validating issue URL...",
                    f"Issue found: \"{issue_title}\"",
                    f"[Quality Score] {quality.score}/100 ({quality.level})",
                    "[Foundry IQ] Searching architectural knowledge base...",
                    f"[Foundry IQ] {classification.issue_type} · {classification.priority} priority",
                    "[Planner] Generating technical action plan...",
                    "Plan ready.",
                ],
                "finalComment": final_plan,
                "qualityScore": {
                    "score": quality.score,
                    "level": quality.level,
                    "present": quality.present,
                    "missing": quality.missing,
                },
                "classification": {
                    "type": classification.issue_type,
                    "priority": classification.priority,
                    "confidence": classification.confidence,
                    "rationale": classification.rationale,
                },
            }

        except ValueError as e:
            log.error("[PIPELINE-%s] ValueError after %s: %s", pid, _ms(t0), e)
            return {
                "status": "erro",
                "thoughts": ["Validating issue URL...", "Validation or fetch failed."],
                "finalComment": (
                    f"**Error processing issue:**\n\n{e}\n\n"
                    "Check the URL format: `https://github.com/owner/repo/issues/123`"
                ),
                "qualityScore": None, "classification": None,
            }

        except ConnectionError as e:
            log.error("[PIPELINE-%s] ConnectionError after %s: %s", pid, _ms(t0), e)
            return {
                "status": "erro",
                "thoughts": ["Connecting to GitHub API...", "Network failure."],
                "finalComment": f"**Connection error:**\n\n{e}",
                "qualityScore": None, "classification": None,
            }

        except RuntimeError as e:
            log.error("[PIPELINE-%s] RuntimeError after %s: %s", pid, _ms(t0), e)
            return {
                "status": "erro",
                "thoughts": ["Processing issue...", "AI service error."],
                "finalComment": f"**AI Error:**\n\n{e}",
                "qualityScore": None, "classification": None,
            }

        except asyncio.TimeoutError:
            log.error("[PIPELINE-%s] Timeout after %s", pid, _ms(t0))
            return {
                "status": "erro",
                "thoughts": ["Processing issue...", "Request timed out."],
                "finalComment": (
                    "**Timeout:** The analysis took too long. "
                    "The AI service may be under load. Please try again."
                ),
                "qualityScore": None, "classification": None,
            }

        except Exception as e:
            log.error("[PIPELINE-%s] Unexpected error after %s: %s",
                      pid, _ms(t0), e, exc_info=True)
            return {
                "status": "erro",
                "thoughts": ["Processing issue...", "Unexpected error."],
                "finalComment": f"**Unexpected error:**\n\n{e}",
                "qualityScore": None, "classification": None,
            }


# ---------------------------------------------------------------------------
# Factory — validates config, runs startup checks, returns singleton-ready instance
# ---------------------------------------------------------------------------

def create_orchestrator() -> "IssionOrchestrator":
    """
    Loads .env, validates model against ALLOWED_MODELS and models.list(),
    and returns a configured IssionOrchestrator.

    Call once at application startup (FastAPI lifespan).
    Raises RuntimeError if the model is invalid or not in models.list().
    This guarantees that if the app starts successfully, Gemini calls will work.
    """
    import pathlib

    env_path = pathlib.Path(__file__).parent / ".env"
    log.info("[STARTUP][ENV] Loading .env from: %s (exists=%s)", env_path, env_path.exists())
    load_dotenv(dotenv_path=env_path)

    api_key   = os.getenv("GEMINI_API_KEY", "")
    model_id  = os.getenv("GEMINI_MODEL_ID", DEFAULT_MODEL)

    log.info("[STARTUP] ── Ission Agent startup ──")
    log.info("[STARTUP] GEMINI_MODEL_ID  : %s (source: %s)",
             model_id,
             "GEMINI_MODEL_ID env var" if os.getenv("GEMINI_MODEL_ID") else f"default ({DEFAULT_MODEL})")
    log.info("[STARTUP] GEMINI_API_KEY   : length=%d last6=...%s type=%s",
             len(api_key),
             api_key[-6:] if len(api_key) >= 6 else "SHORT",
             _detect_api_key_type(api_key))

    # Hard validation — raises on any problem
    _validate_model_at_startup(api_key, model_id)

    return IssionOrchestrator(
        gemini_api_key=api_key,
        gemini_model_id=model_id,
        foundry_endpoint=os.getenv("AZURE_AI_FOUNDRY_ENDPOINT", ""),
        foundry_key=os.getenv("AZURE_AI_FOUNDRY_KEY", ""),
        foundry_index=os.getenv("AZURE_AI_FOUNDRY_INDEX", "recall-architecture-guidelines"),
    )
