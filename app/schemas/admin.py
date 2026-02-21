"""Pydantic schemas for admin-related requests."""

from typing import Optional

from pydantic import BaseModel, Field


class DimensionPresetRequest(BaseModel):
    """Request schema for creating/updating a dimension preset."""
    
    name: str = Field(..., min_length=1, max_length=30)
    width: int = Field(..., gt=0, le=4096)
    height: int = Field(..., gt=0, le=4096)


class CategoryRequest(BaseModel):
    """Request schema for creating/updating a category."""
    
    name: str = Field(..., min_length=1, max_length=30)


class ModelConfigRequest(BaseModel):
    """Request schema for creating/updating a model config."""
    
    name: str = Field(..., min_length=1, max_length=50)
    provider: str = Field(..., min_length=1)
    model: str = Field(..., min_length=1)
    enhancement_prompt: str = ""
    api_key: str = ""
    use_custom_api_key: bool = False


class EnhancementConfigRequest(BaseModel):
    """Request schema for updating enhancement config."""
    
    provider: str = Field(..., min_length=1)
    model: str = Field(..., min_length=1)
    api_key: str = ""
    clear_api_key: bool = False
