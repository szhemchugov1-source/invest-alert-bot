import os
import requests
import yfinance as yf

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

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


def send_message(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    response = requests.post(
        url,
        json={"chat_id": CHAT_ID, "text": text},
        timeout=20,
    )
    response.raise_for_status()


def get_price(ticker):
    hist = yf.Ticker(ticker).history(period="1d", interval="1m")
    if hist.empty:
        hist = yf.Ticker(ticker).history(period="5d", interval="1d")
    if hist.empty:
        raise ValueError(f"Нет данных по {ticker}")
    return float(hist["Close"].dropna().iloc[-1])


def load_state():
    if not os.path.exists(STATE_FILE):
        state = {}

        for ticker, config in WATCHLIST.items():
            state[ticker] = {
                "levels": {},
                "tp": False,
                "sl": False,
            }

            for level in config["levels"]:
                state[ticker]["levels"][level["key"]] = False

        return state

    import json
    with open(STATE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_state(state):
    import json
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def check_entry_levels(state, ticker, config, current_price):
    changed = False

    for level in config["levels"]:
        level_key = level["key"]
        trigger_price = level["price"]
        label = level["label"]

        if current_price <= trigger_price and not state[ticker]["levels"][level_key]:
            send_message(
                f"🚨 Сигнал по системе\n"
                f"{config['name']} ({ticker})\n"
                f"Уровень: {label}\n"
                f"Текущая цена: {current_price:.2f}\n"
                f"Цена уровня: {trigger_price:.2f}\n"
                f"Действие: напиши в чат — купить / ждать / пропустить"
            )
            state[ticker]["levels"][level_key] = True
            changed = True

        elif current_price > trigger_price and state[ticker]["levels"][level_key]:
            state[ticker]["levels"][level_key] = False
            changed = True

    return changed


def check_tp_sl(state, ticker, config, current_price):
    changed = False

    entry_price = config["entry_price"]
    tp_price = round(entry_price * 1.20, 2)
    sl_price = round(entry_price * 0.85, 2)

    if current_price >= tp_price and not state[ticker]["tp"]:
        send_message(
            f"💰 ФИКСАЦИЯ ПРИБЫЛИ\n"
f"{config['name']} ({ticker})\n"
f"Текущая цена: {current_price:.2f}\n"
f"Цель +20%: {tp_price:.2f}\n"
f"Базовая цена: {entry_price:.2f}\n"
f"Действие: зафиксировать прибыль"
        )
        state[ticker]["tp"] = True
        changed = True
    elif current_price < tp_price and state[ticker]["tp"]:
        state[ticker]["tp"] = False
        changed = True

    if current_price <= sl_price and not state[ticker]["sl"]:
        send_message(
            f"🛑 СТОП ЛОСС\n"
f"{config['name']} ({ticker})\n"
f"Текущая цена: {current_price:.2f}\n"
f"Стоп -15%: {sl_price:.2f}\n"
f"Базовая цена: {entry_price:.2f}\n"
f"Действие: продать или сократить позицию"
        )
        state[ticker]["sl"] = True
        changed = True
    elif current_price > sl_price and state[ticker]["sl"]:
        state[ticker]["sl"] = False
        changed = True

    return changed


def main():
    if not BOT_TOKEN:
        raise RuntimeError("Не задан TELEGRAM_BOT_TOKEN")
    if not CHAT_ID:
        raise RuntimeError("Не задан TELEGRAM_CHAT_ID")

    state = load_state()
    changed_any = False

for ticker, config in WATCHLIST.items():
    try:
        current_price = get_price(ticker)
        print(f"{ticker}: {current_price:.2f}")
    except Exception as e:
        send_message(f"⚠️ Ошибка получения цены {ticker}: {e}")
        continue

    if check_entry_levels(state, ticker, config, current_price):
            changed_any = True
    if check_tp_sl(state, ticker, config, current_price):
            changed_any = True

    if changed_any:
        save_state(state)


if __name__ == "__main__":
    main()
