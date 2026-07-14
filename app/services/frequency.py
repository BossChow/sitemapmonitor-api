from datetime import datetime, timedelta

from app.models.site import CheckFrequency

FREQUENCY_DELTAS = {
    CheckFrequency.six_hours.value: timedelta(hours=6),
    CheckFrequency.twelve_hours.value: timedelta(hours=12),
    CheckFrequency.daily.value: timedelta(days=1),
    CheckFrequency.weekly.value: timedelta(weeks=1),
}


def calculate_next_check_at(now: datetime, frequency: str) -> datetime:
    return now + FREQUENCY_DELTAS.get(frequency, FREQUENCY_DELTAS[CheckFrequency.daily.value])

