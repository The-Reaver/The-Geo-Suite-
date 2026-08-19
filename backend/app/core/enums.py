"""Canonical Python enum source for the GEO Platform.

This is the SINGLE Python source of truth for every DB enum. Its string values
must match the SQL `CREATE TYPE ... AS ENUM (...)` values in
`supabase/migrations/20260721000000_init_schema.sql` VERBATIM (values and order),
and any future worker constant must reference these -- never a second copy. The
enum-parity test in `tests/test_auth_and_schema.py` enforces this (the Check 14
catalog-parity rule; a mismatch here is the class of bug that killed a prior deploy).

`SQL_ENUMS` maps each SQL type name to its Python enum so the parity test can pair
them without guessing.
"""
from enum import Enum


class UserRole(str, Enum):
    OWNER = "owner"
    ADMIN = "admin"


class ClientType(str, Enum):
    ESTABLISHED = "established"
    NEW_BUSINESS = "new_business"


class SiteStatus(str, Enum):
    PROVISIONING = "provisioning"
    STAGING = "staging"
    LIVE = "live"
    ROLLED_BACK = "rolled_back"


class BuildKind(str, Enum):
    PROVISION = "provision"
    REGEN = "regen"
    CUTOVER = "cutover"


class BuildStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    FAILED = "failed"
    DONE = "done"


class RegenBatchStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"


class ContentPageType(str, Enum):
    HOME = "home"
    SERVICE = "service"
    FAQ = "faq"
    ABOUT = "about"


class ContentPageStatus(str, Enum):
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    PUBLISHED = "published"


class FactSource(str, Enum):
    INTAKE = "intake"
    CRAWL = "crawl"
    INTERVIEW = "interview"


class ClaimRiskLevel(str, Enum):
    NORMAL = "normal"
    HIGH = "high"


class ClaimStatus(str, Enum):
    FLAGGED = "flagged"
    OWNER_APPROVED = "owner_approved"
    REJECTED = "rejected"


class SchemaValidationStatus(str, Enum):
    VALID = "valid"
    WARNING = "warning"
    ERROR = "error"


class OptFileType(str, Enum):
    LLMS = "llms"
    LLMS_FULL = "llms_full"
    ROBOTS = "robots"
    SITEMAP = "sitemap"
    MANIFEST = "manifest"
    WELLKNOWN = "wellknown"


class QueryStatus(str, Enum):
    ACTIVE = "active"
    AWAITING_REVIEW = "awaiting_review"


class DsKind(str, Enum):
    GROUNDED_API = "grounded_api"
    CONSUMER_API = "consumer_api"
    LICENSED = "licensed"


class DsStatus(str, Enum):
    ACTIVE = "active"
    DISABLED = "disabled"


class CitationEngine(str, Enum):
    PERPLEXITY = "perplexity"
    OPENAI = "openai"
    GEMINI = "gemini"


class TrendDir(str, Enum):
    UP = "up"
    FLAT = "flat"
    DOWN = "down"


class HealthStatus(str, Enum):
    STRONG = "strong"
    ATTENTION = "attention"
    PROBLEM = "problem"


class LeadEventType(str, Enum):
    FORM = "form"
    TAP_CALL = "tap_call"
    DIRECTIONS = "directions"


class LeadStatus(str, Enum):
    NEW = "new"
    SEEN = "seen"


class ReviewStatus(str, Enum):
    NEW = "new"
    RESPONDED = "responded"


class ToolStatus(str, Enum):
    RESERVED = "reserved"
    CONNECTED = "connected"


class AssetKind(str, Enum):
    LOGO = "logo"
    PHOTO = "photo"
    DOC = "doc"


class SubStatus(str, Enum):
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELED = "canceled"


# SQL type name -> Python enum. The parity test pairs these to compare values.
SQL_ENUMS = {
    "user_role": UserRole,
    "client_type_enum": ClientType,
    "site_status": SiteStatus,
    "build_kind": BuildKind,
    "build_status": BuildStatus,
    "regen_batch_status": RegenBatchStatus,
    "content_page_type": ContentPageType,
    "content_page_status": ContentPageStatus,
    "fact_source": FactSource,
    "claim_risk_level": ClaimRiskLevel,
    "claim_status": ClaimStatus,
    "schema_validation_status": SchemaValidationStatus,
    "opt_file_type": OptFileType,
    "query_status": QueryStatus,
    "ds_kind": DsKind,
    "ds_status": DsStatus,
    "citation_engine": CitationEngine,
    "trend_dir": TrendDir,
    "health_status_enum": HealthStatus,
    "lead_event_type": LeadEventType,
    "lead_status": LeadStatus,
    "review_status": ReviewStatus,
    "tool_status": ToolStatus,
    "asset_kind": AssetKind,
    "sub_status": SubStatus,
}
