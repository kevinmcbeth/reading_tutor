from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional

from auth import get_current_family
from database import get_pool
from models.api_models import (
    BalanceResponse,
    RedemptionResponse,
    RewardItemCreate,
    RewardItemResponse,
    DEFAULT_PAGE_LIMIT,
    MAX_PAGE_LIMIT,
)

router = APIRouter(prefix="/api/rewards", tags=["rewards"])


async def _verify_child_ownership(pool, child_id: int, family_id: int):
    """Verify a child belongs to the authenticated family."""
    row = await pool.fetchrow(
        "SELECT id FROM children WHERE id = $1 AND family_id = $2",
        child_id, family_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Child not found")


async def _get_exchange_rate(pool, child_id: int, family_id: int) -> int:
    """Get the effective exchange rate for a child (child override or family default)."""
    child_rate = await pool.fetchval(
        "SELECT words_per_coin FROM children WHERE id = $1", child_id
    )
    if child_rate is not None:
        return child_rate
    family_rate = await pool.fetchval(
        "SELECT words_per_coin FROM families WHERE id = $1", family_id
    )
    return family_rate or 10


async def _get_word_balance(pool, child_id: int) -> tuple[int, int]:
    """Return (total_words_earned, total_words_converted) for a child."""
    earned = await pool.fetchval(
        "SELECT COALESCE(SUM(score), 0) FROM sessions WHERE child_id = $1 AND completed_at IS NOT NULL",
        child_id,
    )
    converted = await pool.fetchval(
        "SELECT COALESCE(SUM(words_spent), 0) FROM coin_conversions WHERE child_id = $1",
        child_id,
    )
    return int(earned), int(converted)


async def _get_coin_balance(pool, child_id: int) -> tuple[int, int]:
    """Return (total_coins_earned, total_coins_spent) for a child."""
    earned = await pool.fetchval(
        "SELECT COALESCE(SUM(coins_earned), 0) FROM coin_conversions WHERE child_id = $1",
        child_id,
    )
    spent = await pool.fetchval(
        "SELECT COALESCE(SUM(cost), 0) FROM redemptions WHERE child_id = $1",
        child_id,
    )
    return int(earned), int(spent)


# --- Reward item CRUD (parent) ---


@router.get("/items", response_model=list[RewardItemResponse])
async def list_items(
    active_only: bool = Query(True),
    family_id: int = Depends(get_current_family),
):
    pool = get_pool()
    if active_only:
        rows = await pool.fetch(
            "SELECT * FROM reward_items WHERE family_id = $1 AND active = TRUE ORDER BY cost, name",
            family_id,
        )
    else:
        rows = await pool.fetch(
            "SELECT * FROM reward_items WHERE family_id = $1 ORDER BY active DESC, cost, name",
            family_id,
        )
    return [
        RewardItemResponse(
            id=r["id"], name=r["name"], description=r["description"],
            emoji=r["emoji"], cost=r["cost"], active=r["active"],
            created_at=str(r["created_at"]) if r["created_at"] else None,
        )
        for r in rows
    ]


@router.post("/items", response_model=RewardItemResponse, status_code=201)
async def create_item(
    item: RewardItemCreate,
    family_id: int = Depends(get_current_family),
):
    pool = get_pool()
    row = await pool.fetchrow(
        "INSERT INTO reward_items (family_id, name, description, emoji, cost) "
        "VALUES ($1, $2, $3, $4, $5) RETURNING *",
        family_id, item.name, item.description, item.emoji, item.cost,
    )
    return RewardItemResponse(
        id=row["id"], name=row["name"], description=row["description"],
        emoji=row["emoji"], cost=row["cost"], active=row["active"],
        created_at=str(row["created_at"]) if row["created_at"] else None,
    )


@router.put("/items/{item_id}", response_model=RewardItemResponse)
async def update_item(
    item_id: int,
    item: RewardItemCreate,
    family_id: int = Depends(get_current_family),
):
    pool = get_pool()
    existing = await pool.fetchrow(
        "SELECT id FROM reward_items WHERE id = $1 AND family_id = $2",
        item_id, family_id,
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Reward item not found")
    row = await pool.fetchrow(
        "UPDATE reward_items SET name = $1, description = $2, emoji = $3, cost = $4 "
        "WHERE id = $5 RETURNING *",
        item.name, item.description, item.emoji, item.cost, item_id,
    )
    return RewardItemResponse(
        id=row["id"], name=row["name"], description=row["description"],
        emoji=row["emoji"], cost=row["cost"], active=row["active"],
        created_at=str(row["created_at"]) if row["created_at"] else None,
    )


@router.delete("/items/{item_id}")
async def deactivate_item(
    item_id: int,
    family_id: int = Depends(get_current_family),
):
    pool = get_pool()
    existing = await pool.fetchrow(
        "SELECT id FROM reward_items WHERE id = $1 AND family_id = $2",
        item_id, family_id,
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Reward item not found")
    await pool.execute(
        "UPDATE reward_items SET active = FALSE WHERE id = $1", item_id
    )
    return {"detail": "Reward item deactivated"}


# --- Exchange rate (parent) ---


class ExchangeRateUpdate(BaseModel):
    words_per_coin: int
    child_id: Optional[int] = None


@router.get("/exchange-rate")
async def get_exchange_rate(family_id: int = Depends(get_current_family)):
    pool = get_pool()
    family_rate = await pool.fetchval(
        "SELECT words_per_coin FROM families WHERE id = $1", family_id
    )
    # Also return per-child rates
    children = await pool.fetch(
        "SELECT id, name, words_per_coin FROM children WHERE family_id = $1 ORDER BY name",
        family_id,
    )
    return {
        "family_rate": family_rate or 10,
        "children": [
            {"child_id": c["id"], "name": c["name"], "words_per_coin": c["words_per_coin"]}
            for c in children
        ],
    }


@router.put("/exchange-rate")
async def set_exchange_rate(
    body: ExchangeRateUpdate,
    family_id: int = Depends(get_current_family),
):
    if body.words_per_coin < 1 or body.words_per_coin > 10000:
        raise HTTPException(status_code=400, detail="Rate must be between 1 and 10,000")
    pool = get_pool()

    if body.child_id is not None:
        # Per-child rate
        await _verify_child_ownership(pool, body.child_id, family_id)
        await pool.execute(
            "UPDATE children SET words_per_coin = $1 WHERE id = $2",
            body.words_per_coin, body.child_id,
        )
        return {"child_id": body.child_id, "words_per_coin": body.words_per_coin}
    else:
        # Family default
        await pool.execute(
            "UPDATE families SET words_per_coin = $1 WHERE id = $2",
            body.words_per_coin, family_id,
        )
        return {"words_per_coin": body.words_per_coin}


@router.delete("/exchange-rate/{child_id}")
async def clear_child_exchange_rate(
    child_id: int,
    family_id: int = Depends(get_current_family),
):
    """Remove per-child override so they use the family default."""
    pool = get_pool()
    await _verify_child_ownership(pool, child_id, family_id)
    await pool.execute(
        "UPDATE children SET words_per_coin = NULL WHERE id = $1", child_id
    )
    return {"detail": "Child rate cleared, using family default"}


# --- Balance & Conversion (child-facing) ---


@router.get("/balance/{child_id}", response_model=BalanceResponse)
async def get_balance(
    child_id: int,
    family_id: int = Depends(get_current_family),
):
    pool = get_pool()
    await _verify_child_ownership(pool, child_id, family_id)

    words_earned, words_converted = await _get_word_balance(pool, child_id)
    coins_earned, coins_spent = await _get_coin_balance(pool, child_id)
    rate = await _get_exchange_rate(pool, child_id, family_id)

    return BalanceResponse(
        child_id=child_id,
        words_available=words_earned - words_converted,
        words_per_coin=rate,
        coins_balance=coins_earned - coins_spent,
        total_coins_earned=coins_earned,
        total_coins_spent=coins_spent,
    )


@router.post("/convert/{child_id}")
async def convert_words_to_coins(
    child_id: int,
    coins: int = Query(..., ge=1, description="Number of coins to buy"),
    family_id: int = Depends(get_current_family),
):
    pool = get_pool()
    await _verify_child_ownership(pool, child_id, family_id)

    rate = await _get_exchange_rate(pool, child_id, family_id)
    words_needed = coins * rate

    words_earned, words_converted = await _get_word_balance(pool, child_id)
    words_available = words_earned - words_converted

    if words_available < words_needed:
        max_coins = words_available // rate
        raise HTTPException(
            status_code=400,
            detail=f"Not enough words. Need {words_needed}, have {words_available}. You can convert up to {max_coins} coins.",
        )

    await pool.execute(
        "INSERT INTO coin_conversions (child_id, words_spent, coins_earned) VALUES ($1, $2, $3)",
        child_id, words_needed, coins,
    )

    return {
        "detail": f"Converted {words_needed} words into {coins} coins",
        "words_spent": words_needed,
        "coins_earned": coins,
        "words_remaining": words_available - words_needed,
    }


# --- Redemption (child-facing) ---


@router.post("/{item_id}/redeem")
async def redeem_item(
    item_id: int,
    child_id: int = Query(..., description="The child redeeming the reward"),
    family_id: int = Depends(get_current_family),
):
    pool = get_pool()
    await _verify_child_ownership(pool, child_id, family_id)

    item = await pool.fetchrow(
        "SELECT * FROM reward_items WHERE id = $1 AND family_id = $2 AND active = TRUE",
        item_id, family_id,
    )
    if not item:
        raise HTTPException(status_code=404, detail="Reward item not found or inactive")

    coins_earned, coins_spent = await _get_coin_balance(pool, child_id)
    coin_balance = coins_earned - coins_spent
    if coin_balance < item["cost"]:
        raise HTTPException(
            status_code=400,
            detail=f"Not enough coins. Need {item['cost']}, have {coin_balance}.",
        )

    row = await pool.fetchrow(
        "INSERT INTO redemptions (child_id, item_id, cost) VALUES ($1, $2, $3) RETURNING *",
        child_id, item_id, item["cost"],
    )
    return {
        "detail": "Redeemed successfully",
        "redemption_id": row["id"],
        "item_name": item["name"],
        "cost": item["cost"],
        "new_balance": coin_balance - item["cost"],
    }


@router.get("/history/{child_id}", response_model=list[RedemptionResponse])
async def redemption_history(
    child_id: int,
    family_id: int = Depends(get_current_family),
    limit: int = Query(DEFAULT_PAGE_LIMIT, ge=1, le=MAX_PAGE_LIMIT),
    offset: int = Query(0, ge=0),
):
    pool = get_pool()
    await _verify_child_ownership(pool, child_id, family_id)
    rows = await pool.fetch(
        """SELECT r.id, r.child_id, r.item_id, r.cost, r.redeemed_at,
                  ri.name AS item_name, ri.emoji AS item_emoji
           FROM redemptions r
           JOIN reward_items ri ON ri.id = r.item_id
           WHERE r.child_id = $1
           ORDER BY r.redeemed_at DESC
           LIMIT $2 OFFSET $3""",
        child_id, limit, offset,
    )
    return [
        RedemptionResponse(
            id=r["id"], child_id=r["child_id"], item_id=r["item_id"],
            item_name=r["item_name"], item_emoji=r["item_emoji"],
            cost=r["cost"],
            redeemed_at=str(r["redeemed_at"]) if r["redeemed_at"] else None,
        )
        for r in rows
    ]
