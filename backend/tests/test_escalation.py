from agent import SYSTEM_PROMPT
from escalation import EscalationStore, sanitize_escalation_summary


def _create(store: EscalationStore, **overrides):
    values = {
        "customer_id": "caller-42",
        "customer_name": "Shivam",
        "issue_type": "PAYMENT_REFUND",
        "summary": "Customer paid but the order was not delivered.",
        "checked_information": "Order ORD-1001: Delivered. Payment: Paid.",
        "urgency": "HIGH",
        "language": "English",
        "preferred_followup": "Phone",
        "consent_given": True,
    }
    values.update(overrides)
    return store.create_or_update(**values)


def test_payment_escalation_persists_across_store_instances(tmp_path) -> None:
    database_path = tmp_path / "callers.sqlite3"
    record, created = _create(EscalationStore(database_path))

    persisted = EscalationStore(database_path).get(record.reference_id)

    assert created is True
    assert record.reference_id.startswith("ESC-")
    assert persisted == record
    assert persisted.status == "OPEN"


def test_order_dispute_uses_supported_medium_urgency(tmp_path) -> None:
    record, created = _create(
        EscalationStore(tmp_path / "callers.sqlite3"),
        issue_type="ORDER_DISPUTE",
        summary="A damaged item arrived.",
        urgency="MEDIUM",
    )

    assert created is True
    assert record.issue_type == "ORDER_DISPUTE"
    assert record.urgency == "MEDIUM"


def test_duplicate_open_issue_updates_existing_request(tmp_path) -> None:
    store = EscalationStore(tmp_path / "callers.sqlite3")
    first, first_created = _create(store)
    duplicate, duplicate_created = _create(
        store, summary="Customer now requests a phone update."
    )

    assert first_created is True
    assert duplicate_created is False
    assert duplicate.reference_id == first.reference_id
    assert len(store.list()) == 1
    assert "Latest update" in duplicate.summary


def test_different_issue_type_is_not_treated_as_duplicate(tmp_path) -> None:
    store = EscalationStore(tmp_path / "callers.sqlite3")
    _create(store)
    second, created = _create(store, issue_type="ORDER_DISPUTE", urgency="MEDIUM")

    assert created is True
    assert len(store.list()) == 2
    assert second.issue_type == "ORDER_DISPUTE"


def test_sensitive_information_is_removed_before_storage(tmp_path) -> None:
    store = EscalationStore(tmp_path / "callers.sqlite3")
    record, _ = _create(
        store,
        summary="Card 4111 1111 1111 1111 was charged twice; OTP is 123456.",
        checked_information="API key: secret-value and CVV 123",
    )

    stored_text = f"{record.summary} {record.checked_information}"
    assert "4111" not in stored_text
    assert "123456" not in stored_text
    assert "secret-value" not in stored_text
    assert "CVV 123" not in stored_text
    assert stored_text.count("[REDACTED]") == 4


def test_status_management_supports_full_workflow(tmp_path) -> None:
    store = EscalationStore(tmp_path / "callers.sqlite3")
    record, _ = _create(store)

    in_progress = store.update_status(record.reference_id, "IN_PROGRESS")
    resolved = store.update_status(record.reference_id, "RESOLVED")

    assert in_progress.status == "IN_PROGRESS"
    assert resolved.status == "RESOLVED"


def test_sanitizer_does_not_store_a_full_bank_account() -> None:
    safe = sanitize_escalation_summary(
        "Bank account number is 123456789012 and the refund has not arrived."
    )

    assert "123456789012" not in safe
    assert "refund has not arrived" in safe


def test_permission_denied_creates_no_escalation(tmp_path) -> None:
    store = EscalationStore(tmp_path / "callers.sqlite3")

    try:
        _create(store, consent_given=False)
    except PermissionError as error:
        assert "permission" in str(error).lower()
    else:
        raise AssertionError("Permission denial should stop escalation creation")

    assert store.list() == []


def test_normal_order_question_does_not_create_an_escalation(tmp_path) -> None:
    store = EscalationStore(tmp_path / "callers.sqlite3")

    assert "normal order-location" in SYSTEM_PROMPT
    assert "do not escalate those" in SYSTEM_PROMPT
    assert store.list() == []
