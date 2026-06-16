from app.core.security import Principal


class PermissionService:
    def payload_is_accessible(self, payload: dict, principal: Principal) -> bool:
        if payload.get("tenant_id") != principal.tenant_id:
            return False
        if payload.get("is_public") is True:
            return True

        allowed_user_ids = set(payload.get("allowed_user_ids") or [])
        if principal.user_id in allowed_user_ids:
            return True

        allowed_group_ids = set(payload.get("allowed_group_ids") or [])
        return bool(allowed_group_ids.intersection(principal.group_ids))
