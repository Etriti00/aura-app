import { motion } from "motion/react";
const PILLARS = [
	{
		name: "The Fleet",
		desc: "Twenty specialist agents that run your pipeline end to end.",
		features: [
			"Commander routes every task",
			"Scout, Qualifier, Closer, Postman execute",
			"Observer watches health around the clock",
			"Skills granted on request, fully audited",
			"Morning briefings on autopilot",
		],
		pro: false,
	},
	{
		name: "The Forge",
		desc: "A living skill library that designs itself as you work.",
		features: [
			"26 built in skills with schemas",
			"Forger designs new skills on demand",
			"Least privilege skill assignments",
			"Six writing personas for outreach",
			"Versioned, editable, exportable",
		],
		pro: false,
	},
	{
		name: "Any model",
		desc: "Bring subscriptions, API keys, or fully local models.",
		features: [
			"Claude, ChatGPT, Gemini subscriptions",
			"Grok, GLM, Kimi, Qwen, MiniMax APIs",
			"Ollama for fully local runs",
			"Per agent model overrides",
			"Two step verification before assignment",
		],
		pro: true,
	},
];

export default function Pricing() {
	return (
		<section id="features" className="c3-pricing-section">
			{/* Pricing noise filter (watermark) */}
			<svg className="absolute w-0 h-0" aria-hidden="true">
				<filter id="c3-noise">
					<feTurbulence
						type="fractalNoise"
						baseFrequency="0.5"
						numOctaves="2"
						stitchTiles="stitch"
					/>
					<feComponentTransfer>
						<feFuncA type="linear" slope="0.075" />
					</feComponentTransfer>
					<feComposite in2="SourceGraphic" operator="in" result="noise" />
					<feBlend in="SourceGraphic" in2="noise" mode="overlay" />
				</filter>
			</svg>

			<div className="c3-watermark-container">
				<motion.div
					className="c3-watermark-main"
					initial={{ opacity: 0, y: 24 }}
					whileInView={{ opacity: 1, y: 0 }}
					viewport={{ once: true, margin: "-80px" }}
					transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
				>
					<span className="c3-watermark-line-1">One app.</span>
					<span className="c3-watermark-line-2">Zero limits.</span>
				</motion.div>
			</div>

			<div className="c3-grid">
				{PILLARS.map(({ name, desc, features, pro }, i) => (
					<motion.div
						key={name}
						className={`c3-card${pro ? " c3-card-pro" : ""}`}
						initial={{ opacity: 0, y: 30 }}
						whileInView={{ opacity: 1, y: 0 }}
						viewport={{ once: true, margin: "-60px" }}
						transition={{ duration: 0.6, delay: i * 0.12, ease: [0.22, 1, 0.36, 1] }}
					>
						<p className="c3-tier-large">{name}</p>
						<p className="c3-desc">{desc}</p>
						<ul className="c3-list">
							{features.map((feature) => (
								<li key={feature}>
									<span className="c3-check">
										<svg
											width="12"
											height="12"
											viewBox="0 0 24 24"
											fill="none"
											stroke="#fff"
											strokeWidth="3"
											strokeLinecap="round"
											strokeLinejoin="round"
											aria-hidden="true"
										>
											<path d="M20 6 9 17l-5-5" />
										</svg>
									</span>
									{feature}
								</li>
							))}
						</ul>
					</motion.div>
				))}
			</div>
		</section>
	);
}
