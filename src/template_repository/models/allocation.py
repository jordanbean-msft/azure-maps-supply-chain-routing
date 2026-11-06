from pydantic import Field

from template_repository.models.cost_breakdown import CostBreakdown
from template_repository.models.domain_model import DomainModel


class Allocation(DomainModel):
    route_id: str
    supplier_id: str
    factory_id: str
    quantity: float = Field(gt=0)
    unit_cost: CostBreakdown
    total_cost: float = Field(ge=0)
