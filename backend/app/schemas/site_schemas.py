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

from pydantic import BaseModel, Field


def slugify(value: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (value or "").lower()).strip("-")
    return s or "item"


class Service(BaseModel):
    name: str
    description: str

    @property
    def slug(self) -> str:
        return slugify(self.name)


class FAQ(BaseModel):
    question: str
    answer: str


class Testimonial(BaseModel):
    author: str
    text: str


class Rating(BaseModel):
    value: float
    count: int


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
    credentials: List[str] = Field(default_factory=list)
    faqs: List[FAQ] = Field(default_factory=list)
    testimonials: List[Testimonial] = Field(default_factory=list)
    same_as: List[str] = Field(default_factory=list)        # GBP + social/profile URLs
    rating: Optional[Rating] = None
    last_updated: str = ""                                   # ISO date, e.g. "2026-07-24"
    tagline: Optional[str] = None

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
