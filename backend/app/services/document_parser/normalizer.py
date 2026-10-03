import re
import unicodedata

def normalize_text(text: str) -> str:
    """
    Conservatively normalizes raw extracted text for downstream NLP tasks
    without destroying source fidelity, paraphrasing, or altering content.

    Handles:
    - Unicode normalization (NFKC)
    - Line ending normalization (\\r\\n, \\r -> \\n)
    - Non-breaking spaces and invisible characters
    - Conservative de-hyphenation across line breaks (e.g. 'implemen-\\ntation' -> 'implementation')
    - Collapsing excessive horizontal whitespace while preserving line structure
    - Limiting excessive consecutive blank lines
    """
    if not text:
        return ""

    # 1. Unicode normalization (NFKC converts non-standard characters/ligatures to standard equivalents)
    normalized = unicodedata.normalize("NFKC", text)

    # 2. Replace non-breaking and invisible whitespace
    normalized = normalized.replace("\u00a0", " ")
    normalized = normalized.replace("\u200b", "")

    # 3. Standardize line endings to Unix style
    normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")

    # 4. Conservative de-hyphenation:
    # Match a lowercase/title word split across lines with a trailing hyphen
    # e.g., 'develop-\nment' -> 'development'
    # Preserves bullet points or hyphenated lists like '- Item'
    normalized = re.sub(r'(\b[A-Za-z]{2,})-\n([a-z]{2,}\b)', r'\1\2', normalized)

    # 5. Normalize whitespace within each line
    lines = normalized.split("\n")
    cleaned_lines = []
    for line in lines:
        # Collapse multiple horizontal tabs/spaces to a single space, strip margins
        cleaned_line = re.sub(r'[ \t]+', ' ', line).strip()
        cleaned_lines.append(cleaned_line)

    normalized = "\n".join(cleaned_lines)

    # 6. Normalize excessive blank lines (cap at 2 newlines = 1 blank line between paragraphs)
    normalized = re.sub(r'\n{3,}', '\n\n', normalized)

    return normalized.strip()
