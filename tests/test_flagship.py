"""State transitions, fault cases and generated protocol inputs; no webcam required."""

import io
import struct
from types import SimpleNamespace
import numpy as np
import pytest
from hypothesis import given, strategies as st
from PIL import Image
from modules.studio_live import LiveSession, pack_frame, unpack_frame
from modules.temporal import Track
from modules.source_checks import analyse_source


def face(x=20, width=60, identity=0):
    return SimpleNamespace(
        bbox=np.array([x, 20, x + width, 110], np.float32),
        kps=np.array(
            [[x + 15, 45], [x + 45, 45], [x + 30, 65], [x + 20, 90], [x + 40, 90]],
            np.float32,
        ),
        embedding=np.eye(4, dtype=np.float32)[identity],
    )


def track(i, x=20, width=60):
    return Track(i, face(x, width), np.eye(4, dtype=np.float32)[i % 4])


def test_selection_recovers_without_manual_click_and_waits_before_switching():
    session = LiveSession()
    a, b = track(1), track(2, 130, 50)
    assert session.choose([a, b], 10, 320, 240).id == 1
    assert session.choose([b], 10.1, 320, 240) is None
    assert session.selected == 1 and session.target_status == "reacquiring"
    assert session.choose([a, b], 10.5, 320, 240).id == 1
    assert session.recoveries == 1
    assert session.choose([b], 11, 320, 240) is None
    assert session.choose([b], 12.6, 320, 240).id == 2
    assert session.choose([a, b], 12.7, 320, 240).id == 2


def test_largest_then_centre_and_manual_target():
    session = LiveSession()
    a, b = track(1, 0), track(2, 130)
    session.tracker.tracks = [a, b]
    assert session.choose([a, b], 0, 320, 240).id == 2
    session.control({"select": 1})
    assert session.selection_mode == "manual"
    assert session.choose([a, b], 0.2, 320, 240).id == 1
    session.control({"auto": True})
    assert session.selection_mode == "auto"


def test_motion_loss_does_not_latch_manual_reselection(monkeypatch):
    from modules import studio_live

    session = LiveSession(dense_geometry=False, detection_interval=0)
    now = [0.0]
    session.clock = lambda: now[0]
    observations = iter([[face()], [], [face(60)]])
    monkeypatch.setattr(
        studio_live,
        "observe",
        lambda f: (next(observations), np.zeros(f.shape[:2], np.uint8)),
    )
    frame = np.zeros((160, 240, 3), np.uint8)
    selected = []
    for i in range(3):
        now[0] = i * 0.1
        packet = session.process(
            {"frame_id": i, "revision": 0, "captured_at": 0}, frame
        )
        header, _ = unpack_frame(packet)
        selected.append(header["selected_face"])
    assert selected == [1, 1, 1]
    assert session.target_status == "tracking"


def test_duplicate_frame_is_not_inferred_and_clear_erases_owned_latent(monkeypatch):
    from modules import studio_live

    session = LiveSession(dense_geometry=False)
    monkeypatch.setattr(
        studio_live, "observe", lambda f: ([], np.zeros(f.shape[:2], np.uint8))
    )
    header = {"frame_id": 0, "revision": 0, "captured_at": 0}
    frame = np.zeros((32, 32, 3), np.uint8)
    assert session.process(header, frame)
    assert session.process(header, frame) is None
    latent = np.ones((1, 512), np.float32)
    session.set_source(latent)
    session.set_source(None)
    assert not latent.any()
    session.reset_camera()
    assert session.latest is None and not session.thumbnails


def test_overlapping_people_keep_identity(monkeypatch):
    from modules import studio_live

    session = LiveSession(dense_geometry=False, detection_interval=0)
    observations = iter(
        [
            [face(10, 80, 0), face(150, 60, 1)],
            [face(70, 80, 0), face(90, 60, 1)],
            [face(10, 80, 0), face(150, 60, 1)],
        ]
    )
    monkeypatch.setattr(
        studio_live,
        "observe",
        lambda f: (next(observations), np.zeros(f.shape[:2], np.uint8)),
    )
    f = np.zeros((160, 280, 3), np.uint8)
    for i in range(2):
        session.process({"frame_id": i, "revision": 0, "captured_at": 0}, f)
    assert session.selected == 1 and session.target_status == "uncertain"
    session.process({"frame_id": 2, "revision": 0, "captured_at": 0}, f)
    assert session.selected == 1 and session.target_status == "tracking"


@given(
    st.integers(min_value=0, max_value=2**31),
    st.integers(min_value=0, max_value=100000),
    st.floats(min_value=0, max_value=1e12, allow_nan=False, allow_infinity=False),
)
def test_protocol_roundtrip_generated(frame_id, revision, captured):
    image = io.BytesIO()
    Image.new("RGB", (8, 8)).save(image, "JPEG")
    header = {"frame_id": frame_id, "revision": revision, "captured_at": captured}
    got, _ = unpack_frame(pack_frame(header, image.getvalue()))
    assert got == header


@given(st.binary(max_size=150))
def test_arbitrary_packet_cannot_escape_with_unexpected_error(data):
    try:
        unpack_frame(data)
    except (ValueError, OSError, struct.error, UnicodeError):
        pass


@pytest.mark.parametrize("value", [True, False, None, "4", float("inf")])
def test_capture_timestamp_rejects_wrong_types(value):
    with pytest.raises(ValueError):
        packet = pack_frame(
            {"frame_id": 0, "revision": 0, "captured_at": value}, b"jpeg"
        )
        unpack_frame(packet)


def test_preflight_advice_is_not_a_probability():
    result = analyse_source(np.zeros((160, 160, 3), np.uint8), face())
    assert result["status"] == "advisory" and len(result["warnings"]) >= 2
    assert "score" not in result


def test_cross_origin_http_write_and_purge():
    from fastapi.testclient import TestClient
    from modules.studio_api import app, sessions

    with TestClient(app) as client:
        assert (
            client.post(
                "/api/sessions", headers={"origin": "https://evil.invalid"}
            ).status_code
            == 403
        )
        key = client.post("/api/sessions").json()["id"]
        sessions[key].set_source(np.ones((1, 512), np.float32))
        response = client.post(f"/api/sessions/{key}/purge")
        assert response.json()["cleared"] and sessions[key].latent is None
        client.delete(f"/api/sessions/{key}")


def test_evidence_requires_all_ten_second_windows_and_unique_swaps():
    from modules.evaluation import browser_gate

    valid = {
        "duration_seconds": 120,
        "ten_second_windows": [16] * 12,
        "unique_frame_ids": 1920,
        "new_displayed_swaps": 1920,
        "p95_capture_to_display_ms": 90,
    }
    assert browser_gate(valid) == "Passed"
    assert browser_gate({**valid, "ten_second_windows": [14] + [20] * 11}) == "Failed"
    assert browser_gate({**valid, "unique_frame_ids": 1}) == "Failed"
    assert browser_gate({**valid, "duration_seconds": 20}) == "Failed"


def test_corpus_disallows_identity_leakage_and_report_does_not_pass_missing_checks(
    tmp_path,
):
    from modules.evaluation import validate_corpus, write_report

    corpus = {
        "clips": [
            {
                "id": str(i),
                "identity": str(i % 12),
                "split": "development" if i < 15 else "heldout",
                "sha256": "a",
                "provenance": "test",
                "licence": "test",
            }
            for i in range(30)
        ]
    }
    assert any("leakage" in e for e in validate_corpus(corpus))
    report = write_report(
        tmp_path,
        {},
        [
            {
                "name": "manual-review",
                "status": "Not Run",
                "required": True,
                "detail": "<script>unsafe</script>",
            }
        ],
    )
    assert report["overall"] == "Failed"
    assert "<script>unsafe" not in (tmp_path / "report.html").read_text()


def test_rejected_upload_always_closes_file():
    import asyncio
    from modules.studio_api import read_upload

    class Upload:
        closed = False

        async def read(self, n):
            return b"12345"

        async def close(self):
            self.closed = True

    upload = Upload()
    with pytest.raises(ValueError, match="too large"):
        asyncio.run(read_upload(upload, 3))
    assert upload.closed


def test_expired_session_drops_identity_buffers(monkeypatch):
    import time
    from modules import studio_api

    session = LiveSession()
    latent = np.ones((1, 512), np.float32)
    session.set_source(latent)
    session.touched = time.monotonic() - 4000
    studio_api.sessions["expiry-test"] = session
    studio_api.expire()
    assert "expiry-test" not in studio_api.sessions and not latent.any()


@pytest.mark.parametrize("mode", [[], {}, True, 1])
def test_malformed_mode_controls_are_validation_errors(mode):
    with pytest.raises(ValueError):
        LiveSession().control({"mode": mode})


def test_deeply_nested_header_is_a_friendly_validation_error():
    header = ("[" * 1200 + "0" + "]" * 1200).encode()
    with pytest.raises(ValueError, match="nested too deeply"):
        unpack_frame(struct.pack("!I", len(header)) + header + b"jpeg")


def test_appearance_ablation_exposes_crossing_tradeoff():
    from modules.temporal import FaceTracker

    appearance = FaceTracker()
    spatial = FaceTracker(appearance=False)
    initial = [face(10, 70, 0), face(150, 70, 1)]
    crossed = [face(150, 70, 0), face(10, 70, 1)]
    for tracker in [appearance, spatial]:
        tracker.update(initial)
        tracker.update(crossed)
    assert appearance.tracks[0].face.embedding[0] == 1
    assert spatial.tracks[0].face.embedding[1] == 1


def test_artifact_gate_does_not_trust_a_passed_label():
    from modules.evaluation import artifact_gate

    assert (
        artifact_gate(
            "one-hour-soak",
            {
                "status": "Passed",
                "complete": True,
                "duration_seconds": 30,
                "memory_gate_passed": True,
            },
        )
        == "Failed"
    )
    assert (
        artifact_gate(
            "visual-author-review",
            {"completed": True, "reviewer_count": 0, "ratings": []},
        )
        == "Failed"
    )
    assert (
        artifact_gate(
            "100-start-stop",
            {
                "complete": True,
                "cycles": 100,
                "camera_tracks_released": True,
                "server_sessions_released": True,
            },
        )
        == "Passed"
    )


def test_stale_person_click_keeps_camera_selection_and_ack_revision():
    session = LiveSession()
    present, missing = track(1), track(2)
    missing.visible = False
    session.tracker.tracks = [present, missing]
    session.selected = 1
    before = session.target_revision
    session.control({"select": 2})
    assert session.selected == 1 and session.target_revision == before + 1


def test_dependency_audit_alone_cannot_pass_container_security():
    from modules.evaluation import artifact_gate

    data = {"dependencies": [{"name": "example", "vulns": []}]}
    assert artifact_gate("security-audit", data) == "Failed"
    data.update(
        container={"completed": True, "unresolved_high_critical": 1},
        controls=[{"passed": True}],
    )
    assert artifact_gate("security-audit", data) == "Failed"
    data["container"]["unresolved_high_critical"] = 0
    assert artifact_gate("security-audit", data) == "Passed"


def test_local_server_rejects_untrusted_host_headers():
    from fastapi.testclient import TestClient
    from modules.studio_api import app

    with TestClient(app) as client:
        assert (
            client.get(
                "/api/system", headers={"host": "rebound.attacker.example"}
            ).status_code
            == 400
        )
        assert (
            client.get("/api/system", headers={"host": "127.0.0.1:7860"}).status_code
            == 200
        )
