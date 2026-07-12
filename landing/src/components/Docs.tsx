import { motion } from "motion/react";
import SectionEyebrow from "./SectionEyebrow";

const EASE: [number, number, number, number] = [0.22, 1, 0.36, 1];

const TOPICS = [
	{
		title: "The agent fleet",
		body: "Twenty specialist agents run as a ranked hierarchy. A Commander triages incoming work into typed tasks and dispatches each to the agent whose role and skills fit. Scout hunts, Enricher fills gaps, Qualifier gatekeeps, Closer writes, Postman delivers, Tracker and Triage Lead handle replies, and Observer watches everyone's health. Agents coordinate through a shared kanban board with escalation and due dates.",
	},
	{
		title: "The skill forge",
		body: "Skills are the superpowers agents apply to tasks. Aura ships 26 built in skills, each with a persona, step by step instructions, input and output schemas, and calibrated sampling. Every agent carries a least privilege set of the skills its duties require. When a task needs a skill an agent does not have, it requests it from the Commander, who grants it and logs the exchange. When a task needs a skill that does not exist at all, the Forger designs a new one on the spot.",
	},
	{
		title: "Model routing",
		body: "Each agent runs on its own model. A four tier cost router (local, ollama, haiku, sonnet) picks the cheapest capable option per task, and any agent can be pinned to an exact model from the fleet. Bring Claude, ChatGPT, or Gemini via subscription CLIs, or API keys for Grok, GLM, Kimi, Qwen, MiniMax, and Nemotron. No assignment is saved until it passes a two step check: the provider authenticates, then a live test prompt returns a real response.",
	},
	{
		title: "Privacy and control",
		body: "Everything runs on your machine. Leads live in a local SQLite database and API keys are sealed with machine bound AES 256 encryption. An autonomy setting gates consequential actions, from fully supervised (every action needs approval) to fully autonomous. A suppression list and per lead approval keep outreach compliant.",
	},
	{
		title: "The desktop app",
		body: "Fourteen pages cover the whole workflow: Dashboard, Hunter, Forge, Outreach, Fleet, Kanban, History, Trends, Budget, Integrations, Settings, Suppression, Research, and Calls. A built in chat assistant runs the same agent stack, and a command palette reaches every action. The interface is a native liquid glass design on Windows, macOS, and Linux.",
	},
	{
		title: "Servers and small devices",
		body: "The same fleet runs headless. An 82 command CLI drives every feature with no display required, so Aura runs around the clock on a VPS or sips power on a Raspberry Pi. Pair it with Ollama and quantized local models for an always on setup, or install the desktop app on your Windows, macOS, or Linux machine.",
	},
];

export default function Docs() {
	return (
		<section id="docs" className="max-w-[1440px] mx-auto px-6 sm:px-8 lg:px-12 py-20 md:py-28 border-t border-white/10">
			<SectionEyebrow label="Documentation" tag="How it works" />
			<h2 className="mt-5 text-3xl md:text-5xl font-semibold tracking-tight leading-[1.02] max-w-2xl">
				Everything Aura does, and how.
			</h2>
			<p className="mt-6 text-white/60 text-base leading-[1.6] max-w-xl">
				Aura is an autonomous B2B sales platform built as a fleet of AI
				agents. Here is how the pieces fit together.
			</p>
			<div className="mt-12 grid md:grid-cols-2 gap-5">
				{TOPICS.map(({ title, body }, i) => (
					<motion.div
						key={title}
						initial={{ opacity: 0, y: 20 }}
						whileInView={{ opacity: 1, y: 0 }}
						viewport={{ once: true, margin: "-60px" }}
						transition={{ duration: 0.6, delay: (i % 2) * 0.08, ease: EASE }}
						className="liquid-glass rounded-2xl p-6"
					>
						<h3 className="text-base font-semibold tracking-tight">{title}</h3>
						<p className="mt-2.5 text-sm text-white/60 leading-[1.65]">{body}</p>
					</motion.div>
				))}
			</div>
		</section>
	);
}
