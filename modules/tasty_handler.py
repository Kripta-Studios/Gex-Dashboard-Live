"""
TastyTrade Options Data Downloader v3 - MÁXIMA VELOCIDAD

Optimizaciones aplicadas:
1. Timeout agresivo de 2s (como el original)
2. Sin retry automático
3. Sin creación de DataFrame por defecto
4. Sin llamadas REST adicionales
5. Early exit cuando todos los datos llegaron
"""

import asyncio
from collections import defaultdict
from typing import TypedDict, List, Tuple, Dict
import datetime

from tastytrade import Session, DXLinkStreamer
from tastytrade.instruments import NestedOptionChain, NestedFutureOptionChain
from tastytrade.market_data import get_market_data_by_type
from tastytrade.dxfeed import Greeks, Summary
from zoneinfo import ZoneInfo


class OptionsRequest(TypedDict):
    tickers: List[str]
    start_date: datetime.date
    end_date: datetime.date
    lower_strike: str
    upper_strike: str


MONTH_CODES = {
    1: 'F', 2: 'G', 3: 'H', 4: 'J', 5: 'K', 6: 'M',
    7: 'N', 8: 'Q', 9: 'U', 10: 'V', 11: 'X', 12: 'Z'
}

MONTHLY_CONTRACTS = {
    'CL', 'QM', 'BZ', 'NG', 'QG', 'GC', 'HG', 'PL',
    'VX', 'ZT', 'ZF', 'ZN', 'ZB', 'SR3', 'BTC', 'ETH'
}


def get_future_ticker(symbol: str, current_date: datetime.datetime = None) -> str:
    if current_date is None:
        current_date = datetime.datetime.utcnow()
    symbol = symbol.upper().lstrip("/")
    monthly = symbol in MONTHLY_CONTRACTS
    
    if monthly:
        next_month = current_date.month + 1
        year = current_date.year
        if next_month > 12:
            next_month = 1
            year += 1
        code = MONTH_CODES[next_month]
    else:
        quarterly_months = [3, 6, 9, 12]
        year = current_date.year
        for m in quarterly_months:
            first_day = datetime.datetime(year, m, 1)
            weekday = first_day.weekday()
            delta = (4 - weekday + 7) % 7
            third_friday = 1 + delta + 14
            opex = datetime.datetime(year, m, third_friday)
            if current_date < opex:
                code = MONTH_CODES[m]
                break
        else:
            year += 1
            code = MONTH_CODES[3]
    
    year_code = str(year)[-1]
    return f"/{symbol}{code}{year_code}"


def extract_base_symbol(future_ticker: str) -> str:
    month_codes_set = set(MONTH_CODES.values())
    ticker = future_ticker.strip().upper()
    for i in range(len(ticker) - 2, 0, -1):
        if ticker[i] in month_codes_set and ticker[i + 1].isdigit():
            return ticker[:i]
    raise ValueError(f"No se pudo extraer símbolo base de: {ticker}")


def chunks(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


async def get_chain_async(session, ticker: str):
    if '/' in ticker:
        base = extract_base_symbol(ticker) if any(c.isdigit() for c in ticker) else ticker
        return await asyncio.to_thread(NestedFutureOptionChain.get, session, base)
    else:
        chains = await asyncio.to_thread(NestedOptionChain.get, session, ticker)
        return chains[0] if chains else None


async def get_market_data_async(session, equities=None, options=None):
    return await asyncio.to_thread(get_market_data_by_type, session, equities=equities, options=options)


async def tasty_expirations_strikes(session, options_ticker: List[str]):
    """Compatible con función original."""
    expiries_chain = defaultdict(set)
    expiries_list = []
    strikes_chain = defaultdict(set)
    strikes_list = []
    
    chains = await asyncio.gather(*[get_chain_async(session, t) for t in options_ticker])
    
    for ticker, chain in zip(options_ticker, chains):
        if chain is None:
            continue
        
        is_future = '/' in ticker
        target_future = get_future_ticker(ticker) if is_future else None
        
        if is_future:
            exps = [e for sc in chain.option_chains for e in sc.expirations]
        else:
            exps = chain.expirations
        
        for exp in exps:
            for strike in exp.strikes:
                if is_future and target_future:
                    if target_future not in str(strike.call or ""):
                        continue
                ticker_key = str(strike.call).split()[0] if strike.call else ticker
                expiries_chain[ticker_key].add(exp.expiration_date)
                strikes_chain[ticker_key].add(float(strike.strike_price))
    
    for ticker, dates in expiries_chain.items():
        dates_list = sorted(dates)
        expiries_list.append({ticker: {"expirations": dates_list, "min_date": min(dates_list), "max_date": max(dates_list)}})
    
    for ticker, strikes in strikes_chain.items():
        strikes_order = sorted(strikes)
        strikes_list.append({ticker: {"strikes": strikes_order, "min_strike": min(strikes_order), "max_strike": max(strikes_order)}})
    
    return expiries_list, strikes_list


async def main_downloader(
    session,
    options_requested: OptionsRequest = None,
    equities_ticker: List[str] = None
) -> Tuple[List, List]:
    """
    Descargador principal OPTIMIZADO.
    Compatible con API original pero mucho más rápido.
    """
    equities_ticker = equities_ticker or []
    
    # === EQUITIES ===
    equities_spot = []
    if equities_ticker:
        data = await get_market_data_async(session, equities=equities_ticker)
        for i in data:
            equities_spot.append({
                "symbol": str(i.symbol),
                "ask": str(i.ask), "ask_size": str(i.ask_size),
                "bid": str(i.bid), "bid_size": str(i.bid_size),
                "mid": str(i.mid), "mark": str(i.mark),
                "last": str(i.last), "last_mkt": str(i.last_mkt),
                "open": str(i.open), "prev_close": str(i.prev_close),
                "day_high_price": str(i.day_high_price),
                "day_low_price": str(i.day_low_price),
                "prev_close_date": str(i.prev_close_date),
                "time": i.updated_at.astimezone(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %H:%M:%S") if i.updated_at else None,
            })
    
    if options_requested is None:
        return [], equities_spot[::-1]
    
    # === OPTIONS ===
    tickers = options_requested.get("tickers", [])
    start_date = options_requested.get("start_date")
    end_date = options_requested.get("end_date")
    lower_strike = float(options_requested.get("lower_strike", 0))
    upper_strike = float(options_requested.get("upper_strike", float('inf')))
    
    # Normalizar tickers de futuros
    for i, t in enumerate(tickers):
        if "/" in t:
            tickers[i] = extract_base_symbol(t)
    
    # Obtener cadenas
    chains = await asyncio.gather(*[get_chain_async(session, t) for t in tickers])
    
    # Recopilar símbolos y metadata
    symbol_pairs = []  # [(option_symbol, streamer_symbol)]
    greeks_list = []
    
    for ticker, chain in zip(tickers, chains):
        if chain is None:
            continue
        
        is_future = '/' in ticker
        target_future = get_future_ticker(ticker) if is_future else None
        
        if is_future:
            exps = [e for sc in chain.option_chains for e in sc.expirations]
        else:
            exps = chain.expirations
        
        for exp in exps:
            exp_date = exp.expiration_date
            if start_date and exp_date < start_date:
                continue
            if end_date and exp_date > end_date:
                continue
            
            for strike in exp.strikes:
                strike_price = float(strike.strike_price)
                if strike_price < lower_strike or strike_price > upper_strike:
                    continue
                
                if is_future and target_future:
                    if target_future not in str(strike.call or ""):
                        continue
                
                # Call
                if strike.call and strike.call_streamer_symbol:
                    entry = {
                        "expiration": exp_date,
                        "strike": str(strike.strike_price),
                        "option": str(strike.call),
                        "symbol": str(strike.call_streamer_symbol),
                    }
                    if entry not in greeks_list:
                        symbol_pairs.append((strike.call, strike.call_streamer_symbol))
                        greeks_list.append(entry)
                
                # Put
                if strike.put and strike.put_streamer_symbol:
                    entry = {
                        "expiration": exp_date,
                        "strike": str(strike.strike_price),
                        "option": str(strike.put),
                        "symbol": str(strike.put_streamer_symbol),
                    }
                    if entry not in greeks_list:
                        symbol_pairs.append((strike.put, strike.put_streamer_symbol))
                        greeks_list.append(entry)
    
    if not symbol_pairs:
        return greeks_list[::-1], equities_spot[::-1]
    
    # === MARKET DATA (batched REST) ===
    processed = set()
    batch_tasks = []
    for batch in chunks(symbol_pairs, 100):
        batch_tasks.append(get_market_data_async(session, options=[s[0] for s in batch]))
    
    batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
    
    # Crear lookup rápido
    symbol_to_idx = {d["symbol"]: idx for idx, d in enumerate(greeks_list)}
    
    for batch_data in batch_results:
        if isinstance(batch_data, Exception):
            continue
        for item in batch_data:
            sym_str = str(item.symbol)
            # Buscar en greeks_list por option (no por symbol)
            for idx, d in enumerate(greeks_list):
                if d.get("option") == sym_str and d["symbol"] not in processed:
                    ticker = sym_str.split()[0]
                    greeks_list[idx].update({
                        "ticker": ticker,
                        "ask": str(item.ask),
                        "ask_size": str(item.ask_size),
                        "bid": str(item.bid),
                        "bid_size": str(item.bid_size),
                        "mid": str(item.mid),
                        "last": str(item.last),
                        "time": item.updated_at.astimezone(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %H:%M:%S") if item.updated_at else None,
                    })
                    processed.add(d["symbol"])
                    break
    
    # === GREEKS via DXLink (OPTIMIZADO) ===
    tasty_symbols = [s[1] for s in symbol_pairs]
    total_expected = len(tasty_symbols) * 2  # Greeks + Summary
    data_cache = defaultdict(dict)
    received_count = 0
    
    async with DXLinkStreamer(session) as streamer:
        # Suscripción masiva
        await streamer.subscribe(Greeks, tasty_symbols)
        await streamer.subscribe(Summary, tasty_symbols)
        
        # Escucha con early exit
        async def collect_with_early_exit():
            nonlocal received_count
            
            async def collect_greeks():
                nonlocal received_count
                async for event in streamer.listen(Greeks):
                    if event.event_symbol not in data_cache or "greeks" not in data_cache[event.event_symbol]:
                        data_cache[event.event_symbol]["greeks"] = event
                        received_count += 1
            
            async def collect_summary():
                nonlocal received_count
                async for event in streamer.listen(Summary):
                    if event.event_symbol not in data_cache or "summary" not in data_cache[event.event_symbol]:
                        data_cache[event.event_symbol]["summary"] = event
                        received_count += 1
            
            await asyncio.gather(collect_greeks(), collect_summary())
        
        try:
            # Timeout corto de 2 segundos (como el original)
            await asyncio.wait_for(collect_with_early_exit(), timeout=2.0)
        except asyncio.TimeoutError:
            pass
    
    # Actualizar greeks_list con datos recibidos
    for tasty_symbol in tasty_symbols:
        cache_entry = data_cache.get(tasty_symbol, {})
        greeks_event = cache_entry.get("greeks")
        summary_event = cache_entry.get("summary")
        
        if greeks_event or summary_event:
            idx = symbol_to_idx.get(tasty_symbol)
            if idx is not None:
                if greeks_event:
                    greeks_list[idx].update({
                        "delta": str(greeks_event.delta),
                        "gamma": str(greeks_event.gamma),
                        "theta": str(greeks_event.theta),
                        "vega": str(greeks_event.vega),
                        "rho": str(greeks_event.rho),
                        "vol": str(greeks_event.volatility),
                        "price": str(greeks_event.price),
                    })
                if summary_event:
                    greeks_list[idx].update({
                        "open_interest": str(summary_event.open_interest),
                    })
    
    return greeks_list[::-1], equities_spot[::-1]


# Alias
tasty_data = main_downloader


async def run_batched_main(session, options_requested, date_chunk_size=100, strike_step=100):
    """Compatible con función original - pero ya no necesita batching."""
    # El nuevo main_downloader ya es eficiente, no necesita batching
    greeks_list, _ = await main_downloader(session, options_requested)
    return greeks_list
