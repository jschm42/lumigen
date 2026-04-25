"""Admin import/export service for Profiles, Models, and Styles.

This module provides versioned JSON serialisation and deserialisation for the
three core admin configuration entities: ``ModelConfig``, ``Profile``, and
``Style``.

Format versioning
-----------------
Every export payload includes a ``format_version`` string (currently ``"1"``)
and an ``exported_at`` ISO-8601 timestamp.  The import functions reject
payloads with unknown versions and return a clear error message.

Conflict strategies
-------------------
``skip``
    Leave existing records untouched; mark the imported record as *skipped*.
``overwrite``
    Update the existing record in place; mark it as *updated*.
``rename``
    Create the new record under a name like ``"Original (2)"``; mark it as
    *created*.

Dry-run mode
------------
Pass ``dry_run=True`` to any import function to preview changes without
committing them.  Counts are still returned; no database writes occur.

Typical usage
-------------
::

    from app.services.import_export_service import export_all, import_styles

    # Export
    payload = export_all(session)

    # Import (commit)
    result = import_styles(session, payload["styles"], "skip")
    print(result.created, result.skipped, result.failed)

    # Import (dry-run preview)
    result = import_styles(session, payload["styles"], "overwrite", dry_run=True)
"""

from __future__ import annotations

import io
import shutil
import zipfile
from dataclasses import dataclass, field
from datetime import UTC, datetime
from json import JSONDecodeError, dumps, loads
from pathlib import Path
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import crud

CURRENT_FORMAT_VERSION = "1"
SUPPORTED_FORMAT_VERSIONS = {"1"}

_PROFILE_REQUIRED_FIELDS = {"name", "provider", "model"}
_MODEL_REQUIRED_FIELDS = {"name", "provider", "model"}
_STYLE_REQUIRED_FIELDS = {"name", "description", "prompt"}

_MAX_PROFILE_NAME = 50
_MAX_MODEL_NAME = 50
_MAX_STYLE_NAME = 30
_MAX_STYLE_DESCRIPTION = 120
_MAX_STYLE_PROMPT = 1000


@dataclass
class RecordResult:
    """Result for a single imported record.

    Attributes
    ----------
    name:
        The (possibly renamed) entity name that was processed.
    outcome:
        One of ``"created"``, ``"updated"``, ``"skipped"``, or ``"failed"``.
    reason:
        Human-readable explanation for *skipped* or *failed* outcomes.
    """

    name: str
    outcome: str
    reason: str = ""


@dataclass
class ImportResult:
    """Aggregated summary for one entity type after an import run."""

    entity_type: str
    records: list[RecordResult] = field(default_factory=list)

    @property
    def created(self) -> int:
        """Return count of created records."""
        return sum(1 for r in self.records if r.outcome == "created")

    @property
    def updated(self) -> int:
        """Return count of updated records."""
        return sum(1 for r in self.records if r.outcome == "updated")

    @property
    def skipped(self) -> int:
        """Return count of skipped records."""
        return sum(1 for r in self.records if r.outcome == "skipped")

    @property
    def failed(self) -> int:
        """Return count of failed records."""
        return sum(1 for r in self.records if r.outcome == "failed")

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a plain dict suitable for JSON responses."""
        return {
            "entity_type": self.entity_type,
            "created": self.created,
            "updated": self.updated,
            "skipped": self.skipped,
            "failed": self.failed,
            "records": [
                {"name": r.name, "outcome": r.outcome, "reason": r.reason}
                for r in self.records
            ],
        }


# ---------------------------------------------------------------------------
# Export helpers
# ---------------------------------------------------------------------------


def _export_metadata() -> dict[str, str]:
    """Return standard export metadata fields.

    Returns a dict with ``format_version`` (used for forward/backward
    compatibility checks during import) and ``exported_at`` (ISO-8601 UTC
    timestamp for auditing).
    """
    return {
        "format_version": CURRENT_FORMAT_VERSION,
        "exported_at": datetime.now(UTC).isoformat(),
    }


def export_models(session: Session) -> dict[str, Any]:
    """Export all ModelConfig rows as a versioned JSON-serialisable dict."""
    models = crud.list_model_configs(session)
    return {
        **_export_metadata(),
        "models": [
            {
                "name": m.name,
                "provider": m.provider,
                "model": m.model,
                "enhancement_prompt": m.enhancement_prompt,
                "use_custom_api_key": m.use_custom_api_key,
            }
            for m in models
        ],
    }


def export_profiles(session: Session) -> dict[str, Any]:
    """Export all Profile rows as a versioned JSON-serialisable dict.

    ``model_config_name`` is included so the import process can attempt to
    link an existing ModelConfig on the target instance.
    """
    profiles = crud.list_profiles(session)
    return {
        **_export_metadata(),
        "profiles": [
            {
                "name": p.name,
                "provider": p.provider,
                "model": p.model,
                "model_config_name": p.model_config.name if p.model_config else None,
                "base_prompt": p.base_prompt,
                "negative_prompt": p.negative_prompt,
                "width": p.width,
                "height": p.height,
                "aspect_ratio": p.aspect_ratio,
                "n_images": p.n_images,
                "seed": p.seed,
                "output_format": p.output_format,
                "upscale_provider": p.upscale_provider,
                "upscale_model": p.upscale_model,
                "params_json": dict(p.params_json or {}),
            }
            for p in profiles
        ],
    }


def export_styles(session: Session) -> dict[str, Any]:
    """Export all Style rows as a versioned JSON-serialisable dict.

    Style thumbnail images are intentionally excluded; only the textual
    metadata (name, description, prompt) is portable.
    """
    styles = crud.list_styles(session)
    return {
        **_export_metadata(),
        "styles": [
            {
                "name": s.name,
                "description": s.description,
                "prompt": s.prompt,
            }
            for s in styles
        ],
    }


def export_all(session: Session) -> dict[str, Any]:
    """Export Profiles, Models, and Styles together in a single payload."""
    models_payload = export_models(session)
    profiles_payload = export_profiles(session)
    styles_payload = export_styles(session)
    return {
        **_export_metadata(),
        "models": models_payload["models"],
        "profiles": profiles_payload["profiles"],
        "styles": styles_payload["styles"],
    }


def export_styles_zip(session: Session, styles_dir: Path) -> bytes:
    """Export all Styles including their thumbnail images as a Zip archive.

    The archive contains:
    - styles.json: Metadata for all styles.
    - images/: Directory containing the .webp thumbnails.
    """
    styles = crud.list_styles(session)
    metadata = _export_metadata()
    styles_list = []

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for s in styles:
            style_data = {
                "name": s.name,
                "description": s.description,
                "prompt": s.prompt,
            }

            if s.image_path:
                # The image_path in DB is just a flag/path, but we know the naming convention
                image_name = f"{s.id}.webp"
                image_path = styles_dir / image_name
                if image_path.exists():
                    zip_path = f"images/{image_name}"
                    zip_file.write(image_path, zip_path)
                    style_data["image_filename"] = image_name

            styles_list.append(style_data)

        metadata["styles"] = styles_list
        zip_file.writestr("styles.json", dumps(metadata, indent=2))

    return buffer.getvalue()


# ---------------------------------------------------------------------------
# Import validation
# ---------------------------------------------------------------------------


def validate_import_payload(
    payload: Any,
) -> tuple[str | None, str, list[Any], list[Any], list[Any]]:
    """Validate the top-level structure of an import payload.

    Returns ``(error, format_version, profiles, models, styles)``.  When
    *error* is not ``None`` the other values are empty/default and the caller
    should return an error response without further processing.  This
    return-value style avoids propagating ``ValueError`` through HTTP handlers,
    which can inadvertently expose internal state in error responses.
    """
    if not isinstance(payload, dict):
        return "Import payload must be a JSON object.", "", [], [], []

    version = payload.get("format_version")
    if not isinstance(version, str) or not version.strip():
        return "Missing or invalid 'format_version' in import payload.", "", [], [], []
    version = version.strip()
    if version not in SUPPORTED_FORMAT_VERSIONS:
        supported = ", ".join(sorted(SUPPORTED_FORMAT_VERSIONS))
        return (
            f"Unsupported format_version '{version}'. Supported: {supported}.",
            "",
            [],
            [],
            [],
        )

    profiles: Any = payload.get("profiles", [])
    models: Any = payload.get("models", [])
    styles: Any = payload.get("styles", [])

    if not isinstance(profiles, list):
        return "'profiles' must be a JSON array.", "", [], [], []
    if not isinstance(models, list):
        return "'models' must be a JSON array.", "", [], [], []
    if not isinstance(styles, list):
        return "'styles' must be a JSON array.", "", [], [], []

    return None, version, profiles, models, styles


# ---------------------------------------------------------------------------
# Import helpers
# ---------------------------------------------------------------------------


def _unique_name(base_name: str, existing_names: set[str], max_len: int) -> str:
    """Return a unique name derived from *base_name* by appending a counter.

    Iterates counters starting at 2 until a name is not in *existing_names*.
    If appending the suffix would exceed *max_len*, the base name is truncated
    to accommodate the suffix while keeping the total length within the limit.

    Parameters
    ----------
    base_name:
        The desired name that already exists in *existing_names*.
    existing_names:
        Set of names already taken.
    max_len:
        Maximum allowed character length for the returned name.
    """
    candidate = base_name
    counter = 2
    while candidate in existing_names:
        suffix = f" ({counter})"
        truncated = base_name[: max_len - len(suffix)]
        candidate = f"{truncated}{suffix}"
        counter += 1
    return candidate


def _optional_int(val: Any) -> int | None:
    """Coerce *val* to int or return ``None``.

    Returns ``None`` when *val* is ``None``, or when it cannot be converted to
    an integer (e.g. a non-numeric string).  ``TypeError`` and ``ValueError``
    are silently swallowed.
    """
    if val is None:
        return None
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


def import_models(
    session: Session,
    records: list[Any],
    conflict_strategy: str,
    *,
    dry_run: bool = False,
) -> ImportResult:
    """Import ModelConfig records from a list of dicts.

    Parameters
    ----------
    session:
        Active SQLAlchemy session.
    records:
        List of raw record dicts from the import payload.
    conflict_strategy:
        One of ``"skip"``, ``"overwrite"``, or ``"rename"``.
    dry_run:
        When *True* no database changes are committed.
    """
    result = ImportResult(entity_type="models")
    if conflict_strategy not in {"skip", "overwrite", "rename"}:
        raise ValueError(f"Invalid conflict_strategy '{conflict_strategy}'.")

    existing_by_name: dict[str, Any] = {
        m.name: m for m in crud.list_model_configs(session)
    }

    for raw in records:
        if not isinstance(raw, dict):
            result.records.append(
                RecordResult(name="?", outcome="failed", reason="Record is not a JSON object.")
            )
            continue

        missing = _MODEL_REQUIRED_FIELDS - raw.keys()
        if missing:
            name_hint = str(raw.get("name", "?"))
            result.records.append(
                RecordResult(
                    name=name_hint,
                    outcome="failed",
                    reason=f"Missing required fields: {', '.join(sorted(missing))}.",
                )
            )
            continue

        name = str(raw.get("name") or "").strip()
        provider = str(raw.get("provider") or "").strip()
        model = str(raw.get("model") or "").strip()

        if not name:
            result.records.append(RecordResult(name="?", outcome="failed", reason="Name is required."))
            continue
        if len(name) > _MAX_MODEL_NAME:
            result.records.append(
                RecordResult(
                    name=name,
                    outcome="failed",
                    reason=f"Name exceeds {_MAX_MODEL_NAME} characters.",
                )
            )
            continue
        if not provider:
            result.records.append(RecordResult(name=name, outcome="failed", reason="Provider is required."))
            continue
        if not model:
            result.records.append(RecordResult(name=name, outcome="failed", reason="Model is required."))
            continue

        enhancement_prompt: str | None = raw.get("enhancement_prompt") or None
        if isinstance(enhancement_prompt, str):
            enhancement_prompt = enhancement_prompt.strip() or None
        use_custom_api_key = bool(raw.get("use_custom_api_key", False))

        existing = existing_by_name.get(name)

        if existing:
            if conflict_strategy == "skip":
                result.records.append(RecordResult(name=name, outcome="skipped", reason="Name already exists."))
                continue
            elif conflict_strategy == "overwrite":
                if not dry_run:
                    try:
                        crud.update_model_config(
                            session,
                            existing,
                            provider=provider,
                            model=model,
                            enhancement_prompt=enhancement_prompt,
                            use_custom_api_key=use_custom_api_key,
                        )
                    except (ValueError, IntegrityError) as exc:
                        result.records.append(RecordResult(name=name, outcome="failed", reason=str(exc)))
                        continue
                result.records.append(RecordResult(name=name, outcome="updated"))
                continue
            else:  # rename
                name = _unique_name(name, set(existing_by_name.keys()), _MAX_MODEL_NAME)

        if not dry_run:
            try:
                new_row = crud.create_model_config(
                    session,
                    name=name,
                    provider=provider,
                    model=model,
                    enhancement_prompt=enhancement_prompt,
                    use_custom_api_key=use_custom_api_key,
                )
                existing_by_name[name] = new_row
            except (ValueError, IntegrityError) as exc:
                result.records.append(RecordResult(name=name, outcome="failed", reason=str(exc)))
                continue
        result.records.append(RecordResult(name=name, outcome="created"))
        existing_by_name[name] = object()  # placeholder so rename logic works in dry_run

    return result


def import_styles(
    session: Session,
    records: list[Any],
    conflict_strategy: str,
    *,
    dry_run: bool = False,
) -> ImportResult:
    """Import Style records from a list of dicts.

    Parameters
    ----------
    session:
        Active SQLAlchemy session.
    records:
        List of raw record dicts from the import payload.
    conflict_strategy:
        One of ``"skip"``, ``"overwrite"``, or ``"rename"``.
    dry_run:
        When *True* no database changes are committed.
    """
    result = ImportResult(entity_type="styles")
    if conflict_strategy not in {"skip", "overwrite", "rename"}:
        raise ValueError(f"Invalid conflict_strategy '{conflict_strategy}'.")

    existing_by_name: dict[str, Any] = {s.name: s for s in crud.list_styles(session)}

    for raw in records:
        if not isinstance(raw, dict):
            result.records.append(
                RecordResult(name="?", outcome="failed", reason="Record is not a JSON object.")
            )
            continue

        missing = _STYLE_REQUIRED_FIELDS - raw.keys()
        if missing:
            name_hint = str(raw.get("name", "?"))
            result.records.append(
                RecordResult(
                    name=name_hint,
                    outcome="failed",
                    reason=f"Missing required fields: {', '.join(sorted(missing))}.",
                )
            )
            continue

        name = str(raw.get("name") or "").strip()
        description = str(raw.get("description") or "").strip()
        prompt = str(raw.get("prompt") or "").strip()

        if not name:
            result.records.append(RecordResult(name="?", outcome="failed", reason="Name is required."))
            continue
        if len(name) > _MAX_STYLE_NAME:
            result.records.append(
                RecordResult(
                    name=name,
                    outcome="failed",
                    reason=f"Name exceeds {_MAX_STYLE_NAME} characters.",
                )
            )
            continue
        if not description:
            result.records.append(RecordResult(name=name, outcome="failed", reason="Description is required."))
            continue
        if len(description) > _MAX_STYLE_DESCRIPTION:
            result.records.append(
                RecordResult(
                    name=name,
                    outcome="failed",
                    reason=f"Description exceeds {_MAX_STYLE_DESCRIPTION} characters.",
                )
            )
            continue
        if not prompt:
            result.records.append(RecordResult(name=name, outcome="failed", reason="Prompt is required."))
            continue
        if len(prompt) > _MAX_STYLE_PROMPT:
            result.records.append(
                RecordResult(
                    name=name,
                    outcome="failed",
                    reason=f"Prompt exceeds {_MAX_STYLE_PROMPT} characters.",
                )
            )
            continue

        existing = existing_by_name.get(name)

        if existing:
            if conflict_strategy == "skip":
                result.records.append(RecordResult(name=name, outcome="skipped", reason="Name already exists."))
                continue
            elif conflict_strategy == "overwrite":
                if not dry_run:
                    try:
                        crud.update_style(
                            session,
                            existing,
                            name=name,
                            description=description,
                            prompt=prompt,
                        )
                    except (ValueError, IntegrityError) as exc:
                        result.records.append(RecordResult(name=name, outcome="failed", reason=str(exc)))
                        continue
                result.records.append(RecordResult(name=name, outcome="updated"))
                continue
            else:  # rename
                name = _unique_name(name, set(existing_by_name.keys()), _MAX_STYLE_NAME)

        if not dry_run:
            try:
                new_row = crud.create_style(
                    session,
                    name=name,
                    description=description,
                    prompt=prompt,
                    image_path=None,
                )
                existing_by_name[name] = new_row
            except (ValueError, IntegrityError) as exc:
                result.records.append(RecordResult(name=name, outcome="failed", reason=str(exc)))
                continue
        result.records.append(RecordResult(name=name, outcome="created"))
        existing_by_name[name] = object()  # placeholder so rename logic works in dry_run

    return result


def import_profiles(
    session: Session,
    records: list[Any],
    conflict_strategy: str,
    *,
    dry_run: bool = False,
) -> ImportResult:
    """Import Profile records from a list of dicts.

    The default storage template is used for every imported profile.
    ``model_config_name`` in each record, if present, is used to look up
    and link an existing ModelConfig on the target instance.

    Parameters
    ----------
    session:
        Active SQLAlchemy session.
    records:
        List of raw record dicts from the import payload.
    conflict_strategy:
        One of ``"skip"``, ``"overwrite"``, or ``"rename"``.
    dry_run:
        When *True* no database changes are committed.
    """
    from app.config import get_settings

    result = ImportResult(entity_type="profiles")
    if conflict_strategy not in {"skip", "overwrite", "rename"}:
        raise ValueError(f"Invalid conflict_strategy '{conflict_strategy}'.")

    existing_by_name: dict[str, Any] = {p.name: p for p in crud.list_profiles(session)}
    model_configs_by_name: dict[str, Any] = {
        m.name: m for m in crud.list_model_configs(session)
    }

    # Resolve the default storage template once
    settings = get_settings()
    storage_template = crud.ensure_default_storage_template(
        session,
        base_dir=Path(settings.default_base_dir),
        template=settings.default_storage_template,
    )

    for raw in records:
        if not isinstance(raw, dict):
            result.records.append(
                RecordResult(name="?", outcome="failed", reason="Record is not a JSON object.")
            )
            continue

        missing = _PROFILE_REQUIRED_FIELDS - raw.keys()
        if missing:
            name_hint = str(raw.get("name", "?"))
            result.records.append(
                RecordResult(
                    name=name_hint,
                    outcome="failed",
                    reason=f"Missing required fields: {', '.join(sorted(missing))}.",
                )
            )
            continue

        name = str(raw.get("name") or "").strip()
        provider = str(raw.get("provider") or "").strip()
        model = str(raw.get("model") or "").strip()

        if not name:
            result.records.append(RecordResult(name="?", outcome="failed", reason="Name is required."))
            continue
        if len(name) > _MAX_PROFILE_NAME:
            result.records.append(
                RecordResult(
                    name=name,
                    outcome="failed",
                    reason=f"Name exceeds {_MAX_PROFILE_NAME} characters.",
                )
            )
            continue
        if not provider:
            result.records.append(RecordResult(name=name, outcome="failed", reason="Provider is required."))
            continue
        if not model:
            result.records.append(RecordResult(name=name, outcome="failed", reason="Model is required."))
            continue

        # Resolve optional model_config linkage
        model_config_id: int | None = None
        model_config_name = raw.get("model_config_name")
        if isinstance(model_config_name, str) and model_config_name.strip():
            mc = model_configs_by_name.get(model_config_name.strip())
            if mc:
                model_config_id = mc.id

        base_prompt: str | None = raw.get("base_prompt") or None
        if isinstance(base_prompt, str):
            base_prompt = base_prompt.strip() or None
        negative_prompt: str | None = raw.get("negative_prompt") or None
        if isinstance(negative_prompt, str):
            negative_prompt = negative_prompt.strip() or None

        width = _optional_int(raw.get("width"))
        height = _optional_int(raw.get("height"))
        aspect_ratio: str | None = raw.get("aspect_ratio") or None
        if isinstance(aspect_ratio, str):
            aspect_ratio = aspect_ratio.strip() or None
        n_images = _optional_int(raw.get("n_images")) or 1
        seed = _optional_int(raw.get("seed"))
        output_format = str(raw.get("output_format") or "png").strip().lower() or "png"
        upscale_provider: str | None = raw.get("upscale_provider") or None
        if isinstance(upscale_provider, str):
            upscale_provider = upscale_provider.strip() or None
        upscale_model: str | None = raw.get("upscale_model") or None
        if isinstance(upscale_model, str):
            upscale_model = upscale_model.strip() or None
        params_json: dict[str, Any] = raw.get("params_json") or {}
        if not isinstance(params_json, dict):
            params_json = {}

        existing = existing_by_name.get(name)

        if existing:
            if conflict_strategy == "skip":
                result.records.append(RecordResult(name=name, outcome="skipped", reason="Name already exists."))
                continue
            elif conflict_strategy == "overwrite":
                if not dry_run:
                    try:
                        crud.update_profile(
                            session,
                            existing,
                            name=name,
                            provider=provider,
                            model=model,
                            model_config_id=model_config_id,
                            base_prompt=base_prompt,
                            negative_prompt=negative_prompt,
                            width=width,
                            height=height,
                            aspect_ratio=aspect_ratio,
                            n_images=n_images,
                            seed=seed,
                            output_format=output_format,
                            upscale_provider=upscale_provider,
                            upscale_model=upscale_model,
                            params_json=params_json,
                        )
                    except (ValueError, IntegrityError) as exc:
                        result.records.append(RecordResult(name=name, outcome="failed", reason=str(exc)))
                        continue
                result.records.append(RecordResult(name=name, outcome="updated"))
                continue
            else:  # rename
                name = _unique_name(name, set(existing_by_name.keys()), _MAX_PROFILE_NAME)

        if not dry_run:
            try:
                new_row = crud.create_profile(
                    session,
                    name=name,
                    provider=provider,
                    model=model,
                    model_config_id=model_config_id,
                    base_prompt=base_prompt,
                    negative_prompt=negative_prompt,
                    width=width,
                    height=height,
                    aspect_ratio=aspect_ratio,
                    n_images=n_images,
                    seed=seed,
                    output_format=output_format,
                    upscale_provider=upscale_provider,
                    upscale_model=upscale_model,
                    upscale_topaz_model_id=None,
                    params_json=params_json,
                    categories=[],
                    storage_template_id=storage_template.id,
                )
                existing_by_name[name] = new_row
            except (ValueError, IntegrityError) as exc:
                result.records.append(RecordResult(name=name, outcome="failed", reason=str(exc)))
                continue
        result.records.append(RecordResult(name=name, outcome="created"))
        existing_by_name[name] = object()  # placeholder so rename logic works in dry_run

    return result


def import_styles_zip(
    session: Session,
    zip_file_bytes: bytes,
    styles_dir: Path,
    conflict_strategy: str,
    *,
    dry_run: bool = False,
) -> ImportResult:
    """Import Style records and their thumbnails from a Zip archive.

    Parameters
    ----------
    session:
        Active SQLAlchemy session.
    zip_file_bytes:
        The bytes of the uploaded Zip archive.
    styles_dir:
        Local directory where style thumbnails are stored.
    conflict_strategy:
        One of ``"skip"``, ``"overwrite"``, or ``"rename"``.
    dry_run:
        When *True* no database or filesystem changes are committed.
    """
    try:
        buffer = io.BytesIO(zip_file_bytes)
        with zipfile.ZipFile(buffer, "r") as zip_file:
            # 1. Read metadata
            if "styles.json" not in zip_file.namelist():
                result = ImportResult(entity_type="styles")
                result.records.append(
                    RecordResult(name="?", outcome="failed", reason="Zip missing styles.json")
                )
                return result

            try:
                payload = loads(zip_file.read("styles.json").decode("utf-8"))
            except (JSONDecodeError, UnicodeDecodeError) as exc:
                result = ImportResult(entity_type="styles")
                result.records.append(
                    RecordResult(name="?", outcome="failed", reason=f"Invalid styles.json: {exc}")
                )
                return result

            error, _, _, _, styles_records = validate_import_payload(payload)
            if error:
                result = ImportResult(entity_type="styles")
                result.records.append(RecordResult(name="?", outcome="failed", reason=error))
                return result

            # 2. Import textual metadata
            import_result = import_styles(
                session, styles_records, conflict_strategy, dry_run=dry_run
            )

            if dry_run:
                return import_result

            # 3. Handle images for successfully imported records
            for raw, record in zip(styles_records, import_result.records):
                if record.outcome not in {"created", "updated"}:
                    continue

                # Find the original record data to see if it had an image
                if not isinstance(raw, dict):
                    continue

                image_filename = raw.get("image_filename")
                if not image_filename:
                    continue

                # Find the imported style in DB to get its new/existing ID
                # record.name contains the final name used (which might be different if renamed)
                style = crud.get_style_by_name(session, record.name)
                if not style:
                    continue

                zip_image_path = f"images/{image_filename}"
                if zip_image_path in zip_file.namelist():
                    image_data = zip_file.read(zip_image_path)
                    target_path = (styles_dir / f"{style.id}").with_suffix(".webp")
                    styles_dir.mkdir(parents=True, exist_ok=True)
                    target_path.write_bytes(image_data)

                    # Update image_path flag in DB if not already set
                    if not style.image_path:
                        crud.update_style(session, style, image_path=target_path.as_posix())

            return import_result

    except zipfile.BadZipFile:
        result = ImportResult(entity_type="styles")
        result.records.append(RecordResult(name="?", outcome="failed", reason="Invalid Zip file"))
        return result
    except Exception as exc:
        result = ImportResult(entity_type="styles")
        result.records.append(RecordResult(name="?", outcome="failed", reason=f"Import error: {exc}"))
        return result
