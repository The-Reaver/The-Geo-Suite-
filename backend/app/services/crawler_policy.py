"""
Standalone crawler-policy validator.
"""
from dataclasses import dataclass, field
from ..core import rubric
from .audit_engine import _parse_robots, _rules_for, _is_blocked

@dataclass
class CrawlerPolicyResult:
    ok: bool
    blocked_required: list[str]
    blocked_user_triggered: list[str]
    wellknown_blocked: bool
    sitemap_referenced: bool
    findings: list[str]

def validate_robots(robots_txt: str) -> CrawlerPolicyResult:
    groups = _parse_robots(robots_txt)
    findings = []
    
    blocked_user_triggered = [b for b in rubric.USER_TRIGGERED_FETCHERS if _is_blocked(_rules_for(groups, b), "/")]
    if blocked_user_triggered:
        findings.append(f"HARD FAIL: user-triggered fetcher(s) blocked: {', '.join(blocked_user_triggered)}")
        
    blocked_required = [b for b in rubric.REQUIRED_BOTS if _is_blocked(_rules_for(groups, b), "/")]
    if blocked_required:
        findings.append(f"Required crawler(s) blocked: {', '.join(blocked_required)}")
        
    wellknown_blocked = any(_is_blocked(_rules_for(groups, b), "/.well-known/security.txt") for b in ("Googlebot", "*"))
    if wellknown_blocked:
        findings.append(".well-known is blocked")
        
    sitemap_referenced = any(d == "sitemap" for _, rules in groups for d, _ in rules)
    if not sitemap_referenced:
        findings.append("sitemap not referenced")
        
    ok = not blocked_user_triggered and not blocked_required and not wellknown_blocked and sitemap_referenced
    
    return CrawlerPolicyResult(
        ok=ok,
        blocked_required=blocked_required,
        blocked_user_triggered=blocked_user_triggered,
        wellknown_blocked=wellknown_blocked,
        sitemap_referenced=sitemap_referenced,
        findings=findings
    )
