"""
Stock Market endpoints — a modular, kid-friendly stock trading game.

Prices tick once per calendar day (on first request of each new day).
Children start with 1000 coins and can buy/sell shares.
News stories are matched to the child's F&P reading level.
"""

import random
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query

from auth import get_current_family
from database import get_pool
from models.api_models import (
    StockCreate,
    StockDepositRequest,
    StockDetail,
    StockInfo,
    StockNewsItem,
    StockPortfolio,
    StockPricePoint,
    StockTradeRequest,
    StockTradeResponse,
)

router = APIRouter(prefix="/api/stockmarket", tags=["stockmarket"])

STARTING_COINS = 0.0


# ---------- helpers ----------

async def _ensure_market_day(pool) -> date:
    """
    Ensure today's prices exist. If not, simulate a new market day.
    Returns today's date.
    """
    today = date.today()
    existing = await pool.fetchval(
        "SELECT COUNT(*) FROM stock_price_history WHERE market_day = $1", today
    )
    if existing > 0:
        return today

    stocks = await pool.fetch("SELECT id, current_price, volatility, dividend_yield, type FROM stocks")
    rng = random.Random(today.toordinal())

    for stock in stocks:
        sid = stock["id"]
        price = stock["current_price"]
        vol = stock["volatility"]

        # Geometric Brownian Motion-ish: mean-reverting random walk
        change_pct = rng.gauss(0, vol)
        # Clamp to avoid extreme moves
        change_pct = max(-0.40, min(0.40, change_pct))
        new_price = round(price * (1 + change_pct), 2)
        new_price = max(1.0, new_price)  # floor at $1

        await pool.execute(
            """INSERT INTO stock_price_history (stock_id, price, change_pct, market_day)
               VALUES ($1, $2, $3, $4)
               ON CONFLICT (stock_id, market_day) DO NOTHING""",
            sid, new_price, round(change_pct * 100, 2), today,
        )
        await pool.execute(
            "UPDATE stocks SET current_price = $1 WHERE id = $2",
            new_price, sid,
        )

    # Pay dividends and bond coupons to holders
    yield_stocks = [s for s in stocks if s["dividend_yield"] and s["dividend_yield"] > 0]
    if yield_stocks:
        yield_ids = [s["id"] for s in yield_stocks]
        holders = await pool.fetch(
            """SELECT h.child_id, h.stock_id, h.shares
               FROM child_stock_holdings h
               WHERE h.shares > 0 AND h.stock_id = ANY($1::int[])""",
            yield_ids,
        )
        yield_map = {s["id"]: s for s in yield_stocks}
        for h in holders:
            stock = yield_map[h["stock_id"]]
            daily_yield = stock["dividend_yield"] / 365.0
            payout = round(h["shares"] * stock["current_price"] * daily_yield, 2)
            if payout < 0.01:
                continue
            action = "coupon" if stock["type"] == "bond" else "dividend"
            result = await pool.execute(
                """INSERT INTO dividend_payouts (child_id, stock_id, amount, market_day)
                   VALUES ($1, $2, $3, $4)
                   ON CONFLICT (child_id, stock_id, market_day) DO NOTHING""",
                h["child_id"], h["stock_id"], payout, today,
            )
            if "INSERT 0 1" in result:
                await pool.execute(
                    "UPDATE child_stock_balances SET coins = coins + $1 WHERE child_id = $2",
                    payout, h["child_id"],
                )
                await pool.execute(
                    """INSERT INTO child_stock_transactions
                       (child_id, stock_id, action, shares, price_per_share, total)
                       VALUES ($1, $2, $3, $4, $5, $6)""",
                    h["child_id"], h["stock_id"], action,
                    h["shares"], stock["current_price"], payout,
                )

    return today


async def _ensure_balance(pool, child_id: int) -> float:
    """Get or create a child's coin balance."""
    row = await pool.fetchrow(
        "SELECT coins FROM child_stock_balances WHERE child_id = $1", child_id
    )
    if row:
        return row["coins"]
    await pool.execute(
        "INSERT INTO child_stock_balances (child_id, coins) VALUES ($1, $2) ON CONFLICT DO NOTHING",
        child_id, STARTING_COINS,
    )
    return STARTING_COINS


async def _get_child_fp_level(pool, child_id: int) -> str:
    """Get a child's current F&P level, defaulting to A."""
    row = await pool.fetchrow("SELECT fp_level FROM children WHERE id = $1", child_id)
    if row and row["fp_level"]:
        return row["fp_level"]
    return "A"


async def _verify_child_ownership(pool, family_id: int, child_id: int) -> None:
    """Verify that the child belongs to the family."""
    owner = await pool.fetchval(
        "SELECT family_id FROM children WHERE id = $1", child_id
    )
    if owner != family_id:
        raise HTTPException(status_code=403, detail="Not your child")


# ---------- endpoints ----------

@router.get("/stocks", response_model=list[StockInfo])
async def list_stocks(family_id: int = Depends(get_current_family)):
    """List all stocks with current prices and today's change."""
    pool = get_pool()
    await _ensure_market_day(pool)
    today = date.today()

    rows = await pool.fetch(
        """SELECT s.*,
                  COALESCE(h.change_pct, 0) AS change_pct
           FROM stocks s
           LEFT JOIN stock_price_history h ON h.stock_id = s.id AND h.market_day = $1
           ORDER BY s.symbol""",
        today,
    )
    return [
        StockInfo(
            id=r["id"],
            symbol=r["symbol"],
            name=r["name"],
            emoji=r["emoji"],
            category=r["category"],
            description=r["description"],
            current_price=r["current_price"],
            change_pct=r["change_pct"] or 0,
            type=r["type"],
            dividend_yield=r["dividend_yield"],
        )
        for r in rows
    ]


@router.get("/stocks/{stock_id}", response_model=StockDetail)
async def get_stock_detail(
    stock_id: int,
    child_id: int = Query(..., description="Child viewing the stock"),
    family_id: int = Depends(get_current_family),
):
    """Get detailed info for a single stock including price history and a news story."""
    pool = get_pool()
    await _verify_child_ownership(pool, family_id, child_id)
    await _ensure_market_day(pool)

    stock = await pool.fetchrow("SELECT * FROM stocks WHERE id = $1", stock_id)
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")

    today = date.today()
    today_change = await pool.fetchval(
        "SELECT change_pct FROM stock_price_history WHERE stock_id = $1 AND market_day = $2",
        stock_id, today,
    )

    # Last 30 days of history
    history = await pool.fetch(
        """SELECT price, change_pct, market_day FROM stock_price_history
           WHERE stock_id = $1 ORDER BY market_day DESC LIMIT 30""",
        stock_id,
    )

    # Get a story matching level and today's direction
    fp_level = await _get_child_fp_level(pool, child_id)
    direction = "up" if (today_change or 0) >= 0 else "down"
    story_row = await pool.fetchrow(
        """SELECT headline, body FROM stock_stories
           WHERE stock_id = $1 AND fp_level = $2 AND direction = $3
           ORDER BY RANDOM() LIMIT 1""",
        stock_id, fp_level, direction,
    )
    # Fallback: any story for this stock in the right direction
    if not story_row:
        story_row = await pool.fetchrow(
            """SELECT headline, body FROM stock_stories
               WHERE stock_id = $1 AND direction = $2
               ORDER BY RANDOM() LIMIT 1""",
            stock_id, direction,
        )

    return StockDetail(
        stock=StockInfo(
            id=stock["id"],
            symbol=stock["symbol"],
            name=stock["name"],
            emoji=stock["emoji"],
            category=stock["category"],
            description=stock["description"],
            current_price=stock["current_price"],
            change_pct=today_change or 0,
            type=stock["type"],
            dividend_yield=stock["dividend_yield"],
        ),
        history=[
            StockPricePoint(
                price=h["price"],
                change_pct=h["change_pct"],
                market_day=str(h["market_day"]),
            )
            for h in reversed(history)
        ],
        story={"headline": story_row["headline"], "body": story_row["body"]} if story_row else None,
    )


@router.get("/news", response_model=list[StockNewsItem])
async def get_daily_news(
    child_id: int = Query(..., description="Child reading the news"),
    family_id: int = Depends(get_current_family),
):
    """Get today's news stories for all stocks, matched to child's reading level."""
    pool = get_pool()
    await _verify_child_ownership(pool, family_id, child_id)
    await _ensure_market_day(pool)

    fp_level = await _get_child_fp_level(pool, child_id)
    today = date.today()

    stocks = await pool.fetch(
        """SELECT s.id, s.symbol, s.name, s.emoji,
                  COALESCE(h.change_pct, 0) AS change_pct
           FROM stocks s
           LEFT JOIN stock_price_history h ON h.stock_id = s.id AND h.market_day = $1
           ORDER BY ABS(COALESCE(h.change_pct, 0)) DESC""",
        today,
    )

    news = []
    for s in stocks:
        direction = "up" if s["change_pct"] >= 0 else "down"
        story = await pool.fetchrow(
            """SELECT headline, body FROM stock_stories
               WHERE stock_id = $1 AND fp_level = $2 AND direction = $3
               ORDER BY RANDOM() LIMIT 1""",
            s["id"], fp_level, direction,
        )
        if not story:
            story = await pool.fetchrow(
                """SELECT headline, body FROM stock_stories
                   WHERE stock_id = $1 AND direction = $2
                   ORDER BY RANDOM() LIMIT 1""",
                s["id"], direction,
            )
        if story:
            news.append(StockNewsItem(
                stock_symbol=s["symbol"],
                stock_name=s["name"],
                stock_emoji=s["emoji"],
                direction=direction,
                headline=story["headline"],
                body=story["body"],
                change_pct=s["change_pct"],
            ))

    return news


@router.get("/portfolio", response_model=StockPortfolio)
async def get_portfolio(
    child_id: int = Query(..., description="Child whose portfolio to view"),
    family_id: int = Depends(get_current_family),
):
    """Get a child's stock portfolio: balance, holdings, and total value."""
    pool = get_pool()
    await _verify_child_ownership(pool, family_id, child_id)
    await _ensure_market_day(pool)

    coins = await _ensure_balance(pool, child_id)

    holdings = await pool.fetch(
        """SELECT h.stock_id, h.shares, s.symbol, s.name, s.emoji, s.current_price,
                  s.type, s.dividend_yield
           FROM child_stock_holdings h
           JOIN stocks s ON s.id = h.stock_id
           WHERE h.child_id = $1 AND h.shares > 0
           ORDER BY s.symbol""",
        child_id,
    )

    holdings_list = []
    holdings_value = 0.0
    for h in holdings:
        value = h["shares"] * h["current_price"]
        holdings_value += value
        holdings_list.append({
            "stock_id": h["stock_id"],
            "symbol": h["symbol"],
            "name": h["name"],
            "emoji": h["emoji"],
            "shares": h["shares"],
            "current_price": h["current_price"],
            "value": round(value, 2),
            "type": h["type"],
            "dividend_yield": h["dividend_yield"],
        })

    return StockPortfolio(
        coins=round(coins, 2),
        holdings=holdings_list,
        total_value=round(coins + holdings_value, 2),
    )


@router.post("/buy", response_model=StockTradeResponse)
async def buy_stock(
    trade: StockTradeRequest,
    child_id: int = Query(..., description="Child buying the stock"),
    family_id: int = Depends(get_current_family),
):
    """Buy shares of a stock."""
    pool = get_pool()
    await _verify_child_ownership(pool, family_id, child_id)
    await _ensure_market_day(pool)

    stock = await pool.fetchrow("SELECT * FROM stocks WHERE id = $1", trade.stock_id)
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")

    total_cost = round(stock["current_price"] * trade.shares, 2)
    coins = await _ensure_balance(pool, child_id)

    if coins < total_cost:
        raise HTTPException(
            status_code=400,
            detail=f"Not enough coins! You have {coins:.2f} but need {total_cost:.2f}",
        )

    # Deduct coins
    await pool.execute(
        "UPDATE child_stock_balances SET coins = coins - $1 WHERE child_id = $2",
        total_cost, child_id,
    )

    # Add shares
    await pool.execute(
        """INSERT INTO child_stock_holdings (child_id, stock_id, shares)
           VALUES ($1, $2, $3)
           ON CONFLICT (child_id, stock_id)
           DO UPDATE SET shares = child_stock_holdings.shares + $3""",
        child_id, trade.stock_id, trade.shares,
    )

    # Record transaction
    await pool.execute(
        """INSERT INTO child_stock_transactions (child_id, stock_id, action, shares, price_per_share, total)
           VALUES ($1, $2, 'buy', $3, $4, $5)""",
        child_id, trade.stock_id, trade.shares, stock["current_price"], total_cost,
    )

    new_balance = await pool.fetchval(
        "SELECT coins FROM child_stock_balances WHERE child_id = $1", child_id
    )

    return StockTradeResponse(
        action="buy",
        symbol=stock["symbol"],
        shares=trade.shares,
        price_per_share=stock["current_price"],
        total=total_cost,
        coins_remaining=round(new_balance, 2),
    )


@router.post("/sell", response_model=StockTradeResponse)
async def sell_stock(
    trade: StockTradeRequest,
    child_id: int = Query(..., description="Child selling the stock"),
    family_id: int = Depends(get_current_family),
):
    """Sell shares of a stock."""
    pool = get_pool()
    await _verify_child_ownership(pool, family_id, child_id)
    await _ensure_market_day(pool)

    stock = await pool.fetchrow("SELECT * FROM stocks WHERE id = $1", trade.stock_id)
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")

    # Check holdings
    current_shares = await pool.fetchval(
        "SELECT shares FROM child_stock_holdings WHERE child_id = $1 AND stock_id = $2",
        child_id, trade.stock_id,
    )
    if not current_shares or current_shares < trade.shares:
        raise HTTPException(
            status_code=400,
            detail=f"You only have {current_shares or 0} shares of {stock['symbol']}",
        )

    total_revenue = round(stock["current_price"] * trade.shares, 2)

    # Add coins
    await pool.execute(
        "UPDATE child_stock_balances SET coins = coins + $1 WHERE child_id = $2",
        total_revenue, child_id,
    )

    # Remove shares
    await pool.execute(
        "UPDATE child_stock_holdings SET shares = shares - $1 WHERE child_id = $2 AND stock_id = $3",
        trade.shares, child_id, trade.stock_id,
    )

    # Record transaction
    await pool.execute(
        """INSERT INTO child_stock_transactions (child_id, stock_id, action, shares, price_per_share, total)
           VALUES ($1, $2, 'sell', $3, $4, $5)""",
        child_id, trade.stock_id, trade.shares, stock["current_price"], total_revenue,
    )

    new_balance = await pool.fetchval(
        "SELECT coins FROM child_stock_balances WHERE child_id = $1", child_id
    )

    return StockTradeResponse(
        action="sell",
        symbol=stock["symbol"],
        shares=trade.shares,
        price_per_share=stock["current_price"],
        total=total_revenue,
        coins_remaining=round(new_balance, 2),
    )


@router.get("/history")
async def get_transaction_history(
    child_id: int = Query(..., description="Child whose history to view"),
    family_id: int = Depends(get_current_family),
    limit: int = Query(20, ge=1, le=100),
):
    """Get a child's recent stock transactions."""
    pool = get_pool()
    await _verify_child_ownership(pool, family_id, child_id)

    rows = await pool.fetch(
        """SELECT t.*, s.symbol, s.name, s.emoji
           FROM child_stock_transactions t
           JOIN stocks s ON s.id = t.stock_id
           WHERE t.child_id = $1
           ORDER BY t.created_at DESC
           LIMIT $2""",
        child_id, limit,
    )

    return [
        {
            "id": r["id"],
            "action": r["action"],
            "symbol": r["symbol"],
            "name": r["name"],
            "emoji": r["emoji"],
            "shares": r["shares"],
            "price_per_share": r["price_per_share"],
            "total": r["total"],
            "created_at": str(r["created_at"]),
        }
        for r in rows
    ]


@router.post("/deposit")
async def deposit_coins(
    body: StockDepositRequest,
    child_id: int = Query(..., description="Child depositing coins"),
    family_id: int = Depends(get_current_family),
):
    """
    Deposit reward-system coins into the stock market balance.
    Spends words at the child's exchange rate, converts to reward coins,
    then adds those coins to the stock market balance.
    """
    pool = get_pool()
    await _verify_child_ownership(pool, family_id, child_id)

    # Get the child's exchange rate (child override or family default)
    child_rate = await pool.fetchval(
        "SELECT words_per_coin FROM children WHERE id = $1", child_id
    )
    if child_rate is None:
        child_rate = await pool.fetchval(
            "SELECT words_per_coin FROM families WHERE id = $1", family_id
        )
    rate = child_rate or 10

    words_needed = body.coins * rate

    # Check available words
    words_earned = await pool.fetchval(
        "SELECT COALESCE(SUM(score), 0) FROM sessions WHERE child_id = $1 AND completed_at IS NOT NULL",
        child_id,
    )
    words_converted = await pool.fetchval(
        "SELECT COALESCE(SUM(words_spent), 0) FROM coin_conversions WHERE child_id = $1",
        child_id,
    )
    words_available = int(words_earned) - int(words_converted)

    if words_available < words_needed:
        max_coins = words_available // rate
        raise HTTPException(
            status_code=400,
            detail=f"Not enough words! Need {words_needed} words ({body.coins} coins x {rate} words/coin), "
                   f"but only have {words_available} words available. You can deposit up to {max_coins} coins.",
        )

    # Record the word conversion
    await pool.execute(
        "INSERT INTO coin_conversions (child_id, words_spent, coins_earned) VALUES ($1, $2, $3)",
        child_id, words_needed, body.coins,
    )

    # Add to stock market balance
    await pool.execute(
        """INSERT INTO child_stock_balances (child_id, coins)
           VALUES ($1, $2)
           ON CONFLICT (child_id)
           DO UPDATE SET coins = child_stock_balances.coins + $2""",
        child_id, float(body.coins),
    )

    new_balance = await pool.fetchval(
        "SELECT coins FROM child_stock_balances WHERE child_id = $1", child_id
    )
    new_words_available = words_available - words_needed

    return {
        "coins_deposited": body.coins,
        "words_spent": words_needed,
        "stock_balance": round(new_balance, 2),
        "words_remaining": new_words_available,
    }


# ---------- Admin (parent) endpoints ----------


@router.post("/admin/stocks", response_model=StockInfo, status_code=201)
async def create_stock(
    stock: StockCreate,
    family_id: int = Depends(get_current_family),
):
    """Create a new stock (parent only)."""
    pool = get_pool()
    existing = await pool.fetchval(
        "SELECT id FROM stocks WHERE symbol = $1", stock.symbol
    )
    if existing:
        raise HTTPException(status_code=409, detail=f"Stock {stock.symbol} already exists")

    row = await pool.fetchrow(
        """INSERT INTO stocks (symbol, name, emoji, category, description, base_price, current_price, volatility, type, dividend_yield)
           VALUES ($1, $2, $3, $4, $5, $6, $6, $7, $8, $9) RETURNING *""",
        stock.symbol, stock.name, stock.emoji, stock.category,
        stock.description, stock.base_price, stock.volatility,
        stock.type, stock.dividend_yield,
    )
    return StockInfo(
        id=row["id"], symbol=row["symbol"], name=row["name"],
        emoji=row["emoji"], category=row["category"],
        description=row["description"], current_price=row["current_price"],
        type=row["type"], dividend_yield=row["dividend_yield"],
    )


@router.put("/admin/stocks/{stock_id}", response_model=StockInfo)
async def update_stock(
    stock_id: int,
    stock: StockCreate,
    family_id: int = Depends(get_current_family),
):
    """Update an existing stock (parent only)."""
    pool = get_pool()
    existing = await pool.fetchrow("SELECT * FROM stocks WHERE id = $1", stock_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Stock not found")

    # Check symbol uniqueness if changed
    if stock.symbol != existing["symbol"]:
        dupe = await pool.fetchval(
            "SELECT id FROM stocks WHERE symbol = $1 AND id != $2",
            stock.symbol, stock_id,
        )
        if dupe:
            raise HTTPException(status_code=409, detail=f"Symbol {stock.symbol} already in use")

    row = await pool.fetchrow(
        """UPDATE stocks SET symbol = $1, name = $2, emoji = $3, category = $4,
           description = $5, volatility = $6, type = $7, dividend_yield = $8
           WHERE id = $9 RETURNING *""",
        stock.symbol, stock.name, stock.emoji, stock.category,
        stock.description, stock.volatility, stock.type, stock.dividend_yield, stock_id,
    )
    return StockInfo(
        id=row["id"], symbol=row["symbol"], name=row["name"],
        emoji=row["emoji"], category=row["category"],
        description=row["description"], current_price=row["current_price"],
        type=row["type"], dividend_yield=row["dividend_yield"],
    )


@router.delete("/admin/stocks/{stock_id}")
async def delete_stock(
    stock_id: int,
    family_id: int = Depends(get_current_family),
):
    """Delete a stock (parent only). Fails if anyone holds shares."""
    pool = get_pool()
    existing = await pool.fetchrow("SELECT * FROM stocks WHERE id = $1", stock_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Stock not found")

    held = await pool.fetchval(
        "SELECT COALESCE(SUM(shares), 0) FROM child_stock_holdings WHERE stock_id = $1",
        stock_id,
    )
    if held and held > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete — {held} shares are held by children",
        )

    # Clean up related data
    await pool.execute("DELETE FROM dividend_payouts WHERE stock_id = $1", stock_id)
    await pool.execute("DELETE FROM stock_stories WHERE stock_id = $1", stock_id)
    await pool.execute("DELETE FROM stock_price_history WHERE stock_id = $1", stock_id)
    await pool.execute("DELETE FROM child_stock_transactions WHERE stock_id = $1", stock_id)
    await pool.execute("DELETE FROM stocks WHERE id = $1", stock_id)

    return {"detail": f"Stock {existing['symbol']} deleted"}
