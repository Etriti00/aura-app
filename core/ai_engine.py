"""
Aura — AI Engine
Universal LiteLLM adapter with tiered intelligence routing.

Tier 1: The Doorman — pure Python checks (handled in scraper_engine)
Tier 2: Junior Analyst — fast, cheap model for lead qualification
Tier 3: The Closer — premium model for personalized email generation
"""

import json
import time
from typing import Optional, Dict, Any

from utils.logger import get_logger
from core.safety_guard import SafetyGuard
from config import DEFAULT_TIER2_MODEL, DEFAULT_TIER3_MODEL

logger = get_logger("ai_engine")


class AIEngine:
    """
    Universal AI adapter using LiteLLM for model-agnostic inference.
    Supports all major providers: Gemini, Anthropic, OpenAI, Ollama, etc.
    """

    def __init__(self, safety_guard: SafetyGuard = None):
        self.safety = safety_guard or SafetyGuard()
        self._api_keys = {}
        self._models = {
            "tier2": DEFAULT_TIER2_MODEL,
            "tier3": DEFAULT_TIER3_MODEL,
        }
        self.router = None  # Optional RouterEngine for intelligent routing
        self.rag_engine = None  # Optional RAGEngine for style mimicry

    def set_router(self, router):
        """Attach a RouterEngine for intelligent tier routing."""
        self.router = router

    def set_rag_engine(self, rag_engine):
        """Attach a RAGEngine for style mimicry context."""
        self.rag_engine = rag_engine

    def generate(self, prompt: str, system_prompt: str = "",
                 model: str = None, temperature: float = 0.7,
                 max_tokens: int = 1024) -> dict:
        """
        General-purpose LLM generation used by sequence_controller and others.
        Returns {"success": bool, "response": str, "error": str | None}.
        """
        target_model = model or self._models.get("tier3", DEFAULT_TIER3_MODEL)
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        # Use router if available for intelligent tier selection
        if self.router:
            try:
                result = self.router.route(
                    "generate_email", prompt,
                    context={"system_prompt": system_prompt},
                )
                if result.get("success"):
                    return {"success": True, "response": result.get("data", "")}
                return {"success": False, "error": result.get("error", "Router failed")}
            except Exception as e:
                logger.warning(f"Router generate failed, falling back to direct: {e}")

        response_text = self._call_llm(target_model, messages, temperature, max_tokens)
        if response_text is not None:
            return {"success": True, "response": response_text}
        return {"success": False, "error": "LLM call returned None"}

    def configure(self, api_keys: Dict[str, str], models: Dict[str, str] = None,
                  sub_tokens: Dict[str, str] = None):
        """
        Configure the AI engine with API keys and model selections.

        Args:
            api_keys: Dict mapping provider to key, e.g. {"gemini": "...", "anthropic": "..."}
            models: Dict mapping tier to model, e.g. {"tier2": "gemini/gemini-1.5-flash"}
            sub_tokens: Dict of subscription tokens as fallback, e.g. {"anthropic_sub": "..."}
        """
        self._api_keys = api_keys
        if models:
            self._models.update(models)

        sub_tokens = sub_tokens or {}

        # Set environment variables for LiteLLM
        import os
        if "gemini" in api_keys and api_keys["gemini"]:
            os.environ["GEMINI_API_KEY"] = api_keys["gemini"]
        if "anthropic" in api_keys and api_keys["anthropic"]:
            os.environ["ANTHROPIC_API_KEY"] = api_keys["anthropic"]
        elif sub_tokens.get("anthropic_sub"):
            os.environ["ANTHROPIC_API_KEY"] = sub_tokens["anthropic_sub"]
        if "openai" in api_keys and api_keys["openai"]:
            os.environ["OPENAI_API_KEY"] = api_keys["openai"]
        elif sub_tokens.get("openai_sub"):
            os.environ["OPENAI_API_KEY"] = sub_tokens["openai_sub"]
        if "openrouter" in api_keys and api_keys["openrouter"]:
            os.environ["OPENROUTER_API_KEY"] = api_keys["openrouter"]

        logger.info(f"AI Engine configured. Tier2: {self._models['tier2']}, Tier3: {self._models['tier3']}")

    # Error substrings that indicate a transient (retryable) failure
    _TRANSIENT_ERRORS = ("429", "rate_limit", "timeout", "502", "503", "529", "overloaded")

    def _call_llm(self, model: str, messages: list, temperature: float = 0.7,
                  max_tokens: int = 1024, _max_retries: int = 3) -> Optional[str]:
        """
        Make a LiteLLM completion call with exponential backoff on transient errors.
        Returns the response text or None on failure.
        """
        import time as _time
        import litellm
        litellm.set_verbose = False

        for attempt in range(_max_retries):
            try:
                response = litellm.completion(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )

                # Track token usage
                usage = response.get("usage", {})
                total_tokens = usage.get("total_tokens", 0)
                cost = litellm.completion_cost(completion_response=response) or 0.0
                self.safety.add_token_usage(total_tokens, cost)

                content = response["choices"][0]["message"]["content"]
                logger.debug(
                    f"LLM call: model={model}, tokens={total_tokens}, "
                    f"cost=${cost:.6f}"
                )
                return content.strip()

            except Exception as e:
                error_str = str(e).lower()
                is_transient = any(t in error_str for t in self._TRANSIENT_ERRORS)

                if is_transient and attempt < _max_retries - 1:
                    wait = 2 ** attempt  # 1s, 2s, 4s
                    logger.warning(
                        f"LLM transient error (attempt {attempt + 1}/{_max_retries}, "
                        f"retry in {wait}s): {e}"
                    )
                    _time.sleep(wait)
                    continue

                # Permanent error or final attempt
                logger.error(f"LLM call failed (model={model}): {e}")
                return None

        return None

    # ─── Tier 2: Junior Analyst — Lead Qualification ──────────────────

    def qualify_lead(self, lead_data: dict, niche: str) -> dict:
        """
        Tier 2 qualification: Use cheap model to analyze a lead's snippet
        and determine if it's a viable business prospect.

        Returns dict with:
            - qualified: bool
            - score: int (1-10)
            - reason: str
            - email_hint: str (suggested approach)
        """
        # ─── Router path: auto-escalate if confidence < 0.7 ───
        if self.router:
            return self._qualify_via_router(lead_data, niche)

        model = self._models["tier2"]

        prompt = f"""You are a lead qualification expert. Analyze this business lead and determine if it's a good prospect for B2B outreach in the "{niche}" niche.

Business: {lead_data.get('business_name', 'Unknown')}
Category: {lead_data.get('category', 'Unknown')}
City: {lead_data.get('city', 'Unknown')}
Phone: {lead_data.get('phone', 'N/A')}
Website: {lead_data.get('website_url', 'N/A')}
Source: {lead_data.get('source_platform', 'Unknown')}
Snippet: {lead_data.get('snippet', 'No additional info')}

Rate this lead on a scale of 1-10 for outreach potential.
Consider: business legitimacy, likely decision-maker access, service relevance.

Respond in this exact JSON format:
{{
    "qualified": true/false,
    "score": 1-10,
    "reason": "Brief explanation",
    "email_hint": "One sentence on the best angle for outreach email"
}}

JSON response only, no markdown fences:"""

        messages = [{"role": "user", "content": prompt}]
        raw_response = self._call_llm(model, messages, temperature=0.3, max_tokens=256)

        if not raw_response:
            return {
                "qualified": False,
                "score": 0,
                "reason": "AI qualification failed — model did not respond.",
                "email_hint": "",
            }

        try:
            # Clean up JSON response (strip markdown fences if present)
            cleaned = raw_response.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[1]
            if cleaned.endswith("```"):
                cleaned = cleaned.rsplit("```", 1)[0]
            cleaned = cleaned.strip()

            result = json.loads(cleaned)
            result["qualified"] = result.get("score", 0) >= 6
            return result
        except json.JSONDecodeError:
            logger.warning(f"Tier 2 returned non-JSON: {raw_response[:200]}")
            return {
                "qualified": False,
                "score": 0,
                "reason": "AI returned unparseable response.",
                "email_hint": "",
            }

    def _qualify_via_router(self, lead_data: dict, niche: str) -> dict:
        """Qualify a lead using the RouterEngine with auto-escalation."""
        prompt = f"""You are a lead qualification expert. Analyze this business lead and determine if it's a good prospect for B2B outreach in the "{niche}" niche.

Business: {lead_data.get('business_name', 'Unknown')}
Category: {lead_data.get('category', 'Unknown')}
City: {lead_data.get('city', 'Unknown')}
Phone: {lead_data.get('phone', 'N/A')}
Website: {lead_data.get('website_url', 'N/A')}
Source: {lead_data.get('source_platform', 'Unknown')}
Snippet: {lead_data.get('snippet', 'No additional info')}

Rate this lead on a scale of 1-10 for outreach potential.
Consider: business legitimacy, likely decision-maker access, service relevance.

Respond in this exact JSON format:
{{"qualified": true/false, "score": 1-10, "reason": "Brief explanation", "email_hint": "One sentence on the best angle for outreach email"}}

JSON response only, no markdown fences:"""

        result = self.router.route("qualify_lead_basic", prompt, {"temperature": 0.3, "max_tokens": 256})
        if not result["success"]:
            return {"qualified": False, "score": 0, "reason": "Router failed", "email_hint": ""}

        try:
            cleaned = result["data"].strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[1]
            if cleaned.endswith("```"):
                cleaned = cleaned.rsplit("```", 1)[0]
            parsed = json.loads(cleaned.strip())
            score = parsed.get("score", 0)
            parsed["qualified"] = score >= 6

            # Auto-escalate to sonnet if confidence is borderline (score 4-6)
            if 4 <= score <= 6 and result.get("tier") != "sonnet":
                logger.info(f"Auto-escalating qualification for borderline score {score}")
                escalated = self.router.route("qualify_lead_complex", prompt, {"temperature": 0.3, "max_tokens": 256})
                if escalated["success"]:
                    esc_cleaned = escalated["data"].strip()
                    if esc_cleaned.startswith("```"):
                        esc_cleaned = esc_cleaned.split("\n", 1)[1]
                    if esc_cleaned.endswith("```"):
                        esc_cleaned = esc_cleaned.rsplit("```", 1)[0]
                    parsed = json.loads(esc_cleaned.strip())
                    parsed["qualified"] = parsed.get("score", 0) >= 6

            return parsed
        except (json.JSONDecodeError, Exception) as e:
            logger.warning(f"Router qualify parse error: {e}")
            return {"qualified": False, "score": 0, "reason": "Parse error", "email_hint": ""}

    # ─── Tier 3: The Closer — Email Generation ────────────────────────

    def generate_email(
        self,
        lead_data: dict,
        skill: dict,
        qualification: dict = None,
        sender_name: str = "Alex",
        sender_company: str = "Aura",
        research_context: str = "",
        case_context: str = "",
    ) -> dict:
        """
        Tier 3 email generation: Use premium model to write a
        personalized outreach email based on the lead's profile and
        the selected skill/persona.

        Returns dict with:
            - subject: str
            - body: str
            - tone: str
        """
        # ─── Router path for email generation ───
        if self.router:
            return self._generate_email_via_router(
                lead_data, skill, qualification, sender_name, sender_company,
                research_context, case_context,
            )

        model = self._models["tier3"]

        email_hint = ""
        if qualification:
            email_hint = qualification.get("email_hint", "")

        skill_prompt = skill.get("system_prompt", "")
        skill_name = skill.get("name", "Professional")

        prompt = f"""You are writing a personalized B2B cold outreach email.

PERSONA: {skill_name}
{skill_prompt}

LEAD INFORMATION:
- Business: {lead_data.get('business_name', 'the company')}
- Category: {lead_data.get('category', 'business')}
- City: {lead_data.get('city', 'their city')}
- Website: {lead_data.get('website_url', 'N/A')}
{f'- Qualification insight: {email_hint}' if email_hint else ''}
{f'{chr(10)}RESEARCH INTELLIGENCE:{chr(10)}{research_context}' if research_context else ''}
{f'{chr(10)}CASE HISTORY:{chr(10)}{case_context}' if case_context else ''}

SENDER:
- Name: {sender_name}
- Company: {sender_company}

RULES:
1. Keep the email under 150 words
2. Be specific about their business — show you did research
3. Include one clear call-to-action
4. Sound human, not robotic — conversational but professional
5. No generic compliments or fake enthusiasm
6. Do NOT include "[Your Name]" placeholders — use the sender name

Write the email as a JSON object:
{{
    "subject": "Email subject line",
    "body": "Full email body with line breaks as \\n",
    "tone": "One word describing the tone used"
}}

JSON response only, no markdown fences:"""

        messages = [{"role": "user", "content": prompt}]
        raw_response = self._call_llm(model, messages, temperature=0.7, max_tokens=512)

        if not raw_response:
            return {
                "subject": f"Quick question for {lead_data.get('business_name', 'you')}",
                "body": "AI email generation failed. Please write manually.",
                "tone": "error",
            }

        try:
            cleaned = raw_response.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[1]
            if cleaned.endswith("```"):
                cleaned = cleaned.rsplit("```", 1)[0]
            cleaned = cleaned.strip()

            result = json.loads(cleaned)
            return result
        except json.JSONDecodeError:
            logger.warning(f"Tier 3 returned non-JSON: {raw_response[:200]}")
            return {
                "subject": f"Quick question for {lead_data.get('business_name', 'you')}",
                "body": raw_response,  # Use the raw text as fallback
                "tone": "unknown",
            }

    def _generate_email_via_router(
        self, lead_data, skill, qualification, sender_name, sender_company,
        research_context="", case_context="",
    ) -> dict:
        """Generate an email using the RouterEngine (optionally with RAG context)."""
        email_hint = ""
        if qualification:
            email_hint = qualification.get("email_hint", "")

        skill_prompt = skill.get("system_prompt", "")
        skill_name = skill.get("name", "Professional")

        # Build RAG context if available
        rag_context = ""
        if self.rag_engine:
            try:
                rag_context = self.rag_engine.build_rag_context(lead_data)
            except Exception as e:
                logger.warning(f"RAG context build failed: {e}")

        prompt = f"""You are writing a personalized B2B cold outreach email.

PERSONA: {skill_name}
{skill_prompt}

LEAD INFORMATION:
- Business: {lead_data.get('business_name', 'the company')}
- Category: {lead_data.get('category', 'business')}
- City: {lead_data.get('city', 'their city')}
- Website: {lead_data.get('website_url', 'N/A')}
{f'- Qualification insight: {email_hint}' if email_hint else ''}
{f'{chr(10)}RESEARCH INTELLIGENCE:{chr(10)}{research_context}' if research_context else ''}
{f'{chr(10)}CASE HISTORY:{chr(10)}{case_context}' if case_context else ''}

SENDER:
- Name: {sender_name}
- Company: {sender_company}
{f'{chr(10)}STYLE REFERENCE (match this tone and structure):{chr(10)}{rag_context}' if rag_context else ''}

RULES:
1. Keep the email under 150 words
2. Be specific about their business — show you did research
3. Include one clear call-to-action
4. Sound human, not robotic — conversational but professional
5. No generic compliments or fake enthusiasm
6. Do NOT include "[Your Name]" placeholders — use the sender name

Write the email as a JSON object:
{{"subject": "Email subject line", "body": "Full email body with line breaks as \\n", "tone": "One word describing the tone used"}}

JSON response only, no markdown fences:"""

        result = self.router.route("generate_email", prompt, {"temperature": 0.7, "max_tokens": 512})
        if not result["success"]:
            return {
                "subject": f"Quick question for {lead_data.get('business_name', 'you')}",
                "body": "AI email generation failed. Please write manually.",
                "tone": "error",
            }

        try:
            cleaned = result["data"].strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[1]
            if cleaned.endswith("```"):
                cleaned = cleaned.rsplit("```", 1)[0]
            return json.loads(cleaned.strip())
        except json.JSONDecodeError:
            return {
                "subject": f"Quick question for {lead_data.get('business_name', 'you')}",
                "body": result["data"],
                "tone": "unknown",
            }

    # ─── Batch Operations ─────────────────────────────────────────────

    def qualify_leads_batch(
        self,
        leads: list,
        niche: str,
        _progress_callback=None,
        _cancel_checker=None,
    ) -> list:
        """
        Qualify a batch of leads. Returns list of (lead_data, qualification) tuples.
        """
        results = []

        for i, lead in enumerate(leads):
            if _cancel_checker and _cancel_checker():
                break

            qualification = self.qualify_lead(lead, niche)
            results.append((lead, qualification))

            if _progress_callback:
                pct = int(((i + 1) / len(leads)) * 100)
                _progress_callback(pct)

            # Small delay between API calls
            time.sleep(0.5)

        return results
