from datetime import datetime, timedelta


def compute_followup_date(sent_at: datetime) -> datetime:
    """
    Returns the follow-up date based on when the initial message was sent:
      Mon-Thu → same weekday +7 days
      Fri     → following Monday (+3 days)
      Sat     → following Monday (+2 days)
      Sun     → following Monday (+1 day)
    """
    weekday = sent_at.weekday()  # 0=Mon, 4=Fri, 5=Sat, 6=Sun

    if weekday <= 3:  # Mon–Thu
        return sent_at + timedelta(days=7)
    elif weekday == 4:  # Fri
        return sent_at + timedelta(days=3)
    elif weekday == 5:  # Sat
        return sent_at + timedelta(days=2)
    else:  # Sun
        return sent_at + timedelta(days=1)
