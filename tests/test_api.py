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
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeout

from app import config, main
from app.grouping import group_issues
from app.models import AxeIssue, FixSuggestion, PageScan, ValidationResult
from app.scanner import PageLoadError

PUBLIC_URL = "https://93.184.216.34/"
BROWSER_A = {"X-Client-Id": "browser-a-1234567890"}
BROWSER_B = {"X-Client-Id": "browser-b-1234567890"}


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
    make_issue("region", "<p>y</p>", level="report_only"),
]


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATABASE_PATH", str(tmp_path / "test.db"))
    monkeypatch.setattr(
        main,
        "run_scan",
        lambda url: PageScan(url=url, final_url=url, issues=FAKE_ISSUES),
    )
    with TestClient(main.app, headers=BROWSER_A) as test_client:
        yield test_client


def start_scan(client: TestClient) -> dict:
    response = client.post("/api/scans", json={"url": PUBLIC_URL})
    assert response.status_code == 202
    return client.get(f"/api/scans/{response.json()['id']}").json()


def fake_suggestion(monkeypatch) -> list:
    calls = []

    def suggest(issue, **kwargs):
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
    assert [g.count for g in groups] == [2, 1, 1, 1]


def test_scan_finishes_with_groups(client):
    scan = start_scan(client)
    assert scan["status"] == "complete"
    assert len(scan["groups"]) == 4


@pytest.mark.parametrize("url", ["http://localhost:8000", "ftp://example.com"])
def test_bad_url_is_rejected(client, url):
    assert client.post("/api/scans", json={"url": url}).status_code == 422


def test_failed_scan_reports_the_error(client, monkeypatch):
    def broken(url):
        raise RuntimeError("page blew up")

    monkeypatch.setattr(main, "run_scan", broken)
    scan = start_scan(client)
    assert scan["status"] == "failed"
    assert "unexpected error" in scan["error"]
    assert "page blew up" not in scan["error"]


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

    with TestClient(main.app, headers=BROWSER_A) as client:
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


def test_scan_list_is_newest_first_with_counts(client):
    first = start_scan(client)
    second = start_scan(client)
    scans = client.get("/api/scans").json()
    assert [s["id"] for s in scans] == [second["id"], first["id"]]
    assert scans[0]["flagged"] == 5


def test_old_scans_use_current_levels(client):
    # the fake saved color-contrast as report only, but it's a draft rule now
    scan = start_scan(client)
    group = next(g for g in scan["groups"] if g["rule_id"] == "color-contrast")
    assert group["level"] == "suggested"


def test_each_browser_only_lists_its_own_scans(client):
    mine = start_scan(client)
    theirs = client.post("/api/scans", json={"url": PUBLIC_URL}, headers=BROWSER_B).json()

    assert [s["id"] for s in client.get("/api/scans").json()] == [mine["id"]]
    other_list = client.get("/api/scans", headers=BROWSER_B).json()
    assert [s["id"] for s in other_list] == [theirs["id"]]


def test_another_browser_cant_open_or_act_on_my_scan(client, monkeypatch):
    fake_suggestion(monkeypatch)
    scan = start_scan(client)
    key = scan["groups"][0]["key"]
    path = f"/api/scans/{scan['id']}"

    assert client.get(path, headers=BROWSER_B).status_code == 404
    assert client.get(f"{path}/reviews", headers=BROWSER_B).status_code == 404
    assert client.post(f"{path}/groups/{key}/suggestion", headers=BROWSER_B).status_code == 404

    suggestion_id = client.post(f"{path}/groups/{key}/suggestion").json()["id"]
    decision = client.post(
        f"/api/suggestions/{suggestion_id}/decision",
        json={"decision": "used"},
        headers=BROWSER_B,
    )
    assert decision.status_code == 404
    assert client.get("/api/evaluation", headers=BROWSER_B).json()["suggestions"] == 0
    assert client.get("/api/evaluation").json()["suggestions"] == 1


@pytest.mark.parametrize("headers", [{}, {"X-Client-Id": "short"}, {"X-Client-Id": "bad id!!!!!!!!!!!!!!!!"}])
def test_missing_or_bad_browser_id_is_rejected(tmp_path, monkeypatch, headers):
    monkeypatch.setattr(config, "DATABASE_PATH", str(tmp_path / "test.db"))
    with TestClient(main.app) as bare_client:
        assert bare_client.get("/api/scans", headers=headers).status_code == 400


def test_old_scans_go_to_the_first_browser_that_asks(client):
    from app import db
    with db.connect() as connection:
        connection.execute(
            "INSERT INTO scans (url, status, client_id) VALUES ('https://old.test', 'complete', NULL)"
        )
    assert len(client.get("/api/scans").json()) == 1
    assert client.get("/api/scans", headers=BROWSER_B).json() == []


def test_older_database_gets_upgraded(tmp_path, monkeypatch):
    import sqlite3
    path = tmp_path / "old.db"
    old = sqlite3.connect(path)
    old.execute(
        "CREATE TABLE scans (id INTEGER PRIMARY KEY AUTOINCREMENT, url TEXT NOT NULL, "
        "status TEXT NOT NULL, final_url TEXT, error TEXT, groups_json TEXT NOT NULL DEFAULT '[]', "
        "created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
    )
    old.execute("INSERT INTO scans (url, status) VALUES ('https://old.test', 'complete')")
    old.commit()
    old.close()
    monkeypatch.setattr(config, "DATABASE_PATH", str(path))
    with TestClient(main.app, headers=BROWSER_A) as client:
        assert [s["url"] for s in client.get("/api/scans").json()] == ["https://old.test"]


def make_suggestion(client, monkeypatch):
    calls = fake_suggestion(monkeypatch)
    scan = start_scan(client)
    key = scan["groups"][0]["key"]
    return calls, client.post(f"/api/scans/{scan['id']}/groups/{key}/suggestion").json()["id"]


def test_retry_replaces_the_fix_and_keeps_the_rejection_counted(client, monkeypatch):
    calls, suggestion_id = make_suggestion(client, monkeypatch)
    seen = {}

    def second_try(issue, **kwargs):
        seen.update(kwargs)
        return FixSuggestion(
            explanation="new",
            fix_target="parent",
            fixed_html="<nav>new</nav>",
            needs_human_input=False,
            human_input_reason="",
        )

    client.post(
        f"/api/suggestions/{suggestion_id}/decision",
        json={"decision": "rejected", "reason": "wrong wrapper"},
    )
    monkeypatch.setattr(main, "suggest_fix", second_try)
    retried = client.post(f"/api/suggestions/{suggestion_id}/retry", json={"reason": "wrong wrapper"})

    assert retried.status_code == 200
    assert retried.json()["attempts"] == 2
    assert retried.json()["suggestion"]["fixed_html"] == "<nav>new</nav>"
    assert seen["feedback"] == "wrong wrapper"
    assert seen["previous_html"] == "<nav><ul>...</ul></nav>"

    # the new attempt starts undecided, but the old rejection still counts
    assert client.get(f"/api/scans/1/reviews").json()[0]["decision"] is None
    rule = client.get("/api/evaluation").json()["rules"][0]
    assert rule["suggestions"] == 2
    assert rule["decisions"] == {"rejected": 1}


def test_retries_stop_after_three_attempts(client, monkeypatch):
    _, suggestion_id = make_suggestion(client, monkeypatch)
    path = f"/api/suggestions/{suggestion_id}/retry"
    assert client.post(path, json={}).status_code == 200
    assert client.post(path, json={}).status_code == 200
    assert client.post(path, json={}).status_code == 409


def test_edit_runs_my_html_through_validation_without_saving(client, monkeypatch):
    _, suggestion_id = make_suggestion(client, monkeypatch)
    seen = {}

    def check(url, issue, suggestion):
        seen["html"] = suggestion.fixed_html
        return ValidationResult(
            verdict="failed",
            applied=True,
            detail="no",
            rule_before=2,
            rule_after=2,
            new_violations={},
            has_placeholder=False,
        )

    monkeypatch.setattr(main, "run_validation", check)
    result = client.post(f"/api/suggestions/{suggestion_id}/test-edit", json={"html": "<nav>mine</nav>"})
    assert result.json()["verdict"] == "failed"
    assert seen["html"] == "<nav>mine</nav>"
    assert client.get("/api/evaluation").json()["rules"][0]["verdicts"] == {"passed": 1}


def test_another_browser_cant_retry_or_test(client, monkeypatch):
    _, suggestion_id = make_suggestion(client, monkeypatch)
    base = f"/api/suggestions/{suggestion_id}"
    assert client.post(f"{base}/retry", json={}, headers=BROWSER_B).status_code == 404
    assert client.post(f"{base}/test-edit", json={"html": "<a>"}, headers=BROWSER_B).status_code == 404


def test_final_verdict_is_saved_with_the_decision(client, monkeypatch):
    _, suggestion_id = make_suggestion(client, monkeypatch)
    saved = client.post(
        f"/api/suggestions/{suggestion_id}/decision",
        json={"decision": "edited", "final_html": "<nav>", "final_verdict": "passed"},
    )
    assert saved.json()["final_verdict"] == "passed"


@pytest.mark.parametrize(
    "error, expected",
    [
        (PlaywrightTimeout("slow"), "60 seconds"),
        (PlaywrightError("net::ERR"), "couldn't be opened"),
        (PageLoadError("The page returned an error (status 404)."), "status 404"),
    ],
)
def test_scan_failures_get_plain_messages(client, monkeypatch, error, expected):
    def broken(url):
        raise error

    monkeypatch.setattr(main, "run_scan", broken)
    assert expected in start_scan(client)["error"]


def test_too_many_running_scans_are_refused(client):
    from app import db
    db.create_scan(PUBLIC_URL, BROWSER_A["X-Client-Id"])
    db.create_scan(PUBLIC_URL, BROWSER_A["X-Client-Id"])

    blocked = client.post("/api/scans", json={"url": PUBLIC_URL})
    assert blocked.status_code == 429
    assert "already have 2" in blocked.json()["detail"]

    # another browser isn't affected
    other = client.post("/api/scans", json={"url": PUBLIC_URL}, headers=BROWSER_B)
    assert other.status_code == 202
