"""
API
===
FastAPI routes for the React app. Scans run in the background because they
take too long for one request, so React starts one and checks back on it.

Run with:
    uvicorn app.main:app --reload

Dependencies:
    - fastapi
    - playwright
"""

import json
import re
from collections import Counter, defaultdict
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from playwright.sync_api import sync_playwright

from app import config, db
from app.grouping import group_issues
from app.models import (
    AxeIssue,
    DecisionRequest,
    DecisionResponse,
    EvaluationResponse,
    FixSuggestion,
    PageScan,
    ReviewStatus,
    RuleSummary,
    ScanRequest,
    ScanResponse,
    ScanSummary,
    SuggestionResponse,
    ValidationResult,
)
from app.scanner import scan_page, validate_url
from app.suggester import suggest_fix
from app.validator import validate_fix


# ── App Setup ──

@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    db.init_db()
    yield


app = FastAPI(title="Accessibility Fix Assistant", lifespan=lifespan)

# Vite runs the React dev server here
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Browser IDs ──

CLIENT_ID_FORMAT = re.compile(r"^[A-Za-z0-9-]{16,64}$")


def get_client_id(x_client_id: str | None = Header(default=None)) -> str:
    """
    Every browser sends a random ID so people only see their own scans.
    This keeps lists separate, but it isn't a login, so it can't protect
    anything truly private.

    Returns:
    --------
    The browser's ID, or a 400 error if it's missing or malformed
    """
    if not x_client_id or not CLIENT_ID_FORMAT.fullmatch(x_client_id):
        raise HTTPException(status_code=400, detail="Missing or invalid browser ID")
    return x_client_id


def require_own_scan(scan_id: int, client_id: str) -> None:
    # same 404 either way, so nobody can tell which scan IDs exist
    if not db.scan_belongs_to(scan_id, client_id):
        raise HTTPException(status_code=404, detail="Scan not found")


# ── Browser Work ──

def run_scan(url: str) -> PageScan:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            return scan_page(browser, url)
        finally:
            browser.close()


def run_validation(url: str, issue: AxeIssue, suggestion: FixSuggestion) -> ValidationResult:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            return validate_fix(browser, url, issue, suggestion)
        finally:
            browser.close()


def scan_job(scan_id: int, url: str) -> None:
    """Runs after the response goes out, and saves how the scan turned out."""
    try:
        scan = run_scan(url)
        # a safe URL could still redirect somewhere it shouldn't
        validate_url(scan.final_url)
        db.complete_scan(scan_id, scan.final_url, group_issues(scan.issues))
    except Exception as e:
        db.fail_scan(scan_id, f"{type(e).__name__}: {e}")


# ── Scan Routes ──

@app.post("/api/scans", response_model=ScanResponse, status_code=202)
def create_scan(
    request: ScanRequest,
    background_tasks: BackgroundTasks,
    client_id: str = Depends(get_client_id),
) -> ScanResponse:
    try:
        url = validate_url(request.url)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    scan_id = db.create_scan(url, client_id)
    background_tasks.add_task(scan_job, scan_id, url)
    return db.get_scan(scan_id)


@app.get("/api/scans", response_model=list[ScanSummary])
def list_scans(client_id: str = Depends(get_client_id)) -> list[ScanSummary]:
    db.adopt_unowned_scans(client_id)
    return db.list_scans(client_id)


@app.get("/api/scans/{scan_id}", response_model=ScanResponse)
def get_scan(scan_id: int, client_id: str = Depends(get_client_id)) -> ScanResponse:
    require_own_scan(scan_id, client_id)
    return db.get_scan(scan_id)


@app.get("/api/scans/{scan_id}/reviews", response_model=list[ReviewStatus])
def get_reviews(scan_id: int, client_id: str = Depends(get_client_id)) -> list[ReviewStatus]:
    require_own_scan(scan_id, client_id)
    return db.get_review_statuses(scan_id)


# ── Suggestion Routes ──

@app.post(
    "/api/scans/{scan_id}/groups/{group_key}/suggestion",
    response_model=SuggestionResponse,
)
def create_suggestion(
    scan_id: int, group_key: str, client_id: str = Depends(get_client_id)
) -> SuggestionResponse:
    """Only runs when I open a group, so Groq only gets called when it's needed."""
    require_own_scan(scan_id, client_id)

    existing = db.get_suggestion(scan_id, group_key)
    if existing:
        return existing

    scan = db.get_scan(scan_id)
    group = next((g for g in scan.groups if g.key == group_key), None)
    if group is None:
        raise HTTPException(status_code=404, detail="Issue group not found")
    if group.level == "report_only" or group.status != "violation":
        raise HTTPException(status_code=409, detail="This issue is report only")

    try:
        suggestion = suggest_fix(group.example)
    except Exception as e:
        raise HTTPException(status_code=502, detail="Could not get a suggestion") from e

    validation = run_validation(scan.final_url, group.example, suggestion)
    return db.save_suggestion(scan_id, group, config.GROQ_MODEL, suggestion, validation)


@app.post("/api/suggestions/{suggestion_id}/decision", response_model=DecisionResponse)
def save_decision(
    suggestion_id: int,
    decision: DecisionRequest,
    client_id: str = Depends(get_client_id),
) -> DecisionResponse:
    if not db.suggestion_belongs_to(suggestion_id, client_id):
        raise HTTPException(status_code=404, detail="Suggestion not found")
    return db.save_decision(suggestion_id, decision)


# ── Evaluation Route ──

@app.get("/api/evaluation", response_model=EvaluationResponse)
def get_evaluation(client_id: str = Depends(get_client_id)) -> EvaluationResponse:
    scans, rows = db.get_evaluation_rows(client_id)

    by_rule = defaultdict(list)
    for row in rows:
        by_rule[row["rule_id"]].append(row)

    rules = [
        RuleSummary(
            rule_id=rule_id,
            suggestions=len(rule_rows),
            verdicts=Counter(json.loads(r["validation_json"])["verdict"] for r in rule_rows),
            decisions=Counter(r["decision"] for r in rule_rows if r["decision"]),
            occurrences_in_groups=sum(r["occurrences"] for r in rule_rows),
        )
        for rule_id, rule_rows in sorted(by_rule.items())
    ]
    return EvaluationResponse(
        scans=scans,
        suggestions=len(rows),
        decisions=sum(1 for r in rows if r["decision"]),
        rules=rules,
    )
