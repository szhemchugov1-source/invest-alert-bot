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


def build_status_message(state):
    cash = state.get("available_cash", 0)
    trades = state.get("trades", {})

    # Защита от старого формата, где trades был списком
    if isinstance(trades, list):
        trades = {}

    if not isinstance(trades, dict):
        trades = {}

    open_count = 0
    closed_count = 0

    active_positions = []
    empty_positions = []

    for ticker in WATCHLIST.keys():
        ticker_trades = trades.get(ticker, [])

        if not isinstance(ticker_trades, list):
            ticker_trades = []

        has_open = False
        total_shares = 0.0

        for trade in ticker_trades:
            if not isinstance(trade, dict):
                continue

            if trade.get("status") == "OPEN":
                open_count += 1
                has_open = True
                total_shares += float(trade.get("shares", 0) or 0)

            elif trade.get("status") == "CLOSED":
                closed_count += 1

        if has_open:
            active_positions.append(f"{ticker} — {round(total_shares, 4)} акций")
        else:
            empty_positions.append(ticker)

    lines = [
        "📊 Статус системы",
        "",
        f"💰 Кэш: ${cash:.2f}",
        f"📂 Открытых сделок: {open_count}",
        f"📁 Закрытых сделок: {closed_count}",
        ""
    ]

    if active_positions:
        lines.append("📦 Активные позиции:")
        lines.extend(active_positions)
        lines.append("")

    if empty_positions:
        lines.append("📉 Без позиций:")
        lines.extend(empty_positions)

    return "\n".join(lines)


def process_telegram_commands(state):
    changed = False

    last_update_id = state.get("last_update_id")
    if last_update_id is None:
        last_update_id = 0

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
            cash = state.get("available_cash", 0)

            if isinstance(trades, list) or not isinstance(trades, dict):
                trades = {}

            has_trades = any(trades.get(ticker) for ticker in trades)
            if not has_trades:
                send_message(f"📭 Сделок пока нет\n\n💰 Кэш: ${cash:.2f}")
                continue

            lines = [
                "📒 Журнал сделок",
                "",
                f"💰 Кэш: ${cash:.2f}",
                ""
            ]

            for ticker, ticker_trades in trades.items():
                if not isinstance(ticker_trades, list) or not ticker_trades:
                    continue

                # получаем текущую цену
                try:
                    current_price = round(get_price(ticker), 2)
                except Exception:
                    current_price = None

                for trade in ticker_trades[-5:]:
                    if not isinstance(trade, dict):
                        continue

                    status = trade.get("status", "UNKNOWN")
                    levels = trade.get("level", "-")
                    avg_price = trade.get("avg_price", trade.get("entry", "-"))
                    shares = trade.get("total_shares", trade.get("shares", "-"))
                    invested = trade.get("total_invested", trade.get("amount_usd", "-"))
                    tp1 = trade.get("tp1", "-")
                    tp2 = trade.get("tp2", "-")
                    sl = trade.get("sl", "-")

                    tp1_status = "достигнута" if trade.get("tp1_hit", False) else "не достигнута"
                    tp2_status = "достигнута" if trade.get("tp2_hit", False) else "не достигнута"
                    sl_status = "сработал" if trade.get("sl_hit", False) else "не сработал"

                    profit_text = "Текущая прибыль: -"
                    current_price_text = "Текущая цена: -"

                    try:
                        avg_price_num = float(avg_price)
                        shares_num = float(shares)

                        if current_price is not None and avg_price_num > 0:
                            profit_usd = round((current_price - avg_price_num) * shares_num, 2)
                            profit_pct = round(((current_price - avg_price_num) / avg_price_num) * 100, 2)

                            sign = "+" if profit_usd >= 0 else ""

                            current_price_text = f"Текущая цена: {current_price}"
                            profit_text = f"Текущая прибыль: {sign}${profit_usd} ({sign}{profit_pct}%)"
                    except Exception:
                        pass

                    lines.append(f"{ticker} | {status}")
                    lines.append(f"Алерт: {levels}")
                    lines.append(f"Средняя: {avg_price}")
                    lines.append(current_price_text)
                    lines.append(f"Акции: {shares}")
                    lines.append(f"Вложено: ${invested}" if invested != "-" else "Вложено: -")
                    lines.append(profit_text)
                    lines.append("")
                    lines.append(f"🎯 Цель 1 (для позиции {levels}): {tp1} [{tp1_status}]")
                    lines.append(f"🎯 Цель 2 (для позиции {levels}): {tp2} [{tp2_status}]")
                    lines.append(f"🛑 Стоп (для позиции {levels}): {sl} [{sl_status}]")
                    lines.append("")

            send_message("\n".join(lines))
            continue

    elif text.lower() == "/positions":
            trades = state.get("trades", {})
            cash = state.get("available_cash", 0)

            if isinstance(trades, list) or not isinstance(trades, dict):
                trades = {}

            lines = [
                "📊 Активные позиции",
                "",
                f"💰 Кэш: ${cash:.2f}",
                ""
            ]

            has_open = False

            for ticker, ticker_trades in trades.items():
                if not isinstance(ticker_trades, list):
                    continue

                open_trade = next(
                    (t for t in ticker_trades if isinstance(t, dict) and t.get("status") == "OPEN"),
                    None
                )

                if not open_trade:
                    continue

                has_open = True

                try:
                    current_price = round(get_price(ticker), 2)
                except Exception:
                    current_price = None

                avg_price = open_trade.get("avg_price", open_trade.get("entry", "-"))
                shares = open_trade.get("total_shares", open_trade.get("shares", "-"))
                tp1 = open_trade.get("tp1", "-")
                tp2 = open_trade.get("tp2", "-")
                sl = open_trade.get("sl", "-")

                profit_text = "Прибыль: -"
                price_text = "Цена: -"

                try:
                    avg_price_num = float(avg_price)
                    shares_num = float(shares)

                    if current_price is not None and avg_price_num > 0:
                        profit_usd = round((current_price - avg_price_num) * shares_num, 2)
                        profit_pct = round(((current_price - avg_price_num) / avg_price_num) * 100, 2)

                        sign = "+" if profit_usd >= 0 else ""

                        price_text = f"Цена: {current_price}"
                        profit_text = f"Прибыль: {sign}${profit_usd} ({sign}{profit_pct}%)"
                except Exception:
                    pass

                lines.append(f"{ticker}")
                lines.append(f"Средняя: {avg_price}")
                lines.append(price_text)
                lines.append(profit_text)
                lines.append("")
                lines.append(f"Цель 1: {tp1}")
                lines.append(f"Цель 2: {tp2}")
                lines.append(f"Стоп: {sl}")
                lines.append("")

            if not has_open:
                lines.append("Нет открытых позиций")

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

    if isinstance(state["trades"], list):
        state["trades"] = {}

    if ticker not in state["trades"]:
        state["trades"][ticker] = []

    # Храним последние цены для анти-повтора после рестарта
    if "last_prices" not in state or not isinstance(state["last_prices"], dict):
        state["last_prices"] = {}

    prev_price = state["last_prices"].get(ticker)

    available_cash = float(state.get("available_cash", 0) or 0)
    asset_budget = available_cash / max(len(WATCHLIST), 1)

    level_weights = {
        "lvl1": 0.40,
        "lvl2": 0.30,
        "lvl3": 0.30,
    }

    # Ищем открытую сделку по тикеру
    open_trade = next(
        (
            t for t in state["trades"][ticker]
            if isinstance(t, dict) and t.get("status") == "OPEN"
        ),
        None
    )

    # Если это первый цикл после рестарта — просто запоминаем цену и не шлём сигнал
    if prev_price is None:
        state["last_prices"][ticker] = current_price
        return False

    for level in config.get("levels", []):
        level_key = level["key"]
        level_price = level["price"]
        level_amount = round(asset_budget * level_weights.get(level_key, 0), 2)

        if level_amount <= 0:
            continue

        crossed_down = prev_price > level_price and current_price <= level_price

        # =========================
        # 1) ЕСЛИ СДЕЛКИ ЕЩЁ НЕТ
        # =========================
        if open_trade is None:
            if crossed_down:
                shares_est = round(level_amount / current_price, 4) if current_price > 0 else 0
                if shares_est <= 0:
                    continue

                avg_price = round(current_price, 2)
                tp1 = round(avg_price * 1.03, 2)
                tp2 = round(avg_price * 1.06, 2)
                sl = round(avg_price * 0.97, 2)

                trade = {
                    "ticker": ticker,
                    "entry": avg_price,
                    "avg_price": avg_price,
                    "shares": shares_est,
                    "total_shares": shares_est,
                    "amount_usd": level_amount,
                    "total_invested": level_amount,
                    "tp1": tp1,
                    "tp2": tp2,
                    "sl": sl,
                    "level": level_key,
                    "levels_hit": [level_key],
                    "status": "OPEN",
                    "tp1_hit": False,
                    "tp2_hit": False,
                    "sl_hit": False
                }

                state["trades"][ticker].append(trade)

                send_message(
                    f"🟢 BUY SIGNAL\n\n"
                    f"Акция: {ticker}\n"
                    f"Текущая цена: {current_price:.2f}\n"
                    f"Уровень входа: {level_key}\n\n"
                    f"Купить: {shares_est} акций\n"
                    f"Сумма входа: ${level_amount:.2f}\n"
                    f"Средняя цена: {avg_price:.2f}\n\n"
                    f"🎯 Цель 1: {tp1} → ПРОДАТЬ 50%\n"
                    f"🎯 Цель 2: {tp2} → ПРОДАТЬ ОСТАТОК\n"
                    f"🛑 Стоп: {sl} → ПРОДАТЬ ВСЁ"
                )

                changed = True
                break

        # =========================
        # 2) ЕСЛИ СДЕЛКА УЖЕ ЕСТЬ
        # =========================
        else:
            levels_hit = open_trade.get("levels_hit")

            if not isinstance(levels_hit, list):
                levels_hit = []

            open_trade["levels_hit"] = levels_hit

            # Уже был этот уровень — повторно не докупаем
            if level_key in levels_hit:
                continue

            if crossed_down:
                add_shares = round(level_amount / current_price, 4) if current_price > 0 else 0
                if add_shares <= 0:
                    continue

                prev_total_invested = float(open_trade.get("total_invested", open_trade.get("amount_usd", 0)) or 0)
                prev_total_shares = float(open_trade.get("total_shares", open_trade.get("shares", 0)) or 0)

                new_total_invested = round(prev_total_invested + level_amount, 2)
                new_total_shares = round(prev_total_shares + add_shares, 4)

                if new_total_shares <= 0:
                    continue

                new_avg_price = round(new_total_invested / new_total_shares, 2)

                new_tp1 = round(new_avg_price * 1.03, 2)
                new_tp2 = round(new_avg_price * 1.06, 2)
                new_sl = round(new_avg_price * 0.97, 2)

                levels_hit.append(level_key)

                open_trade["entry"] = new_avg_price
                open_trade["avg_price"] = new_avg_price
                open_trade["shares"] = new_total_shares
                open_trade["total_shares"] = new_total_shares
                open_trade["amount_usd"] = new_total_invested
                open_trade["total_invested"] = new_total_invested
                open_trade["tp1"] = new_tp1
                open_trade["tp2"] = new_tp2
                open_trade["sl"] = new_sl
                open_trade["level"] = " + ".join(levels_hit)
                open_trade["levels_hit"] = levels_hit

                send_message(
                    f"🔵 DCA / ДОКУПКА\n\n"
                    f"Акция: {ticker}\n"
                    f"Сработал уровень: {level_key}\n"
                    f"Текущая цена: {current_price:.2f}\n\n"
                    f"Докупить: {add_shares} акций\n"
                    f"Сумма докупки: ${level_amount:.2f}\n\n"
                    f"Всего акций: {new_total_shares}\n"
                    f"Всего вложено: ${new_total_invested:.2f}\n"
                    f"Новая средняя цена: {new_avg_price:.2f}\n\n"
                    f"🎯 Цель 1: {new_tp1} → ПРОДАТЬ 50%\n"
                    f"🎯 Цель 2: {new_tp2} → ПРОДАТЬ ОСТАТОК\n"
                    f"🛑 Стоп: {new_sl} → ПРОДАТЬ ВСЁ"
                )

                changed = True
                break

    # В конце обязательно обновляем последнюю цену
    state["last_prices"][ticker] = current_price

    return changed


def check_tp_sl(state, ticker, config, current_price):
    changed = False

    trades = state.get("trades", {})
    if isinstance(trades, list):
        return changed

    if ticker not in trades:
        return changed

    for trade in trades[ticker]:
        if not isinstance(trade, dict):
            continue

        if trade.get("status") == "CLOSED":
            continue

        tp1 = trade.get("tp1")
        tp2 = trade.get("tp2")
        sl = trade.get("sl")

        # Инициализируем флаги предупреждений
        if "tp1_warned" not in trade:
            trade["tp1_warned"] = False
        if "tp2_warned" not in trade:
            trade["tp2_warned"] = False
        if "sl_warned" not in trade:
            trade["sl_warned"] = False

        # -------------------------
        # Почти цель 1
        # -------------------------
        if (
            tp1 is not None
            and not trade.get("tp1_hit", False)
            and not trade.get("tp1_warned", False)
            and current_price < tp1
        ):
            remain_pct_tp1 = ((tp1 - current_price) / tp1) * 100
            if remain_pct_tp1 <= 1:
                send_message(
                    f"⚠️ Почти цель 1\n\n"
                    f"Акция: {ticker}\n"
                    f"Текущая цена: {current_price:.2f}\n"
                    f"Цель 1: {tp1}\n"
                    f"Осталось: {remain_pct_tp1:.2f}%"
                )
                trade["tp1_warned"] = True
                changed = True

        # -------------------------
        # Почти цель 2
        # -------------------------
        if (
            tp2 is not None
            and not trade.get("tp2_hit", False)
            and not trade.get("tp2_warned", False)
            and current_price < tp2
        ):
            remain_pct_tp2 = ((tp2 - current_price) / tp2) * 100
            if remain_pct_tp2 <= 1:
                send_message(
                    f"⚠️ Почти цель 2\n\n"
                    f"Акция: {ticker}\n"
                    f"Текущая цена: {current_price:.2f}\n"
                    f"Цель 2: {tp2}\n"
                    f"Осталось: {remain_pct_tp2:.2f}%"
                )
                trade["tp2_warned"] = True
                changed = True

        # -------------------------
        # Почти стоп
        # -------------------------
        if (
            sl is not None
            and not trade.get("sl_hit", False)
            and not trade.get("sl_warned", False)
            and current_price > sl
        ):
            remain_pct_sl = ((current_price - sl) / sl) * 100
            if remain_pct_sl <= 1:
                send_message(
                    f"⚠️ Почти стоп\n\n"
                    f"Акция: {ticker}\n"
                    f"Текущая цена: {current_price:.2f}\n"
                    f"Стоп: {sl}\n"
                    f"Осталось: {remain_pct_sl:.2f}%"
                )
                trade["sl_warned"] = True
                changed = True

        # -------------------------
        # Цель 1
        # -------------------------
        if (
            tp1 is not None
            and current_price >= tp1
            and not trade.get("tp1_hit", False)
        ):
            send_message(
                f"🎯 TAKE PROFIT 1\n\n"
                f"Акция: {ticker}\n"
                f"Текущая цена: {current_price:.2f}\n"
                f"Действие: ПРОДАТЬ 50%"
            )
            trade["tp1_hit"] = True
            changed = True

        # -------------------------
        # Цель 2
        # -------------------------
        if (
            tp2 is not None
            and current_price >= tp2
            and not trade.get("tp2_hit", False)
        ):
            send_message(
                f"✅ EXIT SIGNAL\n\n"
                f"Акция: {ticker}\n"
                f"Текущая цена: {current_price:.2f}\n"
                f"Действие: ПРОДАТЬ ОСТАТОК"
            )
            trade["tp2_hit"] = True
            trade["status"] = "CLOSED"
            changed = True

        # -------------------------
        # Стоп
        # -------------------------
        if (
            sl is not None
            and current_price <= sl
            and not trade.get("sl_hit", False)
            and trade.get("status") != "CLOSED"
        ):
            send_message(
                f"🛑 STOP SIGNAL\n\n"
                f"Акция: {ticker}\n"
                f"Текущая цена: {current_price:.2f}\n"
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
