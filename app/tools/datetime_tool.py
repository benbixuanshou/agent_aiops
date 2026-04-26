from datetime import datetime, timezone, timedelta
from langchain.tools import tool


@tool
def get_current_datetime() -> str:
    """Get the current date and time in the user's timezone (Asia/Shanghai)"""
    tz = timezone(timedelta(hours=8))
    now = datetime.now(tz)
    return now.isoformat()
