"""FastAPI application and route definitions."""

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.responses import JSONResponse

from alphaforge.api.dependencies import get_market_data_engine
from alphaforge.api.models import (
    AnalyticsRequest,
    BacktestRequest,
    ErrorResponse,
    MarketDataRequest,
    PortfolioRequest,
)
from alphaforge.api.services import (
    calculate_analytics,
    calculate_portfolio,
    fetch_market_data,
    run_backtest,
)
from alphaforge.data.engine import MarketDataEngine

app = FastAPI(
    title="AlphaForge API",
    version="0.1.0",
    description="HTTP access to AlphaForge market-data, analytics, portfolio, and backtesting engines.",
)


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post(
    "/market-data/history",
    tags=["market data"],
    responses={404: {"model": ErrorResponse}, 502: {"model": ErrorResponse}},
)
def market_data_history(
    request: MarketDataRequest,
    engine: MarketDataEngine = Depends(get_market_data_engine),
) -> dict:
    try:
        return fetch_market_data(engine, request)
    except LookupError as error:
        raise HTTPException(status_code=404, detail={"code": "no_data", "message": str(error)}) from error
    except RuntimeError as error:
        raise HTTPException(
            status_code=502,
            detail={"code": "provider_failure", "message": "market-data provider failed."},
        ) from error
    except (TypeError, ValueError) as error:
        raise HTTPException(status_code=422, detail={"code": "invalid_data", "message": str(error)}) from error


@app.post("/analytics", tags=["analytics"])
def analytics(request: AnalyticsRequest) -> dict:
    try:
        return calculate_analytics(request)
    except (TypeError, ValueError) as error:
        raise HTTPException(status_code=422, detail={"code": "invalid_input", "message": str(error)}) from error


@app.post("/portfolio/analytics", tags=["portfolio"])
def portfolio(request: PortfolioRequest) -> dict:
    try:
        return calculate_portfolio(request)
    except (TypeError, ValueError, RuntimeError) as error:
        raise HTTPException(status_code=422, detail={"code": "invalid_input", "message": str(error)}) from error


@app.post("/backtests/run", tags=["backtesting"])
def backtest(
    request: BacktestRequest,
    engine: MarketDataEngine = Depends(get_market_data_engine),
) -> dict:
    try:
        return run_backtest(request, engine)
    except RuntimeError as error:
        raise HTTPException(status_code=502, detail={"code": "market_data_failure", "message": "backtest market-data retrieval failed."}) from error
    except (TypeError, ValueError) as error:
        raise HTTPException(status_code=422, detail={"code": "invalid_backtest", "message": str(error)}) from error


@app.exception_handler(Exception)
async def internal_error_handler(_, __) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": {"code": "internal_error", "message": "internal server error."}},
    )
