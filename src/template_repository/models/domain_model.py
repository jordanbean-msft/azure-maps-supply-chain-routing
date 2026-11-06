from pydantic import BaseModel, ConfigDict


class DomainModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
