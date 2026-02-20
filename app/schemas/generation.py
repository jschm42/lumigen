"""Pydantic schemas for generation-related requests and responses."""

from typing import Optional

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
    upscale_enable: bool = False
    upscale_model: str = ""
    input_images: list = []
    input_image_asset_id: str = ""


class GenerationResponse(BaseModel):
    """Response schema for a generation."""
    
    id: int
    status: str
    prompt: Optional[str] = None
    created_at: Optional[str] = None
    
    model_config = {"from_attributes": True}
