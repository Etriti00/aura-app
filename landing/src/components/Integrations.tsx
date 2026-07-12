import { Clock, Mail } from "lucide-react";
import { motion } from "motion/react";
import SectionEyebrow from "./SectionEyebrow";
import { INTEGRATIONS, type Logo } from "../lib/integrations";

const EASE: [number, number, number, number] = [0.22, 1, 0.36, 1];

export function LogoGlyph({ logo, size = 24 }: { logo: Logo; size?: number }) {
	const dim = logo.scale ? Math.round(size * logo.scale) : size;
	const common = { viewBox: logo.viewBox, width: dim, height: dim, "aria-hidden": true };
	if (logo.stroke) {
		return (
			<svg
				{...common}
				fill="none"
				stroke="currentColor"
				strokeWidth={2}
				strokeLinecap="round"
				strokeLinejoin="round"
			>
				{logo.paths.map((d) => (
					<path key={d} d={d} />
				))}
			</svg>
		);
	}
	return (
		<svg {...common} fill="currentColor">
			{logo.paths.map((d) => (
				<path key={d} d={d} fillRule="evenodd" clipRule="evenodd" />
			))}
		</svg>
	);
}

function Tile({ logo, index }: { logo: Logo; index: number }) {
	return (
		<motion.div
			initial={{ opacity: 0, y: 12 }}
			whileInView={{ opacity: 1, y: 0 }}
			viewport={{ once: true, margin: "-40px" }}
			transition={{ duration: 0.4, delay: index * 0.04, ease: EASE }}
			className="integ-tile flex items-center gap-2.5 rounded-full border bg-white/[0.03] px-4 py-2.5"
			style={{ ["--brand" as string]: logo.hover }}
		>
			<LogoGlyph logo={logo} size={20} />
			<span className="text-sm font-medium whitespace-nowrap">{logo.name}</span>
		</motion.div>
	);
}

export default function Integrations() {
	return (
		<section
			id="integrations"
			className="max-w-[1440px] mx-auto px-6 sm:px-8 lg:px-12 py-20 md:py-28 border-t border-white/10"
		>
			<div className="text-center flex flex-col items-center">
				<SectionEyebrow label="Integrations" tag="Your whole stack" />
				<h2 className="mt-5 text-3xl md:text-5xl font-semibold tracking-tight leading-[1.02] max-w-2xl">
					Plugs into the tools you already use.
				</h2>
				<p className="mt-6 text-white/60 text-base leading-[1.6] max-w-xl">
					Channels, inbox, CRM, research providers, and voice. Aura fits into
					the pipeline you already run.
				</p>
			</div>

			<div className="mt-12 flex flex-wrap justify-center gap-3">
				{INTEGRATIONS.map((logo, i) => (
					<Tile key={logo.name} logo={logo} index={i} />
				))}
			</div>

			<div className="mt-12 grid sm:grid-cols-2 gap-4 max-w-3xl mx-auto">
				<div className="liquid-glass rounded-2xl p-5 flex items-start gap-3">
					<div className="w-9 h-9 rounded-xl bg-[#00d2ff]/10 border border-[#00d2ff]/25 flex items-center justify-center shrink-0">
						<Mail className="w-4 h-4 text-[#7DBEFF]" />
					</div>
					<div>
						<h3 className="text-sm font-semibold">SMTP fallback</h3>
						<p className="mt-1 text-xs text-white/55 leading-[1.6]">
							Prefer Resend, or bring your own SMTP server. If a send fails,
							Aura falls back to SMTP so mail still goes out.
						</p>
					</div>
				</div>
				<div className="liquid-glass rounded-2xl p-5 flex items-start gap-3">
					<div className="w-9 h-9 rounded-xl bg-[#00d2ff]/10 border border-[#00d2ff]/25 flex items-center justify-center shrink-0">
						<Clock className="w-4 h-4 text-[#7DBEFF]" />
					</div>
					<div>
						<h3 className="text-sm font-semibold">Timezone aware scheduling</h3>
						<p className="mt-1 text-xs text-white/55 leading-[1.6]">
							Smart send windows per lead. Aura schedules each email for the
							recipient's business hours and enforces cool down between touches.
						</p>
					</div>
				</div>
			</div>
		</section>
	);
}
