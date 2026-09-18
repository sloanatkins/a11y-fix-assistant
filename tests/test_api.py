"""
API Tests
=========
Runs the routes with a temporary database. The fake tests skip the browser
and Groq, and one test goes through the real scanner on a local page.

Dependencies:
    - pytest
    - fastapi
"""

import pytest
from fastapi.testclient import TestClient

from app import config, main
from app.grouping import group_issues
from app.models import AxeIssue, FixSuggestion, PageScan, ValidationResult

PUBLIC_URL = "https://93.184.216.34/"


def make_issue(rule_id: str, html: str, parent: str = "", level: str = "tested") -> AxeIssue:
    return AxeIssue(
        rule_id=rule_id,
        level=level,
        status="violation",
        impact="serious",
        help="help text",
        selector="x",
        target=["x"],
        html=html,
        parent_html=parent,
    )


FAKE_ISSUES = [
    make_issue("listitem", "<li>1</li>", parent='<ul role="navigation"></ul>'),
    make_issue("listitem", "<li>2</li>", parent='<ul role="navigation"></ul>'),
    make_issue("select-name", '<select id="a">'),
    make_issue("color-contrast", "<p>x</p>", level="report_only"),
]


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATABASE_PATH", str(tmp_path / "test.db"))
    monkeypatch.setattr(
        main,
        "run_scan",
        lambda url: PageScan(url=url, final_url=url, issues=FAKE_ISSUES),
    )
    with TestClient(main.app) as test_client:
        yield test_client


def start_scan(client: TestClient) -> dict:
    response = client.post("/api/scans", json={"url": PUBLIC_URL})
    assert response.status_code == 202
    return client.get(f"/api/scans/{response.json()['id']}").json()


def fake_suggestion(monkeypatch) -> list:
    calls = []

    def suggest(issue):
        calls.append(issue)
        return FixSuggestion(
            explanation="test",
            fix_target="parent",
            fixed_html="<nav><ul>...</ul></nav>",
            needs_human_input=False,
            human_input_reason="",
        )

    monkeypatch.setattr(main, "suggest_fix", suggest)
    monkeypatch.setattr(
        main,
        "run_validation",
        lambda url, issue, suggestion: ValidationResult(
            verdict="passed",
            applied=True,
            detail="ok",
            rule_before=2,
            rule_after=0,
            new_violations={},
            has_placeholder=False,
        ),
    )
    return calls


def test_grouping_merges_children_of_one_parent():
    groups = group_issues(FAKE_ISSUES)
    assert [g.count for g in groups] == [2, 1, 1]


def test_scan_finishes_with_groups(client):
    scan = start_scan(client)
    assert scan["status"] == "complete"
    assert len(scan["groups"]) == 3


@pytest.mark.parametrize("url", ["http://localhost:8000", "ftp://example.com"])
def test_bad_url_is_rejected(client, url):
    assert client.post("/api/scans", json={"url": url}).status_code == 422


def test_failed_scan_reports_the_error(client, monkeypatch):
    def broken(url):
        raise RuntimeError("page blew up")

    monkeypatch.setattr(main, "run_scan", broken)
    scan = start_scan(client)
    assert scan["status"] == "failed"
    assert "page blew up" in scan["error"]


def test_redirect_to_private_address_fails(client, monkeypatch):
    monkeypatch.setattr(
        main,
        "run_scan",
        lambda url: PageScan(url=url, final_url="http://127.0.0.1/", issues=[]),
    )
    assert start_scan(client)["status"] == "failed"


def test_missing_scan_is_404(client):
    assert client.get("/api/scans/999").status_code == 404


def test_suggestion_is_saved_and_not_paid_for_twice(client, monkeypatch):
    calls = fake_suggestion(monkeypatch)
    scan = start_scan(client)
    path = f"/api/scans/{scan['id']}/groups/{scan['groups'][0]['key']}/suggestion"

    first = client.post(path)
    second = client.post(path)
    assert first.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    assert len(calls) == 1


def test_report_only_issue_gets_no_suggestion(client, monkeypatch):
    calls = fake_suggestion(monkeypatch)
    scan = start_scan(client)
    report_only = next(g for g in scan["groups"] if g["level"] == "report_only")
    response = client.post(f"/api/scans/{scan['id']}/groups/{report_only['key']}/suggestion")
    assert response.status_code == 409
    assert calls == []


def test_groq_failure_returns_502_and_saves_nothing(client, monkeypatch):
    fake_suggestion(monkeypatch)

    def broken(issue):
        raise RuntimeError("groq is down")

    monkeypatch.setattr(main, "suggest_fix", broken)
    scan = start_scan(client)
    path = f"/api/scans/{scan['id']}/groups/{scan['groups'][0]['key']}/suggestion"
    assert client.post(path).status_code == 502
    assert client.get("/api/evaluation").json()["suggestions"] == 0


def test_decision_can_change_and_evaluation_counts_it(client, monkeypatch):
    fake_suggestion(monkeypatch)
    scan = start_scan(client)
    path = f"/api/scans/{scan['id']}/groups/{scan['groups'][0]['key']}/suggestion"
    suggestion_id = client.post(path).json()["id"]
    decision_path = f"/api/suggestions/{suggestion_id}/decision"

    client.post(decision_path, json={"decision": "rejected", "reason": "wrong"})
    saved = client.post(decision_path, json={"decision": "used", "seconds_spent": 42})
    assert saved.status_code == 200
    assert saved.json()["decision"] == "used"

    evaluation = client.get("/api/evaluation").json()
    assert evaluation["decisions"] == 1
    rule = evaluation["rules"][0]
    assert rule["rule_id"] == "listitem"
    assert rule["verdicts"] == {"passed": 1}
    assert rule["decisions"] == {"used": 1}
    assert rule["occurrences_in_groups"] == 2


def test_bad_decision_is_rejected(client, monkeypatch):
    fake_suggestion(monkeypatch)
    scan = start_scan(client)
    path = f"/api/scans/{scan['id']}/groups/{scan['groups'][0]['key']}/suggestion"
    suggestion_id = client.post(path).json()["id"]
    response = client.post(f"/api/suggestions/{suggestion_id}/decision", json={"decision": "maybe"})
    assert response.status_code == 422


def test_real_scan_runs_from_the_background_task(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATABASE_PATH", str(tmp_path / "test.db"))
    page = tmp_path / "page.html"
    page.write_text(
        '<!doctype html><html lang="en"><head><title>T</title></head><body><main><h1>x</h1>'
        '<ul role="navigation" aria-label="Pages"><li>1</li><li>2</li></ul></main></body></html>'
    )
    # the local file stands in for a public page in this one test
    monkeypatch.setattr(main, "validate_url", lambda url: url)

    with TestClient(main.app) as client:
        created = client.post("/api/scans", json={"url": page.as_uri()}).json()
        scan = client.get(f"/api/scans/{created['id']}").json()

    assert scan["status"] == "complete"
    group = next(g for g in scan["groups"] if g["rule_id"] == "listitem")
    assert group["count"] == 2


def test_reviews_show_saved_decisions(client, monkeypatch):
    fake_suggestion(monkeypatch)
    scan = start_scan(client)
    key = scan["groups"][0]["key"]
    suggestion_id = client.post(f"/api/scans/{scan['id']}/groups/{key}/suggestion").json()["id"]
    client.post(f"/api/suggestions/{suggestion_id}/decision", json={"decision": "edited"})

    reviews = client.get(f"/api/scans/{scan['id']}/reviews").json()
    assert reviews == [{"group_key": key, "suggestion_id": suggestion_id, "decision": "edited"}]
