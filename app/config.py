import os

MAX_RESULTS = int(os.getenv("MAX_RESULTS", "10000"))
MAX_BULK_ROWS = int(os.getenv("MAX_BULK_ROWS", "250"))
MAX_NAME_LENGTH = int(os.getenv("MAX_NAME_LENGTH", "100"))
MAX_DOMAIN_LENGTH = int(os.getenv("MAX_DOMAIN_LENGTH", "253"))
MAX_CUSTOM_PATTERNS = int(os.getenv("MAX_CUSTOM_PATTERNS", "100"))
MAX_REQUEST_BYTES = int(os.getenv("MAX_REQUEST_BYTES", str(2 * 1024 * 1024)))

# Authentication settings are loaded from environment variables in app.auth.
