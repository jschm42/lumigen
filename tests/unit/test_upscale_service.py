from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from app.config import Settings
from app.services.upscale_service import UpscaleService


def _write_png(path: Path, size: tuple[int, int] = (10, 10)) -> None:
    image = Image.new("RGB", size, color=(10, 20, 30))
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, format="PNG")


def test_is_available_and_format_helpers(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    cmd_path = tmp_path / "fake-upscaler.exe"
    cmd_path.write_text("bin", encoding="utf-8")

    service = UpscaleService(Settings(upscaler_command=str(cmd_path)))
    assert service.is_available() is True

    monkeypatch.setattr("app.services.upscale_service.shutil.which", lambda _cmd: None)
    service_missing = UpscaleService(Settings(upscaler_command="not-found"))
    assert service_missing.is_available() is False

    assert service._normalize_format("jpeg") == "jpg"
    assert service._normalize_format("unknown") == "png"
    assert service._format_to_mime("jpg") == "image/jpeg"
    assert service._format_to_mime("webp") == "image/webp"


def test_list_available_models_filters_invalid_and_missing_pairs(tmp_path: Path) -> None:
    model_dir = tmp_path / "models"
    model_dir.mkdir(parents=True, exist_ok=True)

    (model_dir / "good-x4.param").write_text("p", encoding="utf-8")
    (model_dir / "good-x4.bin").write_text("b", encoding="utf-8")
    (model_dir / "missing-bin.param").write_text("p", encoding="utf-8")
    (model_dir / "bad name.param").write_text("p", encoding="utf-8")
    (model_dir / "UPPER-X2.PARAM").write_text("p", encoding="utf-8")
    (model_dir / "UPPER-X2.BIN").write_text("b", encoding="utf-8")

    service = UpscaleService(Settings(upscaler_model_dir=model_dir))
    models = service.list_available_models()

    assert "good-x4" in models
    assert "UPPER-X2" in models
    assert "missing-bin" not in models


def test_upscale_bytes_runs_command_and_returns_output(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    cmd_path = tmp_path / "fake-upscaler.exe"
    cmd_path.write_text("bin", encoding="utf-8")
    model_dir = tmp_path / "models"
    model_dir.mkdir(parents=True, exist_ok=True)
    (model_dir / "realesrgan-x4plus.param").write_text("p", encoding="utf-8")
    (model_dir / "realesrgan-x4plus.bin").write_text("b", encoding="utf-8")

    captured_args = {}

    def fake_run(args, check, capture_output, text):  # type: ignore[no-untyped-def]
        captured_args["args"] = list(args)
        out_idx = args.index("-o") + 1
        output_path = Path(args[out_idx])
        _write_png(output_path, size=(40, 24))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr("app.services.upscale_service.subprocess.run", fake_run)

    service = UpscaleService(Settings(upscaler_command=str(cmd_path), upscaler_model_dir=model_dir))
    input_file = tmp_path / "in.png"
    _write_png(input_file, size=(10, 10))
    data = input_file.read_bytes()

    out_bytes, width, height, mime = service.upscale_bytes(
        data=data,
        output_format="png",
        model="realesrgan-x4plus",
    )

    assert out_bytes
    assert width == 40
    assert height == 24
    assert mime == "image/png"

    args = captured_args["args"]
    assert "-n" in args and "realesrgan-x4plus" in args
    assert "-s" in args and "4" in args
    assert "-f" in args and "png" in args
    assert "-m" in args


def test_upscale_bytes_errors_for_missing_command_model_or_output(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    service_no_cmd = UpscaleService(Settings(upscaler_command=None))
    with pytest.raises(ValueError, match="UPSCALER_COMMAND"):
        service_no_cmd.upscale_bytes(b"abc", "png", "realesrgan-x4plus")

    cmd_path = tmp_path / "fake-upscaler.exe"
    cmd_path.write_text("bin", encoding="utf-8")
    service = UpscaleService(Settings(upscaler_command=str(cmd_path)))

    with pytest.raises(ValueError, match="model is required"):
        service.upscale_bytes(b"abc", "png", "")

    def fake_run_no_output(args, check, capture_output, text):  # type: ignore[no-untyped-def]
        _ = args, check, capture_output, text
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr("app.services.upscale_service.subprocess.run", fake_run_no_output)
    _write_png(tmp_path / "in.png")
    with pytest.raises(ValueError, match="did not produce any output"):
        service.upscale_bytes((tmp_path / "in.png").read_bytes(), "png", "realesrgan-x4plus")


def test_upscale_bytes_subprocess_error_bubbles_stderr(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    cmd_path = tmp_path / "fake-upscaler.exe"
    cmd_path.write_text("bin", encoding="utf-8")
    service = UpscaleService(Settings(upscaler_command=str(cmd_path)))

    def fake_run_raise(args, check, capture_output, text):  # type: ignore[no-untyped-def]
        import subprocess

        raise subprocess.CalledProcessError(1, args, stderr="boom")

    monkeypatch.setattr("app.services.upscale_service.subprocess.run", fake_run_raise)
    _write_png(tmp_path / "in.png")
    with pytest.raises(ValueError, match="boom"):
        service.upscale_bytes((tmp_path / "in.png").read_bytes(), "png", "realesrgan-x4plus")
