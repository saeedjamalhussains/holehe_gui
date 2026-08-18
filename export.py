import json
import csv
from typing import List, Dict

def export_json(results: List[Dict], path: str) -> None:
    """Write results to *path* as pretty‑printed JSON."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

def export_csv(results: List[Dict], path: str) -> None:
    """Write results to *path* as CSV with a fixed column order.

    Columns: name, domain, exists, rateLimit, emailrecovery, phoneNumber, others
    """
    fieldnames = [
        "name",
        "domain",
        "exists",
        "rateLimit",
        "emailrecovery",
        "phoneNumber",
        "others",
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in results:
            # Ensure all expected keys exist
            writer.writerow({k: row.get(k) for k in fieldnames})
