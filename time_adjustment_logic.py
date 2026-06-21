from datetime import timedelta


STANDARD_JAPAN_LONGITUDE = 135.0

PREFECTURE_LONGITUDES = {
    "北海道": 141.35,
    "青森県": 140.74,
    "岩手県": 141.15,
    "宮城県": 140.87,
    "秋田県": 140.10,
    "山形県": 140.36,
    "福島県": 140.47,
    "茨城県": 140.47,
    "栃木県": 139.88,
    "群馬県": 139.06,
    "埼玉県": 139.65,
    "千葉県": 140.12,
    "東京都": 139.69,
    "神奈川県": 139.64,
    "新潟県": 139.04,
    "富山県": 137.21,
    "石川県": 136.66,
    "福井県": 136.22,
    "山梨県": 138.57,
    "長野県": 138.18,
    "岐阜県": 136.72,
    "静岡県": 138.38,
    "愛知県": 136.91,
    "三重県": 136.51,
    "滋賀県": 135.87,
    "京都府": 135.77,
    "大阪府": 135.50,
    "兵庫県": 135.18,
    "奈良県": 135.83,
    "和歌山県": 135.17,
    "鳥取県": 134.24,
    "島根県": 133.05,
    "岡山県": 133.94,
    "広島県": 132.46,
    "山口県": 131.47,
    "徳島県": 134.56,
    "香川県": 134.04,
    "愛媛県": 132.77,
    "高知県": 133.53,
    "福岡県": 130.42,
    "佐賀県": 130.30,
    "長崎県": 129.87,
    "熊本県": 130.74,
    "大分県": 131.61,
    "宮崎県": 131.42,
    "鹿児島県": 130.56,
    "沖縄県": 127.68,
}

UNSELECTED_BIRTH_PLACES = {"", "未選択", "不明"}


def apply_time_adjustment(raw_birth_datetime, adjustment_minutes=0):
    """
    出生地補正用の土台。

    分単位の補正を受け取り、日付またぎも datetime の加減算に任せる。
    """
    if raw_birth_datetime is None:
        return None

    minutes = float(adjustment_minutes or 0)
    return raw_birth_datetime + timedelta(minutes=minutes)


def get_prefecture_longitude(prefecture):
    if prefecture is None:
        return None

    normalized_prefecture = str(prefecture).strip()
    if normalized_prefecture in UNSELECTED_BIRTH_PLACES:
        return None

    longitude = PREFECTURE_LONGITUDES.get(normalized_prefecture)
    if longitude is None:
        return None

    return float(longitude)


def calculate_longitude_adjustment_minutes(
    longitude,
    standard_longitude=STANDARD_JAPAN_LONGITUDE,
):
    if longitude is None:
        return 0.0

    return (float(longitude) - float(standard_longitude)) * 4


def build_time_adjustment_result(
    raw_birth_datetime,
    adjusted_birth_datetime,
    adjustment_minutes=0,
    longitude=None,
    enabled=False,
    reason="",
):
    return {
        "adjusted_birth_datetime": adjusted_birth_datetime,
        "time_adjustment_minutes": float(adjustment_minutes or 0),
        "longitude": longitude,
        "time_adjustment_enabled": bool(enabled),
        "time_adjustment_reason": reason,
    }


def apply_birthplace_time_adjustment(raw_birth_datetime, birth_place):
    if raw_birth_datetime is None:
        return build_time_adjustment_result(
            raw_birth_datetime,
            None,
            reason="birth_time_unknown",
        )

    longitude = get_prefecture_longitude(birth_place)
    if longitude is None:
        return build_time_adjustment_result(
            raw_birth_datetime,
            raw_birth_datetime,
            reason="birthplace_not_selected",
        )

    adjustment_minutes = calculate_longitude_adjustment_minutes(longitude)
    adjusted_birth_datetime = apply_time_adjustment(
        raw_birth_datetime,
        adjustment_minutes,
    )
    return build_time_adjustment_result(
        raw_birth_datetime,
        adjusted_birth_datetime,
        adjustment_minutes=adjustment_minutes,
        longitude=longitude,
        enabled=True,
        reason="birthplace_longitude",
    )
