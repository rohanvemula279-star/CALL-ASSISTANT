# Sample HTTP client mirroring the user's "FastAPI Endpoint" snippet.

import requests

from app.config import get_settings


def main() -> None:
    settings = get_settings()
    base = f"http://localhost:{settings.app_port}"

    message = input("You: ")
    response = requests.post(
        f"{base}/chat",
        json={"message": message},
        timeout=settings.ollama_timeout,
    )
    response.raise_for_status()
    print("AI:", response.json()["reply"])


if __name__ == "__main__":
    main()
