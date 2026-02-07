"""
Anthropic Claude LLM Client
"""

import json
from typing import Any, Dict, List, Optional

import anthropic

from app.llm.base import BaseLLMClient, LLMConfig, LLMMessage, LLMResponse


class ClaudeClient(BaseLLMClient):
    """Anthropic Claude API client"""
    
    provider_name = "claude"
    
    def __init__(self, api_key: str, config: Optional[LLMConfig] = None):
        """
        Initialize Claude client
        
        Args:
            api_key: Anthropic API key
            config: LLM configuration
        """
        super().__init__(api_key, config)
        
        # Initialize async client
        self.client = anthropic.AsyncAnthropic(api_key=api_key)
        
        # Default model
        if not self.config.model or self.config.model == "default":
            self.config.model = "claude-3-5-sonnet-20241022"
    
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> LLMResponse:
        """
        Generate text using Claude
        
        Args:
            prompt: User prompt
            system_prompt: Optional system instruction
            **kwargs: Additional options
        
        Returns:
            LLMResponse with generated content
        """
        try:
            # Prepare messages
            messages = [{"role": "user", "content": prompt}]
            
            # Build request
            request_params = {
                "model": kwargs.get("model", self.config.model),
                "max_tokens": kwargs.get("max_tokens", self.config.max_tokens),
                "temperature": kwargs.get("temperature", self.config.temperature),
                "messages": messages,
            }
            
            if system_prompt:
                request_params["system"] = system_prompt
            
            # Generate response
            response = await self.client.messages.create(**request_params)
            
            # Extract content
            content = ""
            if response.content:
                content = response.content[0].text
            
            # Build usage info
            usage = None
            if response.usage:
                usage = {
                    "prompt_tokens": response.usage.input_tokens,
                    "completion_tokens": response.usage.output_tokens,
                    "total_tokens": response.usage.input_tokens + response.usage.output_tokens,
                }
            
            return LLMResponse(
                content=content,
                model=response.model,
                provider=self.provider_name,
                usage=usage,
                finish_reason=response.stop_reason,
                raw_response=response,
            )
            
        except anthropic.APIError as e:
            raise RuntimeError(f"Claude API error: {str(e)}")
        except Exception as e:
            raise RuntimeError(f"Claude generation failed: {str(e)}")
    
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
        # Create JSON-specific system prompt
        json_system_prompt = """You are a precise JSON generator. Your task is to respond with valid JSON only.

Rules:
1. Output ONLY valid JSON - no explanations, no markdown
2. Do not include ```json or ``` markers
3. Ensure all strings are properly escaped
4. Use double quotes for all keys and string values
5. The JSON must be directly parseable by json.loads()"""
        
        if system_prompt:
            json_system_prompt = f"{json_system_prompt}\n\nAdditional context:\n{system_prompt}"
        
        # Add schema to prompt
        full_prompt = f"""{prompt}

You must respond with JSON matching this schema:
{json.dumps(schema, indent=2)}

Output the JSON now:"""
        
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
            # Convert to Claude format
            system_prompt = None
            claude_messages = []
            
            for msg in messages:
                if msg.role == "system":
                    system_prompt = msg.content
                else:
                    claude_messages.append({
                        "role": msg.role,
                        "content": msg.content
                    })
            
            # Build request
            request_params = {
                "model": kwargs.get("model", self.config.model),
                "max_tokens": kwargs.get("max_tokens", self.config.max_tokens),
                "temperature": kwargs.get("temperature", self.config.temperature),
                "messages": claude_messages,
            }
            
            if system_prompt:
                request_params["system"] = system_prompt
            
            # Generate response
            response = await self.client.messages.create(**request_params)
            
            # Extract content
            content = ""
            if response.content:
                content = response.content[0].text
            
            return LLMResponse(
                content=content,
                model=response.model,
                provider=self.provider_name,
                finish_reason=response.stop_reason,
                raw_response=response,
            )
            
        except Exception as e:
            raise RuntimeError(f"Claude chat failed: {str(e)}")
