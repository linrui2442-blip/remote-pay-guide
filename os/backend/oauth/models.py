from pydantic import BaseModel
from typing import Optional


class OAuthToken(BaseModel):
    id: Optional[int] = None
    account_id: int
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    expires_at: Optional[str] = None
