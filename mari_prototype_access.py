"""Opt-in teacher-only restriction; never grants membership or changes a DB."""
import json
import os
from uuid import UUID
from auth_service import AuthError

PROFILE = 'two-person-prototype'


def require_prototype_reader(user_id):
    # Existing combined/admin and the accepted default behavior remain intact.
    if os.environ.get('FORTUNE_DEPLOYMENT_SURFACE') != 'teacher':
        return
    profile = os.environ.get('FORTUNE_READING_ACCESS_PROFILE', '')
    if not profile:
        return
    if profile != PROFILE:
        raise AuthError('利用設定を確認できません。', 503)
    try:
        ids = json.loads(os.environ.get('FORTUNE_READING_ALLOWED_USER_IDS', ''))
        if (not isinstance(ids, list) or len(ids) != 2
                or any(not isinstance(value, str) or str(UUID(value)) != value for value in ids)
                or len(set(ids)) != 2):
            raise ValueError()
    except (ValueError, TypeError, AttributeError):
        raise AuthError('利用設定を確認できません。', 503) from None
    if user_id not in ids:
        raise AuthError('このアプリの利用権限がありません。', 403)
