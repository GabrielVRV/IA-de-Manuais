from collections import Counter
from datetime import datetime
from typing import Self

from pydantic import BaseModel, Field

from manual_assistant.application.use_cases.sync_manuals import (
    SyncAction,
    SyncPlan,
    SyncRun,
)


class SyncPlanItemResponse(BaseModel):
    action: SyncAction
    file_name: str
    title: str
    reason: str | None = Field(description="Por que foi ignorado")


class SyncCheckResponse(BaseModel):
    counts: dict[SyncAction, int] = Field(description="Quantidade de manuais por ação")
    to_index: int = Field(description="Quantos serão (re)indexados, ou seja, gastam API de IA")
    items: list[SyncPlanItemResponse] = Field(description="Tudo menos os que não mudaram")

    @classmethod
    def from_plan(cls, plan: SyncPlan) -> Self:
        counts = Counter(item.action for item in plan.items)
        return cls(
            counts={action: counts[action] for action in SyncAction},
            to_index=sum(item.costs_indexing for item in plan.items),
            items=[
                SyncPlanItemResponse(
                    action=item.action,
                    file_name=item.file_name,
                    title=item.title,
                    reason=item.reason,
                )
                for item in plan.items
                if item.action is not SyncAction.UNCHANGED
            ],
        )


class SyncFailureResponse(BaseModel):
    action: SyncAction
    file_name: str
    detail: str


class SyncRunResponse(BaseModel):
    started_at: datetime
    started_by: str
    finished_at: datetime | None
    running: bool
    total: int
    done: int
    succeeded: int
    failures: list[SyncFailureResponse]
    error: str | None = Field(description="Falha que interrompeu a sincronização inteira")

    @classmethod
    def from_run(cls, run: SyncRun) -> Self:
        failures = [o for o in run.outcomes if not o.ok]
        return cls(
            started_at=run.started_at,
            started_by=run.started_by,
            finished_at=run.finished_at,
            running=run.running,
            total=run.total,
            done=len(run.outcomes),
            succeeded=len(run.outcomes) - len(failures),
            failures=[
                SyncFailureResponse(
                    action=o.item.action, file_name=o.item.file_name, detail=o.detail
                )
                for o in failures
            ],
            error=run.error,
        )


class SyncStatusResponse(BaseModel):
    enabled: bool = Field(description="Falso quando a pasta de manuais não está configurada")
    running: bool
    last_run: SyncRunResponse | None = Field(
        description="A sincronização em andamento ou a última (some ao reiniciar a API)"
    )
