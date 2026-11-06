from typing import Literal

from pydantic import AwareDatetime, Field

from template_repository.models.allocation import Allocation
from template_repository.models.domain_model import DomainModel
from template_repository.models.route_candidate import RouteCandidate

RunStatus = Literal["queued", "running", "completed", "failed", "infeasible"]


class OptimizationRun(DomainModel):
    id: str
    scenario_id: str
    status: RunStatus = "queued"
    stage: str = "queued"
    progress: float = Field(default=0, ge=0, le=1)
    created_at: AwareDatetime
    updated_at: AwareDatetime
    routes: list[RouteCandidate] = Field(default_factory=list)
    allocations: list[Allocation] = Field(default_factory=list)
    total_cost: float = Field(default=0, ge=0)
    warnings: list[str] = Field(default_factory=list)
    error: str | None = None
