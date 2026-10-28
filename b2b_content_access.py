"""Current-use authorization for the teacher process. Past-view policy is unchanged."""
import os
from history_repository import HistoryError


def teacher_surface():
    return os.environ.get('FORTUNE_DEPLOYMENT_SURFACE','combined') == 'teacher'


def require_organization(db, owner, organization_id):
    if not isinstance(organization_id,str) or not organization_id or len(organization_id)>200:
        raise HistoryError('利用する教室を指定してください。',422)
    from operations_repository import OperationsRepository
    OperationsRepository.member_access(db,organization_id,owner)
    return organization_id


def require_reading(db, owner, reading_id):
    # Include deleted rows for restore, but never accept an ID owned by someone else.
    row=db.execute('''SELECT r.id,s.organization_id FROM readings r
        LEFT JOIN reading_organization_scopes s ON s.reading_id=r.id AND s.owner_user_id=r.owner_user_id
        WHERE r.owner_user_id=? AND r.id=?''',(owner,reading_id)).fetchone()
    if not row:raise HistoryError('鑑定履歴が見つかりません。',404)
    if not row['organization_id']:raise HistoryError('この鑑定は先生版で変更・出力できません。',403)
    return require_organization(db,owner,row['organization_id'])


def require_person_scope(db, owner, person_id, organization_id=None):
    rows=db.execute('''SELECT s.organization_id FROM readings r
        LEFT JOIN reading_organization_scopes s ON s.reading_id=r.id AND s.owner_user_id=r.owner_user_id
        WHERE r.owner_user_id=? AND r.person_id=?''',(owner,person_id)).fetchall()
    scopes={row[0] for row in rows}
    # A mutable current-person record must not bridge classes or unscoped B2C rows.
    if not rows or len(scopes)!=1 or None in scopes or (organization_id and scopes!={organization_id}):
        raise HistoryError('この教室の鑑定対象者を指定してください。',404)
    return require_organization(db,owner,next(iter(scopes)))


def export_authorizer(owner, repository):
    if not teacher_surface():return None
    def authorize(organization_id):
        if not organization_id:raise HistoryError('この鑑定は先生版で出力できません。',403)
        with repository.connection() as db:require_organization(db,owner,organization_id)
    return authorize
