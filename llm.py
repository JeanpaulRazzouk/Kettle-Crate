import json
import os

from dotenv import load_dotenv

load_dotenv(".env.example")  # holds the real local secrets, see .env.example itself

PROVIDER = os.getenv("PROVIDER", "openai")
MODEL = os.getenv("MODEL") or os.getenv("LLM_MODEL")

RESPOND_TOOL_NAME = "respond_to_customer"

FIELD_ENUM = ["issue", "name", "email", "order_number", "item", "resolution", "phone", "complete"]

# The model calls this tool on every turn instead of printing a reply as
# free-form prose. That gets us two things a plain chat completion can't:
# a `current_field` the frontend can trust directly (no more guessing which
# question is being asked from keywords), and a validated `complaint` object
# once everything has been collected (no more regex-scraping a magic string
# out of the model's prose).
TOOL_SCHEMA = {
    "name": RESPOND_TOOL_NAME,
    "description": (
        "Send the next message to the customer and report where the conversation "
        "stands. Call this exactly once per turn — it is the only way to reply."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "message": {
                "type": "string",
                "description": (
                    "The single next thing to say to the customer — just the current "
                    "question or statement. Do not restate information already "
                    "confirmed earlier in the conversation."
                ),
            },
            "current_field": {
                "type": "string",
                "enum": FIELD_ENUM,
                "description": (
                    "Which of the 7 fields you are currently collecting, or "
                    "'complete' once you've thanked the customer and filed the "
                    "complaint."
                ),
            },
            "complaint": {
                "type": "object",
                "description": (
                    "Include this only once every field below has been collected — "
                    "including it files the complaint."
                ),
                "properties": {
                    "name": {"type": "string"},
                    "email": {"type": "string"},
                    "order_number": {"type": "string"},
                    "item": {"type": "string"},
                    "issue": {"type": "string"},
                    "resolution": {"type": "string"},
                    "phone": {"type": "string"},
                    "urgency": {
                        "type": "string",
                        "enum": ["normal", "high"],
                        "description": (
                            "'high' if the customer seems especially upset, is "
                            "threatening to escalate (bad review, asking for a "
                            "manager, refusing the outcome), or the issue is "
                            "safety-related. 'normal' otherwise."
                        ),
                    },
                },
                "required": [
                    "name",
                    "email",
                    "order_number",
                    "item",
                    "issue",
                    "resolution",
                    "phone",
                    "urgency",
                ],
            },
        },
        "required": ["message", "current_field"],
    },
}


def ask(messages, system):
    """Customer-facing turn: forces the respond_to_customer tool, returns its
    parsed arguments as a dict — {message, current_field, complaint?}."""
    if PROVIDER == "openai":
        return _ask_openai_tool(messages, system)
    return _ask_anthropic_tool(messages, system)


def ask_plain(messages, system):
    """Free-text completion for internal (non-customer-facing) uses, like
    drafting a staff reply — no tool, just a plain string back."""
    if PROVIDER == "openai":
        return _ask_openai_plain(messages, system)
    return _ask_anthropic_plain(messages, system)


def _ask_openai_tool(messages, system):
    from openai import OpenAI

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured")

    client = OpenAI(api_key=api_key)
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "system", "content": system}] + messages,
        max_completion_tokens=700,
        reasoning_effort="low",
        tools=[{"type": "function", "function": TOOL_SCHEMA}],
        tool_choice={"type": "function", "function": {"name": RESPOND_TOOL_NAME}},
    )
    tool_calls = resp.choices[0].message.tool_calls
    if not tool_calls:
        raise RuntimeError("Model did not call the expected tool")
    return json.loads(tool_calls[0].function.arguments)


def _ask_anthropic_tool(messages, system):
    import anthropic

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not configured")

    client = anthropic.Anthropic(api_key=api_key)
    resp = client.messages.create(
        model=MODEL,
        max_tokens=700,
        system=system,
        messages=messages,
        tools=[TOOL_SCHEMA],
        tool_choice={"type": "tool", "name": RESPOND_TOOL_NAME},
    )
    for block in resp.content:
        if block.type == "tool_use":
            return block.input
    raise RuntimeError("Model did not call the expected tool")


def _ask_openai_plain(messages, system):
    from openai import OpenAI

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured")

    client = OpenAI(api_key=api_key)
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "system", "content": system}] + messages,
        max_completion_tokens=400,
        reasoning_effort="low",
    )
    return resp.choices[0].message.content


def _ask_anthropic_plain(messages, system):
    import anthropic

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not configured")

    client = anthropic.Anthropic(api_key=api_key)
    resp = client.messages.create(
        model=MODEL,
        max_tokens=400,
        system=system,
        messages=messages,
    )
    return resp.content[0].text
