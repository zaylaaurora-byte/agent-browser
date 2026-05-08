from pathlib import Path

from runtime_memory import RuntimeMemory


def test_runtime_memory_upsert_and_get(tmp_path: Path):
    db = tmp_path / "runtime_memory.db"
    rm = RuntimeMemory(db)

    rm.upsert_profile(
        domain="booking.com",
        workflow="holiday_checkout",
        payload={"selectors": ["button.search"], "last_success": True},
    )

    prof = rm.get_profile("booking.com", "holiday_checkout")
    assert prof is not None
    assert prof.domain == "booking.com"
    assert prof.workflow == "holiday_checkout"
    assert prof.payload["last_success"] is True


def test_runtime_memory_update_and_list(tmp_path: Path):
    db = tmp_path / "runtime_memory.db"
    rm = RuntimeMemory(db)

    rm.upsert_profile("instagram.com", "comment_flow", {"step_count": 5})
    rm.upsert_profile("instagram.com", "comment_flow", {"step_count": 3})
    rm.upsert_profile("linkedin.com", "job_apply", {"step_count": 8})

    p = rm.get_profile("instagram.com", "comment_flow")
    assert p is not None
    assert p.payload["step_count"] == 3

    listed = rm.list_profiles(limit=10)
    assert len(listed) == 2

    deleted = rm.delete_profile("instagram.com", "comment_flow")
    assert deleted == 1
    assert rm.get_profile("instagram.com", "comment_flow") is None
