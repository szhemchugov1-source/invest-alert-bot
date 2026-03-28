import os
import json
import requests
import yfinance as yf

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

WATCHLIST = {
    "QQQM": {
        "name": "QQQM",
        "entry_price": 239.64,
        "levels": [
            {"key": "lvl1", "price": 229.60, "label": "1-й вход"},
            {"key": "lvl2", "price": 222.35, "label": "2-й вход"},
            {"key": "lvl3", "price": 217.50, "label": "3-й вход"},
        ],
    },
    "NVDA": {
        "name": "NVIDIA",
        "entry_price": 172.70,
        "levels": [
            {"key": "lvl1", "price": 162.70, "label": "1-й вход"},
            {"key": "lvl2", "price": 157.60, "label": "2-й вход"},
            {"key": "lvl3", "price": 154.20, "label": "3-й вход"},
        ],
    },
    "PLTR": {
        "name": "Palantir",
        "entry_price": 150.68,
        "levels": [
            {"key": "lvl1", "price": 141.90, "label": "1-й вход"},
            {"key": "lvl2", "price": 137.45, "label": "2-й вход"},
            {"key": "lvl3", "price": 134.45, "label": "3-й вход"},
        ],
    },
    "RKLB": {
        "name": "Rocket Lab",
        "entry_price": 67.23,
        "levels": [
            {"key": "lvl1", "price": 64.95, "label": "1-й вход"},
            {"key": "lvl2", "price": 62.90, "label": "2-й вход"},
            {"key": "lvl3", "price": 61.50, "label": "3-й вход"},
        ],
    },
}

STATE_FILE = "state.json"
DEFAULT_AVAILABLE_CASH = 20

ASSET_WEIGHTS = {
    "QQQM": 0.40,
    "NVDA": 0.30,
    "PLTR": 0.20,
    "RKLB": 0.10,
}

LADDER_WEIGHTS = {
    "lvl1": 0.30,
    "lvl2": 0.30,
    "lvl3": 0.40,
}

MIN_TRADE_USD = 1.50
MIN_SHARES = 0.001
MAX_OPEN_TRADES = 3
MAX_DEVIATION = 0.01  # 1%


def send_message(text: str) -> None:
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    response = requests.post(
        url,
        json={"chat_id": CHAT_ID, "text": text},
        timeout=20,
    )
    response.raise_for_status()


def get_updates(offset=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"

    params = {
        "timeout": 10
    }

    if offset is not None:
        params["offset"] = offset

    response = requests.get(url, params=params, timeout=20)
    response.raise_for_status()
    data = response.json()

    return data.get("result", [])


def get_open_trades_count(state) -> int:
    return sum(
        1 for asset in state["assets"].values()
        if any(asset["levels"].values())
    )


def build_status_message(state) -> str:
    available_cash = float(state["available_cash"])
    open_trades = get_open_trades_count(state)

    lines = [
        "📊 Статус системы",
        f"Кэш: ${available_cash:.2f}",
        f"Макс. открытых сделок: {MAX_OPEN_TRADES}",
        f"Текущих активных сделок: {open_trades}",
        "",
    ]

    for ticker, config in WATCHLIST.items():
        asset_state = state["assets"][ticker]

        active_labels = []
        for level in config["levels"]:
            level_key = level["key"]
            label = level["label"]
            if asset_state["levels"].get(level_key, False):
                active_labels.append(label)

        if active_labels:
            lines.append(f"{ticker}: {', '.join(active_labels)}")
        else:
            lines.append(f"{ticker}: нет активных уровней")

    return "\n".join(lines)


def process_telegram_commands(state):
    changed = False

    last_update_id = state.get("last_update_id", 0)
    updates = get_updates(last_update_id + 1)

    if not updates:
        return changed

    for update in updates:
        update_id = update["update_id"]
        state["last_update_id"] = update_id
        changed = True

        message = update.get("message")
        if not message:
            continue

        text = message.get("text", "").strip()
        print(f"Telegram update received: {text}")

        if not text:
            continue

        chat_id = str(message.get("chat", {}).get("id", ""))

        if str(CHAT_ID) != chat_id:
            continue

        if text.lower() == "/status":
            send_message(build_status_message(state))
            continue

        elif text.lower() == "/status on":
            send_message(
                f"✅ Бот активен\n"
                f"💰 Кэш: ${state.get('available_cash', 0):.2f}\n"
                f"📊 Активов: {len(WATCHLIST)}"
            )
            continue

        elif text.lower().startswith("/cash"):
            parts = text.split()

            if len(parts) < 2:
                send_message("⚠️ Пример команды: /cash 20")
                continue

            try:
                cash_value = float(parts[1])
            except ValueError:
                send_message("⚠️ Введи число. Пример: /cash 20")
                continue

            state["available_cash"] = cash_value
            changed = True

            send_message(f"✅ Кэш обновлён: ${cash_value:.2f}")
            continue

        elif text.lower() == "/trades":
            trades = state.get("trades", {})

            has_trades = any(trades.get(ticker) for ticker in trades)
            if not has_trades:
                send_message("📭 Сделок пока нет")
                continue

            lines = ["📒 Журнал сделок", ""]

            for ticker, ticker_trades in trades.items():
                if not ticker_trades:
                    continue

                for trade in ticker_trades[-5:]:
                    status = trade.get("status", "UNKNOWN")
                    level = trade.get("level", "-")
                    entry = trade.get("entry", "-")
                    shares = trade.get("shares", "-")
                    tp1 = trade.get("tp1", "-")
                    tp2 = trade.get("tp2", "-")
                    sl = trade.get("sl", "-")

                    lines.append(f"{ticker} | {level} | {status}")
                    lines.append(f"Вход: {entry}")
                    lines.append(f"Акции: {shares}")
                    lines.append(f"Цель 1: {tp1}")
                    lines.append(f"Цель 2: {tp2}")
                    lines.append(f"Стоп: {sl}")
                    lines.append("")

            send_message("\n".join(lines))
            continue

    return changed


def get_price(ticker: str) -> float:
    hist = yf.Ticker(ticker).history(period="1d", interval="1m")
    if hist.empty:
        hist = yf.Ticker(ticker).history(period="5d", interval="1d")
    if hist.empty:
        raise ValueError(f"Нет данных по {ticker}")

    return float(hist["Close"].dropna().iloc[-1])


def load_state():
    if not os.path.exists(STATE_FILE):
        state = {
            "available_cash": DEFAULT_AVAILABLE_CASH,
            "last_update_id": None,
            "assets": {},
            "trades": [],
        }

        for ticker, config in WATCHLIST.items():
            state["assets"][ticker] = {
                "levels": {},
                "tp": False,
                "sl": False,
            }

            for level in config["levels"]:
                state["assets"][ticker]["levels"][level["key"]] = False

        return state

    with open(STATE_FILE, "r", encoding="utf-8") as f:
        state = json.load(f)

    if "available_cash" not in state:
        state["available_cash"] = DEFAULT_AVAILABLE_CASH

    if "last_update_id" not in state:
        state["last_update_id"] = None

    if "trades" not in state:
        state["trades"] = []

    if "assets" not in state:
        old_state = state
        state = {
            "available_cash": DEFAULT_AVAILABLE_CASH,
            "last_update_id": None,
            "assets": old_state,
            "trades": [],
        }

    for ticker, config in WATCHLIST.items():
        if ticker not in state["assets"]:
            state["assets"][ticker] = {
                "levels": {},
                "tp": False,
                "sl": False,
            }

        if "levels" not in state["assets"][ticker]:
            state["assets"][ticker]["levels"] = {}

        if "tp" not in state["assets"][ticker]:
            state["assets"][ticker]["tp"] = False

        if "sl" not in state["assets"][ticker]:
            state["assets"][ticker]["sl"] = False

        for level in config["levels"]:
            if level["key"] not in state["assets"][ticker]["levels"]:
                state["assets"][ticker]["levels"][level["key"]] = False

    return state


def save_state(state) -> None:
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def check_entry_levels(state, ticker, config, current_price):
    changed = False

    if "trades" not in state:
        state["trades"] = {}

    if ticker not in state["trades"]:
        state["trades"][ticker] = []

    for level in config.get("levels", []):
        level_key = level["key"]
        level_price = level["price"]

        # Проверяем, не срабатывал ли уже этот уровень
        already_triggered = any(
            t.get("level") == level_key for t in state["trades"][ticker]
        )

        if already_triggered:
            continue

        # Условие входа
        if current_price <= level_price:
            entry_price = current_price

            # === ДВЕ ЦЕЛИ ===
            tp1 = round(entry_price * 1.03, 2)  # +3%
            tp2 = round(entry_price * 1.06, 2)  # +6%
            sl = round(entry_price * 0.97, 2)   # -3%

            trade = {
    "ticker": ticker,
    "entry": entry_price,
    "shares": shares_est,
    "tp1": tp1,
    "tp2": tp2,
    "sl": sl,
    "level": level_key,
    "status": "OPEN"
}

            state["trades"][ticker].append(trade)

            send_message(
                f"🟢 BUY SIGNAL\n\n"
                f"Акция: {ticker}\n"
                f"Цена входа: {entry_price:.2f}\n\n"
                f"Уровень: {level_key}\n\n"
                f"🎯 Цель 1: {tp1}\n"
                f"Действие: ПРОДАТЬ 50%\n\n"
                f"🎯 Цель 2: {tp2}\n"
                f"Действие: ПРОДАТЬ ОСТАТОК\n\n"
                f"🛑 Стоп: {sl}\n"
                f"Действие: ПРОДАТЬ ВСЁ"
            )

            changed = True

    return changed


def check_tp_sl(state, ticker, config, current_price):
    changed = False

    if "trades" not in state:
        return changed

    if ticker not in state["trades"]:
        return changed

    for trade in state["trades"][ticker]:
        if trade.get("status") == "CLOSED":
            continue

        tp1 = trade.get("tp1")
        tp2 = trade.get("tp2")
        sl = trade.get("sl")

        # Цель 1
        if (
            tp1 is not None
            and current_price >= tp1
            and not trade.get("tp1_hit", False)
        ):
            send_message(
                f"🎯 Цель 1 достигнута\n\n"
                f"Акция: {ticker}\n"
                f"Текущая цена: {current_price:.2f}\n"
                f"Цель 1: {tp1}\n"
                f"Действие: ПРОДАТЬ 50%"
            )
            trade["tp1_hit"] = True
            changed = True

        # Цель 2
        if (
            tp2 is not None
            and current_price >= tp2
            and not trade.get("tp2_hit", False)
        ):
            send_message(
                f"🎯 Цель 2 достигнута\n\n"
                f"Акция: {ticker}\n"
                f"Текущая цена: {current_price:.2f}\n"
                f"Цель 2: {tp2}\n"
                f"Действие: ПРОДАТЬ ОСТАТОК"
            )
            trade["tp2_hit"] = True
            trade["status"] = "CLOSED"
            changed = True

        # Стоп
        if (
            sl is not None
            and current_price <= sl
            and not trade.get("sl_hit", False)
            and trade.get("status") != "CLOSED"
        ):
            send_message(
                f"🛑 Стоп достигнут\n\n"
                f"Акция: {ticker}\n"
                f"Текущая цена: {current_price:.2f}\n"
                f"Стоп: {sl}\n"
                f"Действие: ПРОДАТЬ ВСЁ"
            )
            trade["sl_hit"] = True
            trade["status"] = "CLOSED"
            changed = True

    return changed


def main():
    print(f"BOT_TOKEN loaded: {bool(BOT_TOKEN)}")
    print(f"CHAT_ID loaded: {bool(CHAT_ID)}")
    
    if not BOT_TOKEN:
        raise RuntimeError("Не задан BOT_TOKEN")
    if not CHAT_ID:
        raise RuntimeError("Не задан CHAT_ID")

    state = load_state()
    changed_any = False

    if process_telegram_commands(state):
    changed_any = True
    save_state(state)

    for ticker, config in WATCHLIST.items():
        try:
            current_price = get_price(ticker)
            print(f"{ticker}: {current_price:.2f}")
        except Exception as e:
            print(f"Ошибка получения цены {ticker}: {e}")
            continue

        if check_entry_levels(state, ticker, config, current_price):
            changed_any = True

        if check_tp_sl(state, ticker, config, current_price):
            changed_any = True

    if changed_any:
        save_state(state)

if __name__ == "__main__":
    import time

    while True:
        try:
            main()
        except Exception as e:
            print(f"Ошибка: {e}")
        time.sleep(5)
