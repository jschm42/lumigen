from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image

from app.config import Settings


class UpscaleService:
    """Service that upscales images using the Real-ESRGAN command-line tool."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def is_available(self) -> bool:
        """Return ``True`` if the upscaler command is configured and resolvable."""
        return self._resolve_command() is not None

    def list_available_models(self) -> list[str]:
        """Return the sorted list of upscaling model names found in the model directory."""
        models: set[str] = set()
        model_dir = self._get_model_dir()
        if model_dir and model_dir.exists():
            for item in model_dir.iterdir():
                if not item.is_file() or item.suffix.lower() != '.param':
                    continue
                try:
                    model_name = self._normalize_model_name(item.stem)
                except ValueError:
                    continue
                if self._model_files_exist(model_name, model_dir):
                    models.add(model_name)

        return sorted(models)

    def upscale_bytes(
        self,
        data: bytes,
        output_format: str,
        model: str,
    ) -> tuple[bytes, int, int, str]:
        """Upscale *data* using Real-ESRGAN and return ``(image_bytes, width, height, mime)``."""
        cmd = self._resolve_command()
        if not cmd:
            raise ValueError('UPSCALER_COMMAND is not configured')

        model_name = (model or '').strip()
        if not model_name:
            raise ValueError('Upscaling model is required')
        scale = self._infer_scale(model_name)
        if scale not in {2, 3, 4}:
            raise ValueError('Upscaling model must map to x2, x3, or x4')

        fmt = self._normalize_format(output_format)
        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_root = Path(tmp_dir)
            input_path = temp_root / f'input.{fmt}'
            input_path.write_bytes(data)

            output_path = self._run_realesrgan(
                cmd,
                input_path,
                temp_root / 'out',
                scale,
                model_name,
                fmt,
            )

            output_bytes = output_path.read_bytes()
            width, height = self._get_image_size(output_path)
            mime = self._format_to_mime(fmt)
            return output_bytes, width, height, mime

    def _resolve_command(self) -> str | None:
        cmd = (self.settings.upscaler_command or '').strip()
        if not cmd:
            return None
        if Path(cmd).is_file():
            return cmd
        return shutil.which(cmd)

    def _normalize_format(self, output_format: str) -> str:
        fmt = (output_format or 'png').lower().lstrip('.')
        if fmt == 'jpeg':
            fmt = 'jpg'
        if fmt not in {'png', 'jpg', 'webp'}:
            return 'png'
        return fmt

    def _format_to_mime(self, fmt: str) -> str:
        if fmt == 'jpg':
            return 'image/jpeg'
        return f'image/{fmt}'

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
        output_path = output_dir / f'{input_path.stem}.{fmt}'
        model_dir = self._model_dir_if_available(model)
        args = [
            cmd,
            '-i',
            str(input_path),
            '-o',
            str(output_path),
        ]
        if model_dir:
            args.extend(['-m', str(model_dir)])
        args.extend([
            '-n',
            model,
            '-s',
            str(scale),
            '-f',
            fmt,
        ])
        try:
            subprocess.run(args, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as exc:
            stderr = (exc.stderr or '').strip()
            message = stderr or 'Upscaler command failed'
            raise ValueError(message) from exc

        if output_path.exists():
            return output_path

        matches = sorted(output_dir.glob(f'{input_path.stem}.*'))
        if matches:
            return matches[0]

        raise ValueError('Upscaler did not produce any output')

    def _get_image_size(self, path: Path) -> tuple[int, int]:
        with Image.open(path) as image:
            return image.width, image.height

    def _model_dir_if_available(self, model: str) -> Path | None:
        model_dir = self._get_model_dir()
        if not model_dir:
            return None
        if self._model_files_exist(model, model_dir):
            return model_dir
        return None

    def _model_files_exist(self, model: str, model_dir: Path) -> bool:
        param = model_dir / f'{model}.param'
        bin_file = model_dir / f'{model}.bin'
        if param.exists() and bin_file.exists():
            return True
        param_upper = model_dir / f'{model}.PARAM'
        bin_upper = model_dir / f'{model}.BIN'
        return param_upper.exists() and bin_upper.exists()

    def _infer_scale(self, model: str) -> int:
        lowered = model.lower()
        if 'x2' in lowered:
            return 2
        if 'x3' in lowered:
            return 3
        if 'x4' in lowered:
            return 4
        return 4

    def _normalize_model_name(self, value: str) -> str:
        candidate = (value or '').strip()
        if not candidate:
            return ''
        if len(candidate) > 128:
            raise ValueError('Upscaling model must be 128 characters or fewer')
        if not re.fullmatch(r'[A-Za-z0-9._-]+', candidate):
            raise ValueError('Upscaling model contains invalid characters')
        return candidate

    def _get_model_dir(self) -> Path | None:
        model_dir = self.settings.upscaler_model_dir
        if not model_dir:
            return None
        return model_dir.expanduser().resolve()
