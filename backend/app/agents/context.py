"""
Context Discovery Agent
Responsible for scanning the local repository to find relevant code context (selectors, components).
"""

import os
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
from loguru import logger
from app.core.config import settings

class ContextAgent:
    """
    Agent that bridges the gap between the User Story and the actual Codebase.
    It scans the local repo for relevant UI components and locators.
    """
    
    def __init__(self, repo_path: Optional[str] = None):
        self.repo_path = Path(repo_path) if repo_path else None
        self.excludes = settings.scan_excludes
        self.name = "ContextDiscovery"

    async def get_ui_context(self, story_summary: str, story_description: str) -> str:
        """
        Extracts relevant code snippets or locator hints from the repository.
        """
        if not self.repo_path or not self.repo_path.exists():
            return "No local repository path configured for context analysis."

        # Extract keywords from story
        keywords = self._extract_keywords(story_summary + " " + story_description)
        logger.info(f"[{self.name}] Searching repo for keywords: {keywords}")

        relevant_files = self._find_relevant_files(keywords)
        if not relevant_files:
            return "No relevant files found in the repository for context."

        context_bits = []
        for file_path in relevant_files[:5]: # Limit to top 5 files
            try:
                content = file_path.read_text(errors='ignore')
                # Extract potential selectors or component names (heuristics)
                discovered = self._extract_locators(content, file_path.name)
                if discovered:
                    context_bits.append(f"File: {file_path.relative_to(self.repo_path)}\nFindings:\n{discovered}")
            except Exception as e:
                logger.warning(f"[{self.name}] Failed to read {file_path}: {e}")

        if not context_bits:
            return "Found relevant files but could not extract specific locator context."

        return "\n\n".join(context_bits)

    def _extract_keywords(self, text: str) -> List[str]:
        """Simple keyword extraction (entities)."""
        # Remove common stop words and keep nouns/titled words
        words = re.findall(r'\b[A-Z][a-z]+\b|\b[a-z]{4,}\b', text)
        stop_words = {'user', 'story', 'should', 'could', 'test', 'jira', 'issue', 'page', 'allow', 'ability'}
        keywords = [w for w in words if w.lower() not in stop_words]
        return list(set(keywords))

    def _find_relevant_files(self, keywords: List[str]) -> List[Path]:
        """Search repo for files containing keywords in name or path."""
        matches = []
        for root, dirs, files in os.walk(str(self.repo_path)):
            # Filter excludes
            dirs[:] = [d for d in dirs if d not in self.excludes]
            
            for file in files:
                if any(kw.lower() in file.lower() for kw in keywords):
                    matches.append(Path(root) / file)
        
        # Sort by relevance (maybe extension priority)
        matches.sort(key=lambda p: (not p.suffix in ['.tsx', '.jsx', '.html', '.ts'], len(str(p))))
        return matches

    def _extract_locators(self, content: str, filename: str) -> str:
        """Heuristic locator extraction from code content."""
        findings = []
        
        # Look for data-testid
        test_ids = re.findall(r'data-testid=["\']([^"\']+)["\']', content)
        if test_ids:
            findings.append(f"- Data Test IDs: {', '.join(set(test_ids[:10]))}")
            
        # Look for IDs in HTML-like tags
        ids = re.findall(r'id=["\']([^"\']+)["\']', content)
        if ids:
            findings.append(f"- Element IDs: {', '.join(set(ids[:5]))}")

        # Look for Button/Input labels in React/HTML
        labels = re.findall(r'label=["\']([^"\']+)["\']|placeholder=["\']([^"\']+)["\']', content)
        flattened_labels = [l for group in labels for l in group if l]
        if flattened_labels:
            findings.append(f"- Likely Labels/Placeholders: {', '.join(set(flattened_labels[:5]))}")

        return "\n".join(findings) if findings else ""
