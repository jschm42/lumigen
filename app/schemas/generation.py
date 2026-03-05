"""Pydantic schemas for generation-related requests and responses."""


from pydantic import BaseModel, Field


class GenerationCreateRequest(BaseModel):
    """Request schema for creating a new generation."""

    prompt_user: str = Field(..., min_length=1, max_length=10000)
    profile_id: int = Field(..., gt=0)
    conversation: str = ""
    width: str = ""
    height: str = ""
    n_images: str = ""
    seed: str = ""
    # OpenRouter-specific overrides
    aspect_ratio: str = ""
    image_size: str = ""
    upscale_enable: bool = False
    upscale_model: str = ""
    input_images: list = []
    input_image_asset_id: str = ""


class GenerationResponse(BaseModel):
    """Response schema for a generation."""

    id: int
    status: str
    prompt: str | None = None
    created_at: str | None = None

    model_config = {"from_attributes": True}
