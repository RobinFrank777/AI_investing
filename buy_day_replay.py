"""Isolated, read-only BUY-day replay through the production action chain."""

import pandas as pd

from config import PRIMARY_UNIVERSE_VERSION
from order_draft import build_order_draft
from order_review import build_order_review
from portfolio_risk import build_model_portfolio
from portfolio_risk_calculator import calculate_portfolio_risk_inputs
from position_sizing import add_share_sizing, add_target_dollar_amount
from production_candidate_builder import build_production_candidates
from score import SCORE_MODEL_VERSION
from score_threshold_analysis import build_historical_score_table
from trade_signal import generate_signals


REPLAY_CAPITAL = 100_000


def build_buy_day_candidates(as_of_date="2026-06-18", *, scores=None, market_data=None):
    """Rebuild the date-local candidate snapshot with production score/signal logic."""
    score_history = (
        build_historical_score_table(market_data=market_data)
        if scores is None else scores.copy(deep=True)
    )
    replay_date = pd.Timestamp(as_of_date)
    dates = pd.to_datetime(score_history["Date"], errors="raise")
    date_scores = score_history.loc[dates == replay_date].copy()
    if date_scores.empty:
        raise ValueError(f"no production score snapshot for replay date {as_of_date}")
    signaled = generate_signals(date_scores)
    stock_rank = pd.DataFrame({
        "Ticker": signaled["Ticker"],
        "MarketDataDate": replay_date.date().isoformat(),
        "FinalScore": signaled["FinalScore"],
        "TradeSignal": signaled["TradeSignal"],
        "RS_Score": signaled["RS_Score"],
        "NearHighScore": signaled["NearHighScore"],
        "Confidence": signaled["Confidence"],
        "ScoreModelVersion": signaled.get("ScoreModelVersion", SCORE_MODEL_VERSION),
        "UniverseVersion": PRIMARY_UNIVERSE_VERSION,
    })
    return build_production_candidates(
        stock_rank, reference_date=as_of_date, max_staleness_days=0
    )


def run_buy_day_replay(as_of_date="2026-06-18", *, capital=REPLAY_CAPITAL,
                       scores=None, market_data=None, calculation_timestamp=None,
                       fundamentals=None):
    """Run the isolated in-memory chain; no production artifact or order is sent."""
    candidates = build_buy_day_candidates(
        as_of_date, scores=scores, market_data=market_data
    )
    from portfolio_candidate_adapter import build_validated_portfolio_candidates
    validated = build_validated_portfolio_candidates(candidates)
    risk_inputs = calculate_portfolio_risk_inputs(
        validated, market_data=market_data,
        calculation_timestamp=calculation_timestamp,
    )
    portfolio = build_model_portfolio(risk_inputs)
    if fundamentals is None:
        enriched = portfolio.copy()
        enriched["FundamentalScore"] = pd.NA
        enriched["CombinedScore"] = enriched.get("FinalScore")
        enriched["FundamentalRating"] = "MISSING"
    else:
        enriched = portfolio.merge(fundamentals, on="Ticker", how="left")
    sizing = add_share_sizing(add_target_dollar_amount(enriched, capital))
    draft = build_order_draft(sizing)
    review = build_order_review(draft)
    return {
        "candidates": candidates,
        "risk_inputs": risk_inputs,
        "portfolio": portfolio,
        "sizing": sizing,
        "draft": draft,
        "review": review,
    }
