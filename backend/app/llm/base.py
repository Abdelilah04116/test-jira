"""
LLM Base Client
Abstract base class for LLM providers
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class LLMMessage(BaseModel):
    """Standard message format for LLM communication"""
    role: str  # system, user, assistant
    content: str


class LLMResponse(BaseModel):
    """Standard response format from LLM"""
    content: str
    model: str
    provider: str
    usage: Optional[Dict[str, int]] = None
    finish_reason: Optional[str] = None
    raw_response: Optional[Any] = None


class LLMConfig(BaseModel):
    """LLM configuration"""
    model: str
    temperature: float = 0.3
    max_tokens: int = 4096
    timeout: int = 60


class BaseLLMClient(ABC):
    """Abstract base class for LLM providers"""
    
    provider_name: str = "base"
    
    def __init__(self, api_key: str, config: Optional[LLMConfig] = None):
        """
        Initialize LLM client
        
        Args:
            api_key: API key for the provider
            config: LLM configuration options
        """
        self.api_key = api_key
        self.config = config or LLMConfig(model="default")
    
    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> LLMResponse:
        """
        Generate text from prompt
        
        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            **kwargs: Additional provider-specific options
        
        Returns:
            LLMResponse with generated content
        """
        pass
    
    @abstractmethod
    async def generate_json(
        self,
        prompt: str,
        schema: Dict[str, Any],
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate structured JSON output
        
        Args:
            prompt: User prompt
            schema: Expected JSON schema
            system_prompt: Optional system prompt
            **kwargs: Additional options
        
        Returns:
            Parsed JSON dictionary
        """
        pass
    
    @abstractmethod
    async def chat(
        self,
        messages: List[LLMMessage],
        **kwargs
    ) -> LLMResponse:
        """
        Multi-turn chat conversation
        
        Args:
            messages: List of conversation messages
            **kwargs: Additional options
        
        Returns:
            LLMResponse with assistant reply
        """
        pass
    
    def _parse_json_response(self, text: str) -> Dict[str, Any]:
        """
        Parse JSON from LLM response, handling common formatting issues
        
        Args:
            text: Raw text response
        
        Returns:
            Parsed JSON dictionary
        """
        import json
        import re
        
        # Remove markdown code blocks if present
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        
        text = text.strip()
        
        # Try to find JSON object or array
        json_match = re.search(r'[\[{].*[\]}]', text, re.DOTALL)
        if json_match:
            text = json_match.group()
        
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            # Try to fix common issues
            # Remove trailing commas
            text = re.sub(r',\s*([}\]])', r'\1', text)
            # Replace single quotes with double quotes
            text = text.replace("'", '"')
            
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                raise ValueError(f"Failed to parse JSON response: {e}")
    
    async def health_check(self) -> bool:
        """
        Check if the LLM service is available
        
        Returns:
            True if healthy, False otherwise
        """
        try:
            response = await self.generate("Say 'OK' if you can read this.")
            return "ok" in response.content.lower()
        except Exception:
            return False
