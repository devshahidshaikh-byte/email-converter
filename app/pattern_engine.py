"""
Email permutation engine.

This module generates username candidates from first/last names.
It intentionally generates address *patterns* only; it does not verify,
harvest, or send email.
"""

PATTERNS = [
    "{first}.{last}",
    "{first}{last}",
    "{first}_{last}",
    "{first}-{last}",
    "{first}",
    "{last}",
    "{f}{last}",
    "{f}.{last}",
    "{f}_{last}",
    "{f}-{last}",
    "{first}{l}",
    "{first}.{l}",
    "{first}_{l}",
    "{first}-{l}",
    "{last}.{first}",
    "{last}{first}",
    "{last}_{first}",
    "{last}-{first}",
    "{l}{first}",
    "{l}.{first}",
    "{l}_{first}",
    "{l}-{first}",
    "{last}{f}",
    "{last}.{f}",
    "{last}_{f}",
    "{last}-{f}",
    "{f}{l}",
    "{f}.{l}",
    "{f}_{l}",
    "{f}-{l}",
    "{l}{f}",
    "{l}.{f}",
    "{l}_{f}",
    "{l}-{f}",
    "{f}.{first}.{last}",
    "{f}_{first}_{last}",
    "{f}-{first}-{last}",
    "{first}.{last}.{l}",
    "{first}_{last}_{l}",
    "{first}-{last}-{l}",
    "{last}.{first}.{f}",
    "{last}_{first}_{f}",
    "{last}-{first}-{f}",
    "{f}.{last}.{first}",
    "{f}_{last}_{first}",
    "{f}-{last}-{first}",
    "{l}.{first}.{last}",
    "{l}_{first}_{last}",
    "{l}-{first}-{last}",
    "{first}.{l}.{last}",
]

PATTERN_LABELS = {
    "{first}.{last}": "First.Last",
    "{first}{last}": "FirstLast",
    "{first}_{last}": "First_Last",
    "{first}-{last}": "First-Last",
    "{first}": "First",
    "{last}": "Last",
    "{f}{last}": "FLast",
    "{f}.{last}": "F.Last",
    "{f}_{last}": "F_Last",
    "{f}-{last}": "F-Last",
    "{first}{l}": "FirstL",
    "{first}.{l}": "First.L",
    "{first}_{l}": "First_L",
    "{first}-{l}": "First-L",
    "{last}.{first}": "Last.First",
    "{last}{first}": "LastFirst",
    "{last}_{first}": "Last_First",
    "{last}-{first}": "Last-First",
    "{l}{first}": "LFirst",
    "{l}.{first}": "L.First",
    "{l}_{first}": "L_First",
    "{l}-{first}": "L-First",
    "{last}{f}": "LastF",
    "{last}.{f}": "Last.F",
    "{last}_{f}": "Last_F",
    "{last}-{f}": "Last-F",
    "{f}{l}": "FL",
    "{f}.{l}": "F.L",
    "{f}_{l}": "F_L",
    "{f}-{l}": "F-L",
    "{l}{f}": "LF",
    "{l}.{f}": "L.F",
    "{l}_{f}": "L_F",
    "{l}-{f}": "L-F",
    "{f}.{first}.{last}": "F.First.Last",
    "{f}_{first}_{last}": "F_First_Last",
    "{f}-{first}-{last}": "F-First-Last",
    "{first}.{last}.{l}": "First.Last.L",
    "{first}_{last}_{l}": "First_Last_L",
    "{first}-{last}-{l}": "First-Last-L",
    "{last}.{first}.{f}": "Last.First.F",
    "{last}_{first}_{f}": "Last_First_F",
    "{last}-{first}-{f}": "Last-First-F",
    "{f}.{last}.{first}": "F.Last.First",
    "{f}_{last}_{first}": "F_Last_First",
    "{f}-{last}-{first}": "F-Last-First",
    "{l}.{first}.{last}": "L.First.Last",
    "{l}_{first}_{last}": "L_First_Last",
    "{l}-{first}-{last}": "L-First-Last",
    "{first}.{l}.{last}": "First.L.Last",
}

def clean_name(name: str) -> str:
    if not name:
        return ""
    return " ".join(str(name).strip().lower().split())

def normalize_domain(domain: str) -> str:
    return str(domain or "").strip().lower().removeprefix("@")

def _variables(first_name: str, last_name: str):
    first = clean_name(first_name).replace(" ", "")
    last = clean_name(last_name).replace(" ", "")
    return first, last, {
        "first": first,
        "last": last,
        "f": first[0] if first else "",
        "l": last[0] if last else "",
    }

def generate_candidates(first_name, last_name, domain, patterns=None):
    first, last, variables = _variables(first_name, last_name)
    domain = normalize_domain(domain)
    if not first or not last or not domain:
        return []

    patterns = patterns or PATTERNS
    candidates = []
    seen = set()

    for pattern in patterns:
        try:
            username = pattern.format(**variables)
        except (KeyError, ValueError):
            continue
        email = f"{username}@{domain}"
        if username and email not in seen:
            seen.add(email)
            candidates.append({
                "email": email,
                "pattern": pattern,
                "label": PATTERN_LABELS.get(pattern, pattern),
            })
    return candidates

def generate_custom_pattern(first_name, last_name, domain, pattern):
    return generate_candidates(first_name, last_name, domain, [pattern])
