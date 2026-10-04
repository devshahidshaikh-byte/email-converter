from itertools import product

from app.config import MAX_CUSTOM_PATTERNS, MAX_RESULTS
from app.pattern_engine import PATTERNS, generate_candidates
from app.services.validation_service import validate_pattern

def dedupe_results(results):
    seen = set()
    output = []
    for item in results:
        email = item["email"]
        if email not in seen:
            seen.add(email)
            output.append(item)
    return output

def generate_email_permutations(
    first_name,
    last_name,
    domains,
    selected_patterns=None,
    custom_patterns=None,
    prefixes=None,
    suffixes=None,
    numbers=None,
    case_mode="lowercase",
    include_base=True,
):
    patterns = selected_patterns or PATTERNS
    custom_patterns = custom_patterns or []

    if len(custom_patterns) > MAX_CUSTOM_PATTERNS:
        custom_patterns = custom_patterns[:MAX_CUSTOM_PATTERNS]

    valid_custom = []
    for pattern in custom_patterns:
        if not validate_pattern(pattern):
            valid_custom.append(pattern.strip())

    all_patterns = list(dict.fromkeys(list(patterns) + valid_custom))

    prefixes = prefixes or [""]
    suffixes = suffixes or [""]
    numbers = numbers or [""]

    # Prevent an accidental combinatorial explosion.
    combinations = len(domains) * len(all_patterns) * len(prefixes) * len(suffixes) * len(numbers)
    if combinations > MAX_RESULTS * 2:
        raise ValueError(
            f"Configuration could create too many candidates. "
            f"Reduce patterns, prefixes, suffixes, or numbers (limit {MAX_RESULTS})."
        )

    results = []
    for domain in domains:
        base = generate_candidates(first_name, last_name, domain, all_patterns)
        for item in base:
            if not include_base:
                pass
            for prefix, suffix, number in product(prefixes, suffixes, numbers):
                username, domain_part = item["email"].split("@", 1)
                modified = f"{prefix}{username}{number}{suffix}@{domain_part}"
                if case_mode == "uppercase":
                    modified = modified.upper()
                elif case_mode == "original":
                    pass
                else:
                    modified = modified.lower()
                results.append({
                    "email": modified,
                    "pattern": item["pattern"],
                    "label": item["label"],
                    "domain": domain_part,
                })
                if len(results) >= MAX_RESULTS:
                    return dedupe_results(results)

    return dedupe_results(results)

def estimate_count(
    domains_count,
    patterns_count,
    prefixes_count=1,
    suffixes_count=1,
    numbers_count=1,
):
    return domains_count * patterns_count * prefixes_count * suffixes_count * numbers_count
