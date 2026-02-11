"""
Google Gemini LLM Client
"""

import json
import asyncio
import re
from typing import Any, Dict, List, Optional

import google.generativeai as genai
from google.generativeai.types import GenerationConfig, HarmCategory, HarmBlockThreshold

from app.llm.base import BaseLLMClient, LLMConfig, LLMMessage, LLMResponse


class GeminiClient(BaseLLMClient):
    """Google Gemini API client"""
    
    provider_name = "gemini"
    
    def __init__(self, api_key: str, config: Optional[LLMConfig] = None):
        """
        Initialize Gemini client
        
        Args:
            api_key: Google API key
            config: LLM configuration
        """
        super().__init__(api_key, config)
        
        # Configure the API
        genai.configure(api_key=api_key)
        
        # force default model
        if not self.config.model or self.config.model == "default":
            self.config.model = "gemini-1.5-flash"
        
        # Generation config
        self.generation_config = GenerationConfig(
            temperature=self.config.temperature,
            max_output_tokens=self.config.max_tokens,
            top_p=0.95,
            top_k=40,
        )
        
        # Safety settings - relaxed for enterprise use
        self.safety_settings = {
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_ONLY_HIGH,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
        }
        
        # Initialize model
        self.model = genai.GenerativeModel(
            model_name=self.config.model,
            generation_config=self.generation_config,
            safety_settings=self.safety_settings,
        )
    
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> LLMResponse:
        """
        Generate text using Gemini
        
        Args:
            prompt: User prompt
            system_prompt: Optional system instruction
            **kwargs: Additional options
        
        Returns:
            LLMResponse with generated content
        """
        max_retries = 3
        retry_count = 0
        
        while retry_count <= max_retries:
            try:
                # Combine system prompt and user prompt if provided
                full_prompt = prompt
                if system_prompt:
                    full_prompt = f"{system_prompt}\n\n{prompt}"
                
                # Generate response
                generation_config_args = {
                    "temperature": kwargs.get("temperature", self.config.temperature),
                    "max_output_tokens": kwargs.get("max_tokens", self.config.max_tokens),
                }
                
                if "response_mime_type" in kwargs:
                    generation_config_args["response_mime_type"] = kwargs["response_mime_type"]
                
                response = await self.model.generate_content_async(
                    full_prompt,
                    generation_config=GenerationConfig(**generation_config_args)
                )
                
                # Extract content
                content = ""
                if response.candidates:
                    content = response.candidates[0].content.parts[0].text
                
                # Build usage info
                usage = None
                if hasattr(response, "usage_metadata"):
                    usage = {
                        "prompt_tokens": response.usage_metadata.prompt_token_count,
                        "completion_tokens": response.usage_metadata.candidates_token_count,
                        "total_tokens": response.usage_metadata.total_token_count,
                    }
                
                return LLMResponse(
                    content=content,
                    model=self.config.model,
                    provider=self.provider_name,
                    usage=usage,
                    finish_reason=response.candidates[0].finish_reason.name if response.candidates else None,
                    raw_response=response,
                )
                
            except Exception as e:
                from loguru import logger
                error_str = str(e)
                # logger.warning(f"Gemini generation error: {error_str}")
                


                # Don't retry on 404 (model not found) - fail fast
                if "404" in error_str or "not found" in error_str.lower():
                    raise RuntimeError(f"Gemini generation failed: {error_str}")
                
                # Check if it's a rate limit error (429) - only retry on these
                if "429" in error_str and ("quota" in error_str.lower() or "rate" in error_str.lower()):
                    retry_count += 1
                    if retry_count <= max_retries:
                        # Extract retry delay from error message if available
                        delay_match = re.search(r'retry in (\d+(?:\.\d+)?)', error_str.lower())
                        wait_time = float(delay_match.group(1)) if delay_match else (retry_count * 15)
                        
                        logger.warning(f"Rate limit hit. Waiting {wait_time:.1f}s before retry {retry_count}/{max_retries}...")
                        await asyncio.sleep(wait_time)
                        continue
                
                raise RuntimeError(f"Gemini generation failed: {error_str}")
    
    async def generate_json(
        self,
        prompt: str,
        schema: Dict[str, Any],
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate structured JSON output using native JSON mode
        """
        from loguru import logger
        
        # Merge system prompts
        full_prompt = f"""{prompt}
        
Expected JSON schema:
{json.dumps(schema, indent=2)}

Return ONLY the JSON object."""

        try:
            # Generate with response_mime_type using native support via self.generate
            response = await self.generate(
                prompt=full_prompt,
                system_prompt=None, # Already merged into full_prompt if needed, or pass separately
                response_mime_type="application/json",
                **kwargs
            )
            
            content = response.content.strip()
            return json.loads(content)
            
        except Exception as e:
            logger.warning(f"Native JSON mode failed: {e}. Falling back to manual parsing.")
            
            # Manual fallback
            json_system_prompt = "You are a JSON generator. Respond with valid JSON only."
            if system_prompt:
                json_system_prompt = f"{json_system_prompt}\n\n{system_prompt}"
            
            # Additional instruction to avoid trailing commas which cause 'Expecting property name'
            json_system_prompt += "\nDo not include trailing commas in JSON objects or arrays."
                
            response = await self.generate(
                prompt=full_prompt,
                system_prompt=json_system_prompt,
                **kwargs
            )
            
            # Enhanced cleanup before parsing
            content = response.content.strip()
            
            # Basic cleanup
            if content.startswith("```json"):
                content = content[7:]
            elif content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
            
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                # Advanced cleanup logic
                import re
                # Fix trailing commas
                content = re.sub(r',\s*([}\]])', r'\1', content)
                # Fix missing quotes around keys (basic attempt)
                # This regex looks for Keys that are not quoted (simplified)
                # content = re.sub(r'([{,]\s*)([a-zA-Z0-9_]+)(\s*:)', r'\1"\2"\3', content)
                
                return self._parse_json_response(content)
    
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
            # Start chat session
            chat = self.model.start_chat(history=[])
            
            # Process messages
            last_response = None
            for msg in messages:
                if msg.role == "system":
                    # Add system message as context
                    continue
                elif msg.role == "user":
                    last_response = await chat.send_message_async(msg.content)
                elif msg.role == "assistant":
                    # Add to history
                    pass
            
            if last_response is None:
                raise ValueError("No user messages in conversation")
            
            content = ""
            if last_response.candidates:
                content = last_response.candidates[0].content.parts[0].text
            
            return LLMResponse(
                content=content,
                model=self.config.model,
                provider=self.provider_name,
                raw_response=last_response,
            )
            
        except Exception as e:
            raise RuntimeError(f"Gemini chat failed: {str(e)}")
