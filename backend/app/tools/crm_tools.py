import json
from datetime import datetime, timezone
from uuid import uuid4
from langchain_core.tools import tool

from app.database.session import get_connection

@tool
def search_hcp(query: str) -> str:
    """Search Healthcare Professionals (HCPs) in the database by name, specialty, or organization.
    
    Args:
        query: The search query (e.g., name, specialty, or organization name).
        
    Returns:
        A list of matching HCP records formatted as a JSON string.
    """
    with get_connection() as conn:
        cursor = conn.execute(
            """
            SELECT name, specialty, organization, email 
            FROM hcps 
            WHERE name LIKE ? OR specialty LIKE ? OR organization LIKE ?
            """,
            (f"%{query}%", f"%{query}%", f"%{query}%")
        )
        rows = [dict(row) for row in cursor.fetchall()]
        return json.dumps(rows, indent=2)

@tool
def log_interaction(
    hcp_name: str,
    interaction_type: str,
    topics_discussed: str,
    sentiment: str,
    outcomes: str,
    occurred_at: str = None,
    attendees: str = "",
    follow_up_tasks: str = ""
) -> str:
    """Log a new interaction with a Healthcare Professional in the CRM database.
    
    Args:
        hcp_name: The name of the Healthcare Professional (HCP).
        interaction_type: The type of interaction (e.g., Meeting, In-person meeting, Virtual meeting, Phone call).
        topics_discussed: Clinical or product topics discussed during the meeting.
        sentiment: Sentiment observed during interaction (must be one of: positive, neutral, negative).
        outcomes: Outcomes, agreements, or key takeaways.
        occurred_at: Optional ISO format date-time string (e.g. 2026-07-14T01:00:00). Defaults to current time.
        attendees: Optional comma-separated list of names of additional attendees.
        follow_up_tasks: Optional newline-separated list of follow-up action items.
        
    Returns:
        A success message with the logged interaction ID.
    """
    interaction_id = str(uuid4())
    now_str = datetime.now(timezone.utc).isoformat()
    occurred = occurred_at if occurred_at else now_str
    
    # Clean sentiment
    sent = sentiment.lower().strip()
    if sent not in {"positive", "neutral", "negative"}:
        sent = "neutral"
        
    attendees_list = [a.strip() for a in attendees.split(",") if a.strip()]
    
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO interactions (
                id, hcp_name, interaction_type, occurred_at, attendees, 
                topics_discussed, sentiment, outcomes, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                interaction_id, hcp_name, interaction_type, occurred, 
                json.dumps(attendees_list), topics_discussed, sent, outcomes, 
                now_str, now_str
            )
        )
        
        # Add follow ups if provided
        if follow_up_tasks:
            tasks = [t.strip() for t in follow_up_tasks.split("\n") if t.strip()]
            for task in tasks:
                conn.execute(
                    "INSERT INTO follow_ups (id, interaction_id, task, completed) VALUES (?, ?, ?, 0)",
                    (str(uuid4()), interaction_id, task)
                )
                
    return f"Successfully logged interaction with {hcp_name}. Interaction ID: {interaction_id}"

@tool
def edit_interaction(
    interaction_id: str,
    hcp_name: str = None,
    interaction_type: str = None,
    topics_discussed: str = None,
    sentiment: str = None,
    outcomes: str = None
) -> str:
    """Update/edit an existing interaction in the CRM database.
    
    Args:
        interaction_id: The ID of the interaction to edit.
        hcp_name: Optional new HCP name.
        interaction_type: Optional new interaction type.
        topics_discussed: Optional new topics discussed.
        sentiment: Optional new sentiment.
        outcomes: Optional new outcomes.
        
    Returns:
        A message indicating success or failure.
    """
    updates = {}
    if hcp_name is not None:
        updates["hcp_name"] = hcp_name
    if interaction_type is not None:
        updates["interaction_type"] = interaction_type
    if topics_discussed is not None:
        updates["topics_discussed"] = topics_discussed
    if outcomes is not None:
        updates["outcomes"] = outcomes
    if sentiment is not None:
        sent = sentiment.lower().strip()
        if sent in {"positive", "neutral", "negative"}:
            updates["sentiment"] = sent
            
    if not updates:
        return "No fields provided to update."
        
    updates["updated_at"] = datetime.now(timezone.utc).isoformat()
    columns = ", ".join(f"{col} = ?" for col in updates)
    
    with get_connection() as conn:
        rowcount = conn.execute(
            f"UPDATE interactions SET {columns} WHERE id = ?",
            (*updates.values(), interaction_id)
        ).rowcount
        
        if rowcount == 0:
            return f"Error: Interaction with ID {interaction_id} not found."
            
    return f"Successfully updated interaction {interaction_id}."

@tool
def generate_followup_email(hcp_name: str, topics_discussed: str, outcomes: str) -> str:
    """Generate a draft follow-up email based on the discussion topics and outcomes.
    
    Args:
        hcp_name: The name of the Healthcare Professional.
        topics_discussed: Brief summary of topics discussed.
        outcomes: Key outcomes or agreements reached.
        
    Returns:
        A complete follow-up email draft.
    """
    email_body = f"""Subject: Follow-up regarding our meeting - {topics_discussed[:30]}...

Dear {hcp_name},

Thank you for taking the time to meet with me today. It was a pleasure discussing {topics_discussed}.

To summarize our conversation, we highlighted the following key points:
- Discussions on: {topics_discussed}
- Agreed outcomes / Next steps: {outcomes}

I will follow up with any requested documents or details as discussed. Please let me know if you have any questions or require further information in the meantime.

Looking forward to our next interaction.

Best regards,

[Medical Science Liaison / Representative Name]
[Organization]"""
    return email_body

@tool
def next_best_action(hcp_name: str, topics_discussed: str, sentiment: str) -> str:
    """Recommend the next best action for the sales representative based on the meeting context.
    
    Args:
        hcp_name: The name of the Healthcare Professional.
        topics_discussed: Topics discussed in the meeting.
        sentiment: Sentiment observed (positive, neutral, negative).
        
    Returns:
        A recommended next action summary.
    """
    sent = sentiment.lower().strip()
    topics = topics_discussed.lower()
    
    recommendation = ""
    if "cardio" in topics:
        product = "CardioBest"
    elif "efficacy" in topics:
        product = "efficacy-focused trial data"
    else:
        product = "our clinical portfolio"
        
    if sent == "positive":
        recommendation = f"1. Send the latest clinical study brochure/PDF for {product} immediately.\n2. Schedule a follow-up lunch meeting in 2 weeks to discuss onboarding or formulary status.\n3. Propose adding {hcp_name} to the advisory board invitation list."
    elif sent == "negative":
        recommendation = f"1. Log the specific concerns/hesitations raised regarding {product}.\n2. Request a 1-on-1 review with the Medical Director to draft detailed clinical counter-evidence.\n3. Schedule a brief touchpoint call in 3-4 weeks to address outstanding issues."
    else: # neutral or unknown
        recommendation = f"1. Share standard product information sheets regarding {product}.\n2. Send a follow-up email checking if they have further questions.\n3. Add to the monthly medical update newsletter list and check in during next month's hospital visit."
        
    return f"Next Best Actions for {hcp_name}:\n{recommendation}"
