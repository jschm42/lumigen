"""Style service for managing style presets and defaults.

This module provides predefined default styles, automatic seeding on startup,
and functions for restoring and synchronizing default style presets.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.db import crud

logger = logging.getLogger(__name__)

DEFAULT_STYLES: list[dict[str, str]] = [
    {
        "name": "Photorealistic",
        "description": "Crisp, lifelike photography with natural lighting and fine detail.",
        "prompt": "hyperrealistic photograph, 35mm lens, sharp focus, natural soft lighting, detailed texture, 8k resolution, master photography",
    },
    {
        "name": "Cinematic",
        "description": "Dramatic movie look with intense lighting atmosphere and depth of field.",
        "prompt": "cinematic still, 35mm film, anamorphic lens, dramatic lighting, depth of field, blockbuster movie aesthetic, color graded, highly detailed",
    },
    {
        "name": "Anime / Manga",
        "description": "Classic Japanese anime and manga art style with vivid colors.",
        "prompt": "anime aesthetic, detailed linework, vibrant rich colors, makoto shinkai style, studio ghibli inspired, high quality 2D art",
    },
    {
        "name": "Digital Art",
        "description": "Modern digital concept art style with dynamic composition.",
        "prompt": "digital concept art, trending on artstation, smooth gradients, sharp details, fantasy art, masterpiece, vibrant composition",
    },
    {
        "name": "Oil Painting",
        "description": "Traditional painting on canvas with visible brushstrokes and rich pigments.",
        "prompt": "oil on canvas painting, visible textured brushstrokes, classical composition, rich pigments, fine art masterpiece, impasto technique",
    },
    {
        "name": "Watercolor",
        "description": "Delicate watercolours with soft washes and visible paper texture.",
        "prompt": "watercolor painting, wet-on-wet technique, soft pastel washes, paper texture, elegant artistic splatters, fluid brushwork",
    },
    {
        "name": "Cyberpunk",
        "description": "Futuristic neon lighting and moody high-tech dystopian atmosphere.",
        "prompt": "cyberpunk aesthetic, neon lights, dark moody atmosphere, futuristic cityscape, volumetric fog, reflection, high tech gritty detail",
    },
    {
        "name": "Vintage / Retro",
        "description": "Nostalgic 70s/80s photo look with authentic film grain and warm tones.",
        "prompt": "vintage 1970s photograph, authentic film grain, warm nostalgic tones, kodachrome style, muted retro colors, analog camera",
    },
    {
        "name": "Minimalist",
        "description": "Clean lines, ample negative space, and modern understated aesthetics.",
        "prompt": "minimalist composition, clean lines, negative space, simple elegant shapes, modern flat aesthetic, balanced design",
    },
    {
        "name": "Dark Fantasy",
        "description": "Dark mystical fantasy atmosphere with gothic accents.",
        "prompt": "dark fantasy aesthetic, gothic atmosphere, ominous lighting, intricate dark details, epic scale, moody concept art, ethereal",
    },
    {
        "name": "3D Render",
        "description": "Clean 3D render with soft studio lighting and Octane render look.",
        "prompt": "3d render, octane render, smooth surfaces, subsurface scattering, studio lighting, blender 3d, clean materials, ultra-detailed",
    },
    {
        "name": "Pop Art",
        "description": "Colorful retro comic style with bold outlines and halftone screen print.",
        "prompt": "pop art style, andy warhol and roy lichtenstein inspired, bold outlines, vibrant saturated colors, halftone dots, screen print texture",
    },
]


def ensure_default_styles(session: Session) -> int:
    """Ensure standard default styles are populated in the database.

    If the styles table is completely empty or missing any of the default
    presets, missing presets are inserted without modifying existing records.

    Parameters
    ----------
    session:
        Active SQLAlchemy database session.

    Returns
    -------
    int:
        The number of newly created styles.
    """
    existing_styles = crud.list_styles(session)
    existing_names = {s.name.lower(): s for s in existing_styles}

    created_count = 0
    for preset in DEFAULT_STYLES:
        if preset["name"].lower() not in existing_names:
            try:
                crud.create_style(
                    session,
                    name=preset["name"],
                    description=preset["description"],
                    prompt=preset["prompt"],
                    image_path=None,
                )
                created_count += 1
            except Exception as exc:
                logger.warning(
                    "Failed to create default style '%s': %s", preset["name"], exc
                )

    if created_count > 0:
        logger.info("Seeded %d default styles into database.", created_count)

    return created_count


def restore_default_styles(
    session: Session, *, overwrite: bool = True
) -> dict[str, Any]:
    """Restore or update default styles to their canonical definitions.

    Parameters
    ----------
    session:
        Active SQLAlchemy database session.
    overwrite:
        Whether to overwrite existing styles that match canonical default names.

    Returns
    -------
    dict[str, Any]:
        Summary with counts for created, updated, and total styles.
    """
    existing_styles = crud.list_styles(session)
    existing_by_name = {s.name.lower(): s for s in existing_styles}

    created_count = 0
    updated_count = 0

    for preset in DEFAULT_STYLES:
        key = preset["name"].lower()
        if key in existing_by_name:
            if overwrite:
                style_obj = existing_by_name[key]
                crud.update_style(
                    session,
                    style_obj,
                    name=preset["name"],
                    description=preset["description"],
                    prompt=preset["prompt"],
                )
                updated_count += 1
        else:
            crud.create_style(
                session,
                name=preset["name"],
                description=preset["description"],
                prompt=preset["prompt"],
                image_path=None,
            )
            created_count += 1

    return {
        "created": created_count,
        "updated": updated_count,
        "total": len(DEFAULT_STYLES),
    }
