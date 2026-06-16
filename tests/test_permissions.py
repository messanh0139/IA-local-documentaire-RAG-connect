from app.core.security import Principal
from app.services.permissions import PermissionService


def test_payload_accessible_by_group() -> None:
    principal = Principal(
        tenant_id="deep-bleue-ia",
        user_id="alice",
        email="alice@example.com",
        group_ids=("finance",),
    )
    payload = {
        "tenant_id": "deep-bleue-ia",
        "is_public": False,
        "allowed_user_ids": [],
        "allowed_group_ids": ["finance"],
    }

    assert PermissionService().payload_is_accessible(payload, principal)


def test_payload_rejected_for_other_tenant() -> None:
    principal = Principal(
        tenant_id="deep-bleue-ia",
        user_id="alice",
        email="alice@example.com",
        group_ids=("finance",),
    )
    payload = {
        "tenant_id": "other-tenant",
        "is_public": True,
        "allowed_user_ids": ["alice"],
        "allowed_group_ids": ["finance"],
    }

    assert not PermissionService().payload_is_accessible(payload, principal)
