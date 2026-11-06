"""Car Trading Simulator — CS50P final project.
"""

import json
import random
import time
from pathlib import Path


STARTING_MONEY = 120_000
STARTER_CAR_ID = "ford"
SHOP_CAPACITY = 8
GARAGE_CAPACITY = 20
STORE_SLOTS = 6

BASE_RESTOCK_SECONDS = 300
RESTOCK_SECONDS_PER_LEVEL = 30
MIN_RESTOCK_SECONDS = 60
MAX_RESTOCK_UPGRADE_LEVEL = 5

RARE_SPAWN_BELOW = 5
RARE_WEIGHT_STEP = 0.5
MAX_RARE_UPGRADE_LEVEL = 5

BASE_SELL_MIN_PERCENT = 70
BASE_SELL_MAX_PERCENT = 130
SELL_PERCENT_PER_LEVEL = 5
MAX_PRICE_UPGRADE_LEVEL = 5

DATA_PATH = Path(__file__).resolve().parent / "data" / "cars.json"


def main():
    """Open the desktop window. Tests never call this."""
    from interface import run_game

    run_game()


def format_money(amount):
    """Show every digit. Commas are separators, not scientific notation."""
    if isinstance(amount, bool) or not isinstance(amount, int):
        raise TypeError("amount must be an int")
    return "$" + format(amount, ",")


def rarity_label(spawn_chance):
    """Turn a spawn percentage into a short rarity name."""
    chance = float(spawn_chance)
    if chance >= 10:
        return "Common"
    if chance >= 5:
        return "Uncommon"
    if chance >= 2:
        return "Rare"
    if chance >= 1:
        return "Very Rare"
    return "Legendary"


def make_owned_car(catalog_car, uid, location):
    """Copy one catalog row into a car the player actually owns.

    purchase_price is the catalog price, even for the free starter car.
    Releasing a car later pays 50% of that number. market_value starts equal
    to the purchase price until selling upgrades exist.
    """
    price = int(catalog_car["price"])
    return {
        "uid": uid,
        "car_id": catalog_car["id"],
        "name": catalog_car["name"],
        "purchase_price": price,
        "market_value": price,
        "spawn_chance": float(catalog_car["spawn_chance"]),
        "location": location,
        "listed": False,
    }


def new_game(catalog, now=None, rng=None):
    """Build the starting save in memory. Nothing is written to disk yet."""
    starter = None
    for car in catalog:
        if car["id"] == STARTER_CAR_ID:
            starter = car
            break
    if starter is None:
        raise ValueError(f"starter car {STARTER_CAR_ID!r} is not in the catalog")

    state = {
        "money": STARTING_MONEY,
        "next_uid": 2,
        "next_stock_id": 1,
        "cars": [make_owned_car(starter, 1, "garage")],
        "messages": [
            f"New game. Balance {format_money(STARTING_MONEY)}. "
            "The Ford is in your garage, and your shop is empty.",
        ],
        "upgrades": {"rare": 0, "restock": 0, "customers": 0, "prices": 0},
        "stock": [],
        "restock_at": 0,
        "offers": [],
        "next_offer_id": 1,
        "customer_at": 0,
        "code_redeemed": False,
    }
    if now is None:
        now = time.time()
    refresh_stock(state, catalog, now=now, rng=rng, announce=False)
    state["customer_at"] = now + customer_seconds(0)
    return state


def load_catalog(path=DATA_PATH):
    """Load the editable car list. Ids match image filenames without the extension."""
    with open(path, encoding="utf-8") as handle:
        payload = json.load(handle)
    cars = payload["cars"]
    if not cars:
        raise ValueError("car catalog is empty")
    return cars


def restock_seconds(restock_upgrade_level=0):
    """Seconds between store refreshes. Higher upgrade levels are shorter."""
    if isinstance(restock_upgrade_level, bool) or not isinstance(restock_upgrade_level, int):
        raise TypeError("restock_upgrade_level must be an int")
    if not 0 <= restock_upgrade_level <= MAX_RESTOCK_UPGRADE_LEVEL:
        raise ValueError("restock_upgrade_level is out of range")
    seconds = BASE_RESTOCK_SECONDS - restock_upgrade_level * RESTOCK_SECONDS_PER_LEVEL
    if seconds < MIN_RESTOCK_SECONDS:
        return MIN_RESTOCK_SECONDS
    return seconds


def stock_weight(spawn_chance, rare_upgrade_level=0):
    """Weight used when rolling store stock.

    Common cars keep their catalog chance. Cars under RARE_SPAWN_BELOW get
    heavier as upgrade 1 goes up. Level 0 leaves the catalog chances alone.
    """
    if isinstance(rare_upgrade_level, bool) or not isinstance(rare_upgrade_level, int):
        raise TypeError("rare_upgrade_level must be an int")
    if not 0 <= rare_upgrade_level <= MAX_RARE_UPGRADE_LEVEL:
        raise ValueError("rare_upgrade_level is out of range")
    weight = float(spawn_chance)
    if weight <= 0:
        raise ValueError("spawn_chance must be positive")
    if weight < RARE_SPAWN_BELOW:
        weight = weight * (1 + rare_upgrade_level * RARE_WEIGHT_STEP)
    return weight


def generate_stock(catalog, slots, rare_upgrade_level, first_stock_id, rng=None):
    """Pick up to `slots` different cars. A model appears at most once per stock."""
    if slots < 1:
        raise ValueError("slots must be positive")
    if not catalog:
        raise ValueError("catalog is empty")
    rng = random if rng is None else rng
    pool = list(catalog)
    stock = []
    count = min(slots, len(pool))
    next_id = first_stock_id
    for _ in range(count):
        weights = [stock_weight(car["spawn_chance"], rare_upgrade_level) for car in pool]
        picked = rng.choices(pool, weights=weights, k=1)[0]
        pool.remove(picked)
        stock.append(
            {
                "stock_id": next_id,
                "car_id": picked["id"],
                "name": picked["name"],
                "price": int(picked["price"]),
                "spawn_chance": float(picked["spawn_chance"]),
            }
        )
        next_id += 1
    return stock, next_id


def refresh_stock(state, catalog, now=None, rng=None, announce=True):
    """Replace the current store stock and start the next countdown."""
    if now is None:
        now = time.time()
    stock, next_id = generate_stock(
        catalog,
        STORE_SLOTS,
        state["upgrades"]["rare"],
        state["next_stock_id"],
        rng,
    )
    state["stock"] = stock
    state["next_stock_id"] = next_id
    state["restock_at"] = now + restock_seconds(state["upgrades"]["restock"])
    if announce:
        state["messages"].insert(0, "New stock is in the car store.")
    return state


def cars_in(state, location):
    """Cars sitting in the garage or the shop."""
    return [car for car in state["cars"] if car["location"] == location]


def try_buy(state, stock_id):
    """Buy one stock card if it is still there, affordable, and there is room.

    The car goes to the garage when there is space, otherwise to the shop.
    Money is only taken after both checks pass. Returns (ok, message).
    """
    item = None
    for stock_item in state["stock"]:
        if stock_item["stock_id"] == stock_id:
            item = stock_item
            break
    if item is None:
        return False, "That car is no longer in stock."
    if not can_purchase(state["money"], item["price"]):
        return False, f"Not enough money to buy the {item['name']}."
    if len(cars_in(state, "garage")) < GARAGE_CAPACITY:
        location = "garage"
    elif len(cars_in(state, "shop")) < SHOP_CAPACITY:
        location = "shop"
    else:
        return False, "The garage and the shop are both full."

    state["money"] -= item["price"]
    state["stock"] = [row for row in state["stock"] if row["stock_id"] != stock_id]
    owned = make_owned_car(
        {
            "id": item["car_id"],
            "name": item["name"],
            "price": item["price"],
            "spawn_chance": item["spawn_chance"],
        },
        state["next_uid"],
        location,
    )
    state["next_uid"] += 1
    state["cars"].append(owned)
    return True, f"Bought the {item['name']} for {format_money(item['price'])}."


CREATOR_CODE = "123456789"
CREATOR_BALANCE = 100000000000000000000000
BASE_CUSTOMER_SECONDS = 240
CUSTOMER_SECONDS_PER_LEVEL = 30
MIN_CUSTOMER_SECONDS = 60
MAX_CUSTOMER_UPGRADE_LEVEL = 5
OFFER_SECONDS = 120
SAVE_PATH = Path(__file__).resolve().parent / "saves" / "save.json"

UPGRADE_INFO = {
    "rare": {
        "name": "Better Rare Car Chances",
        "max": MAX_RARE_UPGRADE_LEVEL,
        "costs": [10_000, 25_000, 60_000, 150_000, 400_000],
        "effect": "Rare cars are more likely in the store.",
    },
    "restock": {
        "name": "Faster Restocking",
        "max": MAX_RESTOCK_UPGRADE_LEVEL,
        "costs": [8_000, 20_000, 50_000, 120_000, 300_000],
        "effect": "The store refreshes 30 seconds sooner per level.",
    },
    "customers": {
        "name": "Faster Customers",
        "max": MAX_CUSTOMER_UPGRADE_LEVEL,
        "costs": [8_000, 20_000, 50_000, 120_000, 300_000],
        "effect": "Customers arrive 30 seconds sooner per level.",
    },
    "prices": {
        "name": "Better Selling Prices",
        "max": MAX_PRICE_UPGRADE_LEVEL,
        "costs": [12_000, 30_000, 75_000, 180_000, 450_000],
        "effect": "Offer ranges rise by 5 points per level.",
    },
}


def customer_seconds(level=0):
    """Seconds between customer visits."""
    if isinstance(level, bool) or not isinstance(level, int):
        raise TypeError("level must be an int")
    if not 0 <= level <= MAX_CUSTOMER_UPGRADE_LEVEL:
        raise ValueError("level is out of range")
    seconds = BASE_CUSTOMER_SECONDS - level * CUSTOMER_SECONDS_PER_LEVEL
    return max(MIN_CUSTOMER_SECONDS, seconds)


def find_car(state, uid):
    for car in state["cars"]:
        if car["uid"] == uid:
            return car
    return None


def move_car(state, uid, destination):
    """Move a car between the garage and the shop. It cannot be in both."""
    if destination not in ("garage", "shop"):
        return False, "Unknown destination."
    car = find_car(state, uid)
    if car is None:
        return False, "That car is not in your collection."
    if car["location"] == destination:
        return False, "That car is already there."
    limit = GARAGE_CAPACITY if destination == "garage" else SHOP_CAPACITY
    if len(cars_in(state, destination)) >= limit:
        return False, f"The {destination} is full."
    car["location"] = destination
    if destination == "garage":
        car["listed"] = False
        _drop_offers_for(state, uid)
    return True, f"Moved the {car['name']} to the {destination}."


def set_for_sale(state, uid, listed):
    car = find_car(state, uid)
    if car is None or car["location"] != "shop":
        return False, "Only a car in My Shop can be listed."
    car["listed"] = bool(listed)
    if not listed:
        _drop_offers_for(state, uid)
        return True, f"The {car['name']} is no longer for sale."
    return True, f"The {car['name']} is for sale."


def release_car(state, uid):
    """Remove a shop car and refund half the original purchase price."""
    car = find_car(state, uid)
    if car is None or car["location"] != "shop":
        return False, "Release cars from My Shop."
    refund = car["purchase_price"] // 2
    state["money"] += refund
    _drop_offers_for(state, uid)
    state["cars"] = [row for row in state["cars"] if row["uid"] != uid]
    return True, f"Released the {car['name']} for {format_money(refund)}."


def _drop_offers_for(state, uid):
    state["offers"] = [offer for offer in state["offers"] if offer["uid"] != uid]


def drop_expired_offers(state, now):
    before = len(state["offers"])
    state["offers"] = [offer for offer in state["offers"] if offer["expires_at"] > now]
    return before != len(state["offers"])


def spawn_customer(state, now, rng=None):
    """One offer at a time, for a listed shop car. The price stays hidden."""
    rng = random if rng is None else rng
    state["customer_at"] = now + customer_seconds(state["upgrades"]["customers"])
    if state["offers"]:
        return False, "A customer is already waiting."
    listed = [car for car in cars_in(state, "shop") if car["listed"]]
    if not listed:
        return False, "A customer looked around, but nothing is for sale."
    car = rng.choice(listed)
    offer = {
        "offer_id": state["next_offer_id"],
        "uid": car["uid"],
        "name": car["name"],
        "expires_at": now + OFFER_SECONDS,
    }
    state["next_offer_id"] += 1
    state["offers"].append(offer)
    message = f"A customer wants your {car['name']}. Type yes or no. You have {OFFER_SECONDS} seconds."
    state["messages"].insert(0, message)
    return True, message


def answer_offer(state, text, rng=None):
    """Accept with 'yes' or decline with 'no'. Anything else is invalid."""
    rng = random if rng is None else rng
    if not state["offers"]:
        return False, "There is no offer to answer."
    word = text.strip().lower()
    offer = state["offers"][0]
    car = find_car(state, offer["uid"])
    if car is None or not car["listed"] or car["location"] != "shop":
        state["offers"] = [row for row in state["offers"] if row["offer_id"] != offer["offer_id"]]
        return False, "That offer is no longer available."
    if word == "no":
        state["offers"] = [row for row in state["offers"] if row["offer_id"] != offer["offer_id"]]
        message = f"You declined the offer for the {car['name']}."
        state["messages"].insert(0, message)
        return True, message
    if word != "yes":
        return False, "Type yes to accept or no to decline."
    low, high = calculate_sell_range(car["purchase_price"], state["upgrades"]["prices"])
    paid = rng.randint(low, high)
    state["money"] += paid
    state["offers"] = [row for row in state["offers"] if row["offer_id"] != offer["offer_id"]]
    state["cars"] = [row for row in state["cars"] if row["uid"] != car["uid"]]
    message = f"Sold the {car['name']} for {format_money(paid)}."
    state["messages"].insert(0, message)
    return True, message


def buy_upgrade(state, key):
    info = UPGRADE_INFO.get(key)
    if info is None:
        return False, "Unknown upgrade."
    level = state["upgrades"][key]
    if level >= info["max"]:
        return False, f"{info['name']} is already at the maximum level."
    cost = info["costs"][level]
    if not can_purchase(state["money"], cost):
        return False, f"Not enough money. {info['name']} costs {format_money(cost)}."
    state["money"] -= cost
    state["upgrades"][key] = level + 1
    if key == "prices":
        for car in state["cars"]:
            low, high = calculate_sell_range(car["purchase_price"], state["upgrades"]["prices"])
            car["market_value"] = (low + high) // 2
    return True, f"{info['name']} is now level {level + 1}."


def redeem_creator_code(state, code):
    """Set the balance once. The value stays a Python int."""
    if state["code_redeemed"]:
        return False, "That code was already redeemed on this save."
    if code.strip() != CREATOR_CODE:
        return False, "That code is not valid."
    state["money"] = CREATOR_BALANCE
    state["code_redeemed"] = True
    return True, "Creator code accepted."


def save_state(state, path=SAVE_PATH):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state), encoding="utf-8")


def load_state(catalog, path=SAVE_PATH, now=None, rng=None):
    """Load a save, or start a new game if the file is missing or unreadable."""
    path = Path(path)
    if not path.is_file():
        return new_game(catalog, now=now, rng=rng)
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
        state["money"] = int(state["money"])
        if "offers" not in state or "upgrades" not in state or "cars" not in state:
            raise ValueError("save is incomplete")
    except (OSError, ValueError, KeyError, json.JSONDecodeError, TypeError):
        state = new_game(catalog, now=now, rng=rng)
        state["messages"].insert(0, "The save file could not be read. Started a new game.")
    return state


def calculate_sell_range(purchase_price, price_upgrade_level=0):
    """Return (minimum, maximum) whole-dollar prices a customer may pay.

    purchase_price is the amount the player originally paid, kept as an int.
    price_upgrade_level is upgrade 4, from 0 up to MAX_PRICE_UPGRADE_LEVEL.
    The range is a percent of the purchase price so rare cars stay expensive
    and common cars stay cheap. Money is never converted to float.
    """
    if isinstance(purchase_price, bool) or not isinstance(purchase_price, int):
        raise TypeError("purchase_price must be an int")
    if isinstance(price_upgrade_level, bool) or not isinstance(price_upgrade_level, int):
        raise TypeError("price_upgrade_level must be an int")
    if purchase_price <= 0:
        raise ValueError("purchase_price must be positive")
    if not 0 <= price_upgrade_level <= MAX_PRICE_UPGRADE_LEVEL:
        raise ValueError("price_upgrade_level is out of range")

    bonus = price_upgrade_level * SELL_PERCENT_PER_LEVEL
    min_percent = BASE_SELL_MIN_PERCENT + bonus
    max_percent = BASE_SELL_MAX_PERCENT + bonus
    low = (purchase_price * min_percent) // 100
    high = (purchase_price * max_percent) // 100
    if low < 1:
        low = 1
    if high < low:
        high = low
    return low, high


def collection_net_worth(cars):
    """Add up the estimated market value of every car in a collection.

    Each car is a dict with an integer "market_value". An empty collection
    is worth 0. This is the garage "Collection Net Worth" figure.
    """
    if not isinstance(cars, list):
        raise TypeError("cars must be a list")
    total = 0
    for car in cars:
        value = car["market_value"]
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError("market_value must be an int")
        if value < 0:
            raise ValueError("market_value cannot be negative")
        total += value
    return total


def can_purchase(balance, price):
    """Return True only when the player can pay `price` from `balance`.

    Both values must be real ints (bool is rejected). A price of 0 or less
    is not a purchase. This is the check used before buying a car or an upgrade.
    """
    if isinstance(balance, bool) or not isinstance(balance, int):
        raise TypeError("balance must be an int")
    if isinstance(price, bool) or not isinstance(price, int):
        raise TypeError("price must be an int")
    if price <= 0:
        return False
    return balance >= price


if __name__ == "__main__":
    main()