"""History application service: no calls to the fortune calculation service."""
from datetime import date, datetime, timedelta, timezone
import os
from pathlib import Path
from history_repository import HistoryError, SQLiteHistoryRepository
from history_versions import APP_VERSION, CALCULATION_LOGIC_VERSION, DATA_SCHEMA_VERSION

VERSIONS = (APP_VERSION, CALCULATION_LOGIC_VERSION, DATA_SCHEMA_VERSION)


def development_owner():
    # Explicit opt-in only. Never enable a shared fallback user in production.
    owner = os.environ.get("FORTUNE_HISTORY_DEV_USER_ID", "").strip()
    if os.environ.get("FORTUNE_ENV") != "development" or not owner:
        raise HistoryError("履歴機能は認証設定前のため無効です。ローカル開発設定を確認してください。", 503)
    return owner


def make_service():
    path = os.environ.get("FORTUNE_HISTORY_DB_PATH") or str(Path(__file__).parent / "data" / "history.sqlite3")
    return HistoryService(SQLiteHistoryRepository(path))


def validate_input(snapshot):
    if not isinstance(snapshot, dict) or not isinstance(snapshot.get("form"), dict):
        raise HistoryError("入力スナップショットが不正です。")
    form = snapshot["form"]
    for key in ("surname", "givenName", "surnameKana", "givenNameKana", "birthDate", "readingDate"):
        if not isinstance(form.get(key, ""), str) or len(form.get(key, "")) > 200:
            raise HistoryError("入力値が不正です。")
    try:
        date.fromisoformat(form["birthDate"])
        date.fromisoformat(form["readingDate"])
    except (KeyError, ValueError):
        raise HistoryError("生年月日・鑑定日が不正です。")
    choices = snapshot.get("manualChoices", {})
    selections = snapshot.get("boundarySelections", {})
    if not isinstance(choices, dict) or not isinstance(selections, dict):
        raise HistoryError("手動補正の形式が不正です。")
    for kind, choice in choices.items():
        if kind not in ("birth", "reading") or choice not in ("before", "after"):
            raise HistoryError("手動補正の判定が不正です。")
    for kind, selection in selections.items():
        if kind not in ("birth", "reading") or not isinstance(selection, dict):
            raise HistoryError("手動補正の指定が不正です。")
        if selection.get("choice") not in ("before", "after"):
            raise HistoryError("手動補正の判定が不正です。")
        try:
            datetime.fromisoformat(selection["boundary_datetime"])
        except (KeyError, ValueError, TypeError):
            raise HistoryError("手動補正の境界日時が不正です。")
        if kind in choices and selection["choice"] != choices[kind]:
            raise HistoryError("手動補正の記録が一致しません。")
    return form


class HistoryService:
    """Replace the repository adapter here when Phase 7 selects cloud storage."""

    def __init__(self, repository):
        self.repository = repository

    def create(self, owner, payload, organization_id=None):
        if not owner or not isinstance(payload, dict):
            raise HistoryError("履歴の指定が不正です。")
        form = validate_input(payload.get("input_snapshot"))
        result = payload.get("result_snapshot")
        if not isinstance(result, dict) or result.get("ok") is not True or "meishiki" not in result:
            raise HistoryError("正式な鑑定結果が必要です。")
        if not isinstance(payload.get("memo", ""), str) or len(payload.get("memo", "")) > 100000:
            raise HistoryError("メモが長すぎるか、形式が不正です。")
        link = payload.get("link") or {"mode": "new_person"}
        if not isinstance(link, dict) or link.get("mode") not in ("new_person", "new_group", "existing_group"):
            raise HistoryError("人物・グループの指定が不正です。")
        if link["mode"] != "new_person" and not link.get("person_id"):
            raise HistoryError("鑑定対象者の選択が必要です。")
        # A race with another save requires confirmation; no automatic merge.
        if "link" not in payload and self.repository.candidates(owner, form):
            raise HistoryError("過去に鑑定履歴がありますが、同一人物ですか？", 409)
        return self.repository.create(owner, payload, VERSIONS, organization_id=organization_id)

    def prepare(self, owner, reading_id, mode):
        if mode not in ("existing_group", "new_group"):
            raise HistoryError("再鑑定方法を選択してください。")
        reading = self.repository.detail(owner, reading_id)
        snapshot = self.repository.current_person(owner, reading["person_id"])
        form = snapshot["form"].copy()
        form["readingDate"] = datetime.now(timezone(timedelta(hours=9))).date().isoformat()
        form["consultation"] = ""
        form["specificDatetimeEnabled"] = False
        # Only the resolved birth decision belongs to this person.
        birth_selection = snapshot.get("boundarySelections", {}).get("birth")
        choices = snapshot.get("manualChoices", {})
        return {
            "form": form, "manualChoices": {"birth": choices["birth"]} if "birth" in choices else {},
            "boundarySelections": {"birth": birth_selection} if birth_selection else {},
            "link": {"mode": mode, "person_id": reading["person_id"], "source_reading_id": reading_id,
                     **({"group_id": reading["group_id"]} if mode == "existing_group" else {})},
            "pastMemos": self.repository.memos(owner, reading["group_id"]) if mode == "existing_group" else [],
        }

    def detail(self, owner, reading_id):
        reading = self.repository.detail(owner, reading_id)
        return {**reading, "past_memos": self.repository.memos(owner, reading["group_id"], reading_id)}
