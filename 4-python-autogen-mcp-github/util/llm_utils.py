"""Utilities for working with the selected LLM (now GitHub Models).

This project previously supported ad-hoc local model names via a custom
registry. We simplify everything to rely on standard, hosted GitHub Models
that are exposed through an OpenAI-compatible API surface.

Environment variables:
  LLM_MODELS        - (optional) comma-separated list of model names for rotation.
  LLM_MODEL         - (optional) single model name fallback. Defaults to 'gpt-4o-mini'.
  OPENAI_API_KEY    - Required. Supply a GitHub personal access token (classic
                       with "models.read" scope) or the GitHub Models token.
  OPENAI_BASE_URL   - (optional) override base URL. Defaults to the GitHub
                       Models inference endpoint.
"""

from typing import List, Optional
import os
from openai import OpenAI

GITHUB_MODELS_BASE_URL = "https://models.inference.ai.azure.com"

# Global counter for round-robin model rotation
_model_rotation_counter = 0


def get_llm_models() -> List[str]:
    """
    Get the list of configured LLM models from environment variables.

    Returns:
        List[str]: List of model names for rotation, defaults to single model.
    """
    models_str = os.getenv("LLM_MODELS", "")
    if models_str:
        # Parse comma-separated list and strip whitespace
        return [model.strip() for model in models_str.split(",") if model.strip()]

    # Fallback to single model
    single_model = os.getenv("LLM_MODEL", "gpt-4o-mini")
    return [single_model]


def get_llm_model() -> str:
    """
    Get the configured LLM model name from environment variables.
    Uses the first model from the list if multiple are configured.

    Returns:
        str: The model name to use, defaults to 'gpt-4o-mini'.
    """
    models = get_llm_models()
    return models[0] if models else "gpt-4o-mini"


def get_next_llm_model() -> str:
    """
    Get the next LLM model in rotation for performance comparison.
    Uses round-robin rotation through the configured model list.

    Returns:
        str: The next model name to use for this request.
    """
    global _model_rotation_counter

    models = get_llm_models()
    if not models:
        return "gpt-4o-mini"

    # Round-robin through available models
    model = models[_model_rotation_counter % len(models)]
    _model_rotation_counter += 1

    return model


def query_llm(
    user_message: Optional[str] = None,
    assistant_message: Optional[str] = None,
) -> str:
    """Query the configured GitHub Model via the OpenAI compatible client."""
    messages = []
    if assistant_message:
        messages.append({"role": "assistant", "content": assistant_message})
    if user_message:
        messages.append({"role": "user", "content": user_message})
    if not messages:
        return ""

    client = OpenAI(
        base_url=os.getenv("OPENAI_BASE_URL", GITHUB_MODELS_BASE_URL),
        api_key=os.getenv("OPENAI_API_KEY"),
    )
    completion = client.chat.completions.create(
        model=get_llm_model(),
        messages=messages,
        temperature=0.7,
    )
    return completion.choices[0].message.content or ""  # type: ignore[attr-defined]
