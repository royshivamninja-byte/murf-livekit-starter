from datetime import datetime, timedelta, timezone

from analytics import AnalyticsFilter, CallAnalyticsStore, CallTracker


def test_completed_product_enquiry_is_successful(tmp_path) -> None:
    store = CallAnalyticsStore(tmp_path / "calls.sqlite3")
    tracker = CallTracker(store, call_id="call-1", channel="BROWSER")

    tracker.record_user_turn(language="en", completed_at=100.0)
    tracker.record_agent_speaking(started_at=100.84)
    tracker.mark_success("PRODUCT_ENQUIRY")
    tracker.finish(ended_at=tracker.started_at + timedelta(seconds=42))

    record = store.list_calls(AnalyticsFilter())[0]
    assert record["outcome"] == "SUCCESS"
    assert record["track_outcome"] == "PRODUCT_ENQUIRY"
    assert record["latency_ms"] == 840
    assert record["language"] == "English"


def test_connected_call_without_completed_request_fails(tmp_path) -> None:
    store = CallAnalyticsStore(tmp_path / "calls.sqlite3")
    tracker = CallTracker(store, call_id="call-2", channel="SIP")

    tracker.finish(
        failure_type="USER_HANGUP",
        ended_at=tracker.started_at + timedelta(seconds=7),
    )

    summary = store.summary(AnalyticsFilter())
    assert summary == {
        "total_calls": 1,
        "successful_calls": 0,
        "failed_calls": 1,
        "success_rate": 0.0,
        "average_latency_ms": 0,
    }


def test_filters_apply_to_all_analytics_queries(tmp_path) -> None:
    store = CallAnalyticsStore(tmp_path / "calls.sqlite3")
    now = datetime.now(timezone.utc)
    first = CallTracker(store, call_id="english", channel="BROWSER", started_at=now)
    first.record_user_turn(language="en", completed_at=10.0)
    first.record_agent_speaking(started_at=10.5)
    first.mark_success("PRODUCT_ENQUIRY")
    first.finish(ended_at=now + timedelta(seconds=10))
    second = CallTracker(store, call_id="hindi", channel="SIP", started_at=now)
    second.record_user_turn(language="hi", completed_at=20.0)
    second.finish(failure_type="NO_RESPONSE", ended_at=now + timedelta(seconds=5))

    filters = AnalyticsFilter(language="Hindi", channel="SIP", outcome="FAILED")

    assert store.summary(filters)["total_calls"] == 1
    assert store.list_calls(filters)[0]["call_id"] == "hindi"
    assert store.failures(filters)["NO_RESPONSE"] == 1
    assert sum(point["total_calls"] for point in store.trends(filters)) == 1


def test_handoff_metadata_is_stored_without_changing_success(tmp_path) -> None:
    store = CallAnalyticsStore(tmp_path / "calls.sqlite3")
    tracker = CallTracker(store, call_id="handoff", channel="BROWSER")
    tracker.record_handoff("Returns & Refunds Specialist", success=True)
    tracker.mark_success("PRODUCT_ENQUIRY")
    tracker.finish()

    record = store.list_calls(AnalyticsFilter())[0]
    assert record["outcome"] == "SUCCESS"
    assert record["specialist_used"] == 1
    assert record["handoff_count"] == 1
    assert record["handoff_success"] == 1
    assert record["specialist_name"] == "Returns & Refunds Specialist"


def test_failed_handoff_is_distinguishable(tmp_path) -> None:
    store = CallAnalyticsStore(tmp_path / "calls.sqlite3")
    tracker = CallTracker(store, call_id="failed-handoff", channel="SIP")
    tracker.record_handoff("Returns & Refunds Specialist", success=False)
    tracker.finish()

    record = store.list_calls(AnalyticsFilter())[0]
    assert record["failure_type"] == "HANDOFF_FAILURE"
    assert record["handoff_success"] == 0
