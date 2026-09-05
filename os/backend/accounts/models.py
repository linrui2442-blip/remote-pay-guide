from pydantic import BaseModel


class Account(BaseModel):
    id: int | None = None
    platform: str
    account_name: str
    status: str = "inactive"
