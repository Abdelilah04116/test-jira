"""
OpenAI LLM Client
"""

import json
from typing import Any, Dict, List, Optional

from openai import AsyncOpenAI

from app.llm.base import BaseLLMClient, LLMConfig, LLMMessage, LLMResponse


class OpenAIClient(BaseLLMClient):
    """OpenAI API client"""
    
    provider_name = "openai"
    
    def __init__(self, api_key: str, config: Optional[LLMConfig] = None):
        """
        Initialize OpenAI client
        
        Args:
            api_key: OpenAI API key
            config: LLM configuration
        """
        super().__init__(api_key, config)
        
        # Initialize async client
        self.client = AsyncOpenAI(api_key=api_key)
        
        # Default model
        if not self.config.model or self.config.model == "default":
            self.config.model = "gpt-4-turbo-preview"
    
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> LLMResponse:
        """
        Generate text using OpenAI
        
        Args:
            prompt: User prompt
            system_prompt: Optional system instruction
            **kwargs: Additional options
        
        Returns:
            LLMResponse with generated content
        """
        try:
            # Prepare messages
            messages = []
            
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            
            messages.append({"role": "user", "content": prompt})
            
            # Generate response
            response = await self.client.chat.completions.create(
                model=kwargs.get("model", self.config.model),
                messages=messages,
                temperature=kwargs.get("temperature", self.config.temperature),
                max_tokens=kwargs.get("max_tokens", self.config.max_tokens),
            )
            
            # Extract content
            content = response.choices[0].message.content or ""
            
            # Build usage info
            usage = None
            if response.usage:
                usage = {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                }
            
            return LLMResponse(
                content=content,
                model=response.model,
                provider=self.provider_name,
                usage=usage,
                finish_reason=response.choices[0].finish_reason,
                raw_response=response,
            )
            
        except Exception as e:
            raise RuntimeError(f"OpenAI generation failed: {str(e)}")
    
    async def generate_json(
        self,
        prompt: str,
        schema: Dict[str, Any],
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate structured JSON output using JSON mode
        
        Args:
            prompt: User prompt
            schema: Expected JSON schema
            system_prompt: Optional system prompt
            **kwargs: Additional options
        
        Returns:
            Parsed JSON dictionary
        """
        # Create JSON-specific system prompt
        json_system_prompt = """You are a JSON generator. Respond with valid JSON only.
Do not include any text, explanations, or markdown formatting.
Output pure JSON that can be directly parsed."""
        
        if system_prompt:
            json_system_prompt = f"{json_system_prompt}\n\n{system_prompt}"
        
        # Add schema to prompt
        full_prompt = f"""{prompt}

Expected JSON schema:
{json.dumps(schema, indent=2)}

Your response:"""
        
        # Prepare messages
        messages = [
            {"role": "system", "content": json_system_prompt},
            {"role": "user", "content": full_prompt}
        ]
        
        try:
            # Use JSON mode if available
            response = await self.client.chat.completions.create(
                model=kwargs.get("model", self.config.model),
                messages=messages,
                temperature=kwargs.get("temperature", self.config.temperature),
                max_tokens=kwargs.get("max_tokens", self.config.max_tokens),
                response_format={"type": "json_object"},
            )
            
            content = response.choices[0].message.content or "{}"
            return json.loads(content)
            
        except Exception:
            # Fallback without JSON mode
            response = await self.generate(
                prompt=full_prompt,
                system_prompt=json_system_prompt,
                **kwargs
            )
            return self._parse_json_response(response.content)
    
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
        try:
            # Convert to OpenAI format
            openai_messages = [
                {"role": msg.role, "content": msg.content}
                for msg in messages
            ]
            
            # Generate response
            response = await self.client.chat.completions.create(
                model=kwargs.get("model", self.config.model),
                messages=openai_messages,
                temperature=kwargs.get("temperature", self.config.temperature),
                max_tokens=kwargs.get("max_tokens", self.config.max_tokens),
            )
            
            # Extract content
            content = response.choices[0].message.content or ""
            
            return LLMResponse(
                content=content,
                model=response.model,
                provider=self.provider_name,
                finish_reason=response.choices[0].finish_reason,
                raw_response=response,
            )
            
        except Exception as e:
            raise RuntimeError(f"OpenAI chat failed: {str(e)}")
