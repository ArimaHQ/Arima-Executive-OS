"""Research simulations (Middle Layer 2). Stateless, research-only, no execution."""

from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.auth.csrf import require_valid_csrf
from app.auth.dependencies import get_current_active_user
from app.auth.security import SecurityRateLimiter
from app.core.execution_policy import EXECUTION_POLICY
from app.database.models import User
from app.database.session import get_session
from app.quant.simulation import (
    ALGORITHM,
    ALGORITHM_ORIGIN,
    ALGORITHM_VERSION,
    MAX_SIMULATIONS,
    MAX_TRADES,
    MIN_SIMULATIONS,
    SimulationInputError,
    run_monte_carlo,
)

router = APIRouter(prefix="/research/simulations", tags=["research"])
SessionDependency = Annotated[AsyncSession, Depends(get_session)]
CurrentUser = Annotated[User, Depends(get_current_active_user)]
SIMULATIONS_PER_MINUTE = 6


class MonteCarloRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trade_results: list[float] = Field(min_length=1, max_length=MAX_TRADES)
    initial_equity: float = Field(gt=0)
    simulations: int = Field(default=MIN_SIMULATIONS, ge=MIN_SIMULATIONS, le=MAX_SIMULATIONS)
    seed: int = Field(default=0, ge=0, le=2**32 - 1)
    data_source: str = Field(
        min_length=1,
        max_length=300,
        description="Where the trade results came from; returned as provenance.",
    )


class MonteCarloProvenance(BaseModel):
    algorithm: str
    algorithm_version: str
    algorithm_origin: str
    data_source: str
    input_sha256: str
    seed: int
    generated_at: datetime
    execution_authority: str
    research_only: bool = True


class MonteCarloResponse(BaseModel):
    simulations: int
    trades_per_simulation: int
    initial_equity: float
    probability_of_profit: float
    probability_of_loss: float
    probability_of_new_equity_high: float
    probability_of_ruin: float
    expected_final_equity: float
    median_final_equity: float
    best_final_equity: float
    worst_final_equity: float
    maximum_simulated_drawdown: float
    average_simulated_drawdown: float
    confidence_interval_95: tuple[float, float]
    confidence_interval_99: tuple[float, float]
    provenance: MonteCarloProvenance


@router.post("/monte-carlo", response_model=MonteCarloResponse)
async def monte_carlo(
    data: MonteCarloRequest,
    request: Request,
    actor: CurrentUser,
    session: SessionDependency,
) -> MonteCarloResponse:
    require_valid_csrf(request)
    await SecurityRateLimiter(session).enforce(
        scope="research_monte_carlo",
        key=str(actor.id),
        limit=SIMULATIONS_PER_MINUTE,
        window=timedelta(minutes=1),
    )
    try:
        summary = await run_in_threadpool(
            run_monte_carlo,
            data.trade_results,
            initial_equity=data.initial_equity,
            simulations=data.simulations,
            seed=data.seed,
        )
    except SimulationInputError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)
        ) from error
    values = {
        key: getattr(summary, key)
        for key in MonteCarloResponse.model_fields
        if key != "provenance"
    }
    return MonteCarloResponse(
        **values,
        provenance=MonteCarloProvenance(
            algorithm=ALGORITHM,
            algorithm_version=ALGORITHM_VERSION,
            algorithm_origin=ALGORITHM_ORIGIN,
            data_source=data.data_source,
            input_sha256=summary.input_sha256,
            seed=summary.seed,
            generated_at=datetime.now(UTC),
            execution_authority=EXECUTION_POLICY.execution_authority.value,
        ),
    )
