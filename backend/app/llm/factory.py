"""
LLM Factory
Provider-agnostic LLM client factory
"""

from typing import Optional

from app.core.config import settings
from app.llm.base import BaseLLMClient, LLMConfig
from app.llm.gemini_client import GeminiClient
from app.llm.claude_client import ClaudeClient
from app.llm.openai_client import OpenAIClient


class LLMFactory:
    """Factory for creating LLM clients based on provider"""
    
    _providers = {
        "gemini": GeminiClient,
        "claude": ClaudeClient,
        "openai": OpenAIClient,
    }
    
    @classmethod
    def create(
        cls,
        provider: Optional[str] = None,
        api_key: Optional[str] = None,
        config: Optional[LLMConfig] = None
    ) -> BaseLLMClient:
        """
        Create an LLM client for the specified provider
        
        Args:
            provider: LLM provider name (gemini, claude, openai).
                     If not specified, uses settings.llm_provider
            api_key: API key for the provider.
                    If not specified, uses key from settings
            config: LLM configuration. If not specified, uses defaults from settings
        
        Returns:
            Configured LLM client
        
        Raises:
            ValueError: If provider is not supported or API key is missing
        """
        # Use default provider if not specified
        provider = provider or settings.llm_provider
        provider = provider.lower()
        
        if provider not in cls._providers:
            raise ValueError(
                f"Unsupported LLM provider: {provider}. "
                f"Supported providers: {list(cls._providers.keys())}"
            )
        
        # Get API key
        if not api_key:
            api_key = cls._get_api_key(provider)
        
        if not api_key:
            raise ValueError(
                f"API key not provided for {provider}. "
                f"Set {provider.upper()}_API_KEY environment variable."
            )
        
        # Create config if not provided
        if not config:
            config = cls._get_default_config(provider)
        
        # Create and return client
        client_class = cls._providers[provider]
        return client_class(api_key=api_key, config=config)
    
    @classmethod
    def _get_api_key(cls, provider: str) -> Optional[str]:
        """Get API key for provider from settings"""
        key_map = {
            "gemini": settings.gemini_api_key,
            "claude": settings.claude_api_key,
            "openai": settings.openai_api_key,
        }
        return key_map.get(provider)
    
    @classmethod
    def _get_default_config(cls, provider: str) -> LLMConfig:
        """Get default config for provider from settings"""
        model_map = {
            "gemini": "gemini-3-flash-preview", # Force user requested model
            "claude": settings.llm_claude_model,
            "openai": settings.llm_openai_model,
        }
        
        return LLMConfig(
            model=model_map.get(provider, "default"),
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
            timeout=settings.llm_timeout_seconds,
        )
    
    @classmethod
    def get_available_providers(cls) -> list[str]:
        """Get list of providers with configured API keys"""
        available = []
        for provider in cls._providers.keys():
            if cls._get_api_key(provider):
                available.append(provider)
        return available
    
    @classmethod
    async def health_check_all(cls) -> dict[str, bool]:
        """
        Check health of all available providers
        
        Returns:
            Dictionary of provider -> health status
        """
        results = {}
        for provider in cls.get_available_providers():
            try:
                client = cls.create(provider)
                results[provider] = await client.health_check()
            except Exception:
                results[provider] = False
        return results


def get_llm_client(
    provider: Optional[str] = None,
    api_key: Optional[str] = None
) -> BaseLLMClient:
    """
    Convenience function to get an LLM client
    
    Args:
        provider: Optional provider override
        api_key: Optional API key override
    
    Returns:
        Configured LLM client
    """
    return LLMFactory.create(provider=provider, api_key=api_key)
