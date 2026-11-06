"""Desktop window for the car trading simulator.
"""

import tkinter as tk
from pathlib import Path

from project import (
    GARAGE_CAPACITY,
    SHOP_CAPACITY,
    STORE_SLOTS,
    cars_in,
    collection_net_worth,
    format_money,
    load_catalog,
    load_state,
    move_car,
    rarity_label,
    redeem_creator_code,
    refresh_stock,
    release_car,
    save_state,
    set_for_sale,
    spawn_customer,
    try_buy,
    answer_offer,
    buy_upgrade,
    calculate_sell_range,
    drop_expired_offers,
    UPGRADE_INFO,
)

ASSETS = Path(__file__).resolve().parent / "assets" / "cars"

BG = "#161a1f"
PANEL = "#222831"
CARD = "#2c3440"
TEXT = "#f4f6f8"
MUTED = "#a8b0ba"
ACCENT = "#3b82f6"
ACCENT_ACTIVE = "#2563eb"
MONEY = "#86efac"
WARN = "#fbbf24"

NAV = (
    ("creator", "Creator Code"),
    ("upgrades", "Upgrades"),
    ("store", "Car Store"),
    ("garage", "Garage"),
    ("shop", "My Shop"),
    ("messages", "Messages"),
)


class SimulatorApp:
    """One window. The left bar switches the page on the right."""

    def __init__(self, root, catalog):
        self.root = root
        self.catalog = catalog
        self.state = load_state(catalog)
        self.page = "store"
        self.nav_buttons = {}
        self.photos = []
        self.timer_label = None
        self._after_id = None

        root.title("Car Trading Simulator")
        root.geometry("1100x700")
        root.minsize(960, 640)
        root.configure(bg=BG)
        root.protocol("WM_DELETE_WINDOW", self.close)

        self._build_header()
        self._build_nav()
        self.content = tk.Frame(root, bg=BG)
        self.content.pack(side="left", fill="both", expand=True, padx=(0, 16), pady=(0, 8))
        self._build_status()
        self.show_page("store")
        self._after_id = root.after(1000, self._tick)

    def _build_header(self):
        header = tk.Frame(self.root, bg=PANEL, height=64)
        header.pack(side="top", fill="x")
        header.pack_propagate(False)

        tk.Label(
            header,
            text="Car Trading Simulator",
            bg=PANEL,
            fg=TEXT,
            font=("TkDefaultFont", 16, "bold"),
        ).pack(side="left", padx=20)

        self.money_label = tk.Label(
            header,
            text="",
            bg=PANEL,
            fg=MONEY,
            font=("TkDefaultFont", 16, "bold"),
        )
        self.money_label.pack(side="right", padx=20)
        self.refresh_money()

    def _build_nav(self):
        nav = tk.Frame(self.root, bg=PANEL, width=180)
        nav.pack(side="left", fill="y", padx=(0, 12), pady=12)
        nav.pack_propagate(False)

        for key, label in NAV:
            button = tk.Button(
                nav,
                text=label,
                command=lambda name=key: self.show_page(name),
                bg=CARD,
                fg=TEXT,
                activebackground=ACCENT,
                activeforeground=TEXT,
                relief="flat",
                font=("TkDefaultFont", 11),
                anchor="w",
                padx=14,
                pady=10,
            )
            button.pack(fill="x", padx=12, pady=4)
            self.nav_buttons[key] = button

    def _build_status(self):
        self.status = tk.Label(
            self.root,
            text="",
            bg=BG,
            fg=MUTED,
            anchor="w",
            font=("TkDefaultFont", 10),
        )
        self.status.pack(side="bottom", fill="x", padx=16, pady=(0, 8))

    def close(self):
        """Cancel the countdown callback so closing the window does not leave one running."""
        if self._after_id is not None:
            self.root.after_cancel(self._after_id)
            self._after_id = None
        self._persist()
        self.root.destroy()

    def _persist(self):
        save_state(self.state)

    def _tick(self):
        """One-second timer for restock, customers, and offer expiry."""
        import time

        now = time.time()
        changed = False
        if now >= self.state["restock_at"]:
            refresh_stock(self.state, self.catalog, now=now, announce=True)
            self.set_status("New stock is available.")
            changed = True
        if drop_expired_offers(self.state, now):
            self.state["messages"].insert(0, "A customer offer expired.")
            self.set_status("A customer offer expired.")
            changed = True
        if now >= self.state["customer_at"]:
            _ok, message = spawn_customer(self.state, now)
            self.set_status(message)
            changed = True
        if self.timer_label is not None:
            self.timer_label.configure(text=self._timer_text())
        if changed:
            self._persist()
            if self.page in ("store", "messages", "shop", "garage"):
                self.show_page(self.page)
        self._after_id = self.root.after(1000, self._tick)

    def set_status(self, text):
        self.status.configure(text=text)

    def _timer_text(self):
        import time

        remaining = int(self.state["restock_at"] - time.time())
        if remaining < 0:
            remaining = 0
        return f"New stock in {remaining // 60}:{remaining % 60:02d}"

    def _buy(self, stock_id):
        ok, message = try_buy(self.state, stock_id)
        if ok:
            self.state["messages"].insert(0, message)
        self.refresh_money()
        self.set_status(message)
        self._persist()
        self.show_page("store")

    def refresh_money(self):
        self.money_label.configure(text="Balance  " + format_money(self.state["money"]))

    def show_page(self, name):
        self.page = name
        self.timer_label = None
        self.photos = []
        for key, button in self.nav_buttons.items():
            if key == name:
                button.configure(bg=ACCENT, activebackground=ACCENT_ACTIVE)
            else:
                button.configure(bg=CARD, activebackground=ACCENT)

        for child in self.content.winfo_children():
            child.destroy()

        builders = {
            "creator": self._page_creator,
            "upgrades": self._page_upgrades,
            "store": self._page_store,
            "garage": self._page_garage,
            "shop": self._page_shop,
            "messages": self._page_messages,
        }
        builders[name]()

    def _heading(self, title, subtitle):
        tk.Label(
            self.content,
            text=title,
            bg=BG,
            fg=TEXT,
            font=("TkDefaultFont", 20, "bold"),
            anchor="w",
        ).pack(fill="x", pady=(8, 0))
        tk.Label(
            self.content,
            text=subtitle,
            bg=BG,
            fg=MUTED,
            font=("TkDefaultFont", 11),
            anchor="w",
            justify="left",
        ).pack(fill="x", pady=(2, 12))

    def _page_garage(self):
        garage = cars_in(self.state, "garage")
        worth = collection_net_worth(garage)
        self._heading(
            "Garage",
            f"{len(garage)} / {GARAGE_CAPACITY} cars. "
            f"Collection net worth {format_money(worth)}.",
        )
        if not garage:
            self._empty("The garage is empty.")
            return
        for car in garage:
            self._car_row(car, "garage")
        if garage:
            average = sum(car["spawn_chance"] for car in garage) / len(garage)
            self.set_status(f"Average spawn probability {average:.2f}%.")
        else:
            self.set_status("The garage is empty.")

    def _page_shop(self):
        shop = cars_in(self.state, "shop")
        self._heading(
            "My Shop",
            f"{len(shop)} / {SHOP_CAPACITY} cars. "
            "Customers will buy from cars you list here.",
        )
        if not shop:
            self._empty("Your shop is empty. Move a car here from the garage.")
        else:
            for car in shop:
                self._shop_card(car)
        self.set_status("Select an action on a car. Listed cars can be sold to customers.")

    def _page_store(self):
        self._heading("Car Store", "Six cars, weighted by spawn chance. Buying one removes it until the next refresh.")
        self.timer_label = tk.Label(
            self.content,
            text=self._timer_text(),
            bg=BG,
            fg=WARN,
            font=("TkDefaultFont", 12, "bold"),
            anchor="w",
        )
        self.timer_label.pack(fill="x", pady=(0, 8))

        if not self.state["stock"]:
            self._empty("The store is empty.")
            return

        grid = tk.Frame(self.content, bg=BG)
        grid.pack(fill="both", expand=True)
        for index, item in enumerate(self.state["stock"]):
            card = tk.Frame(grid, bg=CARD, padx=10, pady=10)
            card.grid(row=index // 3, column=index % 3, padx=6, pady=6, sticky="nsew")
            self._stock_image(card, item)
            tk.Label(
                card,
                text=item["name"],
                bg=CARD,
                fg=TEXT,
                font=("TkDefaultFont", 12, "bold"),
                anchor="w",
            ).pack(fill="x", pady=(8, 0))
            tk.Label(
                card,
                text=(
                    f"{rarity_label(item['spawn_chance'])}"
                    f"  ·  {item['spawn_chance']:g}% spawn"
                    f"\n{format_money(item['price'])}"
                ),
                bg=CARD,
                fg=MUTED,
                justify="left",
                anchor="w",
            ).pack(fill="x", pady=(2, 8))
            tk.Button(
                card,
                text="Buy",
                command=lambda stock_id=item["stock_id"]: self._buy(stock_id),
                bg=ACCENT,
                fg=TEXT,
                activebackground=ACCENT_ACTIVE,
                activeforeground=TEXT,
                relief="flat",
                padx=10,
                pady=4,
            ).pack(anchor="w")
        self.set_status("Bought cars go to the garage, or to the shop if the garage is full.")

    def _stock_image(self, card, item):
        photo = self._load_photo(item["car_id"])
        if photo is not None:
            tk.Label(card, image=photo, bg=CARD).pack()
            return
        box = tk.Frame(card, bg="#1a1f26", width=220, height=100)
        box.pack()
        box.pack_propagate(False)
        tk.Label(
            box,
            text="No image\n" + item["car_id"],
            bg="#1a1f26",
            fg=MUTED,
            justify="center",
        ).pack(expand=True)

    def _load_photo(self, car_id):
        """Resize with thumbnail so the picture keeps its proportions."""
        path = ASSETS / f"{car_id}.png"
        if not path.is_file():
            return None
        try:
            from PIL import Image, ImageTk

            image = Image.open(path)
            image.thumbnail((220, 110))
            photo = ImageTk.PhotoImage(image)
        except Exception:
            return None
        self.photos.append(photo)
        return photo

    def _page_upgrades(self):
        self._heading("Upgrades", "Each purchase raises one level. The balance is in the header.")
        for key, info in UPGRADE_INFO.items():
            level = self.state["upgrades"][key]
            row = tk.Frame(self.content, bg=CARD, padx=14, pady=10)
            row.pack(fill="x", pady=4)
            if level >= info["max"]:
                cost = "Maximum level"
            else:
                cost = "Next " + format_money(info["costs"][level])
            tk.Label(
                row,
                text=f"{info['name']}\nLevel {level} / {info['max']}  ·  {info['effect']}\n{cost}",
                bg=CARD,
                fg=TEXT,
                justify="left",
                anchor="w",
            ).pack(side="left")
            tk.Button(
                row,
                text="Buy",
                command=lambda name=key: self._buy_upgrade(name),
                bg=ACCENT,
                fg=TEXT,
                activebackground=ACCENT_ACTIVE,
                activeforeground=TEXT,
                relief="flat",
                padx=10,
                pady=4,
            ).pack(side="right")
        self.set_status("Upgrades are saved with the rest of the game.")

    def _buy_upgrade(self, key):
        ok, message = buy_upgrade(self.state, key)
        self.refresh_money()
        self.set_status(message)
        if ok:
            self.state["messages"].insert(0, message)
            self._persist()
        self.show_page("upgrades")

    def _page_creator(self):
        self._heading(
            "Creator Code",
            "Enter a code and confirm it. Redemption is not active in this stage.",
        )
        box = tk.Frame(self.content, bg=BG)
        box.pack(anchor="w")
        entry = tk.Entry(box, width=24, font=("TkDefaultFont", 12))
        entry.pack(side="left", padx=(0, 8))
        tk.Button(
            box,
            text="Confirm",
            command=lambda: self._redeem(entry.get()),
            bg=ACCENT,
            fg=TEXT,
            activebackground=ACCENT_ACTIVE,
            activeforeground=TEXT,
            relief="flat",
            padx=12,
            pady=6,
        ).pack(side="left")
        if self.state["code_redeemed"]:
            self.set_status("This save has already redeemed a creator code.")
        else:
            self.set_status("The code can be redeemed once per save.")

    def _redeem(self, code):
        ok, message = redeem_creator_code(self.state, code)
        self.refresh_money()
        self.set_status(message)
        if ok:
            self.state["messages"].insert(0, "Creator code redeemed.")
            self._persist()
        self.show_page("creator")

    def _page_messages(self):
        import time

        self._heading("Messages", "Type yes or no for the current customer. The price is hidden until you accept.")
        if self.state["offers"]:
            offer = self.state["offers"][0]
            left = max(0, int(offer["expires_at"] - time.time()))
            tk.Label(
                self.content,
                text=f"Offer for {offer['name']}  ·  {left}s left",
                bg=BG,
                fg=WARN,
                anchor="w",
            ).pack(fill="x", pady=(0, 8))
            box = tk.Frame(self.content, bg=BG)
            box.pack(anchor="w", pady=(0, 8))
            entry = tk.Entry(box, width=16, font=("TkDefaultFont", 12))
            entry.pack(side="left", padx=(0, 8))
            tk.Button(
                box,
                text="Answer",
                command=lambda: self._answer(entry.get()),
                bg=ACCENT,
                fg=TEXT,
                relief="flat",
                padx=10,
                pady=4,
            ).pack(side="left")
        for text in self.state["messages"][:12]:
            row = tk.Frame(self.content, bg=CARD, padx=14, pady=8)
            row.pack(fill="x", pady=3)
            tk.Label(row, text=text, bg=CARD, fg=TEXT, anchor="w", justify="left", wraplength=720).pack(fill="x")
        self.set_status("Yes accepts the hidden price. No keeps the car listed.")

    def _answer(self, text):
        ok, message = answer_offer(self.state, text)
        self.refresh_money()
        self.set_status(message)
        if ok:
            self._persist()
        self.show_page("messages")

    def _car_row(self, car, origin):
        row = tk.Frame(self.content, bg=CARD, padx=14, pady=10)
        row.pack(fill="x", pady=4)
        tk.Label(
            row,
            text=car["name"],
            bg=CARD,
            fg=TEXT,
            font=("TkDefaultFont", 12, "bold"),
            anchor="w",
        ).pack(side="left")
        detail = (
            f"{rarity_label(car['spawn_chance'])}"
            f"   ·   spawn {car['spawn_chance']:g}%"
            f"   ·   value {format_money(car['market_value'])}"
        )
        tk.Label(row, text=detail, bg=CARD, fg=MUTED).pack(side="left", padx=12)
        if origin == "garage":
            tk.Button(
                row,
                text="Move to shop",
                command=lambda uid=car["uid"]: self._move(uid, "shop"),
                bg=ACCENT,
                fg=TEXT,
                relief="flat",
            ).pack(side="right")

    def _shop_card(self, car):
        low, high = calculate_sell_range(car["purchase_price"], self.state["upgrades"]["prices"])
        row = tk.Frame(self.content, bg=CARD, padx=14, pady=10)
        row.pack(fill="x", pady=4)
        flag = "For sale" if car["listed"] else "Not listed"
        tk.Label(
            row,
            text=(
                f"{car['name']}  ·  {rarity_label(car['spawn_chance'])}  ·  {flag}\n"
                f"Paid {format_money(car['purchase_price'])}  ·  value {format_money(car['market_value'])}"
            ),
            bg=CARD,
            fg=TEXT,
            justify="left",
            anchor="w",
        ).pack(side="left")
        actions = tk.Frame(row, bg=CARD)
        actions.pack(side="right")
        self._small(actions, "Price range", lambda: self.set_status(
            f"{car['name']} can sell for {format_money(low)} to {format_money(high)}."
        ))
        self._small(actions, "To garage", lambda uid=car["uid"]: self._move(uid, "garage"))
        self._small(actions, "Sell", lambda uid=car["uid"]: self._list(uid, True))
        self._small(actions, "Unlist", lambda uid=car["uid"]: self._list(uid, False))
        self._small(actions, "Release", lambda uid=car["uid"]: self._release(uid))

    def _small(self, parent, text, command):
        tk.Button(parent, text=text, command=command, bg="#3a4454", fg=TEXT, relief="flat", padx=6).pack(side="left", padx=2)

    def _move(self, uid, destination):
        ok, message = move_car(self.state, uid, destination)
        self.set_status(message)
        if ok:
            self.state["messages"].insert(0, message)
            self._persist()
        self.show_page("garage" if destination == "garage" else "shop")

    def _list(self, uid, listed):
        ok, message = set_for_sale(self.state, uid, listed)
        self.set_status(message)
        if ok:
            self._persist()
        self.show_page("shop")

    def _release(self, uid):
        ok, message = release_car(self.state, uid)
        self.refresh_money()
        self.set_status(message)
        if ok:
            self.state["messages"].insert(0, message)
            self._persist()
        self.show_page("shop")

    def _empty(self, text):
        tk.Label(
            self.content,
            text=text,
            bg=BG,
            fg=MUTED,
            font=("TkDefaultFont", 12),
            anchor="w",
        ).pack(fill="x")


def run_game():
    """Open the window. Importing this module does not start the program."""
    catalog = load_catalog()
    root = tk.Tk()
    SimulatorApp(root, catalog)
    root.mainloop()