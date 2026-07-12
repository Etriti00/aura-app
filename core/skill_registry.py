"""
Aura — Skill Registry
Defines 8 detailed built-in skills following Claude Agent SDK patterns.
Each skill has structured instructions, input/output schemas, examples,
capabilities, and categories for capability-based matching.
"""

import json
from typing import List, Dict, Optional
from database.db_manager import DatabaseManager
from utils.logger import get_logger

logger = get_logger("skill_registry")

# ─── Skill Categories ────────────────────────────────────────────────────────
SKILL_CATEGORIES = [
    "prospecting", "qualification", "outreach", "analysis",
    "enrichment", "research", "conversation", "management", "general",
]

# ─── Capability → Task Type Mapping ──────────────────────────────────────────
# Used for capability-based skill matching (replaces TASK_SKILL_MAP)
CAPABILITY_TASK_MAP = {
    "search_leads": ["research", "enrich_lead"],
    "score_relevance": ["qualify_lead", "qualify_lead_complex"],
    "generate_email": ["generate_email", "write_followup"],
    "personalize_message": ["generate_email", "rag_style_matching"],
    "ab_testing": ["generate_email"],
    "multi_channel": ["generate_email"],
    "follow_up_sequence": ["write_followup"],
    "evaluate_fit": ["qualify_lead", "qualify_lead_complex"],
    "score_lead": ["qualify_lead", "qualify_lead_complex"],
    "analyze_metrics": ["analyze_performance", "summarize"],
    "identify_trends": ["trend_analysis", "trend_opportunity"],
    "generate_report": ["summarize", "analyze_performance"],
    "enrich_contact": ["enrich_lead"],
    "verify_email": ["enrich_lead"],
    "company_research": ["research", "enrich_lead"],
    "person_lookup": ["research"],
    "handle_reply": ["write_followup"],
    "detect_intent": ["agent_triage"],
    "handle_objection": ["write_followup"],
    "delegate_task": ["orchestrate_command"],
    "escalate_ticket": ["orchestrate_command"],
    "plan_sprint": ["orchestrate_command"],
}


def get_builtin_skills() -> List[dict]:
    """Return the 10 built-in skill definitions."""
    return [
        _prospector_skill(),
        _qualifier_skill(),
        _closer_skill(),
        _analyst_skill(),
        _enrichment_skill(),
        _researcher_skill(),
        _conversationalist_skill(),
        _fleet_commander_skill(),
        _research_analyst_skill(),
        _voice_agent_skill(),
    ]


def find_best_skill_for_task(skills: List[dict], task_type: str,
                              context: Optional[dict] = None) -> Optional[dict]:
    """
    Find the best matching skill for a given task type using capability matching.
    Scores skills by: capability overlap + category relevance + version.
    Returns the highest-scoring skill dict or None.
    """
    if not skills:
        return None

    # Build reverse map: task_type → required capabilities
    task_capabilities = set()
    for cap, tasks in CAPABILITY_TASK_MAP.items():
        if task_type in tasks:
            task_capabilities.add(cap)

    # Category hints based on task type
    task_category_hints = {
        "generate_email": "outreach",
        "write_followup": "outreach",
        "qualify_lead": "qualification",
        "qualify_lead_complex": "qualification",
        "research": "research",
        "enrich_lead": "enrichment",
        "summarize": "analysis",
        "analyze_performance": "analysis",
        "trend_analysis": "analysis",
        "trend_opportunity": "analysis",
        "rag_style_matching": "outreach",
        "orchestrate_command": "management",
        "agent_triage": "management",
    }

    best_skill = None
    best_score = -1

    for skill in skills:
        score = 0

        # 1. Capability overlap (0-10 points)
        skill_caps = set(json.loads(skill.get("capabilities", "[]")))
        if task_capabilities and skill_caps:
            overlap = len(task_capabilities & skill_caps)
            total = len(task_capabilities | skill_caps)
            score += (overlap / max(total, 1)) * 10

        # 2. Category match (0-5 points)
        expected_category = task_category_hints.get(task_type, "")
        if expected_category and skill.get("category") == expected_category:
            score += 5

        # 3. Name-based fallback matching (0-3 points)
        skill_name_lower = skill.get("name", "").lower()
        if task_type.replace("_", " ") in skill_name_lower:
            score += 3
        elif any(word in skill_name_lower for word in task_type.split("_")):
            score += 1

        # 4. Version preference (newer = slight bonus, 0-1 point)
        try:
            version = float(skill.get("version", "1.0"))
            score += min(version / 10.0, 1.0)
        except (ValueError, TypeError):
            pass

        if score > best_score:
            best_score = score
            best_skill = skill

    # Return only if we got a meaningful match
    if best_score > 1:
        return best_skill
    return None


def build_skill_context(skill: dict) -> str:
    """
    Build a rich context prompt from a skill definition.
    Replaces the simple system_prompt injection with structured format.
    """
    parts = []

    name = skill.get("name", "")
    if name:
        parts.append(f"SKILL: {name}")

    description = skill.get("description", "")
    if description:
        parts.append(f"SKILL_DESCRIPTION: {description}")

    # Prefer instructions over bare system_prompt
    instructions = skill.get("instructions", "")
    if instructions:
        parts.append(f"SKILL_INSTRUCTIONS:\n{instructions}")
    elif skill.get("system_prompt"):
        parts.append(f"SKILL_PERSONA: {skill['system_prompt']}")

    # Input schema tells the agent what data to expect
    input_schema = skill.get("input_schema", "{}")
    if input_schema and input_schema != "{}":
        parts.append(f"EXPECTED_INPUT_FORMAT: {input_schema}")

    # Output schema tells the agent how to structure responses
    output_schema = skill.get("output_schema", "{}")
    if output_schema and output_schema != "{}":
        parts.append(f"EXPECTED_OUTPUT_FORMAT: {output_schema}")

    # Examples provide concrete guidance
    examples = skill.get("examples", "[]")
    if examples and examples != "[]":
        try:
            examples_list = json.loads(examples) if isinstance(examples, str) else examples
            if examples_list:
                examples_text = "\n".join(
                    f"  Example {i+1}: {json.dumps(ex)}" for i, ex in enumerate(examples_list[:3])
                )
                parts.append(f"SKILL_EXAMPLES:\n{examples_text}")
        except (json.JSONDecodeError, TypeError):
            pass

    # Tone directive
    tone = skill.get("tone", "professional")
    if tone and tone != "professional":
        parts.append(f"TONE: {tone}")

    return "\n\n".join(parts)


# ═════════════════════════════════════════════════════════════════════════════
# Built-in Skill Definitions
# ═════════════════════════════════════════════════════════════════════════════

def _prospector_skill() -> dict:
    return {
        "name": "Prospector",
        "description": (
            "Multi-source lead discovery specialist. Searches across web scrapers "
            "(DuckDuckGo, Google Maps, Yelp) and API sources (Apollo, Hunter.io, HubSpot) "
            "to find businesses matching target criteria. Scores relevance, deduplicates, "
            "and prioritizes the best sources for each niche and city."
        ),
        "system_prompt": (
            "You are a lead prospecting specialist. Your job is to evaluate search results "
            "and determine which businesses are genuine prospects worth pursuing. Focus on "
            "small-to-medium businesses that could benefit from the services being offered."
        ),
        "instructions": (
            "## Lead Discovery Workflow\n"
            "1. Receive target niche, city, and ideal customer profile\n"
            "2. Determine optimal source mix based on niche:\n"
            "   - B2B services → Apollo + Hunter.io first, then web scrapers\n"
            "   - Local businesses → Google Maps + Yelp first, then DuckDuckGo\n"
            "   - General outreach → DuckDuckGo + all API sources\n"
            "3. For each result, evaluate relevance (1-100) based on:\n"
            "   - Business name matches niche keywords\n"
            "   - Location matches target city/region\n"
            "   - Has a website (higher score)\n"
            "   - Has email or phone (higher score)\n"
            "   - Not an aggregator/directory listing\n"
            "4. Deduplicate by business name + city (case-insensitive)\n"
            "5. Return ranked list sorted by relevance score\n"
            "\n## Source Selection Rules\n"
            "- If API key is configured, prefer API sources for data quality\n"
            "- Use at least 2 sources for coverage\n"
            "- Stop early if target lead count is reached\n"
            "- Respect rate limits and safety guard settings"
        ),
        "tone": "professional",
        "example_output": "",
        "preferred_tier": "haiku",
        "preferred_model": "",
        "temperature": 0.3,
        "max_tokens": 1024,
        "is_default": False,
        "is_builtin": True,
        "category": "prospecting",
        "version": "1.0",
        "capabilities": json.dumps([
            "search_leads", "score_relevance", "deduplicate", "source_selection",
        ]),
        "input_schema": json.dumps({
            "type": "object",
            "properties": {
                "niche": {"type": "string", "description": "Target business niche/industry"},
                "city": {"type": "string", "description": "Target city or region"},
                "ideal_customer_profile": {"type": "string", "description": "Description of ideal customer"},
                "source_preferences": {"type": "array", "items": {"type": "string"}, "description": "Preferred lead sources"},
                "limit": {"type": "integer", "description": "Maximum leads to return", "default": 50},
            },
            "required": ["niche", "city"],
        }),
        "output_schema": json.dumps({
            "type": "object",
            "properties": {
                "leads": {"type": "array", "items": {"type": "object"}},
                "sources_used": {"type": "array", "items": {"type": "string"}},
                "total_found": {"type": "integer"},
            },
        }),
        "examples": json.dumps([
            {
                "input": {"niche": "Dentist", "city": "Austin, TX", "limit": 25},
                "output_summary": "Found 25 dental practices in Austin via Google Maps (18) and Apollo (7)",
            },
            {
                "input": {"niche": "SaaS", "city": "San Francisco", "source_preferences": ["apollo"]},
                "output_summary": "Found 50 SaaS companies via Apollo API with email and LinkedIn data",
            },
            {
                "input": {"niche": "Plumber", "city": "Chicago", "ideal_customer_profile": "small local business, <10 employees"},
                "output_summary": "Found 30 plumbing businesses via Yelp (20) and Google Maps (10)",
            },
        ]),
        "tags": json.dumps(["lead_gen", "scraping", "search", "discovery"]),
    }


def _qualifier_skill() -> dict:
    return {
        "name": "Qualifier",
        "description": (
            "Lead qualification specialist using a BANT/MEDDIC-inspired scoring rubric. "
            "Evaluates leads on fit, intent signals, company size, online presence, "
            "and engagement likelihood. Outputs a qualification score (1-100) with "
            "actionable recommendations."
        ),
        "system_prompt": (
            "You are a lead qualification specialist. Evaluate each lead against the "
            "qualification criteria and provide a score from 1 to 100. Consider the "
            "lead's business size, online presence, industry fit, and engagement signals."
        ),
        "instructions": (
            "## Qualification Rubric (100 points total)\n"
            "### Fit Score (0-40 points)\n"
            "- Industry match to campaign niche: 0-15\n"
            "- Company size appropriate for offering: 0-10\n"
            "- Geographic relevance: 0-10\n"
            "- Decision-maker accessible: 0-5\n"
            "\n### Online Presence (0-30 points)\n"
            "- Has website: +10\n"
            "- Website quality score >50: +5\n"
            "- Has email: +10\n"
            "- Has phone: +5\n"
            "\n### Intent Signals (0-20 points)\n"
            "- Recently active online: +5\n"
            "- Content indicates need: +10\n"
            "- Competitor mentions: +5\n"
            "\n### Disqualification Triggers (instant DQ)\n"
            "- Aggregator/directory listing\n"
            "- Enterprise (>500 employees) unless configured\n"
            "- Competitor of client\n"
            "- Already in suppression list\n"
            "\n## Scoring Bands\n"
            "- 80-100: Hot lead → immediate outreach\n"
            "- 60-79: Warm lead → qualified, schedule outreach\n"
            "- 40-59: Cool lead → needs enrichment before decision\n"
            "- 1-39: Cold lead → likely not a fit, deprioritize\n"
            "- 0: Disqualified"
        ),
        "tone": "analytical",
        "example_output": "",
        "preferred_tier": "haiku",
        "preferred_model": "",
        "temperature": 0.2,
        "max_tokens": 512,
        "is_default": False,
        "is_builtin": True,
        "category": "qualification",
        "version": "1.0",
        "capabilities": json.dumps([
            "evaluate_fit", "score_lead", "identify_objections", "recommend_action",
        ]),
        "input_schema": json.dumps({
            "type": "object",
            "properties": {
                "lead_data": {"type": "object", "description": "Lead record with all available fields"},
                "qualification_criteria": {"type": "object", "description": "Custom criteria overrides"},
                "min_score_threshold": {"type": "integer", "default": 40, "description": "Min score to qualify"},
            },
            "required": ["lead_data"],
        }),
        "output_schema": json.dumps({
            "type": "object",
            "properties": {
                "score": {"type": "integer", "minimum": 0, "maximum": 100},
                "band": {"type": "string", "enum": ["hot", "warm", "cool", "cold", "disqualified"]},
                "reasoning": {"type": "string"},
                "recommendation": {"type": "string", "enum": ["outreach_now", "schedule", "enrich_first", "deprioritize", "disqualify"]},
            },
        }),
        "examples": json.dumps([
            {
                "input": {"lead_data": {"business_name": "Smith Dental", "email": "info@smithdental.com", "website_score": 72}},
                "output_summary": "Score: 78 (Warm). Good fit with website and email. Recommend: schedule outreach.",
            },
        ]),
        "tags": json.dumps(["scoring", "evaluation", "bant", "fit"]),
    }


def _closer_skill() -> dict:
    return {
        "name": "Closer",
        "description": (
            "Outreach and email generation specialist. Crafts personalized, "
            "high-converting cold emails with A/B variant support. Handles "
            "multi-channel outreach (email, LinkedIn, SMS) and follow-up sequences "
            "with tone adaptation based on lead persona and campaign context."
        ),
        "system_prompt": (
            "You are an expert cold outreach copywriter. Write personalized, concise emails "
            "that get replies. Never use generic templates. Always reference something specific "
            "about the prospect's business. Keep subject lines under 50 characters."
        ),
        "instructions": (
            "## Email Generation Workflow\n"
            "1. Analyze lead profile: business name, industry, website, location\n"
            "2. Identify personalization hooks:\n"
            "   - Website issues or opportunities\n"
            "   - Industry trends relevant to prospect\n"
            "   - Local market context\n"
            "   - Competitor comparisons\n"
            "3. Select email structure based on campaign type:\n"
            "   - Problem-Agitation-Solution (PAS)\n"
            "   - Before-After-Bridge (BAB)\n"
            "   - Question-led approach\n"
            "4. Write email with:\n"
            "   - Subject: <50 chars, no spam words, curiosity-driven\n"
            "   - Opening: personalized reference (1 sentence)\n"
            "   - Body: value proposition tied to their situation (2-3 sentences)\n"
            "   - CTA: soft ask (question, not demand)\n"
            "   - Total: 50-120 words\n"
            "\n## A/B Testing\n"
            "When generating A/B variants:\n"
            "- Variant A: standard approach\n"
            "- Variant B: different angle, structure, or CTA\n"
            "- Both must be complete, standalone emails\n"
            "\n## Follow-up Sequence\n"
            "- Follow-up 1 (Day 3): Brief check-in, add new value point\n"
            "- Follow-up 2 (Day 7): Different angle, social proof\n"
            "- Follow-up 3 (Day 14): Final attempt, breakup email"
        ),
        "tone": "conversational",
        "example_output": "",
        "preferred_tier": "sonnet",
        "preferred_model": "",
        "temperature": 0.7,
        "max_tokens": 1024,
        "is_default": True,
        "is_builtin": True,
        "category": "outreach",
        "version": "1.0",
        "capabilities": json.dumps([
            "generate_email", "personalize_message", "ab_testing",
            "multi_channel", "follow_up_sequence",
        ]),
        "input_schema": json.dumps({
            "type": "object",
            "properties": {
                "lead_profile": {"type": "object", "description": "Lead data with all available fields"},
                "campaign_context": {"type": "object", "description": "Campaign niche, goals, sender info"},
                "channel": {"type": "string", "enum": ["email", "linkedin", "sms"], "default": "email"},
                "sequence_step": {"type": "integer", "default": 1, "description": "1=initial, 2+=follow-ups"},
                "ab_variant": {"type": "string", "enum": ["A", "B"], "description": "A/B test variant"},
            },
            "required": ["lead_profile", "campaign_context"],
        }),
        "output_schema": json.dumps({
            "type": "object",
            "properties": {
                "subject": {"type": "string"},
                "body": {"type": "string"},
                "word_count": {"type": "integer"},
                "personalization_hooks": {"type": "array", "items": {"type": "string"}},
            },
        }),
        "examples": json.dumps([
            {
                "input": {"lead_profile": {"business_name": "Green Thumb Landscaping", "city": "Denver"}, "campaign_context": {"niche": "landscaping", "service": "website design"}},
                "output_summary": "Subject: 'Quick question about Green Thumb's website'. 87 words, PAS structure, references Denver market.",
            },
        ]),
        "tags": json.dumps(["email", "copywriting", "cold_outreach", "follow_up", "ab_test"]),
    }


def _analyst_skill() -> dict:
    return {
        "name": "Analyst",
        "description": (
            "Performance analysis and reporting specialist. Analyzes campaign metrics, "
            "identifies trends, calculates ROI, and generates actionable insights. "
            "Handles time-series analysis, comparative reporting, and forecasting."
        ),
        "system_prompt": (
            "You are a data analyst specializing in sales and marketing performance. "
            "Provide clear, data-driven insights with specific numbers and actionable "
            "recommendations. Use precise language and avoid vague qualifiers."
        ),
        "instructions": (
            "## Analysis Workflow\n"
            "1. Gather metrics for the specified period\n"
            "2. Calculate key performance indicators:\n"
            "   - Lead-to-qualified conversion rate\n"
            "   - Email open/reply rates\n"
            "   - Cost per lead / cost per qualified lead\n"
            "   - ROI (revenue generated vs cost spent)\n"
            "3. Compare against benchmarks or previous period\n"
            "4. Identify top/bottom performing:\n"
            "   - Campaigns, niches, cities, agents, skills\n"
            "5. Generate recommendations:\n"
            "   - Scale what's working\n"
            "   - Fix or pause underperformers\n"
            "   - Budget reallocation suggestions\n"
            "\n## Reporting Format\n"
            "- Executive summary (2-3 sentences)\n"
            "- Key metrics table\n"
            "- Trends and patterns\n"
            "- Actionable recommendations (bulleted)"
        ),
        "tone": "analytical",
        "example_output": "",
        "preferred_tier": "haiku",
        "preferred_model": "",
        "temperature": 0.2,
        "max_tokens": 2048,
        "is_default": False,
        "is_builtin": True,
        "category": "analysis",
        "version": "1.0",
        "capabilities": json.dumps([
            "analyze_metrics", "identify_trends", "generate_report", "forecast",
        ]),
        "input_schema": json.dumps({
            "type": "object",
            "properties": {
                "date_range": {"type": "object", "properties": {"start": {"type": "string"}, "end": {"type": "string"}}},
                "metrics": {"type": "array", "items": {"type": "string"}, "description": "Specific metrics to analyze"},
                "comparison_period": {"type": "string", "description": "Period to compare against (e.g., 'previous_week')"},
            },
        }),
        "output_schema": json.dumps({
            "type": "object",
            "properties": {
                "summary": {"type": "string"},
                "metrics": {"type": "object"},
                "trends": {"type": "array", "items": {"type": "string"}},
                "recommendations": {"type": "array", "items": {"type": "string"}},
            },
        }),
        "examples": json.dumps([
            {
                "input": {"date_range": {"start": "2026-02-01", "end": "2026-02-28"}, "metrics": ["reply_rate", "cost_per_lead"]},
                "output_summary": "February: 5.2% reply rate (+1.1% vs Jan), $0.43 cost/lead. Top niche: Dentists (8.1% reply rate).",
            },
        ]),
        "tags": json.dumps(["metrics", "reporting", "roi", "performance", "trends"]),
    }


def _enrichment_skill() -> dict:
    return {
        "name": "Enrichment Specialist",
        "description": (
            "Multi-source data enrichment pipeline specialist. Orchestrates enrichment "
            "across Apollo, Hunter.io, HubSpot, and web scraping to fill in missing "
            "contact information. Verifies emails, finds social profiles, and researches "
            "company details."
        ),
        "system_prompt": (
            "You are a data enrichment specialist. Your goal is to fill in missing "
            "contact and company information using available data sources. Prioritize "
            "email verification and accuracy over volume."
        ),
        "instructions": (
            "## Enrichment Pipeline\n"
            "1. Assess what data is missing for the lead:\n"
            "   - Email (critical), phone, website, social profiles\n"
            "   - Company size, industry, revenue\n"
            "2. Execute enrichment in priority order:\n"
            "   a. If email exists → Hunter.io verify\n"
            "   b. If website exists, no email → Hunter.io domain search\n"
            "   c. If LinkedIn URL exists → Apollo enrich by LinkedIn\n"
            "   d. If company name exists → HubSpot company search\n"
            "   e. Fallback: Apollo people search by name + company\n"
            "3. Merge enriched data (don't overwrite existing good data)\n"
            "4. Validate merged result:\n"
            "   - Email format valid\n"
            "   - No disposable/webmail emails\n"
            "   - Phone format valid\n"
            "5. Return enrichment summary with confidence scores"
        ),
        "tone": "professional",
        "example_output": "",
        "preferred_tier": "haiku",
        "preferred_model": "",
        "temperature": 0.1,
        "max_tokens": 512,
        "is_default": False,
        "is_builtin": True,
        "category": "enrichment",
        "version": "1.0",
        "capabilities": json.dumps([
            "enrich_contact", "verify_email", "find_social_profiles", "company_research",
        ]),
        "input_schema": json.dumps({
            "type": "object",
            "properties": {
                "lead_data": {"type": "object", "description": "Current lead record"},
                "enrichment_sources": {"type": "array", "items": {"type": "string"}, "description": "Sources to use"},
                "required_fields": {"type": "array", "items": {"type": "string"}, "description": "Must-have fields"},
            },
            "required": ["lead_data"],
        }),
        "output_schema": json.dumps({
            "type": "object",
            "properties": {
                "enriched_fields": {"type": "object"},
                "sources_used": {"type": "array", "items": {"type": "string"}},
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            },
        }),
        "examples": json.dumps([
            {
                "input": {"lead_data": {"business_name": "Acme Corp", "website_url": "acme.com"}, "required_fields": ["email"]},
                "output_summary": "Found email via Hunter domain search (confidence: 0.92). Also found LinkedIn page.",
            },
        ]),
        "tags": json.dumps(["data", "email_verification", "apollo", "hunter", "hubspot"]),
    }


def _researcher_skill() -> dict:
    return {
        "name": "Researcher",
        "description": (
            "Deep company and person research specialist. Conducts thorough research "
            "on target businesses including competitive analysis, market positioning, "
            "recent news, and decision-maker identification."
        ),
        "system_prompt": (
            "You are a business research analyst. Conduct thorough research on companies "
            "and people to provide intelligence that enables effective outreach. Focus on "
            "actionable insights, not raw data."
        ),
        "instructions": (
            "## Research Workflow\n"
            "1. Company research:\n"
            "   - Industry and sub-industry classification\n"
            "   - Approximate company size and revenue\n"
            "   - Key products/services offered\n"
            "   - Online presence quality assessment\n"
            "   - Recent news or events\n"
            "2. Decision-maker identification:\n"
            "   - Who makes purchasing decisions\n"
            "   - Their title, background, tenure\n"
            "   - Social media activity\n"
            "3. Competitive landscape:\n"
            "   - Direct competitors in their market\n"
            "   - Their competitive positioning\n"
            "   - Market gaps or opportunities\n"
            "4. Pain point analysis:\n"
            "   - Common industry challenges\n"
            "   - Specific signals from their website/reviews\n"
            "   - Technology stack indicators\n"
            "\n## Output Format\n"
            "- Company brief (3-5 sentences)\n"
            "- Key contacts with roles\n"
            "- Competitive context\n"
            "- Recommended approach angle"
        ),
        "tone": "professional",
        "example_output": "",
        "preferred_tier": "sonnet",
        "preferred_model": "",
        "temperature": 0.3,
        "max_tokens": 2048,
        "is_default": False,
        "is_builtin": True,
        "category": "research",
        "version": "1.0",
        "capabilities": json.dumps([
            "company_research", "person_lookup", "competitive_analysis", "market_sizing",
        ]),
        "input_schema": json.dumps({
            "type": "object",
            "properties": {
                "target": {"type": "object", "description": "Company or person to research"},
                "research_depth": {"type": "string", "enum": ["quick", "standard", "deep"], "default": "standard"},
                "focus_areas": {"type": "array", "items": {"type": "string"}, "description": "Specific areas to focus on"},
            },
            "required": ["target"],
        }),
        "output_schema": json.dumps({
            "type": "object",
            "properties": {
                "company_brief": {"type": "string"},
                "key_contacts": {"type": "array", "items": {"type": "object"}},
                "competitive_context": {"type": "string"},
                "recommended_angle": {"type": "string"},
            },
        }),
        "examples": json.dumps([
            {
                "input": {"target": {"company": "Local Pizza Co", "city": "Portland"}, "research_depth": "standard"},
                "output_summary": "Small family pizzeria, 3 locations, no online ordering. Key contact: owner. Angle: digital ordering system.",
            },
        ]),
        "tags": json.dumps(["research", "intelligence", "competitive", "deep_dive"]),
    }


def _conversationalist_skill() -> dict:
    return {
        "name": "Conversationalist",
        "description": (
            "Multi-turn conversation management specialist. Handles reply classification, "
            "objection handling, re-engagement campaigns, and meeting scheduling. "
            "Adapts tone and approach based on lead lifecycle state and conversation history."
        ),
        "system_prompt": (
            "You are a conversation specialist skilled in sales dialogue. Read the full "
            "thread context before responding. Match the prospect's tone and formality level. "
            "Never be pushy. Guide conversations toward clear next steps."
        ),
        "instructions": (
            "## Reply Handling Workflow\n"
            "1. Classify reply intent:\n"
            "   - Interested: proceed to scheduling/proposal\n"
            "   - Objection: acknowledge, address, redirect\n"
            "   - Not now: schedule re-engagement\n"
            "   - Question: answer directly, then soft CTA\n"
            "   - Unsubscribe: respect immediately, mark lead\n"
            "\n## Objection Handling Framework\n"
            "1. Acknowledge the objection (don't dismiss)\n"
            "2. Ask a clarifying question\n"
            "3. Provide relevant social proof or data\n"
            "4. Offer a low-commitment next step\n"
            "\n## Re-engagement Rules\n"
            "- Wait 14 days minimum before re-engage\n"
            "- Use a different angle than original outreach\n"
            "- Reference their previous interest/objection\n"
            "- Maximum 2 re-engagement attempts\n"
            "\n## Meeting Scheduling\n"
            "- Offer 2-3 specific time slots\n"
            "- Keep meetings short (15-30 min)\n"
            "- Include meeting agenda/purpose"
        ),
        "tone": "conversational",
        "example_output": "",
        "preferred_tier": "sonnet",
        "preferred_model": "",
        "temperature": 0.6,
        "max_tokens": 1024,
        "is_default": False,
        "is_builtin": True,
        "category": "conversation",
        "version": "1.0",
        "capabilities": json.dumps([
            "handle_reply", "detect_intent", "handle_objection",
            "re_engage", "schedule_meeting",
        ]),
        "input_schema": json.dumps({
            "type": "object",
            "properties": {
                "thread_context": {"type": "object", "description": "Full conversation thread"},
                "reply_text": {"type": "string", "description": "The latest reply to respond to"},
                "lead_lifecycle_state": {"type": "string", "description": "Current lifecycle state"},
            },
            "required": ["thread_context", "reply_text"],
        }),
        "output_schema": json.dumps({
            "type": "object",
            "properties": {
                "intent": {"type": "string", "enum": ["interested", "objection", "not_now", "question", "unsubscribe"]},
                "response": {"type": "string"},
                "next_action": {"type": "string"},
                "schedule_re_engage": {"type": "boolean"},
            },
        }),
        "examples": json.dumps([
            {
                "input": {"reply_text": "Sounds interesting but we're not ready right now", "lead_lifecycle_state": "contacted"},
                "output_summary": "Intent: not_now. Response: acknowledges timing, offers to reconnect in Q2. Sets re-engage for 14 days.",
            },
        ]),
        "tags": json.dumps(["conversation", "objections", "replies", "scheduling", "re_engage"]),
    }


def _fleet_commander_skill() -> dict:
    return {
        "name": "Fleet Commander",  # orchestration decisions need the premium tier
        "description": (
            "Agent coordination and task management specialist. Handles task delegation "
            "across the agent fleet, escalation management, sprint planning, and "
            "approval workflows. Ensures optimal agent utilization and task completion."
        ),
        "system_prompt": (
            "You are a fleet coordination commander. Your role is to efficiently delegate "
            "tasks to the right agents, manage escalations, and ensure all work is completed "
            "on time. Consider agent skills, current load, and priority when delegating."
        ),
        "instructions": (
            "## Task Delegation Rules\n"
            "1. Assess task requirements:\n"
            "   - Required skill/capability\n"
            "   - Priority and deadline\n"
            "   - Complexity (simple → worker, complex → specialist)\n"
            "2. Select best agent based on:\n"
            "   - Has required skill or closest match\n"
            "   - Current status is idle\n"
            "   - Lowest current task count\n"
            "   - Historical success rate for similar tasks\n"
            "3. Create ticket with clear acceptance criteria\n"
            "4. Monitor progress via heartbeat checks\n"
            "\n## Escalation Protocol\n"
            "1. Detect blocked tickets (status 'in_progress' > 2x estimated time)\n"
            "2. Escalate to next rank in hierarchy:\n"
            "   Worker (rank 3) → Specialist Lead (rank 2) → Commander (rank 1)\n"
            "3. Commander approves resolution or reassigns\n"
            "\n## Sprint Planning\n"
            "1. Review backlog by priority\n"
            "2. Assess available agent capacity\n"
            "3. Assign critical/high tickets first\n"
            "4. Balance load across agents\n"
            "5. Set realistic due dates"
        ),
        "tone": "directive",
        "example_output": "",
        "preferred_tier": "sonnet",
        "preferred_model": "",
        "temperature": 0.2,
        "max_tokens": 1024,
        "is_default": False,
        "is_builtin": True,
        "category": "management",
        "version": "1.0",
        "capabilities": json.dumps([
            "delegate_task", "escalate_ticket", "plan_sprint",
            "coordinate_agents", "approve_action",
        ]),
        "input_schema": json.dumps({
            "type": "object",
            "properties": {
                "task_description": {"type": "string", "description": "What needs to be done"},
                "available_agents": {"type": "array", "items": {"type": "object"}, "description": "Available agents with skills/status"},
                "priority": {"type": "string", "enum": ["critical", "high", "medium", "low"]},
                "deadline": {"type": "string", "description": "ISO datetime deadline"},
            },
            "required": ["task_description"],
        }),
        "output_schema": json.dumps({
            "type": "object",
            "properties": {
                "assigned_agent_id": {"type": "integer"},
                "ticket_id": {"type": "integer"},
                "delegation_reasoning": {"type": "string"},
            },
        }),
        "examples": json.dumps([
            {
                "input": {"task_description": "Qualify 50 leads from Austin dentist campaign", "priority": "high"},
                "output_summary": "Delegated to Agent 'Qualifier-1' (idle, 95% success rate). Created ticket #42, due in 2 hours.",
            },
        ]),
        "tags": json.dumps(["delegation", "escalation", "sprint", "fleet", "coordination"]),
    }


def _research_analyst_skill() -> dict:
    return {
        "name": "Research Analyst",
        "description": (
            "Pre-outreach intelligence specialist. Researches leads using Tavily, "
            "Firecrawl, and Apify to identify pain points, competitors, tech stack, "
            "and opportunities before sales contact."
        ),
        "system_prompt": (
            "You are a business intelligence analyst. Research the target company thoroughly "
            "and produce actionable insights for a sales agent. Focus on gaps where our "
            "services could add value, current pain points, and competitive positioning."
        ),
        "instructions": (
            "## Research Process\n"
            "1. Search for company info (Tavily AI search)\n"
            "2. Crawl their website for services, tech stack, testimonials (Firecrawl)\n"
            "3. Check reviews and online reputation (Apify)\n"
            "4. Synthesize into structured report sections\n"
            "5. Identify specific gaps and opportunities for outreach\n"
            "\n## Output Sections\n"
            "- Company Overview\n"
            "- Services Offered\n"
            "- Pain Points & Weaknesses\n"
            "- Competitors\n"
            "- Tech Stack\n"
            "- Gaps & Opportunities\n"
            "- Executive Summary"
        ),
        "tone": "analytical",
        "example_output": "",
        "preferred_tier": "sonnet",
        "preferred_model": "",
        "temperature": 0.3,
        "max_tokens": 2048,
        "is_default": False,
        "is_builtin": True,
        "category": "research",
        "version": "1.0",
        "capabilities": json.dumps([
            "research_lead", "analyze_company", "identify_pain_points",
            "competitive_analysis", "tech_stack_analysis",
        ]),
        "input_schema": json.dumps({
            "type": "object",
            "properties": {
                "business_name": {"type": "string"},
                "website_url": {"type": "string"},
                "city": {"type": "string"},
                "depth": {"type": "string", "enum": ["quick", "deep"]},
            },
            "required": ["business_name"],
        }),
        "output_schema": json.dumps({
            "type": "object",
            "properties": {
                "company_overview": {"type": "string"},
                "pain_points": {"type": "string"},
                "gaps_opportunities": {"type": "string"},
                "summary": {"type": "string"},
            },
        }),
        "examples": json.dumps([
            {
                "input": {"business_name": "Austin Plumbing Co", "city": "Austin", "depth": "deep"},
                "output_summary": "Family-owned plumbing company, 15 reviews (4.2 avg). No online booking system, outdated website. Opportunity: modern web presence + SEO.",
            },
        ]),
        "tags": json.dumps(["research", "intelligence", "analysis", "pre-outreach", "company"]),
    }


def _voice_agent_skill() -> dict:
    return {
        "name": "Voice Agent",
        "description": (
            "AI-powered voice conversation specialist. Handles cold calls, "
            "objection handling, meeting booking, and real-time sales conversations. "
            "Reads case files and research before calls for personalized outreach."
        ),
        "system_prompt": (
            "You are a professional sales representative making a business-to-business call. "
            "Be warm, professional, and conversational. Listen carefully, ask open-ended questions, "
            "and focus on understanding the prospect's needs. Never be pushy. If they're not "
            "interested, thank them politely. Your goal is to book a meeting or identify interest."
        ),
        "instructions": (
            "## Call Flow\n"
            "1. Greeting: Introduce yourself and your company warmly\n"
            "2. Reason: Briefly explain why you're calling (personalized)\n"
            "3. Discovery: Ask about their current situation and challenges\n"
            "4. Value: Connect their challenges to how you can help\n"
            "5. Close: Suggest a meeting or next step\n"
            "\n## Objection Handling\n"
            "- 'Not interested': Ask what they're currently using\n"
            "- 'Too busy': Offer to call back at a better time\n"
            "- 'Too expensive': Focus on ROI and value\n"
            "- 'Already have someone': Ask about satisfaction level\n"
            "\n## Rules\n"
            "- Keep responses under 3 sentences for natural conversation\n"
            "- Use the lead's name and company name\n"
            "- Reference specific pain points from research\n"
            "- Never lie or make false promises"
        ),
        "tone": "conversational",
        "example_output": "",
        "preferred_tier": "sonnet",
        "preferred_model": "",
        "temperature": 0.7,
        "max_tokens": 256,
        "is_default": False,
        "is_builtin": True,
        "category": "conversation",
        "version": "1.0",
        "capabilities": json.dumps([
            "cold_call", "handle_objection", "book_meeting",
            "voice_conversation", "qualify_by_phone",
        ]),
        "input_schema": json.dumps({
            "type": "object",
            "properties": {
                "lead_context": {"type": "string", "description": "Case file + research summary"},
                "user_speech": {"type": "string", "description": "What the lead just said"},
                "conversation_history": {"type": "array", "items": {"type": "object"}},
            },
            "required": ["user_speech"],
        }),
        "output_schema": json.dumps({
            "type": "object",
            "properties": {
                "response": {"type": "string", "description": "What to say back"},
                "intent_detected": {"type": "string"},
            },
        }),
        "examples": json.dumps([
            {
                "input": {"user_speech": "Yeah, we've been struggling with getting new customers online"},
                "output_summary": "That's a common challenge. Many businesses in Austin have seen great results with targeted local SEO. Would you be open to a quick 15-minute chat about how we could help?",
            },
        ]),
        "tags": json.dumps(["voice", "calls", "cold-calling", "objections", "meetings", "sales"]),
    }


class SkillRegistry:
    """Manages skill registration, discovery, and seeding."""

    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager

    def seed_builtin_skills(self) -> dict:
        """
        Seed or update built-in skills in the database.
        Returns: {"created": int, "updated": int, "errors": list}
        """
        from database.schema import Skill

        created = 0
        updated = 0
        errors = []

        builtin_defs = get_builtin_skills()

        try:
            with self.db_manager.session_scope() as session:
                for skill_def in builtin_defs:
                    existing = session.query(Skill).filter_by(
                        name=skill_def["name"], is_builtin=True
                    ).first()

                    if existing:
                        # Update existing built-in with new definitions
                        for key, value in skill_def.items():
                            if key not in ("name", "is_builtin", "is_default"):
                                setattr(existing, key, value)
                        updated += 1
                    else:
                        skill = Skill(**skill_def)
                        session.add(skill)
                        created += 1

        except Exception as e:
            logger.error(f"Failed to seed skills: {e}")
            errors.append(str(e))

        logger.debug(f"Skill registry: created={created}, updated={updated}, errors={len(errors)}")
        return {"created": created, "updated": updated, "errors": errors}

    def get_all_skills(self) -> List[dict]:
        """Return all skills as dicts."""
        from database.schema import Skill

        try:
            with self.db_manager.session_scope() as session:
                skills = session.query(Skill).all()
                return [
                    {c.name: getattr(s, c.name) for c in s.__table__.columns}
                    for s in skills
                ]
        except Exception as e:
            logger.error(f"Failed to load skills: {e}")
            return []

    def find_skill_for_task(self, task_type: str,
                            context: Optional[dict] = None) -> Optional[dict]:
        """Find the best skill for a given task type."""
        skills = self.get_all_skills()
        return find_best_skill_for_task(skills, task_type, context)

    def get_skills_by_category(self, category: str) -> List[dict]:
        """Return all skills in a given category."""
        from database.schema import Skill

        try:
            with self.db_manager.session_scope() as session:
                skills = session.query(Skill).filter_by(category=category).all()
                return [
                    {c.name: getattr(s, c.name) for c in s.__table__.columns}
                    for s in skills
                ]
        except Exception as e:
            logger.error(f"Failed to load skills for category {category}: {e}")
            return []

    def get_skills_by_capability(self, capability: str) -> List[dict]:
        """Return all skills that have a specific capability."""
        all_skills = self.get_all_skills()
        return [
            s for s in all_skills
            if capability in json.loads(s.get("capabilities", "[]"))
        ]
