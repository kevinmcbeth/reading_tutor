from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, field_validator


class Difficulty(str, Enum):
    easy = "easy"
    medium = "medium"
    hard = "hard"


# --- Story generation ---

class StoryPrompt(BaseModel):
    topic: str
    difficulty: Difficulty
    theme: Optional[str] = None


class BatchPrompt(BaseModel):
    prompts: list[StoryPrompt]

    @field_validator("prompts")
    @classmethod
    def limit_prompts(cls, v: list) -> list:
        if len(v) > 20:
            raise ValueError("Maximum 20 prompts per batch")
        if len(v) == 0:
            raise ValueError("At least one prompt is required")
        return v


class MetaPrompt(BaseModel):
    description: str
    count: int = 5


# --- Story responses ---

class WordResponse(BaseModel):
    id: int
    idx: int
    text: str
    has_audio: bool
    is_challenge_word: bool


class SentenceResponse(BaseModel):
    id: int
    idx: int
    text: str
    image_path: Optional[str]
    has_image: bool
    words: list[WordResponse]


class StoryResponse(BaseModel):
    id: int
    title: Optional[str]
    topic: Optional[str]
    difficulty: Optional[str]
    theme: Optional[str]
    style: Optional[str]
    fp_level: Optional[str] = None
    status: Optional[str]
    sentences: list[SentenceResponse]


# --- Children ---

class ChildCreate(BaseModel):
    name: str
    avatar: Optional[str] = None


class LeaderboardEntry(BaseModel):
    name: str
    avatar: Optional[str]
    total_words: int
    total_sessions: int


class LevelLeaderboardEntry(BaseModel):
    name: str
    avatar: Optional[str]
    fp_level: str
    sort_order: int


class ChildResponse(BaseModel):
    id: int
    name: str
    avatar: Optional[str]
    fp_level: Optional[str] = None
    created_at: Optional[str]
    total_words_read: int = 0
    total_sessions: int = 0


# --- Sessions ---

class SessionCreate(BaseModel):
    child_id: int
    story_id: int


class SessionResponse(BaseModel):
    id: int
    child_id: int
    story_id: int
    attempt_number: int
    score: int
    total_words: int
    completed_at: Optional[str]


class WordResult(BaseModel):
    word_id: int
    attempts: int
    correct: bool


class SessionComplete(BaseModel):
    results: list[WordResult]


# --- Generation ---

class GenerationJobResponse(BaseModel):
    id: int
    story_id: int
    status: str
    progress_pct: float
    created_at: Optional[str]
    completed_at: Optional[str]


class GenerationLogResponse(BaseModel):
    id: int
    level: str
    message: str
    timestamp: Optional[str]


# --- Authentication ---

class FamilyCreate(BaseModel):
    username: str
    password: str
    display_name: Optional[str] = None

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 3 or len(v) > 50:
            raise ValueError("Username must be between 3 and 50 characters")
        if not v.replace("_", "").replace("-", "").isalnum():
            raise ValueError("Username may only contain letters, numbers, hyphens, and underscores")
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if len(v) > 128:
            raise ValueError("Password must be at most 128 characters")
        if v.isalpha() or v.isdigit():
            raise ValueError("Password must contain both letters and numbers or special characters")
        return v


class FamilyLogin(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    family_id: int
    display_name: Optional[str]


class RefreshRequest(BaseModel):
    refresh_token: str


# --- Parent / Analytics ---

class AnalyticsResponse(BaseModel):
    child_id: int
    total_sessions: int
    average_score: float
    commonly_missed_words: list[dict]


# --- Pagination ---

DEFAULT_PAGE_LIMIT = 50
MAX_PAGE_LIMIT = 200


# --- Speech recognition ---

class TranscriptionHypothesis(BaseModel):
    text: str
    probability: float


class SpeechRecognitionResponse(BaseModel):
    transcript: str
    alternatives: list[TranscriptionHypothesis]
    confidence: float


# --- F&P Guided Reading Levels ---

class FPLevelResponse(BaseModel):
    id: int
    level: str
    sort_order: int
    grade_range: Optional[str]
    min_sentences: int
    max_sentences: int
    generate_images: bool
    image_support: Optional[str]
    description: Optional[str]


class FPProgressResponse(BaseModel):
    child_id: int
    fp_level: str
    stories_at_level: int
    stories_passed: int
    average_accuracy: float
    suggest_advance: bool = False
    suggest_drop: bool = False


class FPLevelSet(BaseModel):
    level: str


class FPStartRequest(BaseModel):
    starting_level: str = "A"


class FPStoryPrompt(BaseModel):
    topic: str
    level: str
    theme: Optional[str] = None


# --- Rewards / Ticket Redeem ---

class RewardItemCreate(BaseModel):
    name: str
    description: Optional[str] = None
    emoji: str = "\U0001f381"
    cost: int

    @field_validator("cost")
    @classmethod
    def validate_cost(cls, v: int) -> int:
        if v < 1:
            raise ValueError("Cost must be at least 1")
        if v > 1_000_000:
            raise ValueError("Cost cannot exceed 1,000,000")
        return v

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = v.strip()
        if not v or len(v) > 100:
            raise ValueError("Name must be between 1 and 100 characters")
        return v


class RewardItemResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    emoji: str
    cost: int
    active: bool
    created_at: Optional[str]


class RedemptionResponse(BaseModel):
    id: int
    child_id: int
    item_id: int
    item_name: str
    item_emoji: str
    cost: int
    redeemed_at: Optional[str]


class BalanceResponse(BaseModel):
    child_id: int
    words_available: int
    words_per_coin: int
    coins_balance: int
    total_coins_earned: int
    total_coins_spent: int


# --- Stock Market ---

class StockInfo(BaseModel):
    id: int
    symbol: str
    name: str
    emoji: str
    category: str
    description: Optional[str]
    current_price: float
    change_pct: float = 0.0


class StockPricePoint(BaseModel):
    price: float
    change_pct: float
    market_day: str


class StockDetail(BaseModel):
    stock: StockInfo
    history: list[StockPricePoint]
    story: Optional[dict] = None


class StockPortfolio(BaseModel):
    coins: float
    holdings: list[dict]
    total_value: float


class StockTradeRequest(BaseModel):
    stock_id: int
    shares: int

    @field_validator("shares")
    @classmethod
    def positive_shares(cls, v: int) -> int:
        if v < 1:
            raise ValueError("Must trade at least 1 share")
        if v > 100:
            raise ValueError("Maximum 100 shares per trade")
        return v


class StockTradeResponse(BaseModel):
    action: str
    symbol: str
    shares: int
    price_per_share: float
    total: float
    coins_remaining: float


class StockNewsItem(BaseModel):
    stock_symbol: str
    stock_name: str
    stock_emoji: str
    direction: str
    headline: str
    body: str
    change_pct: float


class StockDepositRequest(BaseModel):
    coins: int

    @field_validator("coins")
    @classmethod
    def positive_coins(cls, v: int) -> int:
        if v < 1:
            raise ValueError("Must deposit at least 1 coin")
        return v


class StockCreate(BaseModel):
    symbol: str
    name: str
    emoji: str = "📊"
    category: str = "other"
    description: Optional[str] = None
    base_price: float = 100.0
    volatility: float = 0.15

    @field_validator("symbol")
    @classmethod
    def validate_symbol(cls, v: str) -> str:
        v = v.strip().upper()
        if not v or len(v) > 10:
            raise ValueError("Symbol must be 1-10 characters")
        if not v.isalpha():
            raise ValueError("Symbol must be letters only")
        return v

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = v.strip()
        if not v or len(v) > 100:
            raise ValueError("Name must be 1-100 characters")
        return v

    @field_validator("base_price")
    @classmethod
    def validate_price(cls, v: float) -> float:
        if v < 1 or v > 10000:
            raise ValueError("Price must be between 1 and 10,000")
        return round(v, 2)

    @field_validator("volatility")
    @classmethod
    def validate_volatility(cls, v: float) -> float:
        if v < 0.01 or v > 1.0:
            raise ValueError("Volatility must be between 0.01 and 1.0")
        return round(v, 2)
