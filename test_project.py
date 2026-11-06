"""Tests for the three required functions in project.py."""

import pytest

from project import (
    GARAGE_CAPACITY,
    SHOP_CAPACITY,
    STARTING_MONEY,
    calculate_sell_range,
    can_purchase,
    collection_net_worth,
    generate_stock,
    load_catalog,
    new_game,
    refresh_stock,
    stock_weight,
    try_buy,
)


def test_calculate_sell_range():
    assert calculate_sell_range(100_000, 0) == (70_000, 130_000)
    assert calculate_sell_range(100_000, 2) == (80_000, 140_000)
    assert calculate_sell_range(65_000, 5) == (61_750, 100_750)
    huge = 10**20
    low, high = calculate_sell_range(huge, 0)
    assert low == huge * 70 // 100
    assert high == huge * 130 // 100
    assert isinstance(low, int) and isinstance(high, int)

    with pytest.raises(ValueError):
        calculate_sell_range(0, 0)
    with pytest.raises(ValueError):
        calculate_sell_range(1000, 6)
    with pytest.raises(TypeError):
        calculate_sell_range(1000.0, 0)


def test_collection_net_worth():
    assert collection_net_worth([]) == 0
    cars = [
        {"market_value": 65_000},
        {"market_value": 2_800_000},
        {"market_value": 1},
    ]
    assert collection_net_worth(cars) == 2_865_001
    giant = [{"market_value": 100000000000000000000000}]
    assert collection_net_worth(giant) == 100000000000000000000000

    with pytest.raises(ValueError):
        collection_net_worth([{"market_value": -1}])
    with pytest.raises(TypeError):
        collection_net_worth([{"market_value": True}])
    with pytest.raises(TypeError):
        collection_net_worth("not a list")


def test_can_purchase():
    assert can_purchase(25_000, 65_000) is False
    assert can_purchase(65_000, 65_000) is True
    assert can_purchase(100_000, 65_000) is True
    assert can_purchase(0, 1) is False
    assert can_purchase(500, 0) is False
    assert can_purchase(500, -10) is False
    giant = 100000000000000000000000
    assert can_purchase(giant, giant) is True
    assert can_purchase(giant - 1, giant) is False

    with pytest.raises(TypeError):
        can_purchase(100.5, 10)
    with pytest.raises(TypeError):
        can_purchase(True, 1)


def test_store_stock_and_buying():
    catalog = load_catalog()
    rng = __import__("random").Random(1)
    state = new_game(catalog, now=1_000, rng=rng)

    assert state["money"] == STARTING_MONEY
    assert len(state["stock"]) == 6
    assert len({item["car_id"] for item in state["stock"]}) == 6
    assert state["restock_at"] == 1_000 + 300

    assert stock_weight(16, 0) == 16
    assert stock_weight(16, 3) == 16
    assert stock_weight(2.5, 0) == 2.5
    assert stock_weight(2.5, 2) == 2.5 * 2

    cheap = min(state["stock"], key=lambda item: item["price"])
    state["money"] = cheap["price"] - 1
    ok, _message = try_buy(state, cheap["stock_id"])
    assert ok is False
    assert len(state["stock"]) == 6

    state["money"] = cheap["price"]
    ok, _message = try_buy(state, cheap["stock_id"])
    assert ok is True
    assert state["money"] == 0
    assert len(state["stock"]) == 5
    assert all(item["stock_id"] != cheap["stock_id"] for item in state["stock"])
    owned = [car for car in state["cars"] if car["uid"] != 1]
    assert len(state["cars"]) == 2
    assert len(owned) == 1
    assert owned[0]["location"] == "garage"

    # The same stock card cannot be bought twice.
    ok, message = try_buy(state, cheap["stock_id"])
    assert ok is False
    assert "no longer" in message

    # A full garage and shop refuse the sale and do not take money.
    state["money"] = 10**12
    while len([car for car in state["cars"] if car["location"] == "garage"]) < GARAGE_CAPACITY:
        state["cars"].append(dict(state["cars"][0], uid=state["next_uid"], location="garage"))
        state["next_uid"] += 1
    while len([car for car in state["cars"] if car["location"] == "shop"]) < SHOP_CAPACITY:
        state["cars"].append(dict(state["cars"][0], uid=state["next_uid"], location="shop"))
        state["next_uid"] += 1
    blocked = state["stock"][0]["stock_id"]
    before = state["money"]
    ok, message = try_buy(state, blocked)
    assert ok is False
    assert state["money"] == before
    assert "full" in message

    refresh_stock(state, catalog, now=2_000, rng=__import__("random").Random(2), announce=True)
    assert len(state["stock"]) == 6
    assert state["restock_at"] == 2_300
    assert state["messages"][0] == "New stock is in the car store."