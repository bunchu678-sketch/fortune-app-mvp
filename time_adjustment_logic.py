from datetime import timedelta


def apply_time_adjustment(raw_birth_datetime, adjustment_minutes=0):
    """
    出生地補正用の土台。

    現時点では画面から補正を有効化しないが、分単位の補正を受け取り、
    日付またぎも datetime の加減算に任せて処理できるようにしておく。
    """
    if raw_birth_datetime is None:
        return None

    minutes = int(adjustment_minutes or 0)
    return raw_birth_datetime + timedelta(minutes=minutes)
