from fastapi import APIRouter, HTTPException, Request, UploadFile, File
from fastapi.responses import PlainTextResponse, Response
import csv
import io
from app.config import MAX_RESULTS, MAX_BULK_ROWS
from app.auth import require_user, require_csrf, user_has_private_access
from app.models import GenerateRequest, CustomPatternRequest
from app.pattern_engine import PATTERNS, PATTERN_LABELS
from app.services.export_service import (
    results_to_csv, results_to_json, results_to_txt, results_to_xlsx
)
from app.services.permutation_service import generate_email_permutations
from app.services.validation_service import (
    validate_domain, validate_name, validate_pattern, validate_request
)

router = APIRouter(prefix="/api")

@router.get("/health")
def health():
    return {"status": "ok", "service": "email-permutation-tool"}

@router.get("/patterns")
def patterns():
    return {
        "count": len(PATTERNS),
        "patterns": [
            {"pattern": p, "label": PATTERN_LABELS.get(p, p)}
            for p in PATTERNS
        ],
    }

@router.post("/generate")
def generate(request: GenerateRequest, http_request: Request):
    # Every generation request requires a logged-in user.
    require_user(http_request)
    errors = validate_request(
        request.first_name,
        request.last_name,
        request.domains,
    )
    if errors:
        raise HTTPException(status_code=422, detail=errors)

    try:
        results = generate_email_permutations(
            first_name=request.first_name,
            last_name=request.last_name,
            domains=request.domains,
            selected_patterns=request.selected_patterns,
            custom_patterns=request.custom_patterns,
            prefixes=request.prefixes,
            suffixes=request.suffixes,
            numbers=request.numbers,
            case_mode=request.case_mode,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return {
        "success": True,
        "total": len(results),
        "limit": MAX_RESULTS,
        "results": results,
    }

@router.post("/custom-preview")
def custom_preview(request: CustomPatternRequest, http_request: Request):
    require_user(http_request)
    errors = {
        "first_name": validate_name(request.first_name),
        "last_name": validate_name(request.last_name),
        "domain": validate_domain(request.domain),
        "pattern": validate_pattern(request.pattern),
    }
    errors = {k: v for k, v in errors.items() if v}
    if errors:
        raise HTTPException(status_code=422, detail=errors)

    result = generate_email_permutations(
        request.first_name,
        request.last_name,
        [request.domain],
        selected_patterns=[request.pattern],
    )
    return {"success": True, "results": result}

@router.post("/export/{file_type}")
def export(file_type: str, request: GenerateRequest, http_request: Request):
    require_user(http_request)
    errors = validate_request(
        request.first_name,
        request.last_name,
        request.domains,
    )
    if errors:
        raise HTTPException(status_code=422, detail=errors)

    results = generate_email_permutations(
        first_name=request.first_name,
        last_name=request.last_name,
        domains=request.domains,
        selected_patterns=request.selected_patterns,
        custom_patterns=request.custom_patterns,
        prefixes=request.prefixes,
        suffixes=request.suffixes,
        numbers=request.numbers,
        case_mode=request.case_mode,
    )

    if file_type == "txt":
        return PlainTextResponse(
            results_to_txt(results),
            media_type="text/plain",
            headers={"Content-Disposition": "attachment; filename=emails.txt"},
        )
    if file_type == "csv":
        return PlainTextResponse(
            results_to_csv(results),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=emails.csv"},
        )
    if file_type == "json":
        return PlainTextResponse(
            results_to_json(results),
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=emails.json"},
        )
    if file_type == "xlsx":
        return Response(
            content=results_to_xlsx(results),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=emails.xlsx"},
        )

    raise HTTPException(status_code=400, detail="Supported exports: txt, csv, json, xlsx")


@router.post("/private/bulk-generate")
async def private_bulk_generate(
    request: Request,
    file: UploadFile = File(...),
):
    """
    Private feature: server-side CSV bulk generation.

    Only users approved by the administrator (or the admin itself) can call
    this endpoint. This is important: hiding a button in JavaScript alone is
    NOT a security boundary.
    """
    user = require_user(request)
    require_csrf(request, user)

    if not user_has_private_access(user):
        raise HTTPException(
            status_code=403,
            detail="Bulk generation is a private feature. Ask the administrator for access.",
        )

    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Please upload a CSV file.")

    raw = await file.read()
    if len(raw) > 2 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="CSV file is too large. Maximum is 2 MB.")

    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="CSV must be UTF-8 encoded.")

    reader = csv.DictReader(io.StringIO(text))
    required = {"first_name", "last_name", "domain"}

    if not reader.fieldnames or not required.issubset(
        {str(x).strip().lower() for x in reader.fieldnames}
    ):
        raise HTTPException(
            status_code=400,
            detail="CSV must contain first_name,last_name,domain columns.",
        )

    # Map headers case-insensitively so "First_Name" still works.
    header_map = {
        str(name).strip().lower(): name
        for name in reader.fieldnames
        if name
    }

    rows = []
    data_rows_processed = 0
    for row_number, row in enumerate(reader, start=2):
        if row_number > MAX_BULK_ROWS + 1:
            raise HTTPException(
                status_code=400,
                detail=f"CSV contains more than {MAX_BULK_ROWS} data rows.",
            )

        first = str(row.get(header_map["first_name"], "") or "").strip()
        last = str(row.get(header_map["last_name"], "") or "").strip()
        domain = str(row.get(header_map["domain"], "") or "").strip()

        if not first and not last and not domain:
            continue

        errors = validate_request(first, last, [domain])
        if errors:
            # One bad row should not silently create surprising output.
            raise HTTPException(
                status_code=422,
                detail=f"Invalid CSV row {row_number}: {errors}",
            )

        data_rows_processed += 1

        generated = generate_email_permutations(
            first_name=first,
            last_name=last,
            domains=[domain],
        )
        rows.extend(generated)

    # Keep the same global output safety limit as normal generation.
    unique = dedupe_bulk(rows)
    return {
        "success": True,
        "rows_processed": data_rows_processed,
        "total": len(unique),
        "results": unique[:MAX_RESULTS],
    }


def dedupe_bulk(results):
    """Small helper for the private bulk endpoint."""
    seen = set()
    output = []
    for item in results:
        if item["email"] in seen:
            continue
        seen.add(item["email"])
        output.append(item)
    return output
