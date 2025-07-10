import re

def normalize_phone(raw: str | None) -> str | None:
    """Приводит телефон к формату +7XXXXXXXXXX или возвращает None."""
    if not raw:
        return None

    digits = re.sub(r"\D", "", raw)

    if len(digits) == 11 and digits[0] == "8":
        digits = "7" + digits[1:]
    elif len(digits) == 10:
        digits = "7" + digits
    elif len(digits) == 11 and digits[0] == "7":
        pass
    else:
        return None

    return f"+{digits}"