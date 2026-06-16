from pydantic import BaseModel, EmailStr, Field


class PrincipalRead(BaseModel):
    tenant_id: str
    user_id: str
    email: str | None
    display_name: str | None
    group_ids: list[str]


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    display_name: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    email: str | None
    display_name: str | None
