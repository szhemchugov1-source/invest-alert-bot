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

def send_message(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    response = requests.post(
        url,
        json={"chat_id": CHAT_ID, "text": text},
        timeout=20,
    )
    response.raise_for_status()
def get_updates(offset=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
    params = {"timeout": 10}
    if offset is not None:
        params["offset"] = offset

    response = requests.get(url, params=params, timeout=20)
    response.raise_for_status()
    return response.json()["result"] 
def process_telegram_commands(state):
    last_update_id = state.get("last_update_id")
    offset = last_update_id + 1 if last_update_id is not None else None

    updates = get_updates(offset=offset)
    changed = False

    for update in updates:
        state["last_update_id"] = update["update_id"]
        changed = True

        message = update.get("message")
        if not message:
            continue

        text = message.get("text", "").strip()
        chat_id = str(message.get("chat", {}).get("id", ""))

        if chat_id != str(CHAT_ID):
            continue

        if text.startswith("/cash"):
            parts = text.split()

            if len(parts) == 2:
                raw_value = parts[1]
            else:
                raw_value = text.replace("/cash", "", 1).strip()

            try:
                cash_value = float(raw_value)
            except ValueError:
                send_message("⚠️ Неверный формат. Пример: /cash 20")
                continue

            if cash_value <= 0:
                send_message("⚠️ Кэш должен быть больше 0.")
                continue

            state["available_cash"] = cash_value
            changed = True
            send_message(f"✅ Кэш обновлён: ${cash_value:.2f}")

    return changed   


def get_price(ticker):
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

    import json
    with open(STATE_FILE, "r", encoding="utf-8") as f:
        state = json.load(f)

    # Мягкая миграция старого state.json
    if "available_cash" not in state:
        state["available_cash"] = DEFAULT_AVAILABLE_CASH
    if "last_update_id" not in state:
        state["last_update_id"] = None
    if "assets" not in state:
        old_state = state
        state = {
            "available_cash": DEFAULT_AVAILABLE_CASH,
            "last_update_id": None,
            "assets": old_state,
        }

    return state


def save_state(state):
    import json
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def check_entry_levels(state, ticker, config, current_price):
    changed = False
    asset_state = state["assets"][ticker]
    available_cash = float(state["available_cash"])

    asset_budget = available_cash * ASSET_WEIGHTS[ticker]

    for level in config["levels"]:
        level_key = level["key"]
        trigger_price = level["price"]
        label = level["label"]

        amount_usd = asset_budget * LADDER_WEIGHTS[level_key]
        shares_est = amount_usd / current_price if current_price > 0 else 0
        trade_percent = (amount_usd / available_cash * 100) if available_cash > 0 else 0
        cash_after_trade = available_cash - amount_usd
        
        if amount_usd < MIN_TRADE_USD:
            continue
        if current_price <= trigger_price and not asset_state["levels"]
        [send_message(
    f"🚨 Сигнал по системе\n"
    f"{config['name']} ({ticker})\n"
    f"Уровень: {label}\n"
    f"Текущая цена: {current_price:.2f}\n"
    f"Цена уровня: {trigger_price:.2f}\n"
    f"Кэш в расчёте: ${available_cash:.2f}\n"
    f"Сумма покупки: ${amount_usd:.2f}\n"
    f"Доля сделки от кэша: {trade_percent:.2f}%\n"
    f"Остаток кэша после входа: ${cash_after_trade:.2f}\n"
    f"Примерно акций: {shares_est:.4f}\n"
    f"Действие: купить / ждать / пропустить"
)
            asset_state["levels"][level_key] = True
            changed = True

        elif current_price > trigger_price and asset_state["levels"][level_key]:
            asset_state["levels"][level_key] = False
            changed = True

    return changed


def check_tp_sl(state, ticker, config, current_price):
    changed = False
    asset_state = state["assets"][ticker]

    entry_price = config["entry_price"]
    tp_price = round(entry_price * 1.20, 2)
    sl_price = round(entry_price * 0.85, 2)

    if current_price >= tp_price and not asset_state["tp"]:
        send_message(
            f"💰 ФИКСАЦИЯ ПРИБЫЛИ\n"
            f"{config['name']} ({ticker})\n"
            f"Текущая цена: {current_price:.2f}\n"
            f"Цель +20%: {tp_price:.2f}\n"
            f"Базовая цена: {entry_price:.2f}\n"
            f"Действие: зафиксировать прибыль"
        )
        asset_state["tp"] = True
        changed = True
    elif current_price < tp_price and asset_state["tp"]:
        asset_state["tp"] = False
        changed = True

    if current_price <= sl_price and not asset_state["sl"]:
        send_message(
            f"🛑 СТОП ЛОСС\n"
            f"{config['name']} ({ticker})\n"
            f"Текущая цена: {current_price:.2f}\n"
            f"Стоп -15%: {sl_price:.2f}\n"
            f"Базовая цена: {entry_price:.2f}\n"
            f"Действие: продать или сократить позицию"
        )
        asset_state["sl"] = True
        changed = True
    elif current_price > sl_price and asset_state["sl"]:
        asset_state["sl"] = False
        changed = True

    return changed


def main():
    if not BOT_TOKEN:
        raise RuntimeError("Не задан TELEGRAM_BOT_TOKEN")
    if not CHAT_ID:
        raise RuntimeError("Не задан TELEGRAM_CHAT_ID")

    state = load_state()
    changed_any = False

    if process_telegram_commands(state):
        changed_any = True

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
