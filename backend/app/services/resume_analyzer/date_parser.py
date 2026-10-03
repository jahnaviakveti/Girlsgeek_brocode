import re
from typing import Optional, Tuple
from datetime import datetime

MONTH_MAP = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "september": 9, "sept": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}

CURRENT_MARKERS = {"present", "current", "ongoing", "now"}

# Pattern for range: [Date1] (- / to / – / —) [Date2 / Present]
DATE_RANGE_PATTERN = re.compile(
    r'(?P<start>(?:[A-Za-z]{3,9}\.?\s+)?(?:\d{1,2}[/.-])?\d{4})'
    r'\s*(?:-|–|—|to|until)\s*'
    r'(?P<end>(?:[A-Za-z]{3,9}\.?\s+)?(?:\d{1,2}[/.-])?\d{4}|present|current|ongoing|now)',
    re.IGNORECASE
)

# Pattern for single date
SINGLE_DATE_PATTERN = re.compile(
    r'\b(?:expected|graduating|graduation|issued|completed)?\s*'
    r'(?P<date>(?:[A-Za-z]{3,9}\.?\s+)?(?:\d{1,2}[/.-])?\d{4})\b',
    re.IGNORECASE
)

def parse_month_year(date_str: str) -> Tuple[Optional[int], Optional[int]]:
    """
    Parses a single date component into (month, year).
    Supports 'Jan 2023', 'January 2023', '01/2023', '2023', etc.
    """
    cleaned = date_str.strip().strip(".,;:()").lower()
    if not cleaned:
        return None, None

    # Check for 4-digit year
    year_match = re.search(r'\b(19\d\d|20\d\d)\b', cleaned)
    if not year_match:
        return None, None
    year = int(year_match.group(1))

    # Check for month name
    for m_name, m_num in MONTH_MAP.items():
        if re.search(r'\b' + re.escape(m_name) + r'\b', cleaned):
            return m_num, year

    # Check for numeric month: e.g. 01/2023, 1-2023
    num_match = re.search(r'\b(0?[1-9]|1[0-2])[/.-](?:19|20)?\d\d\b', cleaned)
    if num_match:
        return int(num_match.group(1)), year

    # Year only
    return None, year

def normalize_date_component(month: Optional[int], year: Optional[int]) -> str:
    """Formats month and year to 'Mon YYYY' or 'YYYY'."""
    if not year:
        return ""
    if month and 1 <= month <= 12:
        month_abbr = [
            "Jan", "Feb", "Mar", "Apr", "May", "Jun",
            "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"
        ][month - 1]
        return f"{month_abbr} {year}"
    return str(year)

def parse_date_range(text: str) -> Tuple[Optional[str], Optional[str], bool, Optional[float]]:
    """
    Extracts and normalizes a date range from text.
    Returns (normalized_start, normalized_end, is_current, duration_months).
    """
    range_match = DATE_RANGE_PATTERN.search(text)
    if range_match:
        raw_start = range_match.group("start").strip()
        raw_end = range_match.group("end").strip().lower()

        is_current = raw_end in CURRENT_MARKERS

        s_month, s_year = parse_month_year(raw_start)
        norm_start = normalize_date_component(s_month, s_year) if s_year else raw_start

        if is_current:
            norm_end = "Present"
            # Calculate duration relative to current time (default 2026/09 or system time)
            now = datetime.now()
            e_month, e_year = now.month, now.year
        else:
            e_month, e_year = parse_month_year(raw_end)
            norm_end = normalize_date_component(e_month, e_year) if e_year else raw_end

        # Calculate duration in months if years are available
        duration_months: Optional[float] = None
        if s_year and e_year:
            m_start = s_month or 1
            m_end = e_month or 12
            months = (e_year - s_year) * 12 + (m_end - m_start)
            if months >= 0:
                duration_months = float(months)

        return norm_start, norm_end, is_current, duration_months

    # Check for single date
    single_match = SINGLE_DATE_PATTERN.search(text)
    if single_match:
        raw_date = single_match.group("date").strip()
        m, y = parse_month_year(raw_date)
        norm_date = normalize_date_component(m, y) if y else raw_date
        return norm_date, None, False, None

    return None, None, False, None
