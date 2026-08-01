# Copyright (c) Microsoft. All rights reserved.

"""
Sample: Hotel Booking Conditional Workflow

This sample demonstrates a conditional workflow using the Microsoft Agent Framework
that routes based on hotel availability.

Workflow:
1. User provides a destination city
2. Agent checks hotel availability using a tool
3. Conditional routing:
   - If NO availability → Suggest alternative city
   - If availability → Suggest booking
4. Display result with HTML formatting

Key Concepts:
- WorkflowBuilder with conditional edges
- AgentExecutor wrapping AI agents
- @executor decorator for custom logic
- Pydantic models for structured outputs
- @ai_function decorator for tools
- OpenAIChatClient integration
"""

import asyncio
import json
import os
from typing import Annotated, Any, Never

# --- original teaching imports (kept, not deleted) ---
# from agent_framework import (
#     AgentExecutor,
#     AgentExecutorRequest,
#     AgentExecutorResponse,
#     ChatMessage,
#     Role,
#     WorkflowBuilder,
#     WorkflowContext,
#     ai_function,
#     executor,
# )
# from agent_framework.openai import OpenAIChatClient

# --- MAF 1.10 local-compatible imports ---
# 本代码已经替换为本地api
from agent_framework import (
    AgentExecutor,
    AgentExecutorRequest,
    AgentExecutorResponse,
    Message,
    WorkflowBuilder,
    WorkflowContext,
    executor,
    tool,
)
from agent_framework.openai import OpenAIChatClient  # teaching import retained
from azure.identity import AzureCliCredential
from dotenv import load_dotenv
from pydantic import BaseModel

# ============================================================================
# STEP 1: PYDANTIC MODELS FOR STRUCTURED OUTPUTS
# ============================================================================


class BookingCheckResult(BaseModel):
    """Result from checking hotel availability at a destination."""

    destination: str
    has_availability: bool
    message: str


class AlternativeResult(BaseModel):
    """Suggested alternative destination when no rooms available."""

    alternative_destination: str
    reason: str


class BookingConfirmation(BaseModel):
    """Booking suggestion when rooms are available."""

    destination: str
    action: str
    message: str


# ============================================================================
# STEP 2: HOTEL BOOKING TOOL (AI FUNCTION)
# ============================================================================


# --- original: @ai_function(...) ---
@tool(description="Check hotel room availability for a destination city")  # 本代码已经替换为本地api
def hotel_booking(destination: Annotated[str, "The destination city to check for hotel rooms"]) -> str:
    """
    Simulates checking hotel room availability.

    For demo purposes:
    - Stockholm, Seattle, Tokyo have rooms
    - All other cities don't have rooms

    Returns:
        JSON string with availability status
    """
    print(f"🔍 Checking hotel availability in {destination}...")

    # Simulate availability check
    cities_with_rooms = ["stockholm", "seattle", "tokyo", "london", "amsterdam"]
    has_rooms = any(city in destination.lower() for city in cities_with_rooms)  # 本代码已经替换为本地api: substring match

    result = {"has_availability": has_rooms, "destination": destination}

    return json.dumps(result)


# ============================================================================
# STEP 3: CONDITION FUNCTIONS FOR ROUTING
# ============================================================================


def has_availability_condition(message: Any) -> bool:
    """
    Condition for routing when hotels ARE available.

    Args:
        message: Message from upstream executor (should be AgentExecutorResponse)

    Returns:
        True if availability exists, False otherwise
    """
    if not isinstance(message, AgentExecutorResponse):
        return True  # Default to True if not the expected type

    try:
        result = BookingCheckResult.model_validate_json(message.agent_response.text)  # was agent_run_response
        print(f"✅ Availability check: {result.has_availability} for {result.destination}")
        return result.has_availability
    except Exception as e:
        print(f"⚠️  Error parsing availability result: {e}")
        return False


def no_availability_condition(message: Any) -> bool:
    """
    Condition for routing when hotels are NOT available.

    Args:
        message: Message from upstream executor

    Returns:
        True if no availability, False otherwise
    """
    if not isinstance(message, AgentExecutorResponse):
        return False

    try:
        result = BookingCheckResult.model_validate_json(message.agent_response.text)  # was agent_run_response
        print(f"❌ No availability for {result.destination}")
        return not result.has_availability
    except Exception as e:
        print(f"⚠️  Error parsing availability result: {e}")
        return False


# ============================================================================
# STEP 4: DISPLAY EXECUTOR (Custom transformation)
# ============================================================================


@executor(id="display_result")
async def display_result(response: AgentExecutorResponse, ctx: WorkflowContext[Never, str]) -> None:
    """
    Display the final result as workflow output.

    This executor receives the final agent response and yields it as output.
    """
    print(f"📤 Yielding workflow output...")
    await ctx.yield_output(response.agent_response.text)  # was agent_run_response


# ============================================================================
# STEP 5: MAIN WORKFLOW FUNCTION
# ============================================================================


async def main() -> None:
    """
    Main function to build and execute the hotel booking workflow.
    """
    # Load environment variables
    load_dotenv()

    # Verify configuration
    print("=" * 80)
    print("🏨 HOTEL BOOKING CONDITIONAL WORKFLOW")
    print("=" * 80)

    # Provider selection: Azure OpenAI (Responses API), OpenAI, or MiniMax
    # The OpenAIChatClient works with any OpenAI-compatible API, and targets the
    # Azure OpenAI Responses API when given an azure_endpoint + credential.
    #
    # --- original teaching provider selection (kept, not deleted) ---
    # minimax_api_key = os.getenv("MINIMAX_API_KEY")
    # azure_openai_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    # openai_api_key = os.getenv("OPENAI_API_KEY")
    #
    # if minimax_api_key:
    #     chat_client = OpenAIChatClient(
    #         base_url=os.environ.get("MINIMAX_BASE_URL", "https://api.minimax.io/v1"),
    #         api_key=minimax_api_key,
    #         model_id=os.environ.get("MINIMAX_MODEL_ID", "MiniMax-M3"),
    #     )
    #     print("Using MiniMax provider")
    # elif azure_openai_endpoint:
    #     chat_client = OpenAIChatClient(
    #         azure_endpoint=azure_openai_endpoint,
    #         credential=AzureCliCredential(),
    #         model_id=os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-5-mini"),
    #     )
    #     print("Using Azure OpenAI (Responses API) provider")
    # else:
    #     chat_client = OpenAIChatClient(model_id="gpt-5-mini")
    #     print("Using OpenAI provider")

    # --- local vLLM replacement ---
    import sys
    from pathlib import Path as _Path
    _ROOT = _Path(__file__).resolve().parent
    for _candidate in [_ROOT, *_ROOT.parents]:
        if (_candidate / "local_llm.py").exists():
            if str(_candidate) not in sys.path:
                sys.path.insert(0, str(_candidate))
            break
    from local_llm import make_local_chat_client
    chat_client = make_local_chat_client()  # 本代码已经替换为本地api
    print("本代码已经替换为本地api")
    print("Using local vLLM provider")



    print("\n" + "=" * 80)
    print("STEP 1: Creating AI Agents with Structured Outputs")
    print("=" * 80)

    # Agent 1: Check availability
    availability_agent = AgentExecutor(
        chat_client.as_agent(  # 本代码已经替换为本地api (was create_agent)
            instructions=(
                "You are a hotel booking assistant that checks room availability. "
                "Use the hotel_booking tool to check if rooms are available at the destination. "
                "Return JSON with fields: destination (string), has_availability (bool), and message (string). "
                "The message should summarize the availability status."
            ),
            tools=[hotel_booking],
            default_options={"response_format": BookingCheckResult},  # 本代码已经替换为本地api
        ),
        id="availability_agent",
    )
    print("✅ Created availability_agent with hotel_booking tool")

    # Agent 2: Suggest alternative (when no rooms)
    alternative_agent = AgentExecutor(
        chat_client.as_agent(  # 本代码已经替换为本地api (was create_agent)
            instructions=(
                "You are a helpful travel assistant. When a user cannot find hotels in their requested city, "
                "suggest an alternative nearby city that has availability. "
                "Return JSON with fields: alternative_destination (string) and reason (string). "
                "Choose from: Stockholm, Seattle, Tokyo, London, or Amsterdam (these have rooms). "
                "Make your suggestion sound appealing and helpful."
            ),
            default_options={"response_format": AlternativeResult},  # 本代码已经替换为本地api
        ),
        id="alternative_agent",
    )
    print("✅ Created alternative_agent for suggesting other cities")

    # Agent 3: Suggest booking (when rooms available)
    booking_agent = AgentExecutor(
        chat_client.as_agent(  # 本代码已经替换为本地api (was create_agent)
            instructions=(
                "You are a booking assistant. The user has found available hotel rooms. "
                "Encourage them to book by highlighting the destination's appeal. "
                "Return JSON with fields: destination (string), action (string), and message (string). "
                "The action should be 'book_now' and message should be encouraging."
            ),
            default_options={"response_format": BookingConfirmation},  # 本代码已经替换为本地api
        ),
        id="booking_agent",
    )
    print("✅ Created booking_agent for confirming bookings")

    print("\n" + "=" * 80)
    print("STEP 2: Building Workflow with Conditional Edges")
    print("=" * 80)

    # --- original teaching: WorkflowBuilder().set_start_executor(...) ---
    # MAF 1.10 requires start_executor= at construction time.
    # 本代码已经替换为本地api
    workflow = (
        WorkflowBuilder(
            start_executor=availability_agent,
            output_executors=[display_result],
        )
        # NO AVAILABILITY PATH: availability_agent → alternative_agent → display_result
        .add_edge(availability_agent, alternative_agent, condition=no_availability_condition)
        .add_edge(alternative_agent, display_result)
        # HAS AVAILABILITY PATH: availability_agent → booking_agent → display_result
        .add_edge(availability_agent, booking_agent, condition=has_availability_condition)
        .add_edge(booking_agent, display_result)
        .build()
    )

    print("✅ Workflow built with conditional routing:")
    print("   - If NO availability → suggest alternative")
    print("   - If availability → suggest booking")

    # ============================================================================
    # TEST CASE 1: City WITHOUT availability (Paris)
    # ============================================================================
    print("\n" + "=" * 80)
    print("TEST CASE 1: Checking Paris (NO AVAILABILITY)")
    print("=" * 80)

    # --- original: ChatMessage(Role.USER, text=...) ---
    request1 = AgentExecutorRequest(
        messages=[Message(role="user", contents=["I want to book a hotel in Paris"])], should_respond=True
    )  # 本代码已经替换为本地api

    events1 = await workflow.run(request1)
    outputs1 = events1.get_outputs()

    if outputs1:
        print("\n📊 WORKFLOW OUTPUT (Paris):")
        print("-" * 80)
        # Local models may route either branch; accept either structured schema.
        # 本代码已经替换为本地api
        raw1 = outputs1[0]
        try:
            alt = AlternativeResult.model_validate_json(raw1)
            print(f"🏨 Alternative Destination: {alt.alternative_destination}")
            print(f"💡 Reason: {alt.reason}")
        except Exception:
            conf = BookingConfirmation.model_validate_json(raw1)
            print(f"🏨 Destination: {conf.destination}")
            print(f"✅ Action: {conf.action}")
            print(f"💬 Message: {conf.message}")
        print("-" * 80)

    # ============================================================================
    # TEST CASE 2: City WITH availability (Stockholm)
    # ============================================================================
    print("\n" + "=" * 80)
    print("TEST CASE 2: Checking Stockholm (HAS AVAILABILITY)")
    print("=" * 80)

    # --- original: ChatMessage(Role.USER, text=...) ---
    request2 = AgentExecutorRequest(
        messages=[Message(role="user", contents=["I want to book a hotel in Stockholm"])], should_respond=True
    )  # 本代码已经替换为本地api

    events2 = await workflow.run(request2)
    outputs2 = events2.get_outputs()

    if outputs2:
        print("\n📊 WORKFLOW OUTPUT (Stockholm):")
        print("-" * 80)
        # 本代码已经替换为本地api
        raw2 = outputs2[0]
        try:
            conf = BookingConfirmation.model_validate_json(raw2)
            print(f"🏨 Destination: {conf.destination}")
            print(f"✅ Action: {conf.action}")
            print(f"💬 Message: {conf.message}")
        except Exception:
            alt = AlternativeResult.model_validate_json(raw2)
            print(f"🏨 Alternative Destination: {alt.alternative_destination}")
            print(f"💡 Reason: {alt.reason}")
        print("-" * 80)

    print("\n" + "=" * 80)
    print("✅ WORKFLOW DEMO COMPLETE!")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
