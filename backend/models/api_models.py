from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel


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


class ChildResponse(BaseModel):
    id: int
    name: str
    avatar: Optional[str]
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


# --- Speech recognition ---

class SpeechRecognitionResponse(BaseModel):
    transcript: str
    alternatives: list[str]
    confidence: float
