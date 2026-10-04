import csv
import io
import json

def results_to_txt(results):
    return "\n".join(item["email"] for item in results)

def results_to_csv(results):
    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=["email", "pattern", "label", "domain"],
    )
    writer.writeheader()
    writer.writerows(results)
    return output.getvalue()

def results_to_json(results):
    return json.dumps(results, indent=2)

def results_to_xlsx(results):
    from openpyxl import Workbook
    output = io.BytesIO()
    wb = Workbook()
    ws = wb.active
    ws.title = "Email Permutations"
    ws.append(["Email", "Pattern", "Label", "Domain"])
    for item in results:
        ws.append([
            item["email"],
            item["pattern"],
            item["label"],
            item["domain"],
        ])
    ws.freeze_panes = "A2"
    ws.column_dimensions["A"].width = 42
    ws.column_dimensions["B"].width = 28
    ws.column_dimensions["C"].width = 24
    ws.column_dimensions["D"].width = 30
    wb.save(output)
    return output.getvalue()
