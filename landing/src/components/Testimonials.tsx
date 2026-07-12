import { motion } from "motion/react";
import { Cpu, Lock, Workflow } from "lucide-react";

const EASE: [number, number, number, number] = [0.22, 1, 0.36, 1];

const POINTS = [
	{
		Icon: Workflow,
		title: "One pipeline, fully automated",
		body: "Name a niche and a city. Aura scrapes real businesses, qualifies them against a quality gate, researches the promising ones, drafts personalized emails, sends sequences, and routes the replies back to you. Each step runs on its own and asks approval until you say otherwise.",
	},
	{
		Icon: Cpu,
		title: "Any model you trust",
		body: "Route each agent to Claude, ChatGPT, or Gemini through your existing subscriptions, plug in API keys for Grok, GLM, Kimi, Qwen, and MiniMax, or run everything locally with Ollama. A cost aware router picks the cheapest capable model for every task.",
	},
	{
		Icon: Lock,
		title: "Private by design",
		body: "Everything lives on your machine. Your leads sit in a local SQLite database and your API keys are sealed with machine bound encryption. No cloud account, no telemetry, no data leaving your device.",
	},
];

export default function Testimonials() {
	return (
		<section className="max-w-[1440px] mx-auto px-6 sm:px-8 lg:px-12 py-20 md:py-28 border-t border-white/10">
			<div className="grid md:grid-cols-3 gap-6">
				{POINTS.map(({ Icon, title, body }, i) => (
					<motion.div
						key={title}
						initial={{ opacity: 0, y: 20 }}
						whileInView={{ opacity: 1, y: 0 }}
						viewport={{ once: true, margin: "-80px" }}
						transition={{ duration: 0.6, delay: i * 0.1, ease: EASE }}
						className="liquid-glass rounded-2xl p-6"
					>
						<div className="w-10 h-10 rounded-xl flex items-center justify-center bg-[#00d2ff]/10 border border-[#00d2ff]/25">
							<Icon className="w-5 h-5 text-[#7DBEFF]" />
						</div>
						<h3 className="mt-4 text-base font-semibold tracking-tight">{title}</h3>
						<p className="mt-2 text-sm text-white/60 leading-[1.6]">{body}</p>
					</motion.div>
				))}
			</div>
		</section>
	);
}
