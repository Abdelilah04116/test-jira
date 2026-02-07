from typing import Any, Dict, Optional, Type
from pydantic import BaseModel
from app.llm.base import BaseLLMClient
from loguru import logger

class BaseAgent:
    """Base class for all specific agents"""
    
    def __init__(self, llm: BaseLLMClient, name: str = "BaseAgent"):
        self.llm = llm
        self.name = name
        
    async def run(self, prompt: str, schema: Optional[Dict[str, Any]] = None, **kwargs) -> Any:
        """Executes the agent's main task using the LLM"""
        logger.info(f"[{self.name}] Starting task...")
        
        system_prompt = self.get_system_prompt()
        
        try:
            if schema:
                result = await self.llm.generate_json(
                    prompt=prompt,
                    schema=schema,
                    system_prompt=system_prompt,
                    **kwargs
                )
                return result
            else:
                response = await self.llm.generate(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    **kwargs
                )
                return response.content
                
        except Exception as e:
            logger.error(f"[{self.name}] Failed: {e}")
            raise e

    def get_system_prompt(self) -> str:
        """Returns the persona/system prompt for this agent"""
        return "You are a helpful AI assistant."
