"""分层事件总线测试（纯 Python，无 Qt/硬件依赖）。"""
import threading

from autotest.bus.event_bus import EventBus


def test_publish_and_subscribe():
    bus = EventBus(capacity=10)
    seen = []
    unsubscribe = bus.subscribe(seen.append)
    bus.publish("hal", "command", "query", detail=":IDN?", result="RIGOL")
    assert len(seen) == 1
    assert seen[0]["layer"] == "hal"
    assert seen[0]["action"] == "query"
    assert bus.stats()["total"] == 1
    unsubscribe()
    bus.publish("hal", "command", "query")
    assert len(seen) == 1


def test_ring_buffer_capacity():
    bus = EventBus(capacity=3)
    for i in range(5):
        bus.publish("app", "step", "s%d" % i)
    snapshot = bus.snapshot()
    assert len(snapshot) == 3
    assert [e["action"] for e in snapshot] == ["s2", "s3", "s4"]
    stats = bus.stats()
    assert stats["total"] == 5
    assert stats["stored"] == 3
    assert stats["capacity"] == 3


def test_span_records_result_and_duration():
    bus = EventBus()
    info = {}
    with bus.span("data", "write", "save_result", detail="t-1", info=info):
        info["result"] = "1 条结果"
    event = bus.snapshot()[-1]
    assert event["layer"] == "data"
    assert event["kind"] == "write"
    assert event["status"] == "ok"
    assert event["result"] == "1 条结果"
    assert event["duration_ms"] >= 0.0


def test_span_records_error_status():
    bus = EventBus()
    try:
        with bus.span("hal", "command", "query", detail="bad"):
            raise RuntimeError("boom")
    except RuntimeError:
        pass
    event = bus.snapshot()[-1]
    assert event["status"] == "error"
    assert "boom" in event["result"]


def test_quiet_context_counts_but_not_stored():
    bus = EventBus()
    with bus.quiet():
        bus.publish("hal", "command", "query", detail="polling")
    assert bus.snapshot() == []
    stats = bus.stats()
    assert stats["total"] == 1
    assert stats["noisy"] == 1
    assert stats["by_layer"]["hal"] == 1


def test_subscriber_exception_does_not_break_publish():
    bus = EventBus()

    def bad_subscriber(_payload):
        raise ValueError("subscriber error")

    bus.subscribe(bad_subscriber)
    bus.publish("ui", "action", "click")  # 不应抛异常
    assert bus.stats()["total"] == 1


def test_context_sets_correlation_and_source():
    bus = EventBus()
    with bus.context(corr_id="run-1", source="sim"):
        bus.publish("app", "step", "measure")
    event = bus.snapshot()[-1]
    assert event["corr_id"] == "run-1"
    assert event["source"] == "sim"


def test_thread_safety_of_publish():
    bus = EventBus(capacity=1000)

    def worker(n):
        for i in range(50):
            bus.publish("hal", "command", "query", detail="t%d-%d" % (n, i))

    threads = [threading.Thread(target=worker, args=(n,)) for n in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    stats = bus.stats()
    assert stats["total"] == 200
    assert stats["stored"] == 200
