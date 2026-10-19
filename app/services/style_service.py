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
    {
        "name": "Studio Portrait",
        "description": "High-end editorial studio photography with soft Rembrandt lighting and sharp focus.",
        "prompt": "professional studio portrait photograph, 85mm lens, f/1.4 aperture, rembrandt lighting, sharp facial details, seamless backdrop, Hasselblad photography, elegant magazine editorial",
    },
    {
        "name": "Steampunk",
        "description": "Victorian era aesthetic fused with brass gears, steam machinery, and copper details.",
        "prompt": "steampunk aesthetic, intricate brass gears, polished copper pipes, ornate victorian details, steam-powered machinery, sepia and bronze tones, detailed mechanical craftsmanship",
    },
    {
        "name": "Surrealism",
        "description": "Dreamlike, illogical scenes with floating elements and impossible geometry.",
        "prompt": "surrealist masterpiece, dreamlike impossible geometry, salvador dali and rene magritte inspired, enigmatic symbolism, ethereal lighting, uncanny and bizarre juxtapositions",
    },
    {
        "name": "Claymation",
        "description": "Stop-motion plasticine clay look with handcrafted textures and miniature studio lighting.",
        "prompt": "claymation stop-motion aesthetic, handcrafted plasticine clay textures, subtle fingerprint details, studio miniature lighting, aardman and laika animation style, tactile depth",
    },
    {
        "name": "Synthwave / Vaporwave",
        "description": "1980s retro-futurism with neon grids, glowing horizons, and chrome reflections.",
        "prompt": "vaporwave synthwave aesthetic, 1980s retro-futurism, glowing neon grid, magenta and cyan color palette, chrome reflections, outrun sunset, nostalgic glow",
    },
    {
        "name": "Pixel Art",
        "description": "Nostalgic 16-bit video game pixel art with crisp clusters and vibrant palettes.",
        "prompt": "detailed 16-bit pixel art, isometric retro video game graphics, crisp pixel clusters, carefully limited vibrant palette, nostalgic arcade aesthetic",
    },
    {
        "name": "Papercraft / Origami",
        "description": "Layered dimensional paper cutouts with delicate shadows and tactile paper texture.",
        "prompt": "layered papercraft art, intricate paper cutouts, dimensional cardstock layers, origami folds, delicate drop shadows, craft studio lighting, tactile paper texture",
    },
    {
        "name": "Isometric 3D",
        "description": "Charming miniature diorama with tilt-shift perspective and detailed stylized models.",
        "prompt": "isometric 3d diorama, miniature voxel world, tilt-shift depth of field, orthographic projection, cute stylized micro details, vibrant lighting, octane render",
    },
    {
        "name": "Gothic Noir",
        "description": "High-contrast black and white ink style with dramatic shadows and graphic novel grit.",
        "prompt": "gritty noir comic book style, high-contrast black and white, dramatic chiaroscuro shadows, stark ink hatching, graphic novel aesthetic, cinematic silhouettes, sin city inspired",
    },
    {
        "name": "Art Nouveau",
        "description": "Ornate organic curves, flowing floral motifs, and elegant decorative borders.",
        "prompt": "art nouveau illustration, alphonse mucha inspired, flowing sinuous lines, organic floral motifs, elegant decorative borders, pastel and gold foil accents, intricate stained glass aesthetic",
    },
    {
        "name": "Pencil & Charcoal",
        "description": "Hand-drawn graphite and charcoal sketch with visible cross-hatching and paper grain.",
        "prompt": "detailed graphite and charcoal drawing, traditional hand-drawn sketch, cross-hatching, fine smudged textures, textured drawing paper, expressive fine art study",
    },
    {
        "name": "Double Exposure",
        "description": "Poetic blend of silhouettes with natural landscapes, starfields, and cityscapes.",
        "prompt": "artistic double exposure photography, seamless blend of silhouette and natural landscape, ethereal exposure layering, poetic fine art photography, delicate transparency",
    },
    {
        "name": "Stained Glass",
        "description": "Luminous leaded glass window with jewel tones and radiant streaming sunlight.",
        "prompt": "luminous stained glass window, intricate black leaded seams, vibrant jewel-tone colored glass, radiant sunlight streaming through, medieval cathedral rose window aesthetic",
    },
    {
        "name": "Baroque Painting",
        "description": "Opulent classical European fine art with dramatic chiaroscuro and deep emotional intensity.",
        "prompt": "baroque fine art painting, caravaggio chiaroscuro, dramatic tenebrism, rich deep shadows, luminous golden highlights, classical oil on canvas, majestic emotional intensity",
    },
    {
        "name": "Ukiyo-e Woodblock",
        "description": "Traditional Japanese Edo-period woodblock print with flowing lines and mineral washes.",
        "prompt": "traditional ukiyo-e woodblock print, hokusai and hiroshige style, washi paper texture, bold ink outlines, flat mineral pigment washes, japanese traditional art",
    },
    {
        "name": "Glitch Art",
        "description": "Digital distortion with chromatic aberration, VHS scanlines, and RGB shifts.",
        "prompt": "glitch art aesthetic, chromatic aberration, digital artifacting, RGB channel shift, VHS CRT scanlines, datamosh distortion, futuristic cyber malfunction",
    },
    {
        "name": "Neon Tokyo",
        "description": "Rain-slicked night streets reflecting vibrant neon signs in a Blade Runner haze.",
        "prompt": "cyberpunk tokyo street at night, rain-slicked reflective asphalt, glowing neon signage, volumetric mist and neon glow, moody cinematic atmosphere, blade runner urban vibe",
    },
    {
        "name": "Low Poly",
        "description": "Geometric faceted 3D art with flat-shaded colorful polygon meshes and studio lighting.",
        "prompt": "low poly 3d art, stylized faceted geometry, flat-shaded colorful polygon meshes, ambient occlusion, clean minimalist isometric, indie game aesthetic",
    },
    {
        "name": "Fantasy Concept Art",
        "description": "Grand scale epic fantasy landscape with ancient overgrown ruins and mystical lighting.",
        "prompt": "epic fantasy concept art, sweeping mystical landscape, floating islands, ancient overgrown ruins, magical ambient glow, vast sense of scale, artstation featured",
    },
    {
        "name": "Risograph Print",
        "description": "Textured indie riso print with subtle misregistration, halftone dots, and soy inks.",
        "prompt": "risograph print, tactile rough paper grain, two-color overlay with subtle misregistration, vibrant fluorescent soy inks, halftone dot pattern, indie zine aesthetic",
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
