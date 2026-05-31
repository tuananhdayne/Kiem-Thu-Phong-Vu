import re


def shorten_for_log(text, limit=80):
    """Shorten long values before writing them to logs."""
    value = str(text)
    if len(value) <= limit:
        return value
    return f"{value[:limit]}... (len={len(value)})"


def parse_price_to_int(price_text):
    """Extract an integer price from a formatted price string."""
    digits = re.sub(r"[^\d]", "", price_text)
    return int(digits) if digits else 0


def is_sorted(values, ascending=True):
    """Return whether a numeric sequence is sorted."""
    if not values:
        return True
    seq = list(values)
    expected = sorted(seq)
    if not ascending:
        expected = list(reversed(expected))
    return seq == expected

