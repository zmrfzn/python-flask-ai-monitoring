"""Streamlit client for interacting with the MCP testing server."""

import json
import os
import time
from typing import Any, Dict, List, Optional, cast

import httpx
import streamlit as st

DEFAULT_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://localhost:8080")
HEALTH_ENDPOINT = "/health"
CHAT_ENDPOINT = "/chat"
FEEDBACK_ENDPOINT = "/feedback"


@st.cache_resource(show_spinner=False)
def _get_client() -> httpx.Client:
    """
    Get a cached HTTP client for making requests to the server.

    Returns:
        httpx.Client: Configured HTTP client with 10 second timeout.
    """
    return httpx.Client(timeout=httpx.Timeout(10.0))


def ping_server(base_url: str) -> bool:
    """
    Check if the server is healthy by pinging the health endpoint.

    Args:
        base_url: The base URL of the server to check.

    Returns:
        bool: True if server is healthy, False otherwise.
    """
    client = _get_client()
    try:
        response = client.get(f"{base_url.rstrip('/')}{HEALTH_ENDPOINT}")
        response.raise_for_status()
    except httpx.HTTPError:
        return False
    return True


def send_message(
    base_url: str, message: str, max_retries: int = 3
) -> tuple[Dict[str, Any], float]:  # type: ignore
    """
    Send a chat message to the server and return the response with timing.

    Args:
        base_url: The base URL of the server.
        message: The user's message to send.
        max_retries: Maximum number of retry attempts on failure.

    Returns:
        tuple[Dict[str, Any], float]: JSON response from the server and response time in seconds.

    Raises:
        httpx.HTTPError: If all retry attempts fail.
    """
    client = _get_client()

    for attempt in range(max_retries):
        try:
            start_time = time.time()
            response = client.post(
                f"{base_url.rstrip('/')}{CHAT_ENDPOINT}",
                json={"message": message},
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()
            elapsed_time = time.time() - start_time
            return response.json(), elapsed_time
        except httpx.HTTPError as exc:
            if attempt < max_retries - 1:
                time.sleep(1 * (attempt + 1))  # Exponential backoff
                continue
            raise exc


def send_feedback(
    base_url: str, trace_id: str, rating: int, message: str = "", metadata: Optional[dict] = None
) -> Dict[str, Any]:
    """
    Send feedback for a chat response to the server.

    Args:
        base_url: The base URL of the server.
        trace_id: The New Relic trace_id from the chat response.
        rating: The user's rating (1 for thumbs up, 0 for thumbs down).
        message: Optional message associated with the feedback.
        metadata: Optional additional metadata.

    Returns:
        Dict[str, Any]: JSON response from the server.

    Raises:
        httpx.HTTPError: If the request fails.
    """
    client = _get_client()
    payload = {
        "trace_id": trace_id,
        "rating": rating,
        "message": message,
    }
    if metadata:
        payload["metadata"] = metadata

    response = client.post(
        f"{base_url.rstrip('/')}{FEEDBACK_ENDPOINT}",
        json=payload,
        headers={"Content-Type": "application/json"},
    )
    response.raise_for_status()
    return response.json()


def render_sidebar() -> str:
    """
    Render the Streamlit sidebar with server settings and health check.

    Returns:
        str: The configured server base URL.
    """
    st.sidebar.header("⚙️ Server Settings")
    base_url = st.sidebar.text_input(
        "Server URL",
        value=DEFAULT_SERVER_URL,
        help="Base URL for the FastAPI MCP server (e.g. http://localhost:8080)",
    )

    status_placeholder = st.sidebar.empty()
    if st.sidebar.button("🔍 Check Health", use_container_width=True):
        healthy = ping_server(base_url)
        if healthy:
            status_placeholder.success("✅ Server is healthy")
        else:
            status_placeholder.error("❌ Server check failed")

    st.sidebar.markdown("---")

    # Chat statistics
    if "chat_history" in st.session_state:
        chat_history = st.session_state["chat_history"]
        total_messages = len(chat_history)
        user_messages = sum(1 for m in chat_history if m.get("role") == "user")
        assistant_messages = sum(
            1 for m in chat_history if m.get("role") == "assistant"
        )

        # Calculate average response time
        response_times = [
            m.get("response_time", 0) for m in chat_history if m.get("response_time")
        ]
        avg_response_time = (
            sum(response_times) / len(response_times) if response_times else 0
        )

        st.sidebar.header("📊 Session Statistics")
        st.sidebar.metric("Total Messages", total_messages)
        col1, col2 = st.sidebar.columns(2)
        col1.metric("User", user_messages)
        col2.metric("Assistant", assistant_messages)
        if avg_response_time > 0:
            st.sidebar.metric("Avg Response Time", f"{avg_response_time:.2f}s")

        st.sidebar.markdown("---")

    st.sidebar.caption("💡 Tip: Set MCP_SERVER_URL env var to override the default.")
    st.sidebar.caption("🔄 Retry logic: 3 attempts with exponential backoff")

    return base_url


def render_chat(base_url: str) -> None:
    """
    Render the main chat interface and handle user interactions.

    Args:
        base_url: The base URL of the server to send messages to.
    """
    # Add custom CSS for scrollable chat
    st.markdown(
        """
        <style>
        /* Keep chat input at bottom */
        .stChatInputContainer {
            position: sticky;
            bottom: 0;
            background-color: var(--background-color);
            padding: 1rem 0;
            z-index: 100;
        }
        </style>
    """,
        unsafe_allow_html=True,
    )

    # Fixed header container
    with st.container():
        col_title, col_clear = st.columns([4, 1])
        with col_title:
            st.title("MCP Testing Client")
            st.caption("Chat with the orchestrator backed by MCP tools.")
        with col_clear:
            st.write("")  # Spacing
            if st.button("🗑️ Clear Chat", use_container_width=True, type="secondary"):
                st.session_state["chat_history"] = []
                st.rerun()

        # Initialize session state
        if "pending_prompt" not in st.session_state:
            st.session_state["pending_prompt"] = None
        if "show_examples" not in st.session_state:
            st.session_state["show_examples"] = True

        # Collapsible example prompts section
        col_header, col_toggle = st.columns([4, 1])
        with col_header:
            st.subheader("Example Prompts")
        with col_toggle:
            st.write("")  # Spacing
            if st.button(
                "🔼 Hide" if st.session_state["show_examples"] else "🔽 Show",
                use_container_width=True,
                type="secondary",
            ):
                st.session_state["show_examples"] = not st.session_state[
                    "show_examples"
                ]

        if st.session_state["show_examples"]:
            st.caption("Click a button to try example queries that use the MCP tools:")

            col1, col2, col3, col4 = st.columns(4)

            with col1:
                if st.button("🧮 Calculator", use_container_width=True):
                    st.session_state["pending_prompt"] = (
                        "What is 123 multiplied by 456?"
                    )

            with col2:
                if st.button("🌤️ Weather", use_container_width=True):
                    st.session_state["pending_prompt"] = (
                        "What's the weather like in Tokyo?"
                    )

            with col3:
                if st.button("📄 File Reader", use_container_width=True):
                    st.session_state["pending_prompt"] = "Summarize the sample.txt file"

            with col4:
                if st.button("📊 Cache Stats", use_container_width=True):
                    st.session_state["pending_prompt"] = (
                        "Show me the weather cache statistics"
                    )

            # Additional example row for combo queries
            col5, col6, col7 = st.columns(3)

            with col5:
                if st.button("🔢 Math + Weather", use_container_width=True):
                    st.session_state["pending_prompt"] = (
                        "Calculate 25 times 4, then tell me the weather in Paris"
                    )

            with col6:
                if st.button("🌍 Multiple Cities", use_container_width=True):
                    st.session_state["pending_prompt"] = (
                        "Compare the weather in London, New York, and Sydney"
                    )

            with col7:
                if st.button("📈 Complex Query", use_container_width=True):
                    st.session_state["pending_prompt"] = (
                        "Get the weather in San Francisco, multiply the temperature by 2, and show cache stats"
                    )

        st.markdown("---")

    if "chat_history" not in st.session_state:
        st.session_state["chat_history"] = []

    chat_history = cast(List[Dict[str, Any]], st.session_state["chat_history"])

    # Scrollable chat history container with message count
    total_messages = len(chat_history)
    st.markdown(
        f"### Chat History ({total_messages // 2} exchanges)"
        if total_messages > 0
        else "### Chat History (empty)"
    )
    with st.container(height=500, border=True):
        if total_messages == 0:
            st.info(
                "👋 Start a conversation by typing a message or clicking an example button above!"
            )
        else:
            # Display chat history in reverse order (most recent at top)
            for idx, entry in enumerate(reversed(chat_history)):
                with st.chat_message(entry["role"]):
                    st.markdown(entry["content"])
                    # Show response time and model for assistant messages
                    if entry["role"] == "assistant":
                        caption_parts = []
                        if "response_time" in entry:
                            caption_parts.append(f"⏱️ {entry['response_time']:.2f}s")
                        if "model" in entry:
                            caption_parts.append(f"🤖 {entry['model']}")
                        if caption_parts:
                            st.caption(" | ".join(caption_parts))
                        
                        # Add feedback buttons if trace_id is available
                        if "trace_id" in entry and entry.get("trace_id"):
                            feedback_key = f"feedback_{entry['trace_id']}"
                            
                            # Check if feedback already given
                            if feedback_key not in st.session_state:
                                col1, col2, col3 = st.columns([1, 1, 8])
                                with col1:
                                    if st.button("👍", key=f"thumbs_up_{idx}", help="This response was helpful"):
                                        st.session_state[feedback_key] = "positive"
                                        try:
                                            send_feedback(base_url, entry["trace_id"], 1, metadata={"model": entry.get("model")})
                                            st.toast("✅ Thanks for the positive feedback!", icon="👍")
                                        except Exception as e:
                                            st.toast(f"❌ Failed to send feedback: {e}", icon="❌")
                                        st.rerun()
                                with col2:
                                    if st.button("👎", key=f"thumbs_down_{idx}", help="This response needs improvement"):
                                        st.session_state[feedback_key] = "negative"
                                        try:
                                            send_feedback(base_url, entry["trace_id"], 0, metadata={"model": entry.get("model")})
                                            st.toast("✅ Thanks for the feedback!", icon="👎")
                                        except Exception as e:
                                            st.toast(f"❌ Failed to send feedback: {e}", icon="❌")
                                        st.rerun()
                            else:
                                # Show feedback status
                                feedback_status = st.session_state[feedback_key]
                                if feedback_status == "positive":
                                    st.caption("👍 You found this helpful")
                                else:
                                    st.caption("👎 You provided negative feedback")

    # Always show the chat input, but check for pending prompt from button click
    user_input = st.chat_input("Ask me anything...")

    # Use pending prompt if available, otherwise use chat input
    if st.session_state["pending_prompt"]:
        user_input = st.session_state["pending_prompt"]
        st.session_state["pending_prompt"] = None  # Clear it after using

    # Initialize processing state
    if "processing" not in st.session_state:
        st.session_state["processing"] = False

    # Handle new user input
    if user_input and not st.session_state["processing"]:
        # Add user message to history
        chat_history.append({"role": "user", "content": user_input})
        # Mark as processing and store the message to process
        st.session_state["processing"] = True
        st.session_state["current_message"] = user_input
        st.rerun()

    # Process the message after rerun (so it shows in the container)
    if st.session_state["processing"]:
        current_msg = st.session_state.get("current_message", "")
        retry_count = 3

        try:
            payload, response_time = send_message(
                base_url, current_msg, max_retries=retry_count
            )
            answer = payload.get("response", "(no response)")

            # Handle MCP-style content blocks if they weren't cleaned server-side
            if isinstance(answer, str) and answer.startswith('[{"type":'):
                try:
                    blocks = json.loads(answer)
                    if isinstance(blocks, list):
                        text_parts = [
                            block.get("text", "")
                            for block in blocks
                            if isinstance(block, dict) and block.get("type") == "text"
                        ]
                        answer = "".join(text_parts) if text_parts else answer
                except json.JSONDecodeError:
                    pass  # Keep original answer if parsing fails

            # Extract model information and trace_id from response
            model_used = payload.get("model", "unknown")
            trace_id = payload.get("trace_id", "")

            chat_history.append(
                {
                    "role": "assistant",
                    "content": answer,
                    "response_time": response_time,
                    "model": model_used,
                    "trace_id": trace_id,
                }
            )
            st.toast(
                f"✅ Response from {model_used} in {response_time:.2f}s", icon="✅"
            )

        except httpx.HTTPError as exc:
            error_message = f"❌ Request failed after {retry_count} attempts: {exc}"
            chat_history.append({"role": "assistant", "content": error_message})
            st.toast(f"❌ Error: {type(exc).__name__}", icon="❌")

        finally:
            # Clear processing state
            st.session_state["processing"] = False
            st.session_state["current_message"] = None
            st.rerun()


def main() -> None:
    """Run the Streamlit client application."""
    base_url = render_sidebar()
    render_chat(base_url)


if __name__ == "__main__":
    main()
