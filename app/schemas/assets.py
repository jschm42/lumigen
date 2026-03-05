"""Pydantic schemas for asset-related requests."""


from pydantic import BaseModel, Field


class BulkCategoryRequest(BaseModel):
    """Request schema for bulk category assignment."""

    asset_ids: list[int] = Field(..., min_length=1)
    category_ids: list[int] = Field(..., min_length=1)
    return_to: str = "/gallery"


class BulkDeleteRequest(BaseModel):
    """Request schema for bulk asset deletion."""

    asset_ids: list[int] = Field(..., min_length=1)
    return_to: str = "/gallery"


class AssetDetailResponse(BaseModel):
    """Response schema for asset details."""

    id: int
    file_path: str
    mime: str
    width: int | None = None
    height: int | None = None

    model_config = {"from_attributes": True}
