import { motion, useReducedMotion, useScroll, useTransform } from "motion/react";
import type { CSSProperties } from "react";
import DownloadRow from "./DownloadRow";

const EASE: [number, number, number, number] = [0.22, 1, 0.36, 1];

const gradientStyle: CSSProperties = {
	backgroundImage:
		"linear-gradient(to right, #0B2551 0%, #4FC3F7 12%, #A4F4FD 28%, #ffffff 42%, #00d2ff 58%, #A4F4FD 74%, #4FC3F7 88%, #0B2551 100%)",
	backgroundSize: "200% auto",
	WebkitBackgroundClip: "text",
	backgroundClip: "text",
	color: "transparent",
	WebkitTextFillColor: "transparent",
	filter: "url(#c3-noise)",
};

export default function Hero() {
	const reduce = useReducedMotion();
	const { scrollY } = useScroll();
	// The hero drifts up and fades as you scroll into the page.
	const y = useTransform(scrollY, [0, 500], [0, reduce ? 0 : 70]);
	const opacity = useTransform(scrollY, [0, 460], [1, reduce ? 1 : 0]);

	return (
		<section className="pt-16 md:pt-28 pb-20 text-center flex flex-col items-center px-6">
			<motion.div style={{ y, opacity }} className="flex flex-col items-center w-full">
				<motion.h1
					initial={{ opacity: 0, y: 20 }}
					animate={{ opacity: 1, y: 0 }}
					transition={{ duration: 0.8, delay: 0.3, ease: EASE }}
					className="text-5xl sm:text-6xl md:text-7xl lg:text-8xl font-semibold tracking-tight leading-[0.9]"
				>
					<span className="block">Your pipeline.</span>
					<span className="block animate-shiny" style={gradientStyle}>
						Revitalized
					</span>
				</motion.h1>

				<motion.p
					initial={{ opacity: 0, y: 20 }}
					animate={{ opacity: 1, y: 0 }}
					transition={{ duration: 0.8, delay: 0.5, ease: EASE }}
					className="mt-8 text-white/60 max-w-lg text-base md:text-lg leading-[1.55]"
				>
					Aura is the premier outbound platform for the current era. It leverages
					a fleet of AI agents to find leads, qualify them, and write outreach
					that lands.
				</motion.p>

				<motion.div
					initial={{ opacity: 0, y: 20 }}
					animate={{ opacity: 1, y: 0 }}
					transition={{ duration: 0.8, delay: 0.7, ease: EASE }}
					className="mt-10 flex flex-col items-center gap-3"
				>
					<DownloadRow />
					<span className="text-xs text-white/40">
						Free and open source. One build for every machine you own.
					</span>
				</motion.div>
			</motion.div>
		</section>
	);
}
