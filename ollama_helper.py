import requests
import logging
from exceptions import AIError

logger = logging.getLogger(__name__)


class OllamaAPI:
    def __init__(self, base_url="http://localhost:11434"):
        self.base_url = base_url
        self.system_prompt = """You are Buddy, a warm and friendly AI companion who loves chatting with people! Your personality is:
- Super friendly and enthusiastic
- Casual and down-to-earth
- Always positive and supportive
- Uses simple, conversational language
- Asks follow-up questions to show interest
- Shares brief personal opinions (while making clear you're an AI)
- Admits when you don't know something with a friendly "Hmm, I'm not sure about that one!"

Keep responses concise but engaging. Make the conversation feel natural and fun!"""

    def generate_response(self, prompt, model="llama3.2"):
        try:
            formatted_prompt = f"{self.system_prompt}\n\nHuman: {prompt}\n\nBuddy:"

            try:
                response = requests.post(
                    f"{self.base_url}/api/generate",
                    json={
                        "model": model,
                        "prompt": formatted_prompt,
                        "stream": False,
                        "options": {
                            "temperature": 0.7,
                            "top_p": 0.9,
                            "top_k": 40,
                            "num_predict": 256,
                        },
                    },
                    timeout=30,  # Add timeout
                )
            except requests.Timeout:
                raise AIError("Oops! I'm taking too long to respond. Please try again.")
            except requests.ConnectionError:
                raise AIError(
                    "Hi! I'm having trouble connecting. Is the AI service running?"
                )

            if response.status_code == 200:
                return response.json()["response"]
            else:
                raise AIError(
                    "Sorry! Something went wrong. Please try again in a moment."
                )

        except Exception as e:
            logger.error(f"AI generation error: {str(e)}")
            if not isinstance(e, AIError):
                raise AIError(f"Failed to generate AI response: {str(e)}")
            raise
