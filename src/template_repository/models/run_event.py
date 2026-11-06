from pydantic import Field

from template_repository.models.domain_model import DomainModel
from template_repository.models.optimization_run import RunStatus


class RunEvent(DomainModel):
    sequence: int = Field(ge=1)
    run_id: str
    status: RunStatus
    stage: str
    progress: float = Field(ge=0, le=1)
    message: str
