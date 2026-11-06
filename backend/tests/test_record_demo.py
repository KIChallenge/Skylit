import pytest

from scripts.record_demo import checks, parse_sse


def test_parse_sse_multiline_comments_and_final_event():
    lines = [
        ': comment', 'event: text.delta', 'data: {"delta":', 'data: "Hello"}', '',
        'event: status', 'data: {"stage":"thinking"}',
    ]
    assert list(parse_sse(lines)) == [
        {"type": "text.delta", "delta": "Hello"},
        {"type": "status", "stage": "thinking"},
    ]


def test_parse_sse_rejects_invalid_data():
    with pytest.raises(ValueError):
        list(parse_sse(['event: status', 'data: []', '']))


def demo_turns():
    complete = {"type": "message.completed"}
    return [
        [complete],
        [{"type": "case.updated"}, complete],
        [{"type": "tool.result", "card": {"type": "form_draft"}}, complete],
        [{"type": "escalation"}, complete],
        [{"type": "emergency"}, {"type": "text.delta", "delta": "Help"}, complete],
        [
            {"type": "text.delta", "delta": "Your child can get the check-ups."},
            complete,
        ],
    ]


def test_checks_accept_demo():
    assert all(checks(demo_turns()).values())


def test_checks_detect_missing_and_misordered_events():
    turns = demo_turns()
    turns[1] = [{"type": "message.completed"}]
    turns[2] = [{"type": "tool.result", "card": None}]
    turns[3] = [{"type": "error"}]
    turns[4].reverse()
    turns[5] = [
        {"type": "text.delta", "delta": "Ihr Kind kann die Untersuchung machen."}
    ]
    assert not any(checks(turns).values())
