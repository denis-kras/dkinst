import langcodes
from langcodes import Language, LanguageTagError
import locale

"""
Microsoft LCID (Locale ID) reference:
https://learn.microsoft.com/en-us/openspecs/office_standards/ms-oe376/6c085406-a698-4e12-9d4d-c3b0ee3dbc4a
"""

# Build reverse mapping. Example: 'en_US' (locale language tags) -> 1033 (LCID - Locale ID)
LOCALE_TO_LCID = {v.lower(): k for k, v in locale.windows_locale.items()}


def normalize_string_to_locale_name(
        text: str
) -> str:
    """
    Normalize a language string to a locale name like 'en_US'.
    Examples:
        'en' -> 'en_US'
        'eng' -> 'en_US'
        'english' -> 'en_US'
    """
    text = text.strip()
    if not text:
        raise ValueError("Empty language string")

    # 1) Interpret codes like 'en', 'eng', 'en_US', 'en-GB'
    try:
        lang = Language.get(text)
    except LanguageTagError:
        # 2) Fall back to language *names* like 'english'
        lang = langcodes.find(text)

    # Expand 'en' -> 'en-Latn-US'
    lang = lang.maximize().simplify_script()

    # Convert BCP-47 tag 'en-US' -> locale-style 'en_US'
    tag = lang.to_tag()       # e.g. 'en-US'
    parts = tag.split('-')
    if len(parts) == 1:
        return parts[0].lower()
    lang_part = parts[0].lower()
    country_part = parts[-1].upper()
    return f"{lang_part}_{country_part}"   # 'en_US'


def convert_string_to_lcid(text: str) -> int | None:
    """
    Convert a language string to a Microsoft LCID (Locale ID).
    Examples of input strings:
        'en' -> 1033
        'eng' -> 1033
        'english' -> 1033
        'en_US' -> 1033
        'en-GB' -> 2057
    """
    loc = normalize_string_to_locale_name(text)   # e.g. 'en_US'
    return LOCALE_TO_LCID.get(loc.lower())
