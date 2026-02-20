"""Pydantic schemas for session-related requests."""

from typing import Optional

from pydantic import BaseModel, Field


class SessionRenameRequest(BaseModel):
    """Request schema for renaming a chat session."""
    
    session_token: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1, max_length=200)
    active_conversation: str = ""
    workspace_view: str = "chat"


class SessionDeleteRequest(BaseModel):
    """Request schema for deleting a chat session."""
    
    session_token: str = Field(..., min_length=1)
    active_conversation: str = ""
    workspace_view: str = "chat"


class SessionPreferencesRequest(BaseModel):
    """Request schema for updating session preferences."""
    
    chat_session_id: str = Field(..., min_length=1)
    last_profile_id: Optional[int] = Field(None, gt=0)
    last_thumb_size: Optional[str] = Field(None, pattern="^(sm|md|lg)$")
