# SPEC: SPEC_CCC_M9_ADMIN
"""Platform administration — prompt clustering and multi-brand workspaces."""
from .prompt_clustering import (
    cluster_prompts,
    ingest_prompts,
    monitor_cluster_health,
    select_representatives,
    tag_journey_stage,
)
from .workspace import (
    budget_status,
    configure_rbac,
    create_workspace,
    list_workspaces,
    path_a_data_flow,
)

__all__ = [
    "ingest_prompts",
    "cluster_prompts",
    "select_representatives",
    "tag_journey_stage",
    "monitor_cluster_health",
    "create_workspace",
    "list_workspaces",
    "configure_rbac",
    "budget_status",
    "path_a_data_flow",
]
