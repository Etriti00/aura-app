# Aura — User Manual

> **Your Local AI Sales Agent**
> Version 2.5.0

---

## Table of Contents

1. [Getting Started](#1-getting-started)
2. [Dashboard](#2-dashboard)
3. [Hunter — Lead Discovery](#3-hunter--lead-discovery)
4. [Forge — AI Personas](#4-forge--ai-personas)
5. [Outreach — Email Campaigns](#5-outreach--email-campaigns)
6. [Fleet — Agent Management](#6-fleet--agent-management)
7. [Kanban — Task Board](#7-kanban--task-board)
8. [History — Activity Log](#8-history--activity-log)
9. [Trends — Market Intelligence](#9-trends--market-intelligence)
10. [Budget — Cost Control](#10-budget--cost-control)
11. [Integrations — Telegram & Discord](#11-integrations--telegram--discord)
12. [Settings — Configuration](#12-settings--configuration)
13. [Suppression — Email Blacklist](#13-suppression--email-blacklist)
14. [Research — Lead Intelligence](#14-research--lead-intelligence)
15. [Calls — Voice System](#15-calls--voice-system)
16. [Chat Assistant](#16-chat-assistant)
17. [Advanced AI Features](#17-advanced-ai-features)
18. [Feature Toggles Reference](#18-feature-toggles-reference)
19. [Keyboard Shortcuts](#19-keyboard-shortcuts)
20. [Troubleshooting](#20-troubleshooting)

---

## 1. Getting Started

### 1.1 First Launch

When you run Aura for the first time, a **Setup Wizard** appears to guide you through initial configuration:

1. **API Keys** — Enter at least one AI provider key (Gemini, Anthropic, or OpenAI)
2. **Sender Identity** — Set your name, email address, and company name
3. **Email Delivery** — Configure Resend API key or SMTP server credentials

You can skip optional steps and configure them later in Settings.

### 1.2 Navigation

The **sidebar** on the left contains 14 navigation buttons:

| Icon | Page | What It Does |
|------|------|--------------|
| 📊 | Dashboard | Campaign overview and analytics |
| 🔍 | Hunter | Find and scrape business leads |
| 🛠 | Forge | Create and manage AI writing personas |
| 📧 | Outreach | Generate and send personalized emails |
| 🤖 | Fleet | Manage your AI agent team |
| 📋 | Kanban | Track tasks on a visual board |
| 📜 | History | View command and activity history |
| 📈 | Trends | Google Trends market intelligence |
| 💰 | Budget | Monitor and control AI costs |
| 🔗 | Integrations | Connect Telegram and Discord |
| ⚙️ | Settings | API keys, models, and preferences |
| 🚫 | Suppression | Manage email blacklists |
| 🔬 | Research | Deep-dive lead and company research |
| 📞 | Calls | Voice calling system and call logs |

### 1.3 Chat Assistant

Click the **💬 button** in the top-right corner (or press `Ctrl+Space`) to open the **Chat Panel**. You can also press **`Ctrl+K`** to open the **Command Palette** for fuzzy search across all pages, actions, and commands.

You can type natural language commands like:

- "Start a campaign for plumbers in Austin"
- "Show me today's stats"
- "Export the latest campaign as PDF"
- "Check fleet health"

The AI assistant parses your intent, executes the appropriate action, and shows the result.

---

## 2. Dashboard

The Dashboard is your command center. It shows at a glance:

### Stat Cards (Top Row)
- **Total Campaigns** — Number of campaigns created
- **Total Leads** — All scraped leads across campaigns
- **Qualified** — Leads that passed AI qualification
- **Emailed** — Leads that have been sent emails
- **Replied** — Leads that responded
- **Conversion Rate** — Qualified / Total percentage

### Pipeline Funnel
A visual bar chart showing the progression: **Scraped → New → Qualified → Emailed**. This helps you identify where leads are dropping off.

### A/B Test Results
If A/B testing is enabled, shows side-by-side comparison of Variant A vs Variant B performance (sends, opens, replies, win rate).

### Model Usage
Tracks your AI API usage broken down by tier:
- **Local/Ollama** — Free, runs on your machine
- **Haiku** — Low-cost cloud AI
- **Sonnet** — Premium cloud AI
- **Apollo/Hunter** — External enrichment APIs

Shows total calls, tokens used, and cost for the current month.

### Additional Widgets
- **Morning Triage** — Run inbox triage to categorize overnight emails
- **Fleet Health** — Quick view of agent system status
- **Trending Opportunities** — Rising niches from Google Trends
- **Ticket Pipeline** — Quick Kanban stats (total, in progress, overdue)

### Actions
- **Export PDF** — Generate a campaign performance report
- **Export CSV** — Download lead data as spreadsheet
- **Run Triage Now** — Manually trigger inbox classification

---

## 3. Hunter — Lead Discovery

The Hunter page is where you find new business leads.

### 3.1 Starting a Scrape

1. Enter a **Campaign Name** (e.g., "Austin Plumbers Q1")
2. Enter the **Business Niche** (e.g., "plumber", "dentist", "restaurant")
3. Enter the **Target City** (e.g., "Austin, TX")
4. Optionally enter a **Custom Query** to override the auto-generated search
5. Select **Sources** (checkboxes for Google, LinkedIn, Apollo, etc.)
6. Set **Max Leads** (default: 50)
7. Click **"Start Hunting"**

### 3.2 During the Scrape

- A **progress bar** shows completion percentage
- **Results appear in real-time** in the table below as leads are found
- Each lead shows: Business Name, Category, City, Phone, Email, Source, Website, Status
- The table auto-scrolls to show the newest results
- **Status messages** appear at the bottom showing what the scraper is doing

### 3.3 Safety Features

Aura includes built-in safety to avoid detection:

- **Human-like delays**: Random 2-6 second pauses between requests
- **Reading pauses**: Every 15 requests, a longer 8-18 second pause
- **Break pauses**: Every 50 requests, a 30-90 second break
- **Kill switch**: If 5 consecutive requests fail, scraping automatically stops for 30 minutes. A red warning bar appears with a countdown timer.

You can click **"Stop"** at any time to halt the scrape gracefully.

### 3.4 Batch Import

Below the results table, the **Batch Import** card lets you import leads from a CSV file:

1. Click **"Choose File"** and select a CSV
2. Required columns: `niche`, `city`
3. Optional columns: `limit`, `skill_name`
4. Click **"Import"** to create campaigns from each row

### 3.5 Apollo Search

The **Apollo Search** card provides an alternative discovery method using the Apollo.io API:

1. Enter **Title Keywords** (e.g., "owner, manager")
2. Set **Max Employees** and **Result Limit**
3. Click **"Search Apollo"**

This searches Apollo's database directly and saves results to your campaign.

---

## 4. Forge — AI Personas

The Forge is where you create and manage **Skills** — AI writing personas that control how emails are written.

### 4.1 Understanding Skills

A Skill defines:
- **Name** — Identifier (e.g., "The Closer", "Friendly Neighbor")
- **Tone** — Writing style (professional, casual, friendly, formal, witty, etc.)
- **System Prompt** — Detailed instructions for the AI on how to write emails
- **Temperature** — Creativity level (0.0 = predictable, 1.0 = creative)

### 4.2 Built-in Skills

Aura comes with 15 pre-built skills (marked with 🔒):
- **The Closer** — Confident, direct sales approach
- **The Consultant** — Position as an expert advisor
- **Friendly Neighbor** — Warm, community-focused approach
- **Cold Outreach Pro** — Structured cold email format
- **Follow-up Specialist** — Context-aware follow-up emails
- **Lead Scoring Expert** — Analytical lead qualification
- **Deep Qualifier** — Thorough lead assessment
- And more...

Built-in skills are read-only. You can view their prompts but not modify them.

### 4.3 Creating Custom Skills

1. Click **"+ New Skill"** at the bottom of the skill list
2. Enter a **Name**
3. Select a **Tone** from the dropdown
4. Write your **System Prompt** — instructions for how the AI should write
5. Click **"Save"**

### 4.4 Import/Export

- **Export**: Select a skill → click Export → saves as JSON file
- **Import**: Click Import → select a JSON file → skill is added to your list

### 4.5 A/B Testing

The A/B Testing Stats card shows performance comparison when two skills are assigned to a campaign. Metrics include sends, opens, replies, and win rate. Minimum 20 sends required for statistical confidence.

### 4.6 RAG Memory

The RAG (Retrieval-Augmented Generation) Memory system learns from your sent emails:
- **Import CSV**: Upload previously sent emails to train the AI on your writing style
- **Clear Memory**: Wipe all stored email examples
- Stats show total emails stored and how many received replies

When enabled, the AI references similar successful past emails when generating new ones.

---

## 5. Outreach — Email Campaigns

The Outreach page handles the entire email workflow across 5 tabs.

### 5.1 Compose Tab

This is your main email drafting workspace:

**Left Panel — Lead Selection:**
1. Select a **Campaign** from the dropdown
2. Select a **Skill** (AI persona) from the dropdown
3. The table shows all qualified leads: Business Name, City, Email, Status
4. Click a lead to select it

**Right Panel — Email Editor:**
1. The **To** field auto-fills with the selected lead's email
2. Click **"Generate Email"** — the AI drafts a personalized subject and body
3. A **tone indicator** shows the detected writing tone
4. Edit the subject and body as needed
5. Click **"Send Email"** to deliver

**CRM Sync**: Click the CRM button to push campaign leads to HubSpot or Pipedrive.

### 5.2 Sequences Tab

Shows active follow-up sequences. The system automatically checks every 30 minutes for leads that are due for their next follow-up step.

Each sequence has multiple steps with configurable delays (e.g., Step 1: immediate, Step 2: 3 days later, Step 3: 7 days later).

### 5.3 Replies Tab

Displays detected replies from your inbox. The system checks IMAP every 2 hours for new replies:
- Shows lead name, subject, received time, and sentiment
- Replies automatically update the lead's status
- Pending follow-ups are cancelled when a reply is detected

### 5.4 Scheduled Tab

Shows emails that are scheduled for future delivery based on timezone optimization:
- The system calculates the optimal send time (9am in the lead's local timezone)
- Scheduled emails are sent automatically when their time arrives
- Queue drains every 5 minutes

### 5.5 Channels Tab

Generate outreach drafts for multiple channels simultaneously:
1. Select a lead and skill
2. Click **"Generate All Channels"**
3. View drafts across sub-tabs: **Email**, **LinkedIn**, **Twitter**
4. Use **Copy to Clipboard** buttons for LinkedIn and Twitter messages

---

## 6. Fleet — Agent Management

The Fleet page lets you manage Aura's team of 20 AI agents.

### 6.1 Fleet Overview

The top row shows fleet-wide stats:
- **Fleet Health %** — Percentage of healthy agents
- **Total Agents** — Count (20)
- **Running** — Currently active agents
- **Tasks Today** — Completed tasks count
- **Cost Today** — Total AI spend
- **Errors** — Agents in error state
- **Idle** — Available agents
- **Queued** — Tasks waiting to be assigned

### 6.2 Booting the Fleet

Click **"Boot Fleet"** to activate all agents. This:
1. Sets each agent's status to "idle"
2. Starts the heartbeat timer (checks every 1 minute)
3. Starts the observer timer (health checks every 5 minutes)
4. Starts the escalation timer (ticket checks every 5 minutes)

Click **"Shutdown Fleet"** to deactivate all agents and stop timers.

### 6.3 Agent Cards

Each agent is displayed as a card showing:
- **Emoji + Name** (e.g., 🔍 Scout)
- **Role** (orchestrator, worker, canary, observer)
- **Status badge** (idle, running, paused, error)
- **Model tier** (local, haiku, sonnet)
- **Tasks completed** and **cost**
- **Current task** indicator (⚡) when working

### 6.4 Agent Detail Dialog

Click any agent card to open the detail dialog with 3 tabs:

**Persona Tab:**
- **Soul** — The agent's personality description
- **Mission** — What the agent is trying to accomplish
- **Playbook** — Step-by-step procedures the agent follows
- **Boundaries** — Hard constraints the agent must obey

All fields are editable. Changes are saved immediately.

**Config Tab:**
- Model tier selection
- Heartbeat interval
- Assigned skills
- Memory notes

**Activity Tab:**
- Table of recent tasks with type, status, cost, and timestamps

### 6.5 Health Checks

Click **"Health Check"** to run the Observer agent's diagnostics:
- Checks heartbeat staleness (agents not responding)
- Monitors error rates
- Detects stuck tasks
- Identifies silent agents (no activity for too long)

Results appear in the Observer Panel at the bottom of the page.

---

## 7. Kanban — Task Board

The Kanban page provides a visual task board for tracking work.

### 7.1 Board Layout

Five columns represent the task lifecycle:

```
Backlog → To Do → In Progress → Review → Done
```

Each column shows a count badge with the number of tickets.

### 7.2 Creating Tickets

1. Click **"+ Create Ticket"** in the header
2. Fill in:
   - **Title** (required)
   - **Description** (optional, supports multi-line)
   - **Priority** — Critical, High, Medium, Low
   - **Assignee** — Select an agent from dropdown
   - **Due Date** — Optional deadline
   - **Labels** — Comma-separated tags
3. Click **"Create Ticket"**

### 7.3 Ticket Cards

Each ticket appears as a card showing:
- **Priority dot** — Color-coded (red=critical, orange=high, blue=medium, gray=low)
- **Title** (truncated to fit)
- **Assignee emoji** and **due date**
- **Labels** (max 2 displayed)
- **Sub-ticket count** if any

**Overdue tickets** are highlighted with a red border and show "OVERDUE" in the due date.

### 7.4 Moving Tickets

Right-click a ticket card to see a context menu with all available statuses. Select a new status to move the ticket.

### 7.5 Ticket Detail Dialog

Click a ticket card to open the detail view:
- **Header**: Title + status dropdown
- **Fields**: Description, priority, assignee, due date, labels (all editable)
- **Comments**: Threaded discussion with timestamp and author
- **Add Comment**: Text input at the bottom
- **Save / Delete** buttons in the footer

### 7.6 Filtering

Use the filter bar above the board:
- **Priority** dropdown — Show only specific priority levels
- **Assignee** dropdown — Show only tickets assigned to a specific agent
- **Label** dropdown — Filter by tag
- **Search** — Text search across ticket titles

### 7.7 Sprints

Sprints group tickets into time-boxed work periods. Created programmatically with a name, start date, end date, and list of ticket IDs.

### 7.8 Due Date Alerts

The system automatically checks for overdue and upcoming-due tickets every 5 minutes (when the fleet is running). Agents assigned to overdue tickets receive notification messages.

---

## 8. History — Activity Log

The History page shows a unified timeline of everything that happens in Aura.

### 8.1 What Gets Logged

- **User commands** from Telegram, Discord, or in-app chat
- **Agent actions** — task dispatches, completions, failures
- **System events** — scheduled operations, escalations

Each entry forms a **tree**: a user command at the root with agent actions as branches.

### 8.2 Browsing History

**Filter Bar** (top):
- **Source** — All, Telegram, Discord, Chat, System, Scheduled
- **Agent** — Filter by specific agent
- **Type** — All, user_command, task_dispatched, task_completed, etc.
- **Status** — Pending, Running, Completed, Failed
- **Search** — Text search across command text

**Stat Cards**:
- **Total Commands** — Lifetime count
- **Today** — Commands today
- **Success Rate** — Completion percentage
- **Total Cost** — Cumulative AI spend

### 8.3 Command Trees

Each command row shows:
- **Timestamp** — When it happened
- **Source badge** — Color-coded (Telegram=blue, Discord=purple, Chat=indigo, System=gray)
- **Command text** — What was said/done
- **Agent** — Which agent handled it (if applicable)
- **Status badge** — Completed (green), Failed (red), Running (indigo), Pending (amber)
- **Cost** — AI cost for this action

Click the **expand button (▸)** to reveal child actions. For example, expanding "Start a campaign for plumbers" might show:
- Scout → scrape leads (completed, $0.00)
- Qualifier → qualify leads (completed, $0.02)
- Closer → generate emails (completed, $0.15)

### 8.4 Detail Dialog

Click any command row to open a full tree view dialog:
- **Tree widget** showing the entire command hierarchy
- **JSON detail** for parameters and results
- **Total cost and duration** summary

### 8.5 Pagination

Navigate through history with **Prev/Next** buttons at the bottom. Each page shows 50 entries.

### 8.6 Pruning

Click **"Prune Old"** to delete history entries older than 90 days. This keeps the database lean.

---

## 9. Trends — Market Intelligence

The Trends page uses Google Trends to discover market opportunities.

### 9.1 Keyword Analysis

1. Enter up to 5 **keywords** (comma-separated, e.g., "plumber, electrician, HVAC")
2. Select a **Region** (US, GB, DE, FR, etc.)
3. Select a **Timeframe** (past 7 days, 30 days, 90 days, 12 months, 5 years)
4. Click **"Analyze"**

Results show:
- **Interest Over Time** — Table of dates and scores (0-100)
- **Current Score** — Latest interest level
- **Direction** — Rising, Stable, Declining, or Breakout
- **Peak Date** — When interest was highest

### 9.2 Related Queries

Click **"Related"** after analyzing a keyword to see:
- **Top queries** — Most popular related searches
- **Rising queries** — Rapidly growing related searches
- **Breakout queries** — Explosive growth (500%+)

### 9.3 Opportunity Discovery

1. Enter **seed keywords** (your current niches)
2. Click **"Find Niches"**
3. Results show rising niches you're not yet targeting, sorted by growth rate

### 9.4 Campaign Monitoring

For active campaigns, Aura can monitor keyword trends and alert you to:
- **Breakouts** — Sudden spikes in interest
- **Seasonal changes** — Predictable patterns
- **New competitors** — Related terms indicating competition

### 9.5 Alerts

The alerts table shows all trend notifications:
- **Keyword** — What triggered the alert
- **Type** — Breakout, spike, seasonal, new_competitor
- **Message** — Description of the change
- **Time** — When detected

Click to acknowledge alerts and clear them from the list.

---

## 10. Budget — Cost Control

The Budget page helps you manage AI spending with cruise-control pacing.

### 10.1 Setting a Budget

1. Enter **Budget ($)** — Total amount to spend (e.g., $5.00)
2. Enter **Window (hours)** — Time period for the budget (e.g., 24 hours)
3. Set **Max Tasks** — Maximum number of AI tasks to run
4. Toggle **Eco-Mode** — Automatically downgrade to cheaper AI tiers when budget is tight

### 10.2 Pre-Flight Check

Before activating, click **"Pre-Flight Check"** to verify:
- Is the budget sufficient for the estimated workload?
- What tier can be sustained at the target burn rate?
- How many tasks can be completed within budget?

### 10.3 Active Pacing Monitor

Once activated, the monitor shows real-time stats:
- **Remaining** — Budget dollars left
- **Burn Rate** — Current spending rate ($/hour)
- **Runway** — Estimated time until budget exhaustion
- **Current Tier** — Active AI model tier
- **Usage Bar** — Visual progress of budget consumption

Status indicators:
- **On Track** — Spending within plan
- **Pacing Tight** — Approaching limits
- **Over Budget** — Spending exceeds target rate
- **Expired** — Budget or time exhausted

### 10.4 Eco-Mode

When enabled, Eco-Mode automatically:
- Downgrades expensive tasks to cheaper AI tiers
- Uses the fallback chain: Sonnet → Haiku → Ollama → Local
- Only applies when burn rate exceeds 120% of target
- Notifies you when tier changes occur

### 10.5 Tier Costs

| Tier | Cost per 1K Tokens | Best For |
|------|--------------------:|----------|
| Local | $0.000 | Data formatting, CSV exports |
| Ollama | $0.000 | HTML parsing, classification |
| Haiku | $0.0005 | Lead qualification, basic analysis |
| Sonnet | $0.006 | Email generation, complex analysis |

---

## 11. Integrations — Telegram & Discord

The Integrations page lets you connect Aura to messaging platforms so you can control it remotely.

### 11.1 Connecting Telegram

1. Create a Telegram bot via @BotFather
2. Copy the **bot token**
3. Paste it in the Telegram token field
4. Click **"Connect"**
5. The status badge turns green when connected

### 11.2 Connecting Discord

1. Create a Discord application at discord.com/developers
2. Create a bot and copy the **bot token**
3. Paste it in the Discord token field
4. Click **"Connect"**

### 11.3 Access Control

Only **authorized users** can send commands to Aura through messaging platforms:

1. Select the **Platform** (Telegram or Discord)
2. Enter the **User ID** (numeric ID from the platform)
3. Optionally enter a **Display Name**
4. Click **"+ Add"**

To remove access, click the delete button next to the user in the authorized users table.

### 11.4 Sending Commands

Once connected and authorized, you can send messages to your Aura bot:

- "Show me today's stats"
- "Start a campaign for dentists in LA"
- "How many leads do we have?"
- "Export the latest report"

Aura parses your intent, executes the action, and sends back the result. Responses are formatted for each platform (Telegram uses HTML, Discord uses Markdown).

### 11.5 Notification Preferences

Toggle which proactive notifications you want to receive:
- **Budget pacing alerts** — Warnings when approaching budget limits
- **Inbox triage summaries** — Morning email classification reports
- **Campaign completion alerts** — When campaigns finish running

---

## 12. Settings — Configuration

The Settings page is organized into **7 tabs** for easy navigation, similar to the Outreach page layout:

| Tab | What It Contains |
|-----|-----------------|
| **API Keys** | API key management, authentication modes, subscription auth |
| **AI Config** | Model selection, autonomy level, advanced AI engine toggles |
| **Email & Delivery** | Sender identity, SMTP fallback, IMAP reply detection |
| **Features** | Feature toggles, CRM platform, research & voice config |
| **Business & Invoicing** | Company info, banking details, invoice configuration |
| **Knowledge Base** | Product info, ICP criteria, approach & tone settings |
| **Appearance** | Theme selection (light/dark) |

### 12.1 API Keys Tab

Enter API keys for the services you want to use:

| Provider | Purpose | Required? |
|----------|---------|-----------|
| **Google Gemini** | AI (cheapest option) | At least one AI key required |
| **Anthropic** | AI (Claude models) | At least one AI key required |
| **OpenAI** | AI (GPT models) | At least one AI key required |
| **OpenRouter** | AI (multi-model access) | Optional |
| **Resend** | Email delivery | Recommended |
| **Apollo** | Lead enrichment | Optional |
| **Hunter** | Email finding/verification | Optional |
| **HubSpot** | CRM sync | Optional |
| **Pipedrive** | CRM sync | Optional |
| **Tavily** | AI-powered web search (research) | Optional |
| **Firecrawl** | Website scraping (research) | Optional |
| **Apify** | Web automation (research) | Optional |
| **Twilio** | Voice calling (Account SID + Auth Token) | Optional |
| **ElevenLabs** | Premium text-to-speech | Optional |

Keys are stored encrypted using hardware-bound encryption. They never leave your machine.

Each key field shows a masked preview (e.g., `sk-proj-****6789`). Click the eye button to reveal.

**Authentication Modes**: For Anthropic and OpenAI, choose between API Key or Subscription mode. Subscription lets you use your existing Claude Pro/Max or ChatGPT Plus account.

**Subscription Auth**: each provider routes through its official CLI — Anthropic via `claude` (Claude Code, `claude login`), OpenAI via `codex` (`codex login` with a ChatGPT account), Google via `gemini` (`gemini auth login`). Install the CLI, log in once, then click Enable Subscription.

### 12.2 AI Config Tab

**Model Selection**: Choose which AI models to use for each task tier:
- **Tier 2 (Qualification)** — Cheap, fast model for lead scoring. Default: Gemini 2.0 Flash
- **Tier 3 (Email Generation)** — Premium model for writing emails. Default: Claude Sonnet
- **Chat (Assistant)** — Model for the chat panel. Default: same as Tier 3

**Autonomy Level**: Controls how much independence your AI agents have (Observer, Supervised, Autonomous, Full Trust). See Section 17.7 for details.

**Advanced AI Engines**: Toggle individual AI subsystems — Reflection (auto-critique), Self-Improvement (daily optimization), Knowledge Graph (entity tracking), Conversation Engine (reply tracking).

### 12.3 Email & Delivery Tab

**Sender Identity**: Configure who emails appear to come from — your name, email address, and company name.

**SMTP Fallback**: Optional SMTP server for when Resend is unavailable — host, port, username, password.

**IMAP (Reply Detection)**: For reply detection and inbox triage — host, port, username, password, SSL toggle.

### 12.4 Features Tab

**Feature Toggles**:

| Toggle | What It Controls |
|--------|-----------------|
| **A/B Testing** | Test two skills against each other per campaign |
| **Lead Enrichment** | Auto-enrich leads with Google Maps, WHOIS, social data |
| **Global Suppression** | Check suppression list before sending emails |
| **Timezone Scheduling** | Schedule emails for 9am in the lead's local time |
| **RAG Memory** | Learn from past emails to improve future ones |
| **Cross-Channel** | Generate LinkedIn and Twitter drafts alongside email |
| **Inbox Triage** | Automated morning email classification |
| **Fleet System** | Enable the multi-agent fleet |
| **Google Trends** | Enable trend monitoring and analysis |
| **CRM Platform** | Select HubSpot or Pipedrive for CRM sync |

**Research & Voice Config**: Toggle auto-research and voice calls, configure Twilio phone number, ElevenLabs Voice ID, TTS/STT provider selection.

### 12.5 Business & Invoicing Tab

This tab provides the company and billing information that AI agents use when generating invoices and professional communications.

**Company Information**:
- **Company Legal Name** — Used on invoices and official documents
- **Tax ID / VAT** — Tax identification number
- **Company Email & Phone** — Contact information for invoices
- **Company Website** — Included in email signatures
- **Company Address** — Full postal address (multi-line)
- **Company Logo Path** — Path to logo file (used on PDF invoices). Click "Browse" to select
- **Telegram Owner Chat ID** — Your personal Telegram ID for owner notifications

**Banking Details**:
- **Bank Name** — Your company's bank
- **SWIFT / BIC** — International bank identifier
- **IBAN** — International Bank Account Number

All banking data is stored locally and encrypted. It is only used for invoice generation.

**Invoice Configuration**:
- **Invoice Prefix** — Prefix for invoice numbers (e.g., "INV-", "AURA-")
- **Next Number** — The next invoice number to use (auto-increments)
- **Currency** — Default currency (EUR, USD, GBP, CHF, CAD, AUD, JPY)
- **Payment Terms** — Days until payment is due (default: 30)
- **Default Invoice Notes** — Footer text on invoices (e.g., "Thank you for your business")

### 12.6 Appearance Tab

Switch between **Light** and **Dark** themes. The change applies immediately across all pages.

---

## 13. Suppression — Email Blacklist

The Suppression page manages a global blacklist of emails and domains that should never receive outreach.

### 13.1 Adding Entries

1. Select type: **Email** or **Domain**
2. Enter the value (e.g., `john@example.com` or `example.com`)
3. Click **"+ Add"**

When you add a domain, all emails at that domain are automatically suppressed.

### 13.2 Importing from CSV

1. Click **"Import CSV"**
2. Select a CSV file with columns: `email` and/or `domain`
3. All entries are added to the suppression list

### 13.3 How Suppression Works

- Before sending any email, Aura checks the suppression list
- Before saving any scraped lead, Aura checks the suppression list
- Unsubscribe replies detected by the Triage Engine are automatically added
- The list uses an in-memory cache (refreshed every 10 minutes) for fast lookups

### 13.4 Managing Entries

- The table shows all suppressed entries with ID, Email, Domain, Reason, and Date
- Select rows and click **"Delete Selected"** to remove entries
- Click **"Refresh"** to reload the list

---

## 14. Research — Lead Intelligence

The Research page enables deep enrichment of leads using multiple intelligence providers.

### 14.1 Research Providers

Aura supports three research providers (configure API keys in Settings):

| Provider | Capability |
|----------|-----------|
| **Tavily** | Web search and summarization |
| **Firecrawl** | Website scraping and content extraction |
| **Apify** | Advanced web automation and data collection |

Provider status badges at the top of the page show which providers are configured and active.

### 14.2 Starting Research

1. Navigate to the **Research** page
2. Select a lead from the queue or enter a company name
3. Choose **Depth**:
   - **Quick** — Surface-level overview (faster, cheaper)
   - **Deep** — Comprehensive multi-source analysis
4. Click **"Start Research"**
5. Monitor progress in the research queue table

> **Auto-Research**: When enabled in Settings, leads are automatically researched after AI qualification. The depth is selected based on qualification score vs. the deep research threshold.

### 14.3 Research Reports

Each completed report includes:
- **Company Overview** — What the company does, size, location
- **Pain Points** — Challenges and problems they face
- **Gaps & Opportunities** — Where they're underserved or have room to grow
- **Services Offered** — Their current product/service lineup
- **Tech Stack** — Technologies they use
- **Competitor Analysis** — Key competitors and positioning

Research data is automatically injected into email drafts for highly personalized outreach.

### 14.4 Configuration

In **Settings**, configure:
- **Tavily API Key** — Web search provider
- **Firecrawl API Key** — Website scraping provider
- **Apify API Key** — Web automation provider
- **Auto-Research** toggle — Enable auto-research after qualification
- **Deep Research Threshold** — Qualification score threshold for deep vs. quick research

---

## 15. Calls — Voice System

The Calls page manages AI-powered voice outreach via Twilio integration.

### 15.1 When Calls Are Triggered

Voice calls are a **last resort** — they trigger automatically when leads are stalled:
- **3+ failed email deliveries** — The email channel isn't working for this lead
- **Interested but silent for 7+ days** — Lead showed interest but stopped responding

The **Caller** agent (part of the AI fleet) detects these conditions and requests approval to make a call.

### 15.2 Making Calls

1. The fleet identifies a stalled lead meeting the criteria above
2. A **make_call** approval request appears in the approval queue
3. You **approve** (or deny) the call
4. On approval, the Caller agent initiates the voice call via Twilio
5. The call uses text-to-speech (TTS) for the agent's voice and speech-to-text (STT) for the lead's responses

> **Important**: Voice calls **always require your approval**, even at the highest autonomy level (Full Trust).

### 15.3 Active Calls

The Active Calls panel shows in-progress calls with:
- Lead name and company
- Call duration timer
- Live transcript (agent and lead turns)

### 15.4 Call Logs

The Call Log table displays completed calls with:
- Date and time
- Lead information
- Duration
- Outcome (connected, voicemail, no answer, declined)
- Sentiment analysis score

Click any row to view the **full transcript** in the detail panel.

### 15.5 Voice Configuration

In **Settings**, configure:
- **Twilio Account SID** — Your Twilio account credentials
- **Twilio Auth Token** — Authentication token
- **Twilio Phone Number** — Outbound caller ID
- **Voice Call Enabled** toggle — Master switch for voice calling
- **TTS Provider** — ElevenLabs (premium), OpenAI (mid-tier), or Piper (free local)
- **STT Provider** — Whisper local or OpenAI API
- **ElevenLabs API Key** — For premium voice synthesis (optional)

---

## 16. Chat Assistant

The Chat Panel is a slide-in interface for natural language interaction with Aura.

### 16.1 Opening the Chat

- Click the **💬 button** in the top bar
- Or press **Ctrl+Space**

### 16.2 Supported Commands

The chat assistant understands a wide range of commands:

**Campaign Management:**
- "Start a campaign for [niche] in [city]"
- "Pause campaign [name]"
- "Show campaign stats"

**Lead Operations:**
- "Enrich the leads in [campaign]"
- "Export leads as CSV"
- "How many qualified leads do we have?"

**Email:**
- "Generate drafts for [campaign]"
- "Send emails to qualified leads"

**Fleet:**
- "Boot the fleet"
- "Shut down the fleet"
- "What's the fleet status?"
- "Dispatch a task to [agent]"

**Analysis:**
- "Show me today's stats"
- "What's our best performing skill?"
- "Analyze campaign [name]"

**Budget:**
- "Set a budget of $10 for 24 hours"
- "What's our current spend?"

**Gateway:**
- "Connect Telegram"
- "Add user [id] to Telegram"

**Reports:**
- "Export report for [campaign]"
- "Generate a PDF report"

### 16.3 Confirmation Cards

For actions that have side effects (like sending emails), the chat shows a **confirmation card** with:
- Action description
- Details of what will happen
- **Confirm** and **Cancel** buttons

### 16.4 Inline Editors

When the AI generates an email draft, an inline editor appears:
- **To** field (read-only)
- **Subject** input (editable)
- **Body** textarea (editable)
- **Approve** and **Discard** buttons

### 16.5 Suggestion Chips

Quick-action buttons at the bottom of the chat:
- "Show stats" — View dashboard summary
- "Best skill?" — Ask about top performers
- "Export report" — Generate campaign report

---

## 17. Advanced AI Features

Aura includes a suite of advanced AI capabilities that work behind the scenes to make your outreach smarter, more adaptive, and increasingly effective over time. Here is what each one does for you.

### 17.1 Self-Learning (Reflection)

Every time an AI agent completes a task -- whether it is qualifying a lead, drafting an email, or analyzing a campaign -- Aura automatically reviews the quality of that work. If the output does not meet the quality bar, the agent is asked to revise and improve it before you ever see it. Over time, the system builds a record of what works and what does not, so each agent gets better at its job the longer you use Aura.

You do not need to configure anything. Reflection happens automatically in the background. You benefit from higher-quality emails, more accurate lead scores, and fewer errors as the system learns from its own output.

### 17.2 Smart Lead Tracking (Lifecycle States)

Instead of simple labels like "new" or "emailed," Aura now tracks each lead through a detailed journey with 19 distinct stages. A lead moves from discovery through research, qualification, outreach, conversation, negotiation, and eventually to a closed deal or a graceful exit.

This means you can see exactly where every lead stands in your pipeline at any moment. If a lead raised an objection, you will see that. If a lead asked to be contacted later, Aura remembers and schedules the follow-up. Every state change is recorded, so you have a complete history of how each lead progressed.

### 17.3 Intelligent Memory (RAG and Knowledge Graph)

Aura remembers everything it learns and uses that knowledge to improve future results.

**Email Memory**: When you send emails and receive replies, Aura studies what worked. The next time it drafts an email for a similar lead, it draws on those successful examples to write something more likely to get a response.

**Relationship Mapping**: Aura builds a map of how leads, companies, niches, and campaigns connect to each other. If a competitor of one of your clients responds well to a certain approach, Aura can suggest using a similar angle for related companies. If a particular niche is converting well, Aura surfaces that insight so you can double down.

The memory system works across four areas: past emails, lead interactions, domain knowledge, and agent-discovered patterns. All of this is stored locally on your machine.

### 17.4 Conversation Management

When a lead replies to your email, Aura does not just detect the reply -- it understands the intent behind it. The system classifies replies into categories: interested, raising an objection, asking a question, deferring to later, or requesting to unsubscribe.

For objections, Aura suggests tailored responses based on the type of pushback (pricing concerns, timing issues, competitor comparisons, or authority questions). For leads who say "not now," Aura automatically schedules a re-engagement at an appropriate future date. For questions, it helps you draft helpful answers that keep the conversation moving forward.

All messages in a conversation thread are tracked together, so every response has full context of everything that came before.

### 17.5 Self-Improvement

Beyond individual task reflection, Aura runs a broader improvement cycle that monitors agent performance over time. The system tracks success rates, quality scores, and cost efficiency for every agent in your fleet.

When an agent's performance drops below the fleet average, the system flags it and analyzes what changed. It also studies high-performing agents to extract the patterns and rules that make them effective, then applies those learnings to the underperformers.

This improvement cycle runs daily and requires no manual intervention. The result is a fleet of agents that collectively gets better at finding leads, writing emails, and closing deals over time.

### 17.6 Strategic Goal Planning

Instead of running campaigns ad hoc, you can set a concrete goal -- for example, "I want 10 new clients this quarter" -- and Aura will work backward to calculate exactly what needs to happen to get there. How many meetings do you need? How many replies? How many emails? How many qualified leads? How many contacts should you scrape?

The Strategy Engine breaks your goal into 5 phases with estimated timelines and cost projections. As you make progress, you can track where you stand against each milestone. This turns Aura from a tool you operate into a system that drives toward your business objectives.

### 17.7 Autonomy Control

You decide how much independence your AI agents have. Aura provides four levels of autonomy:

- **Observer** -- The agents can analyze and recommend, but they cannot take any action. You review everything before it happens.
- **Supervised** -- Agents can research, qualify, and organize leads on their own, but any email generation or sending requires your approval. This is the recommended starting point.
- **Autonomous** -- Agents handle the full pipeline from discovery to outreach without your intervention. The only thing they cannot do is modify their own skills and prompts.
- **Full Trust** -- Agents operate with no restrictions.

When an agent tries to do something beyond its current autonomy level, the action is placed in an approval queue. You can review pending actions and approve or deny them one by one. You can change the autonomy level at any time from the Settings page.

> **Note**: Voice calls (`make_call`) always require approval, even at the Full Trust level.

### 17.8 Voice Calling

When leads stop responding to emails, Aura can escalate to voice calls as a last resort. The Caller agent automatically detects stalled leads (3+ failed emails, or interested leads silent for 7+ days) and requests permission to call them via Twilio.

The voice system uses a TTS cascade (ElevenLabs → OpenAI → Piper local) for the agent's voice and Whisper for speech-to-text transcription. All calls are recorded, transcribed, and analyzed for sentiment.

See [Section 15 — Calls](#15-calls--voice-system) for the full UI guide.

### 17.9 Lead Research

Aura conducts deep research on leads using multiple intelligence providers (Tavily, Firecrawl, Apify). Research reports include company overview, pain points, market gaps, tech stack, and competitor analysis. This data is automatically injected into email drafts for hyper-personalized outreach.

Auto-research can be triggered after lead qualification, with depth (quick vs. deep) selected based on the qualification score.

See [Section 14 — Research](#14-research--lead-intelligence) for the full UI guide.

---

## 18. Feature Toggles Reference

| Feature | Default | Description |
|---------|---------|-------------|
| A/B Testing | Off | Split-test two skills per campaign. Requires 20+ sends for confidence. |
| Lead Enrichment | Off | Auto-enrich with Google Maps rating, domain age, social profiles, screenshots. |
| Global Suppression | On | Check blacklist before sending. Prevents sending to opted-out contacts. |
| Timezone Scheduling | Off | Schedule sends for 9am in lead's local timezone instead of immediately. |
| RAG Memory | Off | Learn from past emails to improve style matching. Stores embeddings locally. |
| Cross-Channel | Off | Generate LinkedIn and Twitter drafts alongside email. |
| Inbox Triage | Off | Morning inbox classification: categorize replies, bounces, unsubscribes. |
| Fleet System | Off | Enable multi-agent fleet with 19 specialized AI agents. |
| Google Trends | Off | Enable trend monitoring, spike detection, and niche discovery. |
| CRM Platform | None | Select HubSpot or Pipedrive for automatic lead sync. |
| Auto-Research | Off | Automatically research leads after AI qualification. |
| Voice Call Enabled | Off | Enable voice calling system (requires Twilio credentials). |
| Conversation Engine | On | Track multi-turn email threads with intent classification. |
| Knowledge Graph | On | Build entity-relationship graph from lead interactions. |
| Self-Improvement | On | Enable daily agent performance analysis and learning cycles. |

---

## 19. Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+Space` | Toggle Chat Panel |
| `Ctrl+K` | Open Command Palette (fuzzy search across pages and commands) |

---

## 20. Troubleshooting

### 20.1 "Kill switch activated"

The scraper detected potential blocking (5 consecutive failures). Wait for the cooldown timer to expire (30 minutes), then try again with a smaller batch size.

### 20.2 Emails not sending

1. Check that you have a **Resend API key** or **SMTP** configured in Settings
2. Verify your **sender email** is set in Settings
3. Check the **daily limit** (100 emails/day max)
4. Ensure the lead is not on the **suppression list**

### 20.3 No AI responses

1. Verify at least one **API key** is configured (Gemini, Anthropic, or OpenAI)
2. Check your API key is valid and has credits
3. Check the **Budget** page — pacing may have exhausted the budget
4. Look at the **Model Usage** section on Dashboard for error counts

### 20.4 Replies not detected

1. Ensure **IMAP** is configured in Settings
2. Verify the IMAP credentials work (test with your email client)
3. Enable **SSL** if using Gmail/Outlook
4. The reply checker runs every 2 hours — use "Check Now" in Outreach > Replies tab

### 20.5 Fleet agents in error state

1. Run a **Health Check** from the Fleet page
2. Check the Observer Panel for specific issues
3. Try **shutting down** and **rebooting** the fleet
4. Open the agent's detail dialog to check for stuck tasks

### 20.6 Database issues

The database is stored at `~/.aura/aura.db`. If you encounter corruption:
1. Close Aura
2. Back up the database file
3. Relaunch — migrations will attempt to fix the schema
4. If issues persist, rename/delete the DB file and restart (creates a fresh database)

### 20.7 Build issues

If rebuilding the executable:
```bash
venv/Scripts/pyinstaller aura.spec --noconfirm
```

If you get import errors, check that all modules are listed in `aura.spec` hiddenimports.

### 20.8 Logs

Check the log file at `~/.aura/aura.log` for detailed error information. The log rotates at 5MB with 3 backups.

---

*Aura v2.5.0 — Your Local AI Sales Agent*
*Last updated: 2026-07-09*
