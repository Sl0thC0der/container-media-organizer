"""Docker Model Runner API client."""

import time
from typing import Optional
import requests

from ..config import DMR_URL, DMR_MODEL, DMR_TIMEOUT, DMR_MAX_RETRIES
from ..core.logger import Logger


class DMRClient:
    """Client for interacting with Docker Model Runner API."""

    def __init__(self, logger: Logger) -> None:
        """Initialize DMR client."""
        self.logger = logger

    def check_connection(self) -> bool:
        """Check if Docker Model Runner is available and has the required model."""
        try:
            response = requests.get(f"{DMR_URL}/engines/v1/models", timeout=5)
            if response.status_code == 200:
                models = response.json().get('data', [])
                model_ids = [m.get('id', '') for m in models]

                if any(DMR_MODEL in mid for mid in model_ids):
                    self.logger.log(f"[DMR] Connected - using {DMR_MODEL}", "green")
                    return True
                else:
                    self.logger.log(f"[DMR] Model {DMR_MODEL} not found. Available: {model_ids}", "yellow")
                    self.logger.log(f"[DMR] Pull model: docker model pull {DMR_MODEL}", "yellow")
                    return False
            else:
                self.logger.log(f"[DMR] API returned {response.status_code}", "red")
                return False
        except requests.exceptions.RequestException as e:
            self.logger.log(f"[ERROR] Docker Model Runner not available: {e}", "red")
            self.logger.log("[DMR] Check status: docker model status", "yellow")
            self.logger.log(f"[DMR] Pull model: docker model pull {DMR_MODEL}", "yellow")
            return False

    def call_api(self, prompt: str, max_retries: Optional[int] = None) -> Optional[str]:
        """
        Call Docker Model Runner API with retry logic.

        Args:
            prompt: Text prompt to send to the model
            max_retries: Maximum number of retry attempts (uses DMR_MAX_RETRIES if None)

        Returns:
            Model response text, or None if all retries failed
        """
        if max_retries is None:
            max_retries = DMR_MAX_RETRIES

        payload = {
            "model": DMR_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
            "max_tokens": 500,
        }

        for attempt in range(1, max_retries + 1):
            try:
                self.logger.log(f"[DMR] Request attempt {attempt}/{max_retries}...", "cyan")
                start_time = time.time()

                response = requests.post(
                    f"{DMR_URL}/engines/v1/chat/completions",
                    json=payload,
                    timeout=DMR_TIMEOUT
                )

                elapsed = time.time() - start_time

                if response.status_code == 200:
                    result = response.json()
                    answer = result['choices'][0]['message']['content'].strip()
                    self.logger.log(f"[DMR] Response received in {elapsed:.1f}s", "green")
                    return answer
                else:
                    self.logger.log(f"[WARN] DMR error: {response.status_code}", "yellow")
                    if attempt < max_retries:
                        wait = 2 ** attempt
                        self.logger.log(f"[DMR] Retrying in {wait}s...", "yellow")
                        time.sleep(wait)

            except requests.exceptions.Timeout:
                self.logger.log(f"[WARN] DMR timeout on attempt {attempt}", "yellow")
                if attempt < max_retries:
                    time.sleep(2 ** attempt)
            except requests.exceptions.RequestException as e:
                self.logger.log(f"[ERROR] DMR request failed: {e}", "red")
                if attempt < max_retries:
                    time.sleep(2 ** attempt)

        self.logger.log(f"[ERROR] DMR failed after {max_retries} attempts", "red")
        return None
