import { ChevronRight } from "lucide-react";
import { motion } from "motion/react";
import DownloadRow from "./DownloadRow";
import { SERVER_INSTALL_CMD } from "../lib/downloads";

const EASE: [number, number, number, number] = [0.22, 1, 0.36, 1];

export default function FinalCTA() {
	return (
		<section id="downloads" className="max-w-[1440px] mx-auto px-6 sm:px-8 lg:px-12 py-20 md:py-32">
			<motion.div
				initial={{ opacity: 0, y: 30 }}
				whileInView={{ opacity: 1, y: 0 }}
				viewport={{ once: true, margin: "-80px" }}
				transition={{ duration: 0.8, ease: EASE }}
				className="liquid-glass relative overflow-hidden rounded-3xl px-8 py-16 md:py-24 text-center"
			>
				<div
					className="absolute inset-0 opacity-30 pointer-events-none"
					style={{
						background:
							"radial-gradient(600px circle at 50% 0%, rgba(255,255,255,0.15), transparent 70%)",
					}}
				/>
				<div className="relative">
					<h2 className="text-4xl md:text-6xl font-semibold tracking-tight leading-[1.02]">
						Close the tabs.
						<br />
						Open your day.
					</h2>
					<p className="mt-6 text-white/60 max-w-md mx-auto text-sm leading-[1.6]">
						Join the builders, founders, and operators who treat outbound
						like a system, not an obligation.
					</p>
					<div className="mt-10">
						<DownloadRow />
					</div>
					<div className="mt-6 flex flex-col items-center gap-2">
						<p className="text-[11px] text-white/40">
							Raspberry Pi or a VPS? One line, no wizard:
						</p>
						<code className="max-w-full overflow-x-auto rounded-lg border border-white/10 bg-black/40 px-3 py-2 text-[11px] text-[#9BD1FF] font-mono">
							{SERVER_INSTALL_CMD}
						</code>
					</div>
					<div className="mt-6 flex justify-center">
						<a
							href="https://github.com/Etriti00/aura-app"
							target="_blank"
							rel="noopener"
							className="group inline-flex items-center justify-center gap-2 rounded-full border border-white/15 text-white text-sm font-medium px-5 py-3 hover:bg-white/5 transition-colors"
						>
							View on GitHub
							<ChevronRight className="w-4 h-4 transition-transform group-hover:translate-x-[1px]" />
						</a>
					</div>
				</div>
			</motion.div>
		</section>
	);
}
