import pytest

from agent import (
    ORDER_SPECIALIST_NAME,
    PRODUCT_SPECIALIST_NAME,
    RETURNS_SPECIALIST_NAME,
    RETURNS_SPECIALIST_PROMPT,
    SYSTEM_PROMPT,
    Assistant,
    OrderSpecialist,
    ProductSpecialist,
    ReturnsRefundsSpecialist,
    _requires_returns_specialist,
    _sanitize_handoff_context,
    _specialist_route,
)
from analytics import CallAnalyticsStore, CallTracker


@pytest.mark.parametrize(
    ("utterance", "should_handoff"),
    [
        ("What products do you have?", False),
        ("I want to buy a blue shirt.", False),
        ("Can you recommend a shirt?", False),
        ("I want to return the shirt I bought.", True),
        ("The product I received is damaged.", True),
        ("Can I get a refund for my order?", True),
        ("Where is my order?", False),
        ("Can I exchange this product?", True),
        ("What is your return policy?", True),
        ("I want to buy another product.", False),
    ],
)
def test_ten_required_routing_examples(utterance: str, should_handoff: bool) -> None:
    assert _requires_returns_specialist(utterance) is should_handoff


def test_main_prompt_requires_announced_selective_handoff() -> None:
    assert "I'll connect you with our returns and refunds specialist" in SYSTEM_PROMPT
    assert "Returns/refunds always take precedence" in SYSTEM_PROMPT
    assert "Keep broad capability questions" in SYSTEM_PROMPT


def test_specialist_receives_context_and_shared_dependencies(tmp_path) -> None:
    tracker = CallTracker(
        CallAnalyticsStore(tmp_path / "calls.sqlite3"),
        call_id="context",
        channel="BROWSER",
    )
    main = Assistant(caller_id="caller-1", call_tracker=tracker)
    specialist = ReturnsRefundsSpecialist(
        main_agent=main,
        context="Intent: refund; issue: damaged; product: shoes",
    )

    assert specialist.main_agent is main
    assert specialist.memory_store is main.memory_store
    assert specialist.escalation_store is main.escalation_store
    assert specialist.call_tracker is tracker
    assert "damaged; product: shoes" in specialist.instructions


def test_specialist_scope_and_return_rules_are_explicit() -> None:
    prompt = RETURNS_SPECIALIST_PROMPT.casefold()
    assert RETURNS_SPECIALIST_NAME.casefold() in prompt
    assert "never ask the caller to repeat" in prompt
    assert "known details" in prompt
    assert "never invent" in prompt
    assert "return_to_main_agent" in prompt


def test_handoff_context_redacts_secrets() -> None:
    context = _sanitize_handoff_context(
        "Damaged shoes, refund requested; OTP: 123456; card number=4111111111111111"
    )

    assert "Damaged shoes" in context
    assert "123456" not in context
    assert "4111111111111111" not in context
    assert context.count("[REDACTED]") == 2


@pytest.mark.parametrize(
    ("utterance", "route"),
    [
        ("Hello", "MAIN"),
        ("What products do you sell?", "MAIN"),
        ("Recommend a shirt for me.", "PRODUCT"),
        ("Do you have blue shoes?", "PRODUCT"),
        ("Where is my order?", "ORDER"),
        ("When will my order arrive?", "ORDER"),
        ("I want to return my shoes.", "RETURNS"),
        ("My product arrived damaged.", "RETURNS"),
        ("Can I get a refund?", "RETURNS"),
        ("I want to buy another product.", "MAIN"),
    ],
)
def test_three_specialist_routing_examples(utterance: str, route: str) -> None:
    assert _specialist_route(utterance) == route


def test_returns_intent_takes_precedence_over_product_and_order_words() -> None:
    assert (
        _specialist_route(
            "The blue shoes I ordered last week arrived damaged and I want a refund."
        )
        == "RETURNS"
    )


def test_three_distinct_specialist_agents_share_context(tmp_path) -> None:
    tracker = CallTracker(
        CallAnalyticsStore(tmp_path / "three-specialists.sqlite3"),
        call_id="three-specialists",
        channel="BROWSER",
    )
    main = Assistant(caller_id="caller-2", call_tracker=tracker)
    specialists = (
        ProductSpecialist(main_agent=main, context="blue shoes under INR 5000"),
        OrderSpecialist(main_agent=main, context="order ORD-10, placed last week"),
        ReturnsRefundsSpecialist(
            main_agent=main, context="damaged blue shoes; refund requested"
        ),
    )

    assert len({type(agent) for agent in specialists}) == 3
    assert all(agent.main_agent is main for agent in specialists)
    assert all(agent.call_tracker is tracker for agent in specialists)


def test_main_agent_exposes_all_handoff_tools() -> None:
    assert hasattr(Assistant, "handoff_to_product_specialist")
    assert hasattr(Assistant, "handoff_to_order_specialist")
    assert hasattr(Assistant, "handoff_to_returns_specialist")
    assert PRODUCT_SPECIALIST_NAME == "Product Specialist"
    assert ORDER_SPECIALIST_NAME == "Order Specialist"


def test_specialist_greets_first_with_preserved_request_context(tmp_path) -> None:
    tracker = CallTracker(
        CallAnalyticsStore(tmp_path / "greeting.sqlite3"),
        call_id="greeting",
        channel="BROWSER",
    )
    specialist = ReturnsRefundsSpecialist(
        main_agent=Assistant(call_tracker=tracker),
        context="You received a damaged product and would like a refund.",
    )
    assert specialist._specialist_greeting() == (
        "Hi, I'm the Returns & Refunds specialist. I have the details of your "
        "request. You received a damaged product and would like a refund. "
        "Let's get this sorted."
    )
