import { motion } from "motion/react";
import SectionEyebrow from "./SectionEyebrow";

const EASE: [number, number, number, number] = [0.22, 1, 0.36, 1];

const CHIPS = [
	"Hands off routing",
	"Skills granted on request",
	"Cost aware model tiers",
	"Every step audited",
];

const STEPS: {
	agent: string;
	detail: string;
	state: "done" | "active" | "queued";
}[] = [
	{ agent: "Scout", detail: "scraped 128 dentists in Vienna", state: "done" },
	{ agent: "Qualifier", detail: "47 passed the quality gate", state: "done" },
	{ agent: "Closer", detail: "drafting 36 personalized emails", state: "active" },
	{ agent: "Postman", detail: "sends inside business hours", state: "queued" },
	{ agent: "Triage Lead", detail: "routes replies to your inbox", state: "queued" },
];

const STATE_STYLES: Record<string, { dot: string; text: string }> = {
	done: { dot: "#28c840", text: "text-white/50" },
	active: { dot: "#00d2ff", text: "text-white" },
	queued: { dot: "#525252", text: "text-white/40" },
};

export default function FeatureTriage() {
	return (
		<section id="fleet" className="max-w-[1440px] mx-auto px-6 sm:px-8 lg:px-12 py-20 md:py-28">
			<div className="grid md:grid-cols-2 gap-10 md:gap-16 items-start">
				<motion.div
					initial={{ opacity: 0, y: 20 }}
					whileInView={{ opacity: 1, y: 0 }}
					viewport={{ once: true, margin: "-80px" }}
					transition={{ duration: 0.7, ease: EASE }}
				>
					<SectionEyebrow label="The pipeline" tag="Agent fleet" />
					<h2 className="mt-5 text-3xl md:text-5xl font-semibold tracking-tight leading-[1.02]">
						From niche to booked call
						<br />
						in a single pass.
					</h2>
					<p className="mt-6 text-white/60 text-base leading-[1.6] max-w-md">
						Name a niche and a city. Twenty specialist agents hand the work to
						each other, step by step, until replies from real leads land in
						your inbox. You approve, they execute.
					</p>
					<div className="mt-8 flex flex-wrap gap-2">
						{CHIPS.map((chip) => (
							<span
								key={chip}
								className="text-xs text-white/70 px-3 py-1.5 rounded-full border border-white/10 bg-white/[0.03]"
							>
								{chip}
							</span>
						))}
					</div>
				</motion.div>

				<motion.div
					initial={{ opacity: 0, y: 20 }}
					whileInView={{ opacity: 1, y: 0 }}
					viewport={{ once: true, margin: "-80px" }}
					transition={{ duration: 0.7, delay: 0.15, ease: EASE }}
					className="liquid-glass rounded-2xl p-5"
				>
					<p className="text-xs text-white/50">
						Campaign — Dentists Vienna
					</p>
					<div className="mt-4 space-y-3">
						{STEPS.map(({ agent, detail, state }, i) => (
							<div key={agent} className="liquid-glass rounded-lg p-3">
								<div className="flex items-center gap-2.5">
									<span className="text-[10px] w-4 text-white/30">{i + 1}</span>
									<span
										className="w-2 h-2 rounded-full"
										style={{
											backgroundColor: STATE_STYLES[state].dot,
											boxShadow:
												state === "active"
													? "0 0 8px rgba(0,210,255,0.8)"
													: "none",
										}}
									/>
									<span className="text-sm font-medium text-white">{agent}</span>
									<span className={`ml-auto text-xs ${STATE_STYLES[state].text}`}>
										{detail}
									</span>
								</div>
							</div>
						))}
					</div>
				</motion.div>
			</div>
		</section>
	);
}
