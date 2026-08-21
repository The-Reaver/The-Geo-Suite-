"""
Business facts and generated-site models for the site engine (Sprint days 6-8).

`BusinessFacts` is the confirmed intake payload the generator turns into a site.
`GeneratedSite` is the traceable result: the files written plus the hash of the
facts they were built from, so a regeneration is auditable.

These are Pydantic models for the real API path. The engine itself reads facts by
attribute access and does not import Pydantic, so it can be exercised against the
audit grader with any object that carries the same fields.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


def slugify(value: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (value or "").lower()).strip("-")
    return s or "item"


# 2026-08-21, Opus review round 3: site_prose.py used to signal its one
# internal "read more" link with an embedded \x01 control-character marker
# -- since removed for an unrelated forgery reason (see site_prose.py's
# module comment), but the underlying exposure was broader than that one
# marker: a business_name (or any other free-text field here) containing
# ANY C0 control character reaches rendered output completely unfiltered.
# Reproduced directly: a business_name containing a raw \x01 byte produced
# an invalid assets/logo.svg (XML forbids C0 controls other than tab/
# newline/CR) -- a real, broken static file, not a theoretical risk.
# site_engine.py's own escaping (_esc/_esc_inline) only ever handles the
# five HTML-significant characters (& < > " '); it was never meant to be
# the place raw control bytes get filtered. Stripped once, here, at the
# real intake boundary every API request actually validates through --
# not per-renderer, so no future call site can reintroduce this gap.
#
# 2026-08-21, Opus review round 4: the C0-only class was incomplete against
# the actual XML 1.0 Char production (#x9 | #xA | #xD | [#x20-#xD7FF] |
# [#xE000-#xFFFD] | [#x10000-#x10FFFF]) -- U+FFFE/U+FFFF fall in the gap
# right after #xFFFD and are forbidden too, reproduced with the same
# invalid-logo.svg failure via this exact validator. Lone UTF-16 surrogates
# (U+D800-U+DFFF) are a separate, real crash: Python's json module accepts
# an unpaired "\ud800" while decoding a request body, Pydantic doesn't
# reject it, and Path.write_text(..., encoding="utf-8") then raises an
# unhandled UnicodeEncodeError -- reproduced as a real HTTP 500 with the
# raw exception text leaked to the caller. Both ranges added.
_CONTROL_CHARS_RE = re.compile("[\\x00-\\x08\\x0b\\x0c\\x0e-\\x1f\\ud800-\\udfff\\ufffe\\uffff]")


def _strip_control_chars(value: str) -> str:
    return _CONTROL_CHARS_RE.sub("", value)


class Service(BaseModel):
    name: str
    description: str

    @field_validator("name", "description")
    @classmethod
    def _no_control_chars(cls, value: str) -> str:
        return _strip_control_chars(value)

    @property
    def slug(self) -> str:
        return slugify(self.name)


class MenuItem(BaseModel):
    # 2026-08-21: Site Generator page-structure taxonomy, slice 1 (menu
    # page). price is a free-form str, not a float -- real menu pricing
    # isn't always a single number ("$10-14", "Market price"). dietary_tags
    # is a free-form list, not an enum, matching this codebase's existing
    # "no invented taxonomy" pattern (credentials/service_areas are also
    # free strings, never a closed set).
    name: str
    description: str = ""
    price: str = ""
    category: str = ""
    dietary_tags: List[str] = Field(default_factory=list)

    @field_validator("name")
    @classmethod
    def _name_required_after_stripping(cls, value: str) -> str:
        # 2026-08-21, Opus 5 review: a bare `str` field is required to be
        # present, not non-empty -- name="" (or a value that's only control
        # characters/whitespace) validated cleanly and rendered as an
        # anonymous priced item ("<li> <span class="price">$3</span>"),
        # fabricated structure around no real name. name is the one field
        # this whole feature exists to display; reject it outright rather
        # than silently rendering nothing where a real name belongs.
        cleaned = _strip_control_chars(value)
        if not cleaned.strip():
            raise ValueError("MenuItem.name must not be empty")
        return cleaned

    @field_validator("description", "price", "category")
    @classmethod
    def _no_control_chars(cls, value: str) -> str:
        return _strip_control_chars(value)

    @field_validator("dietary_tags")
    @classmethod
    def _no_control_chars_list(cls, values: List[str]) -> List[str]:
        return [_strip_control_chars(v) for v in values]


class FAQ(BaseModel):
    question: str
    answer: str

    @field_validator("question", "answer")
    @classmethod
    def _no_control_chars(cls, value: str) -> str:
        return _strip_control_chars(value)


class Testimonial(BaseModel):
    author: str
    text: str

    @field_validator("author", "text")
    @classmethod
    def _no_control_chars(cls, value: str) -> str:
        return _strip_control_chars(value)


class Rating(BaseModel):
    # 2026-08-21, Opus 5 review of the Site Generator rating-display slice:
    # these were unconstrained, so a bad upstream value (a corrupted DB
    # row, a malformed API payload) could reach round() in site_engine.py
    # as NaN/Infinity (a real 500) or render visibly wrong output --
    # scientific notation for an absurd value, more than 5 filled stars
    # for value > 5, a negative star count. A real rating is always 0-5
    # stars with a non-negative review count; ge/le make that a schema
    # guarantee instead of an assumption the renderer has to defend.
    value: float = Field(ge=0, le=5)
    count: int = Field(ge=0)


class BusinessFacts(BaseModel):
    business_name: str
    # The specific schema.org LocalBusiness subtype (Dentist, Plumber, HairSalon...).
    subtype: str
    # NAP.
    street: str
    locality: str
    region: str            # state/province, e.g. "OR"
    postal_code: str
    country: str = "US"
    telephone: str
    email: Optional[str] = None
    # Presence.
    domain: str            # bare domain, e.g. "cedarridgedental.example"
    # Operations.
    hours: List[str] = Field(default_factory=list)         # ["Mon-Fri 8:00-17:00", ...]
    service_areas: List[str] = Field(default_factory=list)  # ["Portland", "Beaverton"]
    services: List[Service] = Field(default_factory=list)
    menu_items: List[MenuItem] = Field(default_factory=list)
    credentials: List[str] = Field(default_factory=list)
    faqs: List[FAQ] = Field(default_factory=list)
    testimonials: List[Testimonial] = Field(default_factory=list)
    same_as: List[str] = Field(default_factory=list)        # GBP + social/profile URLs
    rating: Optional[Rating] = None
    last_updated: str = ""                                   # ISO date, e.g. "2026-07-24"
    tagline: Optional[str] = None

    @field_validator("business_name", "subtype", "street", "locality", "region",
                      "postal_code", "country", "telephone", "domain", "last_updated")
    @classmethod
    def _no_control_chars(cls, value: str) -> str:
        return _strip_control_chars(value)

    @field_validator("email", "tagline")
    @classmethod
    def _no_control_chars_optional(cls, value: Optional[str]) -> Optional[str]:
        return _strip_control_chars(value) if value else value

    @field_validator("hours", "service_areas", "credentials", "same_as")
    @classmethod
    def _no_control_chars_list(cls, values: List[str]) -> List[str]:
        return [_strip_control_chars(v) for v in values]

    def base_url(self) -> str:
        return f"https://{self.domain}"

    def facts_hash(self) -> str:
        payload = json.dumps(self.model_dump(), sort_keys=True, default=str)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


class GeneratedSite(BaseModel):
    out_dir: str
    files: List[str]
    facts_hash: str
    pages: List[str]        # the HTML page filenames
