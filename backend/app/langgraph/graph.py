from datetime import datetime, timezone
import json
from typing import TypedDict
from pydantic import BaseModel, Field

from langchain_groq import ChatGroq
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.prebuilt import create_react_agent

from app.core.config import settings
from app.tools.crm_tools import search_hcp, log_interaction, edit_interaction, generate_followup_email, next_best_action

# Define the tools list
tools = [search_hcp, log_interaction, edit_interaction, generate_followup_email, next_best_action]

def get_model(model_name: str = None):
    m_name = model_name if model_name else settings.groq_model
    if settings.groq_api_key:
        return ChatGroq(
            model=m_name,
            temperature=0,
            api_key=settings.groq_api_key
        )
    elif settings.gemini_api_key:
        return ChatGoogleGenerativeAI(
            model=settings.gemini_model,
            temperature=0,
            api_key=settings.gemini_api_key
        )
    else:
        raise RuntimeError("No API key configured. Please set GROQ_API_KEY or GEMINI_API_KEY in backend/.env.")

# Compile the react agent
def build_agent_graph(model_name: str = None):
    model = get_model(model_name)
    system_prompt = (
        "You are an AI assistant for a pharmaceutical CRM. "
        "You have access to tools for managing interactions and Healthcare Professionals (HCPs).\n"
        "Use search_hcp to find HCP details.\n"
        "Use log_interaction to save new meetings.\n"
        "Use edit_interaction to update existing records.\n"
        "Use generate_followup_email to draft professional emails to doctors.\n"
        "Use next_best_action to determine recommendations.\n"
        "Always be concise and helpful. Respond in plain, clear text."
    )
    return create_react_agent(model, tools, prompt=system_prompt)

agent_graph = None

def get_agent_graph():
    global agent_graph
    if agent_graph is None:
        agent_graph = build_agent_graph()
    return agent_graph

class InteractionExtraction(BaseModel):
    summary: str = Field(description="A concise, factual summary of the interaction.")
    hcp_name: str = Field(default="", description="HCP name, including title when provided. Empty if unknown.")
    interaction_type: str = Field(default="meeting", description="Meeting, phone call, virtual meeting, or other interaction type.")
    topics_discussed: str = Field(default="", description="Clinical or product topics discussed.")
    sentiment: str = Field(default="neutral", description="One of: positive, neutral, negative.")
    follow_up_suggestions: list[str] = Field(default_factory=list, description="Concrete next actions inferred from the note.")

# Structured extractor for draft form
def extract_draft(message: str) -> dict:
    system_prompt = (
        "You extract compliant CRM records from HCP interaction notes. "
        "Analyze the message and return a JSON object with these keys:\n"
        "- hcp_name: Name of HCP (or empty string if not mentioned)\n"
        "- interaction_type: 'Meeting', 'In-person meeting', 'Virtual meeting', or 'Phone call'\n"
        "- topics_discussed: Key topics discussed\n"
        "- sentiment: 'positive', 'neutral', or 'negative'\n"
        "- attendees: List of names of additional attendees (excluding the main HCP)\n"
        "- outcomes: Key outcomes or agreements reached\n"
        "- materials: List of materials shared (e.g. CardioBest Product Brochure)\n"
        "- samples: List of sample products distributed (e.g. CardioBest 10mg sample)\n"
        "- follow_ups: List of follow-up tasks\n"
        "- summary: A concise, factual summary of the interaction\n"
        "Return ONLY the raw JSON object, without markdown formatting."
    )
    
    def call_llm(model_name):
        llm = get_model(model_name)
        response = llm.invoke([
            ("system", system_prompt),
            ("human", message)
        ])
        content = response.content.strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()
        return json.loads(content)

    data = {}
    try:
        data = call_llm(settings.groq_model)
    except Exception as e:
        if "decommissioned" in str(e) or "gemma2-9b-it" in str(e):
            try:
                data = call_llm("llama-3.3-70b-versatile")
            except Exception:
                pass

    topics = data.get("topics_discussed", "")
    if isinstance(topics, list):
        topics = ", ".join(str(t) for t in topics)
        
    return {
        "hcp_name": str(data.get("hcp_name", "")),
        "interaction_type": str(data.get("interaction_type", "Meeting")).capitalize(),
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "topics_discussed": str(topics),
        "sentiment": str(data.get("sentiment", "neutral")).lower().strip(),
        "attendees": [str(x) for x in data.get("attendees", [])] if isinstance(data.get("attendees"), list) else [],
        "outcomes": str(data.get("outcomes", "")),
        "materials": [str(x) for x in data.get("materials", [])] if isinstance(data.get("materials"), list) else [],
        "samples": [str(x) for x in data.get("samples", [])] if isinstance(data.get("samples"), list) else [],
        "follow_ups": [str(x) for x in data.get("follow_ups", [])] if isinstance(data.get("follow_ups"), list) else [],
        "follow_up_suggestions": [str(x) for x in data.get("follow_ups", [])] if isinstance(data.get("follow_ups"), list) else [],
        "summary": str(data.get("summary", "")),
    }

def run_interaction_agent(
    message: str,
    interaction_id: str = None,
    hcp_name: str = None,
    interaction_type: str = None,
    topics_discussed: str = None,
    sentiment: str = None,
    outcomes: str = None
) -> dict:
    agent_response = ""
    
    # Construct system prompt with current active state to prevent name-guessing and parameter invention
    system_inst = (
        "You are an AI assistant for a pharmaceutical CRM. "
        "The user is currently viewing/editing the following interaction in the form:\n"
    )
    if interaction_id:
        system_inst += f"- Active Interaction ID: {interaction_id}\n"
    else:
        system_inst += "- Active Interaction ID: None (new interaction draft)\n"
        
    system_inst += (
        f"- Current HCP Name: {hcp_name if hcp_name else 'None'}\n"
        f"- Current Interaction Type: {interaction_type if interaction_type else 'Meeting'}\n"
        f"- Current Topics: {topics_discussed if topics_discussed else 'None'}\n"
        f"- Current Sentiment: {sentiment if sentiment else 'neutral'}\n"
        f"- Current Outcomes: {outcomes if outcomes else 'None'}\n\n"
        "Instructions:\n"
        "1. If the user wants to EDIT or UPDATE the interaction, you MUST call the `edit_interaction` tool using the active interaction ID.\n"
        "2. When calling `edit_interaction`, ONLY supply the parameters the user explicitly asked to change. "
        "Do NOT invent or guess values. For example, if the user only asks to change the sentiment, leave hcp_name and other fields as None. "
        "Never change the doctor's name or make up a default name (like Dr. Smith) unless the user explicitly requested to rename/change the HCP."
    )

    try:
        graph = get_agent_graph()
        inputs = {
            "messages": [
                ("system", system_inst),
                ("user", message)
            ]
        }
        result = graph.invoke(inputs)
        messages = result.get("messages", [])
        if messages:
            agent_response = messages[-1].content
    except Exception as e:
        if "decommissioned" in str(e) or "gemma2-9b-it" in str(e):
            try:
                fallback_graph = build_agent_graph("llama-3.3-70b-versatile")
                inputs = {
                    "messages": [
                        ("system", system_inst),
                        ("user", message)
                    ]
                }
                result = fallback_graph.invoke(inputs)
                messages = result.get("messages", [])
                if messages:
                    agent_response = messages[-1].content
            except Exception as fe:
                agent_response = f"Assistant error: {str(fe)}"
        else:
            agent_response = f"Assistant error: {str(e)}"
        
    draft = extract_draft(message)
    
    return {
        "message": agent_response,
        "draft": draft
    }
