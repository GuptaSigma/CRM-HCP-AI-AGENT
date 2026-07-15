import json
from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.database.session import get_connection
from app.langgraph.graph import run_interaction_agent

router = APIRouter(prefix="/api/v1", tags=["interactions"])

Sentiment = Literal["positive", "neutral", "negative"]


class DistributionItemCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    quantity: int = Field(default=1, ge=1, le=10000)


class FollowUpCreate(BaseModel):
    task: str = Field(min_length=1, max_length=1000)
    due_date: datetime | None = None


class InteractionCreate(BaseModel):
    hcp_name: str = Field(min_length=1, max_length=200)
    interaction_type: str = Field(min_length=1, max_length=100)
    occurred_at: datetime
    attendees: list[str] = Field(default_factory=list)
    topics_discussed: str = ""
    voice_note_summary: str | None = None
    sentiment: Sentiment = "neutral"
    outcomes: str = ""
    materials: list[DistributionItemCreate] = Field(default_factory=list)
    samples: list[DistributionItemCreate] = Field(default_factory=list)
    follow_ups: list[FollowUpCreate] = Field(default_factory=list)


class InteractionUpdate(BaseModel):
    hcp_name: str | None = Field(default=None, min_length=1, max_length=200)
    interaction_type: str | None = Field(default=None, min_length=1, max_length=100)
    occurred_at: datetime | None = None
    attendees: list[str] | None = None
    topics_discussed: str | None = None
    voice_note_summary: str | None = None
    sentiment: Sentiment | None = None
    outcomes: str | None = None


class AssistantLogRequest(BaseModel):
    message: str = Field(min_length=1, max_length=5000)
    interaction_id: str | None = None
    hcp_name: str | None = None
    interaction_type: str | None = None
    topics_discussed: str | None = None
    sentiment: str | None = None
    outcomes: str | None = None


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_items(connection, table: str, interaction_id: str) -> list[dict]:
    return [dict(row) for row in connection.execute(f"SELECT id, name, quantity FROM {table} WHERE interaction_id = ?", (interaction_id,))]


def read_followups(connection, interaction_id: str) -> list[dict]:
    rows = connection.execute("SELECT id, task, due_date, completed FROM follow_ups WHERE interaction_id = ?", (interaction_id,))
    return [{**dict(row), "completed": bool(row["completed"])} for row in rows]


def read_interaction(connection, interaction_id: str) -> dict:
    row = connection.execute("SELECT * FROM interactions WHERE id = ?", (interaction_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Interaction not found")
    interaction = dict(row)
    interaction["attendees"] = json.loads(interaction["attendees"])
    interaction["materials"] = read_items(connection, "materials", interaction_id)
    interaction["samples"] = read_items(connection, "samples", interaction_id)
    interaction["follow_ups"] = read_followups(connection, interaction_id)
    return interaction


def add_distribution_items(connection, table: str, interaction_id: str, items: list[DistributionItemCreate]) -> None:
    connection.executemany(
        f"INSERT INTO {table} (id, interaction_id, name, quantity) VALUES (?, ?, ?, ?)",
        [(str(uuid4()), interaction_id, item.name, item.quantity) for item in items],
    )


def add_followups(connection, interaction_id: str, followups: list[FollowUpCreate]) -> None:
    connection.executemany(
        "INSERT INTO follow_ups (id, interaction_id, task, due_date) VALUES (?, ?, ?, ?)",
        [(str(uuid4()), interaction_id, item.task, item.due_date.isoformat() if item.due_date else None) for item in followups],
    )


@router.get("/health", tags=["health"])
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/interactions", status_code=status.HTTP_201_CREATED)
def create_interaction(payload: InteractionCreate) -> dict:
    interaction_id, timestamp = str(uuid4()), now()
    with get_connection() as connection:
        connection.execute(
            """INSERT INTO interactions (id, hcp_name, interaction_type, occurred_at, attendees, topics_discussed,
            voice_note_summary, sentiment, outcomes, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (interaction_id, payload.hcp_name, payload.interaction_type, payload.occurred_at.isoformat(), json.dumps(payload.attendees),
             payload.topics_discussed, payload.voice_note_summary, payload.sentiment, payload.outcomes, timestamp, timestamp),
        )
        add_distribution_items(connection, "materials", interaction_id, payload.materials)
        add_distribution_items(connection, "samples", interaction_id, payload.samples)
        add_followups(connection, interaction_id, payload.follow_ups)
        return read_interaction(connection, interaction_id)


@router.get("/interactions")
def list_interactions(limit: int = 50, offset: int = 0) -> list[dict]:
    safe_limit = max(1, min(limit, 100))
    safe_offset = max(0, offset)
    with get_connection() as connection:
        rows = connection.execute("SELECT id FROM interactions ORDER BY occurred_at DESC LIMIT ? OFFSET ?", (safe_limit, safe_offset)).fetchall()
        return [read_interaction(connection, row["id"]) for row in rows]


@router.get("/interactions/{interaction_id}")
def get_interaction(interaction_id: str) -> dict:
    with get_connection() as connection:
        return read_interaction(connection, interaction_id)


@router.patch("/interactions/{interaction_id}")
def update_interaction(interaction_id: str, payload: InteractionUpdate) -> dict:
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields supplied for update")
    if "attendees" in updates:
        updates["attendees"] = json.dumps(updates["attendees"])
    if "occurred_at" in updates:
        updates["occurred_at"] = updates["occurred_at"].isoformat()
    updates["updated_at"] = now()
    columns = ", ".join(f"{column} = ?" for column in updates)
    with get_connection() as connection:
        if connection.execute(f"UPDATE interactions SET {columns} WHERE id = ?", (*updates.values(), interaction_id)).rowcount == 0:
            raise HTTPException(status_code=404, detail="Interaction not found")
        return read_interaction(connection, interaction_id)


@router.put("/interactions/{interaction_id}")
def put_interaction(interaction_id: str, payload: InteractionCreate) -> dict:
    with get_connection() as connection:
        row = connection.execute("SELECT id FROM interactions WHERE id = ?", (interaction_id,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Interaction not found")
        
        connection.execute(
            """UPDATE interactions SET hcp_name = ?, interaction_type = ?, occurred_at = ?, attendees = ?, 
            topics_discussed = ?, voice_note_summary = ?, sentiment = ?, outcomes = ?, updated_at = ?
            WHERE id = ?""",
            (payload.hcp_name, payload.interaction_type, payload.occurred_at.isoformat(), json.dumps(payload.attendees),
             payload.topics_discussed, payload.voice_note_summary, payload.sentiment, payload.outcomes, now(), interaction_id),
        )
        
        connection.execute("DELETE FROM materials WHERE interaction_id = ?", (interaction_id,))
        connection.execute("DELETE FROM samples WHERE interaction_id = ?", (interaction_id,))
        connection.execute("DELETE FROM follow_ups WHERE interaction_id = ?", (interaction_id,))
        
        add_distribution_items(connection, "materials", interaction_id, payload.materials)
        add_distribution_items(connection, "samples", interaction_id, payload.samples)
        add_followups(connection, interaction_id, payload.follow_ups)
        
        return read_interaction(connection, interaction_id)


@router.delete("/interactions/{interaction_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_interaction(interaction_id: str) -> None:
    with get_connection() as connection:
        if connection.execute("DELETE FROM interactions WHERE id = ?", (interaction_id,)).rowcount == 0:
            raise HTTPException(status_code=404, detail="Interaction not found")


@router.post("/interactions/{interaction_id}/materials", status_code=status.HTTP_201_CREATED)
def add_material(interaction_id: str, item: DistributionItemCreate) -> dict:
    with get_connection() as connection:
        read_interaction(connection, interaction_id)
        add_distribution_items(connection, "materials", interaction_id, [item])
        return read_interaction(connection, interaction_id)


@router.post("/interactions/{interaction_id}/samples", status_code=status.HTTP_201_CREATED)
def add_sample(interaction_id: str, item: DistributionItemCreate) -> dict:
    with get_connection() as connection:
        read_interaction(connection, interaction_id)
        add_distribution_items(connection, "samples", interaction_id, [item])
        return read_interaction(connection, interaction_id)


@router.post("/interactions/{interaction_id}/follow-ups", status_code=status.HTTP_201_CREATED)
def add_follow_up(interaction_id: str, item: FollowUpCreate) -> dict:
    with get_connection() as connection:
        read_interaction(connection, interaction_id)
        add_followups(connection, interaction_id, [item])
        return read_interaction(connection, interaction_id)


@router.patch("/follow-ups/{follow_up_id}")
def complete_follow_up(follow_up_id: str, completed: bool = True) -> dict:
    with get_connection() as connection:
        row = connection.execute("UPDATE follow_ups SET completed = ? WHERE id = ? RETURNING *", (int(completed), follow_up_id)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Follow-up not found")
        result = dict(row)
        result["completed"] = bool(result["completed"])
        return result


@router.post("/assistant/log")
def log_from_assistant(request: AssistantLogRequest) -> dict:
    try:
        return run_interaction_agent(
            message=request.message.strip(),
            interaction_id=request.interaction_id,
            hcp_name=request.hcp_name,
            interaction_type=request.interaction_type,
            topics_discussed=request.topics_discussed,
            sentiment=request.sentiment,
            outcomes=request.outcomes
        )
    except RuntimeError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Groq assistant request failed. Please try again.") from error
