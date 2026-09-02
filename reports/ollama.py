import logging

import requests

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 5
GENERATE_TIMEOUT_SECONDS = 240


class OllamaError(Exception):
    """Raised when the Ollama instance can't be reached or returns something unexpected."""


def list_models(base_url):
    """Return the list of model names available on the given Ollama instance."""
    logger.info("Fetching model list from %s", base_url)
    try:
        response = requests.get(f"{base_url}/api/tags", timeout=TIMEOUT_SECONDS)
        response.raise_for_status()
    except requests.exceptions.RequestException as exc:
        logger.warning("Fetching model list from %s failed: %s", base_url, exc)
        raise OllamaError(f"Could not reach Ollama at {base_url}: {exc}") from exc

    try:
        data = response.json()
    except ValueError as exc:
        logger.warning("Fetching model list from %s returned non-JSON response", base_url)
        raise OllamaError(f"Ollama at {base_url} returned an unexpected response.") from exc

    models = data.get("models", [])
    names = [m.get("model") or m.get("name") for m in models]
    result = sorted(name for name in names if name)
    logger.info("Fetched %d model(s) from %s", len(result), base_url)
    return result


def generate(base_url, model, prompt):
    """Send a one-shot prompt to Ollama and return the generated text."""
    url = f"{base_url}/api/generate"
    logger.info("Calling Ollama generate: url=%s model=%s prompt_chars=%d", url, model, len(prompt))
    try:
        response = requests.post(
            url,
            json={"model": model, "prompt": prompt, "stream": False},
            timeout=GENERATE_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except requests.exceptions.RequestException as exc:
        logger.warning("Ollama generate call to %s failed: %s", url, exc)
        raise OllamaError(f"Could not reach Ollama at {base_url}: {exc}") from exc

    try:
        data = response.json()
    except ValueError as exc:
        logger.warning("Ollama generate call to %s returned non-JSON response: %r", url, response.text[:500])
        raise OllamaError(f"Ollama at {base_url} returned an unexpected response.") from exc

    text = data.get("response", "").strip()
    if not text:
        logger.warning("Ollama generate call to %s returned an empty response body: %r", url, data)
        raise OllamaError("Ollama returned an empty response.")

    logger.info("Ollama generate call to %s succeeded: response_chars=%d", url, len(text))
    return text
