def format_playtime_duration(minutes: int) -> str:
    if minutes < 60:
        return f"{minutes}分钟"

    days, remainder = divmod(minutes, 24 * 60)
    hours, minute = divmod(remainder, 60)
    parts = []
    if days:
        parts.append(f"{days}天")
    if hours:
        parts.append(f"{hours}小时")
    if minute:
        parts.append(f"{minute}分钟")
    return "".join(parts)
