"""Tests for token extraction, configured model pricing and studio currency."""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Base
from app.services.app_settings_service import AppSettingsService
from app.services.usage_service import build_pricing, compute_usage, extract_tokens, sum_usage

OPENROUTER_META = {"usage": {"prompt_tokens": 1000, "completion_tokens": 2000, "total_tokens": 3000, "cost": 0.04}}


def test_extract_tokens_supports_openai_and_gemini_shapes():
    assert extract_tokens(OPENROUTER_META) == {"input_tokens": 1000, "output_tokens": 2000, "total_tokens": 3000}
    gemini = extract_tokens({"usage": {"promptTokenCount": 7, "candidatesTokenCount": 1290}})
    assert gemini["total_tokens"] == 1297
    assert extract_tokens({"cost": 4}) is None
    assert extract_tokens(None) is None


def test_without_prices_only_tokens_are_returned():
    usage = compute_usage(OPENROUTER_META, None, image_count=1)
    assert usage["total_tokens"] == 3000
    assert usage["cost"] is None and usage["currency"] is None


def test_provider_reported_costs_are_ignored():
    # Provider costs/credits are not shown; only configured prices produce a cost.
    assert compute_usage({"cost": 4}, None, image_count=1) is None


def test_token_prices_per_million():
    pricing = build_pricing(input_per_mtok=2.5, output_per_mtok=10, per_image=None, currency="EUR")
    usage = compute_usage(OPENROUTER_META, pricing, image_count=1)
    # 1000 * 2.5 / 1e6 + 2000 * 10 / 1e6
    assert usage["cost"] == pytest.approx(0.0225)
    assert usage["currency"] == "EUR"


def test_per_image_price_without_tokens():
    pricing = build_pricing(input_per_mtok=None, output_per_mtok=None, per_image=0.04, currency="USD")
    usage = compute_usage({"provider": "bfl"}, pricing, image_count=3)
    assert usage["total_tokens"] is None
    assert usage["cost"] == pytest.approx(0.12)


def test_build_pricing_ignores_empty_and_negative():
    assert build_pricing(input_per_mtok=None, output_per_mtok=None, per_image=None, currency="USD") is None
    assert build_pricing(input_per_mtok=-1, output_per_mtok=None, per_image=None, currency="USD") is None


def test_sum_usage_per_currency():
    eur = {"input_tokens": 1, "output_tokens": 2, "total_tokens": 3, "cost": 0.5, "currency": "EUR"}
    total = sum_usage([eur, None, dict(eur)])
    assert total["total_tokens"] == 6 and total["cost"] == pytest.approx(1.0) and total["currency"] == "EUR"
    mixed = sum_usage([eur, {**eur, "currency": "USD"}])
    assert mixed["cost"] is None and mixed["currency"] == "mixed"
    tokens_only = sum_usage([{**eur, "cost": None, "currency": None}])
    assert tokens_only["cost"] is None and tokens_only["total_tokens"] == 3


def test_currency_setting_validation():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine, future=True)() as session:
        service = AppSettingsService()
        assert service.get_ui_settings(session)["cost_currency"] == "USD"
        assert service.update_ui_settings(session, {"cost_currency": " eur "})["cost_currency"] == "EUR"
        with pytest.raises(ValueError):
            service.update_ui_settings(session, {"cost_currency": "EURO"})


def test_admin_model_prices_roundtrip():
    from fastapi import HTTPException

    from app.api import admin as admin_api

    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine, future=True)() as session:
        created = admin_api.create_model_config(
            {"name": "GPT Image", "provider": "openai", "model_identifier": "gpt-image-1",
             "price_input_per_mtok": "5", "price_output_per_mtok": 40},
            session=session,
        )
        assert created["price_input_per_mtok"] == 5.0
        assert created["price_output_per_mtok"] == 40.0
        assert created["price_per_image"] is None

        updated = admin_api.update_model_config(
            created["id"], {"price_input_per_mtok": "", "price_per_image": 0.04}, session=session
        )
        assert updated["price_input_per_mtok"] is None
        assert updated["price_output_per_mtok"] == 40.0
        assert updated["price_per_image"] == 0.04

        with pytest.raises(HTTPException):
            admin_api.update_model_config(created["id"], {"price_per_image": -1}, session=session)
