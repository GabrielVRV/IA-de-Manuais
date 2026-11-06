from collections import Counter
from datetime import datetime
from typing import Self

from pydantic import BaseModel, Field

from manual_assistant.application.use_cases.sync_manuals import (
    SyncAction,
    SyncPlan,
    SyncRun,
)
from manual_assistant.application.use_cases.sync_schedule import SyncScheduleView


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
    describe_figures: bool = Field(description="As figuras dos manuais vão para a IA")
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
            describe_figures=run.describe_figures,
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


class SyncScheduleResponse(BaseModel):
    enabled: bool
    time: str = Field(description="HH:MM no fuso da empresa", examples=["00:00"])
    describe_figures: bool = Field(description="Também descreve as figuras por IA")
    timezone: str = Field(examples=["America/Sao_Paulo"])
    next_run_at: datetime | None = Field(description="Próxima execução; nulo se desligado")
    last_triggered_at: datetime | None
    last_trigger_error: str | None = Field(
        description="Por que a última execução agendada não começou"
    )
    updated_at: datetime | None
    updated_by: str | None

    @classmethod
    def from_view(cls, view: SyncScheduleView) -> Self:
        schedule = view.schedule
        return cls(
            enabled=schedule.enabled,
            time=schedule.time_of_day.strftime("%H:%M"),
            describe_figures=schedule.describe_figures,
            timezone=view.timezone,
            next_run_at=view.next_run,
            last_triggered_at=schedule.last_triggered_at,
            last_trigger_error=schedule.last_trigger_error,
            updated_at=schedule.updated_at,
            updated_by=schedule.updated_by,
        )


class UpdateSyncScheduleRequest(BaseModel):
    enabled: bool
    time: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$", examples=["00:00"])
    describe_figures: bool = False
