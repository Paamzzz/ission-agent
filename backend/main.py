"""
Ission Agent — API entry point.

SINGLETON PATTERN:
  IssionOrchestrator is created ONCE during the FastAPI lifespan startup event.
  It is stored in app.state.orchestrator and reused for every request.

  This means:
    - models.list() runs exactly once per process (not per request)
    - Gemini client configuration is validated at startup
    - If the model is invalid, the app refuses to start (fail-fast)
"""

import json
import logging
import os
import re
import urllib.request
import urllib.error
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

from auth_router import router as auth_router, get_current_token
from orchestrator import create_orchestrator

log = logging.getLogger("ission.main")

# ---------------------------------------------------------------------------
# Lifespan — creates the singleton orchestrator once at startup
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup: validate config + create orchestrator singleton.
    Shutdown: nothing to clean up.

    If create_orchestrator() raises (invalid model, bad key, model not in
    models.list()), uvicorn will refuse to start and print the error.
    """
    load_dotenv()
    log.info("[MAIN] Application startup — creating orchestrator singleton...")
    app.state.orchestrator = create_orchestrator()
    log.info("[MAIN] Orchestrator ready. Accepting requests.")
    yield
    log.info("[MAIN] Application shutdown.")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(title="Ission Agent API", version="0.1.0", lifespan=lifespan)

app.include_router(auth_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class IssueRequest(BaseModel):
    url: str


class CommentRequest(BaseModel):
    issue_url: str
    comment_body: str


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.post("/api/analyze")
async def analyze_issue(
    request: Request,
    payload: IssueRequest,
    token: str | None = Depends(get_current_token),
):
    """Receives a GitHub issue URL and delegates to the singleton orchestrator."""
    orchestrator = request.app.state.orchestrator
    result = await orchestrator.process_issue(payload.url, token=token)
    return result


@app.post("/api/publish-comment")
async def publish_comment(
    payload: CommentRequest,
    token: str | None = Depends(get_current_token),
):
    """Publishes a comment on a GitHub issue."""
    effective_token = token if token else os.getenv("GITHUB_TOKEN")

    if not effective_token:
        raise HTTPException(status_code=500, detail="GITHUB_TOKEN not configured.")

    pattern = r"(?:https?://)?github\.com/([^/]+)/([^/]+)/issues/(\d+)"
    match = re.search(pattern, payload.issue_url.strip())
    if not match:
        raise HTTPException(
            status_code=400,
            detail="Invalid URL. Expected: https://github.com/owner/repo/issues/123",
        )

    owner, repo, issue_number = match.group(1), match.group(2), match.group(3)
    api_url = f"https://api.github.com/repos/{owner}/{repo}/issues/{issue_number}/comments"
    body = json.dumps({"body": payload.comment_body}).encode("utf-8")

    headers = {
        "Authorization": f"token {effective_token}",
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json",
        "User-Agent": "Ission-Agent/0.1",
    }
    req = urllib.request.Request(api_url, data=body, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            data = json.loads(response.read().decode("utf-8"))
            return {
                "status": "sucesso",
                "message": "Comment published successfully.",
                "comment_url": data.get("html_url", ""),
            }
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8") if e.fp else ""
        raise HTTPException(
            status_code=e.code,
            detail=f"GitHub error (HTTP {e.code}): {error_body}",
        )
    except urllib.error.URLError as e:
        raise HTTPException(status_code=502, detail=f"GitHub connection failed: {e.reason}")
