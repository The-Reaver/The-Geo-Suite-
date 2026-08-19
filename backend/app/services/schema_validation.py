from typing import Any
from .audit_engine import _find_local_business

def validate_jsonld(graph_objects: Any) -> tuple[str, list[str]]:
    """Validate a JSON-LD graph. Returns (status, findings)
    where status is 'valid', 'warning', or 'error'."""
    if not isinstance(graph_objects, list) or not graph_objects:
        return "error", ["Invalid or empty JSON-LD graph"]
        
    node, is_specific = _find_local_business(graph_objects)
    if node is None:
        return "error", ["No LocalBusiness (or subtype) node found in graph"]
        
    findings = []
    if not is_specific:
        findings.append("Uses generic LocalBusiness type instead of specific subtype")
        
    required = ["name", "address", "telephone", "url"]
    missing = [f for f in required if not node.get(f)]
    if missing:
        findings.append(f"Missing required fields: {', '.join(missing)}")
        
    if findings:
        return "warning", findings
        
    return "valid", []
