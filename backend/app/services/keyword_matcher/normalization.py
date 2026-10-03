import re
from typing import List, Set

# Punctuation to strip from token edges, leaving internal technical characters (+, #, ., -, /) intact
STRIP_PUNCT_PATTERN = re.compile(r'^[\s\(\)\[\]\{\}<>"\',;:!?•*~`]+|[\s\(\)\[\]\{\}<>"\',;:!?•*~`]+$')

def normalize_text(text: str) -> str:
    """
    Standardize text for lexical comparison:
    - lowercased
    - whitespace collapsed
    - surrounding punctuation trimmed
    """
    if not text:
        return ""
    lowered = text.lower()
    # Collapse multiple whitespace characters into a single space
    collapsed = re.sub(r'\s+', ' ', lowered).strip()
    return collapsed

def clean_token(token: str) -> str:
    """
    Clean token boundaries while preserving interior tech characters (e.g., 'C++', 'C#', '.NET', 'Node.js').
    """
    if not token:
        return ""
    cleaned = STRIP_PUNCT_PATTERN.sub('', token.strip().lower())
    return cleaned

def tokenize_words(text: str) -> List[str]:
    """
    Tokenizes text into individual words/tokens while preserving technical symbols.
    Splits on spaces, commas, semicolons, pipes, and slashes when appropriate.
    """
    if not text:
        return []
    # Split on whitespace and common delimiter punctuation
    raw_tokens = re.split(r'[\s,;|/]+', text)
    tokens = [clean_token(t) for t in raw_tokens if clean_token(t)]
    return tokens

def extract_candidate_phrases(text: str, max_words: int = 4) -> Set[str]:
    """
    Extracts 1-gram to max_words-gram phrases from text for multi-word skill matching.
    """
    words = tokenize_words(text)
    phrases: Set[str] = set()
    n = len(words)
    for length in range(1, min(max_words + 1, n + 1)):
        for i in range(n - length + 1):
            phrase = " ".join(words[i:i + length])
            if phrase:
                phrases.add(phrase)
    return phrases
