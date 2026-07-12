import { Check, Cloud, HardDrive } from "lucide-react";
import { motion } from "motion/react";
import SectionEyebrow from "./SectionEyebrow";
import { MODEL_LOGOS, type Logo } from "../lib/integrations";
import { LogoGlyph } from "./Integrations";

const EASE: [number, number, number, number] = [0.22, 1, 0.36, 1];

function ModelChip({ logo }: { logo: Logo }) {
	return (
		<span
			className="integ-tile inline-flex items-center gap-1.5 rounded-full border bg-white/[0.03] px-2.5 py-1"
			style={{ ["--brand" as string]: logo.hover }}
		>
			<LogoGlyph logo={logo} size={14} />
			<span className="text-[11px] font-medium">{logo.name}</span>
		</span>
	);
}

const PLAYWRIGHT: Logo = { ...MODEL_LOGOS.playwright, category: "", stroke: false };

function Row({ children }: { children: React.ReactNode }) {
	return (
		<li className="flex items-start gap-2.5 text-sm text-white/70 leading-[1.5]">
			<Check className="w-4 h-4 mt-0.5 text-[#7DBEFF] shrink-0" />
			<span>{children}</span>
		</li>
	);
}

export default function LocalOrCloud() {
	return (
		<section className="max-w-[1440px] mx-auto px-6 sm:px-8 lg:px-12 py-20 md:py-28 border-t border-white/10">
			<div className="text-center flex flex-col items-center">
				<SectionEyebrow label="Models" tag="Local or cloud" />
				<h2 className="mt-5 text-3xl md:text-5xl font-semibold tracking-tight leading-[1.02] max-w-2xl">
					Run it your way. Your data, your call.
				</h2>
				<p className="mt-6 text-white/60 text-base leading-[1.6] max-w-xl">
					Point every agent at the model that fits the task. Run entirely on
					your own hardware, reach for the frontier in the cloud, or mix both.
				</p>
			</div>

			<div className="mt-14 grid md:grid-cols-2 gap-5">
				<motion.div
					initial={{ opacity: 0, y: 20 }}
					whileInView={{ opacity: 1, y: 0 }}
					viewport={{ once: true, margin: "-80px" }}
					transition={{ duration: 0.6, ease: EASE }}
					className="liquid-glass rounded-2xl p-7"
				>
					<div className="flex items-center gap-3">
						<div className="w-10 h-10 rounded-xl bg-white/[0.05] border border-white/10 flex items-center justify-center">
							<HardDrive className="w-5 h-5 text-white/80" />
						</div>
						<div>
							<h3 className="text-lg font-semibold tracking-tight">Local</h3>
							<p className="text-xs text-white/45">Private, free, on your hardware</p>
						</div>
					</div>
					<div className="mt-5 flex flex-wrap gap-2">
						<ModelChip logo={{ ...MODEL_LOGOS.ollama, category: "" }} />
						<ModelChip logo={PLAYWRIGHT} />
					</div>
					<ul className="mt-5 space-y-2.5">
						<Row>Any Ollama model runs fully offline. Nothing leaves your device.</Row>
						<Row>No API cost. Only your own compute.</Row>
						<Row>Lead scraping runs on a bundled Playwright browser, on device.</Row>
						<Row>Ideal for a Raspberry Pi or an always on VPS.</Row>
					</ul>
				</motion.div>

				<motion.div
					initial={{ opacity: 0, y: 20 }}
					whileInView={{ opacity: 1, y: 0 }}
					viewport={{ once: true, margin: "-80px" }}
					transition={{ duration: 0.6, delay: 0.12, ease: EASE }}
					className="liquid-glass rounded-2xl p-7"
				>
					<div className="flex items-center gap-3">
						<div className="w-10 h-10 rounded-xl bg-[#00d2ff]/10 border border-[#00d2ff]/25 flex items-center justify-center">
							<Cloud className="w-5 h-5 text-[#7DBEFF]" />
						</div>
						<div>
							<h3 className="text-lg font-semibold tracking-tight">Cloud</h3>
							<p className="text-xs text-white/45">The frontier, subscription or API</p>
						</div>
					</div>
					<div className="mt-5 flex flex-wrap gap-2">
						<ModelChip logo={{ ...MODEL_LOGOS.claude, category: "" }} />
						<ModelChip logo={{ ...MODEL_LOGOS.openai, category: "" }} />
						<ModelChip logo={{ ...MODEL_LOGOS.gemini, category: "" }} />
					</div>
					<ul className="mt-5 space-y-2.5">
						<Row>Run on the Claude, ChatGPT, or Gemini subscription you already pay for, through the official CLIs.</Row>
						<Row>Or use API keys for Grok, GLM, Kimi, Qwen, MiniMax, and Nemotron.</Row>
						<Row>One OpenRouter key can reach the entire fleet.</Row>
						<Row>A cost aware router picks the cheapest capable model per task.</Row>
					</ul>
				</motion.div>
			</div>

			<p className="mt-8 text-center text-sm text-white/45 max-w-2xl mx-auto">
				Every agent can carry its own model, so a local classifier and a
				cloud copywriter run side by side in the same pipeline.
			</p>
		</section>
	);
}
