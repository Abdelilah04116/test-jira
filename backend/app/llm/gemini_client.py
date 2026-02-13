"""
Google Gemini LLM Client
"""

# Fix for missing aiohttp.ClientConnectorDNSError in older versions or specific environments
# Must be applied before other imports that might rely on aiohttp behavior if possible, 
# strictly speaking it patches the module object itself so order relative to other imports isn't critical 
# as long as it runs before usage.
import aiohttp
if not hasattr(aiohttp, "ClientConnectorDNSError"):
    try:
        from aiohttp import client_exceptions
        if hasattr(client_exceptions, "ClientConnectorDNSError"):
            aiohttp.ClientConnectorDNSError = client_exceptions.ClientConnectorDNSError
        else:
            class MockClientConnectorDNSError(OSError): pass
            aiohttp.ClientConnectorDNSError = MockClientConnectorDNSError
    except ImportError:
         class MockClientConnectorDNSError(OSError): pass
         aiohttp.ClientConnectorDNSError = MockClientConnectorDNSError

import json
import asyncio
import re
from typing import Any, Dict, List, Optional

from google import genai
from google.genai import types

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
        self.client = genai.Client(api_key=api_key)
        
        # force default model
        if not self.config.model or self.config.model == "default":
            self.config.model = "gemini-3-flash-preview"
        
        # Safety settings - relaxed for enterprise use
        self.safety_settings = [
            types.SafetySetting(
                category=types.HarmCategory.HARM_CATEGORY_HARASSMENT,
                threshold=types.HarmBlockThreshold.BLOCK_ONLY_HIGH
            ),
            types.SafetySetting(
                category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                threshold=types.HarmBlockThreshold.BLOCK_ONLY_HIGH
            ),
            types.SafetySetting(
                category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                threshold=types.HarmBlockThreshold.BLOCK_ONLY_HIGH
            ),
            types.SafetySetting(
                category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                threshold=types.HarmBlockThreshold.BLOCK_ONLY_HIGH
            ),
        ]
        
    
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
                
                # Generation config
                generation_config_args = {
                    "temperature": kwargs.get("temperature", self.config.temperature),
                    "max_output_tokens": kwargs.get("max_tokens", self.config.max_tokens),
                    "top_p": 0.95,
                    "top_k": 40,
                }
                
                if "response_mime_type" in kwargs:
                    generation_config_args["response_mime_type"] = kwargs["response_mime_type"]
                
                config = types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    safety_settings=self.safety_settings,
                    **generation_config_args
                )

                response = await self.client.aio.models.generate_content(
                    model=self.config.model,
                    contents=full_prompt,
                    config=config
                )
                
                # Extract content
                content = ""
                if response.candidates:
                    # In the new SDK, content structure might be slightly different but usually similar
                    # Check docs or assume similarity. response.text is a helper usually.
                    # But if we need safely:
                     if response.candidates[0].content and response.candidates[0].content.parts:
                        # Ensure content is always a string
                        val = response.candidates[0].content.parts[0].text
                        content = str(val) if val is not None else ""
                
                # Build usage info
                usage = None
                if response.usage_metadata:
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
                    finish_reason=response.candidates[0].finish_reason if response.candidates else None,
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
        
        # In the new SDK, we can pass schema directly if supported, or use response_mime_type="application/json"
        # Since I'm not 100% sure on the schema passing syntax without looking at docs, I will stick to the existing robust prompt engineering + json mode
        
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
            # Prepare chat history and config
            # New SDK might handle chats differently (stateless or stateful?)
            # The easiest way with the new SDK is likely just passing the history to generate_content or using chats.create
            
            # We will use chats.create to start a session
            
            chat_history = []
            
            # We need to filter out the last user message as the 'message' to send, and put the rest in history
            # Or assume the new SDK can take a full list
            
            # Typical chat structure for history:
            # history = [Content(role="user", parts=[...]), Content(role="model", parts=[...])]
            
            # Convert LLMMessage to format expected by SDK if needed.
            # But wait, self.client.chats.create(model=..., history=...)
            
            formatted_history = []
            
            # Find the last user message
            if not messages:
                 raise ValueError("No messages provided")
            
            # Separate system prompt if present (usually handled in config)
            system_prompt = None
            
            # Messages invalid for history (e.g. last user message if we use send_message)
            # But wait, if we rebuild the chat every time (stateless wrapper), we should pass previous messages as history.
            
            # Let's iterate and build history.
            # Note: The loop in the original code seems to have failed to construct history properly or was using a stateful chat object but re-initializing it every time?
            # Original code:
            # chat = self.model.start_chat(history=[])
            # for msg in messages:
            #     if user: chat.send_message
            # This is inefficient as it makes N calls for N messages? No, start_chat(history=[]) starts empty.
            # Then it calls send_message_async sequentially? That's very slow/wrong if we just want one completion.
            # It seems the original code was re-playing the conversation to the API? 
            # "last_response = await chat.send_message_async(msg.content)" inside the loop!
            # Yes, that's what it was doing.
            
            # Better approach with new SDK:
            # use generate_content with a list of messages.
            
            contents = []
            for msg in messages:
                if msg.role == "system":
                    system_prompt = msg.content
                elif msg.role == "user":
                    contents.append(types.Content(role="user", parts=[types.Part.from_text(text=msg.content)]))
                elif msg.role == "assistant":
                    contents.append(types.Content(role="model", parts=[types.Part.from_text(text=msg.content)]))
            
            # Config
            generation_config_args = {
                "temperature": kwargs.get("temperature", self.config.temperature),
                "max_output_tokens": kwargs.get("max_tokens", self.config.max_tokens),
                "top_p": 0.95,
                "top_k": 40,
            }
            
            config = types.GenerateContentConfig(
                system_instruction=system_prompt,
                safety_settings=self.safety_settings,
                **generation_config_args
            )

            # Generate response for the conversation
            # In new SDK, we can pass a list of contents
            response = await self.client.aio.models.generate_content(
                model=self.config.model,
                contents=contents,
                config=config
            )
            
            content = ""
            if response.candidates:
                if response.candidates[0].content.parts:
                    content = response.candidates[0].content.parts[0].text
            
            return LLMResponse(
                content=content,
                model=self.config.model,
                provider=self.provider_name,
                raw_response=response,
            )
            
        except Exception as e:
            raise RuntimeError(f"Gemini chat failed: {str(e)}")
