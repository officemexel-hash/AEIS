from __future__ import annotations

from device_harness import CaptureBackend, CommandResult, DeviceHarness, DeviceType


class _DummyRunner:
    def __init__(self):
        self.calls: list[tuple[str, list[str]]] = []

    def run_adb(self, command_id: str, args: list[str]) -> CommandResult:
        self.calls.append((command_id, args))
        return CommandResult(
            command_id=command_id,
            exit_code=0,
            stdout="ok",
            stderr="",
            elapsed_s=0.01,
            device=DeviceType.PIXEL,
        )


def test_start_capture_pixel_falls_back_to_screenrecord():
    runner = _DummyRunner()
    harness = DeviceHarness(runner=runner, max_resolution="1280x720")

    session = harness.start_capture_pixel(
        backend=CaptureBackend.SURFACEFLINGER,
        duration_s=30,
        output_path="/data/local/tmp/sylion/test.mp4",
    )

    assert session.backend == CaptureBackend.SCREENRECORD
    assert session.active is True
    assert runner.calls == [
        (
            "shell_screen",
            ["--size", "1280x720", "--time-limit", "30", "/data/local/tmp/sylion/test.mp4"],
        )
    ]
