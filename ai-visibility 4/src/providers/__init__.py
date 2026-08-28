from .chatgpt import ChatGPTProvider
from .gemini import GeminiProvider
from .google_ai_overview import GoogleAIOverviewProvider

PROVIDERS = {
    ChatGPTProvider.key: ChatGPTProvider(),
    GeminiProvider.key: GeminiProvider(),
    GoogleAIOverviewProvider.key: GoogleAIOverviewProvider(),
}
