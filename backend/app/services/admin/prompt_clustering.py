# SPEC: SPEC_CCC_M9_ADMIN
"""Prompt ingest, lexical clustering, representatives, journey tags (ADM-9.1)."""
from __future__ import annotations

from collections import Counter
from typing import Any, Callable

from .admin_registry import (
    CLUSTER_TOKEN_JACCARD_MIN,
    HEALTH_DIVERGENCE_THRESHOLD,
    JOURNEY_STAGE_PHRASES,
    REPRESENTATIVE_K,
    WEIGHTS_STATUS,
)


def _norm(text: str) -> str:
    return " ".join((text or "").casefold().strip().split())


def _tokens(text: str) -> set[str]:
    return {t for t in _norm(text).replace("?", " ").replace(",", " ").split() if t}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def ingest_prompts(raw: list[str]) -> dict:
    """ADM-9.1.1 — exact-match dedupe; empty → honest EMPTY pool."""
    if not raw:
        return {
            "status": "EMPTY",
            "prompts": [],
            "deduped_count": 0,
            "reason": "empty prompt pool — not a fabricated seed list",
        }
    seen: set[str] = set()
    out: list[str] = []
    for p in raw:
        n = _norm(p)
        if not n or n in seen:
            continue
        seen.add(n)
        out.append(p.strip())
    if not out:
        return {
            "status": "EMPTY",
            "prompts": [],
            "deduped_count": 0,
            "reason": "all inputs empty after strip",
        }
    return {
        "status": "OK",
        "prompts": out,
        "deduped_count": len(out),
        "reason": "exact-match dedupe (casefold+strip)",
    }


def cluster_prompts(
    prompts: list[str],
    *,
    embedder: Callable[[list[str]], list[list[float]]] | None = None,
) -> dict:
    """ADM-9.1.2 — injected embedder or deterministic lexical fallback."""
    if not prompts:
        return {
            "status": "EMPTY",
            "clusters": [],
            "method": "none",
            "weights_status": WEIGHTS_STATUS,
            "reason": "no prompts to cluster",
        }

    if embedder is not None:
        vectors = embedder(list(prompts))
        # Simple greedy cosine-ish clustering on injected vectors (offline).
        clusters = _cluster_by_vectors(prompts, vectors)
        return {
            "status": "OK",
            "clusters": clusters,
            "method": "embedder",
            "weights_status": WEIGHTS_STATUS,
            "reason": "clustered via injected embedder",
        }

    # Lexical fallback — never pretend HDBSCAN ran.
    clusters = _lexical_clusters(prompts)
    return {
        "status": "OK",
        "clusters": clusters,
        "method": "lexical_fallback",
        "weights_status": WEIGHTS_STATUS,
        "reason": "no embedder — deterministic lexical clustering",
    }


def _lexical_clusters(prompts: list[str]) -> list[dict]:
    token_sets = [_tokens(p) for p in prompts]
    assigned = [-1] * len(prompts)
    clusters: list[dict] = []
    next_id = 0
    for i, p in enumerate(prompts):
        if assigned[i] >= 0:
            continue
        members = [p]
        idxs = [i]
        assigned[i] = next_id
        for j in range(i + 1, len(prompts)):
            if assigned[j] >= 0:
                continue
            if _jaccard(token_sets[i], token_sets[j]) >= CLUSTER_TOKEN_JACCARD_MIN:
                assigned[j] = next_id
                members.append(prompts[j])
                idxs.append(j)
            else:
                # Also join if sharing a dominant commercial/info stem with centroid
                shared = token_sets[i] & token_sets[j]
                if len(shared) >= 2:
                    assigned[j] = next_id
                    members.append(prompts[j])
                    idxs.append(j)
        clusters.append(
            {
                "cluster_id": f"c{next_id}",
                "members": members,
                "size": len(members),
            }
        )
        next_id += 1
    return clusters


def _dot(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def _norm_vec(a: list[float]) -> float:
    return sum(x * x for x in a) ** 0.5


def _cluster_by_vectors(prompts: list[str], vectors: list[list[float]]) -> list[dict]:
    if len(vectors) != len(prompts):
        raise ValueError("embedder length must match prompts")
    assigned = [-1] * len(prompts)
    clusters: list[dict] = []
    next_id = 0
    for i in range(len(prompts)):
        if assigned[i] >= 0:
            continue
        members = [prompts[i]]
        assigned[i] = next_id
        ni = _norm_vec(vectors[i]) or 1.0
        for j in range(i + 1, len(prompts)):
            if assigned[j] >= 0:
                continue
            nj = _norm_vec(vectors[j]) or 1.0
            sim = _dot(vectors[i], vectors[j]) / (ni * nj)
            if sim >= 0.75:
                assigned[j] = next_id
                members.append(prompts[j])
        clusters.append(
            {
                "cluster_id": f"c{next_id}",
                "members": members,
                "size": len(members),
            }
        )
        next_id += 1
    return clusters


def select_representatives(cluster: dict, *, k: int | None = None) -> list[dict]:
    """ADM-9.1.3 — medoid + intent extremes; cap k from registry."""
    members = list((cluster or {}).get("members") or [])
    if not members:
        return []
    cap = REPRESENTATIVE_K if k is None else min(int(k), REPRESENTATIVE_K)
    if cap < 1:
        return []

    # Lexical medoid: maximize mean Jaccard to others
    token_sets = [_tokens(m) for m in members]
    best_i = 0
    best_score = -1.0
    for i, ts in enumerate(token_sets):
        if len(members) == 1:
            best_i = 0
            break
        score = sum(_jaccard(ts, token_sets[j]) for j in range(len(members)) if j != i) / (
            len(members) - 1
        )
        if score > best_score:
            best_score = score
            best_i = i

    commercial = ("cost", "price", "near", "book", "appointment", "buy")
    informational = ("what", "how", "why", "benefits", "explained")

    def _intent_score(text: str, bag: tuple[str, ...]) -> int:
        t = _tokens(text)
        return sum(1 for w in bag if w in t)

    commercial_i = max(range(len(members)), key=lambda i: _intent_score(members[i], commercial))
    info_i = max(range(len(members)), key=lambda i: _intent_score(members[i], informational))

    # Boundary: farthest from medoid
    medoid_tok = token_sets[best_i]
    boundary = sorted(
        range(len(members)),
        key=lambda i: _jaccard(medoid_tok, token_sets[i]),
    )

    ordered_idx: list[int] = []
    for i in (best_i, commercial_i, info_i, *boundary):
        if i not in ordered_idx:
            ordered_idx.append(i)
        if len(ordered_idx) >= cap:
            break

    roles = ["centroid", "commercial_intent", "informational_intent", "boundary", "boundary"]
    out: list[dict] = []
    for rank, i in enumerate(ordered_idx[:cap]):
        out.append(
            {
                "prompt": members[i],
                "role": roles[rank] if rank < len(roles) else "member",
                "cluster_id": (cluster or {}).get("cluster_id"),
                "from_membership": True,
            }
        )
    return out


def tag_journey_stage(cluster: dict) -> str:
    """ADM-9.1.4 — rule table; unknown → UNTAGGED (never silent AWARENESS)."""
    members = list((cluster or {}).get("members") or [])
    if not members:
        return "UNTAGGED"
    blob = " ".join(_norm(m) for m in members)
    scores: Counter[str] = Counter()
    for stage, phrases in JOURNEY_STAGE_PHRASES.items():
        for ph in phrases:
            if ph in blob:
                scores[stage] += 1
    if not scores:
        return "UNTAGGED"
    return scores.most_common(1)[0][0]


def monitor_cluster_health(cluster_id: str, results: list[dict]) -> dict:
    """ADM-9.1.5 — divergence after model_id change → NEEDS_REEVALUATION."""
    rows = list(results or [])
    if not rows:
        return {
            "cluster_id": cluster_id,
            "status": "EMPTY",
            "reason": "no representative results to compare",
        }
    model_ids = {r.get("model_id") for r in rows if r.get("model_id") is not None}
    patterns = [str(r.get("pattern") or r.get("response_fingerprint") or "") for r in rows]
    # Jaccard across pattern token sets as a crude divergence proxy
    tok_sets = [_tokens(p) for p in patterns if p]
    if len(tok_sets) < 2:
        return {
            "cluster_id": cluster_id,
            "status": "OK",
            "reason": "insufficient pattern pairs for divergence",
            "model_ids": sorted(str(m) for m in model_ids),
        }
    pairs = []
    for i in range(len(tok_sets)):
        for j in range(i + 1, len(tok_sets)):
            pairs.append(1.0 - _jaccard(tok_sets[i], tok_sets[j]))
    divergence = sum(pairs) / len(pairs)
    if len(model_ids) > 1 and divergence >= HEALTH_DIVERGENCE_THRESHOLD:
        return {
            "cluster_id": cluster_id,
            "status": "NEEDS_REEVALUATION",
            "divergence": divergence,
            "model_ids": sorted(str(m) for m in model_ids),
            "reason": (
                "representative response patterns diverge after model_id change "
                "(co-occurrence with model drift — not a causal claim)"
            ),
        }
    return {
        "cluster_id": cluster_id,
        "status": "OK",
        "divergence": divergence,
        "model_ids": sorted(str(m) for m in model_ids),
        "reason": "patterns within registry threshold",
    }
