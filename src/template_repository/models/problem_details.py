from template_repository.models.domain_model import DomainModel


class ProblemDetails(DomainModel):
    type: str = "about:blank"
    title: str
    status: int
    detail: str
    instance: str | None = None
