import re
from app.config import MAX_NAME_LENGTH, MAX_DOMAIN_LENGTH, MAX_CUSTOM_PATTERNS

DOMAIN_RE = re.compile(
    r"^(?=.{1,253}$)(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,63}$"
)

ALLOWED_TOKENS = {"first", "last", "f", "l"}

def validate_name(name):
    value = str(name or "").strip()
    if not value:
        return "This field is required."
    if len(value) > MAX_NAME_LENGTH:
        return f"Maximum {MAX_NAME_LENGTH} characters."
    return None

def validate_domain(domain):
    value = str(domain or "").strip().lower().removeprefix("@")
    if not value:
        return "Domain is required."
    if len(value) > MAX_DOMAIN_LENGTH:
        return f"Maximum {MAX_DOMAIN_LENGTH} characters."
    if not DOMAIN_RE.match(value):
        return "Enter a valid domain such as example.com."
    return None

def validate_pattern(pattern):
    value = str(pattern or "").strip()
    if not value:
        return "Pattern cannot be empty."
    if len(value) > 200:
        return "Pattern is too long."
    tokens = set(re.findall(r"\{([^{}]+)\}", value))
    invalid = tokens - ALLOWED_TOKENS
    if invalid:
        return "Unsupported variable(s): " + ", ".join(sorted(invalid))
    if not tokens:
        return "Use at least one variable such as {first} or {last}."
    return None

def validate_request(first_name, last_name, domains):
    errors = {}
    first_error = validate_name(first_name)
    last_error = validate_name(last_name)
    if first_error:
        errors["first_name"] = first_error
    if last_error:
        errors["last_name"] = last_error

    if not domains:
        errors["domains"] = "Add at least one domain."
    else:
        domain_errors = []
        for domain in domains:
            error = validate_domain(domain)
            if error:
                domain_errors.append({"domain": domain, "error": error})
        if domain_errors:
            errors["domains"] = domain_errors

    return errors
