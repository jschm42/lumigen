from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, Tuple

from PIL import Image

from app.config import Settings


class UpscaleService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def is_available(self) -> bool:
        return self._resolve_command() is not None

    def list_available_models(self) -> list[str]:
        models: set[str] = set()
        model_dir = self._get_model_dir()
        if model_dir and model_dir.exists():
            for item in model_dir.iterdir():
                if item.is_file() and item.suffix.lower() == ".param":
                    if self._model_files_exist(item.stem, model_dir):
                        models.add(item.stem)

        return sorted(models)

    def upscale_bytes(
        self,
        data: bytes,
        output_format: str,
        model: str,
    ) -> Tuple[bytes, int, int, str]:
        cmd = self._resolve_command()
        if not cmd:
            raise ValueError("UPSCALER_COMMAND is not configured.")

        model_name = (model or "").strip()
        if not model_name:
            raise ValueError("Upscale model is required.")
        scale = self._infer_scale(model_name)
        if scale not in {2, 3, 4}:
            raise ValueError("Upscale model must map to x2, x3, or x4.")

        fmt = self._normalize_format(output_format)
        self._ensure_models_available(model_name)
        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_root = Path(tmp_dir)
            input_path = temp_root / f"input.{fmt}"
            input_path.write_bytes(data)

            output_path = self._run_realesrgan(
                cmd,
                input_path,
                temp_root / "out",
                scale,
                model_name,
                fmt,
            )

            output_bytes = output_path.read_bytes()
            width, height = self._get_image_size(output_path)
            mime = self._format_to_mime(fmt)
            return output_bytes, width, height, mime

    def _resolve_command(self) -> Optional[str]:
        cmd = (self.settings.upscaler_command or "").strip()
        if not cmd:
            return None
        if Path(cmd).is_file():
            return cmd
        return shutil.which(cmd)

    def _normalize_format(self, output_format: str) -> str:
        fmt = (output_format or "png").lower().lstrip(".")
        if fmt == "jpeg":
            fmt = "jpg"
        if fmt not in {"png", "jpg", "webp"}:
            return "png"
        return fmt

    def _format_to_mime(self, fmt: str) -> str:
        if fmt == "jpg":
            return "image/jpeg"
        return f"image/{fmt}"

    def _run_realesrgan(
        self,
        cmd: str,
        input_path: Path,
        output_dir: Path,
        scale: int,
        model: str,
        fmt: str,
    ) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{input_path.stem}.{fmt}"
        model_dir = self._model_dir_if_available(model)
        args = [
            cmd,
            "-i",
            str(input_path),
            "-o",
            str(output_path),
        ]
        if model_dir:
            args.extend(["-m", str(model_dir)])
        args.extend(
            [
                "-n",
                model,
                "-s",
                str(scale),
                "-f",
                fmt,
            ]
        )
        try:
            subprocess.run(args, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as exc:
            stderr = (exc.stderr or "").strip()
            message = stderr or "Upscaler command failed."
            raise ValueError(message) from exc

        if output_path.exists():
            return output_path

        matches = sorted(output_dir.glob(f"{input_path.stem}.*"))
        if matches:
            return matches[0]

        raise ValueError("Upscaler did not produce output.")

    def _get_image_size(self, path: Path) -> Tuple[int, int]:
        with Image.open(path) as image:
            return image.width, image.height

    def _model_dir_if_available(self, model: str) -> Optional[Path]:
        model_dir = self._get_model_dir()
        if not model_dir:
            return None
        if self._model_files_exist(model, model_dir):
            return model_dir
        return None

    def _ensure_models_available(self, model: str) -> None:
        if not self.settings.upscaler_auto_download:
            return

        repo = (self.settings.upscaler_hf_repo or "").strip()
        if not repo:
            raise ValueError("UPSCALER_HF_REPO is required for auto-download.")

        model_dir = self._get_model_dir()
        model_dir.mkdir(parents=True, exist_ok=True)

        if not self._model_files_exist(model, model_dir):
            self._download_model_files(repo, model, model_dir)

    def _model_files_exist(self, model: str, model_dir: Path) -> bool:
        param = model_dir / f"{model}.param"
        bin_file = model_dir / f"{model}.bin"
        if param.exists() and bin_file.exists():
            return True
        param_upper = model_dir / f"{model}.PARAM"
        bin_upper = model_dir / f"{model}.BIN"
        return param_upper.exists() and bin_upper.exists()

    def _download_model_files(self, repo: str, model: str, model_dir: Path) -> None:
        try:
            from huggingface_hub import hf_hub_download
        except ImportError as exc:
            raise ValueError(
                "huggingface_hub is required for auto-download. Install dependencies."
            ) from exc

        revision = (self.settings.upscaler_hf_revision or "").strip() or None
        for suffix in (".param", ".bin"):
            filename = f"{model}{suffix}"
            hf_hub_download(
                repo_id=repo,
                filename=filename,
                revision=revision,
                local_dir=str(model_dir),
                local_dir_use_symlinks=False,
            )

    def _infer_scale(self, model: str) -> int:
        lowered = model.lower()
        if "x2" in lowered:
            return 2
        if "x3" in lowered:
            return 3
        if "x4" in lowered:
            return 4
        return 4

    def _get_model_dir(self) -> Optional[Path]:
        model_dir = self.settings.upscaler_model_dir
        if not model_dir:
            return None
        return model_dir.expanduser().resolve()
