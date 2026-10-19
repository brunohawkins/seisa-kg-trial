"""SUMMARY: The tidying rule for Companies House numbers (D-076, finding F30).

Companies House numbers in control (PSC) records are typed by hand, e.g.
"1899316" (leading zero missing), "Oc301825" (lower case), " 03220373 "
(spaces). This rule turns such a number into the register's own form, or
says it can't.

The as-given value is always kept as well; this tidy form is only used to
draw a link, which is labelled as made by this rule.
"""

# Pattern matching, used to recognise a valid Companies House number.
import re

# A tidy Companies House number: 8 digits, or 2 capital letters then 6 digits (e.g. OC301825, SL032338).
VALID = re.compile(r"^(\d{8}|[A-Z]{2}\d{6})$")
# The words that show a controller is registered in the UK (in "country_registered" or "place_registered").
UK_WORDS = ("england", "wales", "scotland", "northern ireland", "united kingdom", "companies house", "uk")


# Tidy a hand-typed Companies House number; return None if it can't be made valid.
def tidy_company_number(raw: str | None) -> str | None:
    # Nothing given: nothing to tidy.
    if not raw:
        # Signal "can't be tidied".
        return None
    # Remove spaces and make letters upper case, e.g. " Oc301825" -> "OC301825".
    s = re.sub(r"\s+", "", raw).upper()
    # Digits only but too short: add the missing leading zeros, e.g. "1899316" -> "01899316".
    if s.isdigit() and len(s) < 8:
        # Pad on the left with zeros up to 8 characters.
        s = s.zfill(8)
    # Two letters then too few digits: pad the digits, e.g. "SC57176" -> "SC057176".
    m = re.match(r"^([A-Z]{2})(\d{1,5})$", s)
    # If that pattern matched, pad its digits to 6.
    if m:
        # Letters, then the digits padded to 6.
        s = m.group(1) + m.group(2).zfill(6)
    # Only hand back numbers that now look like a real Companies House number.
    return s if VALID.match(s) else None


# Does a controller's identification say it is registered in the UK?
def is_uk_registered(identification: dict | None) -> bool:
    # No identification: we can't tell, so treat it as not UK.
    if not identification:
        # Not UK.
        return False
    # The country and place registered, joined and in lower case.
    text = f"{identification.get('country_registered', '')} {identification.get('place_registered', '')}".lower()
    # UK if any of the UK words appears.
    return any(w in text for w in UK_WORDS)
