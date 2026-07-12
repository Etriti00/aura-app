import { Search } from "lucide-react";
import { motion } from "motion/react";
import { useEffect, useState } from "react";
import LogoMark from "./LogoMark";

const MENU_ITEMS = ["File", "Edit", "View", "Go", "Window", "Help"];

function menuItemVisibility(index: number): string {
	if (index > 3) return "hidden md:inline";
	if (index > 2) return "hidden sm:inline";
	return "";
}

function formatNow(): string {
	// The viewer's own locale and timezone, resolved by the browser.
	return new Date().toLocaleString(undefined, {
		weekday: "short",
		month: "short",
		day: "numeric",
		hour: "numeric",
		minute: "2-digit",
	});
}

export default function MenuBar() {
	const [now, setNow] = useState(formatNow());
	useEffect(() => {
		const id = setInterval(() => setNow(formatNow()), 1000);
		return () => clearInterval(id);
	}, []);

	return (
		<motion.div
			initial={{ opacity: 0 }}
			whileInView={{ opacity: 1 }}
			viewport={{ once: true, margin: "-60px" }}
			transition={{ duration: 0.6, ease: "easeOut" }}
			className="h-10 bg-black/40 backdrop-blur-md border-t border-b border-white/10"
		>
			<div className="max-w-[1440px] mx-auto px-6 sm:px-8 lg:px-12 h-full flex items-center justify-between text-xs">
				<div className="flex items-center gap-4 text-white/70">
					<LogoMark className="w-3.5 h-3.5 text-white" />
					<span className="font-bold text-white">Aura</span>
					{MENU_ITEMS.map((item, i) => (
						<span key={item} className={menuItemVisibility(i)}>
							{item}
						</span>
					))}
				</div>
				<div className="flex items-center gap-3 text-white/70">
					<Search className="w-3.5 h-3.5" />
					<span suppressHydrationWarning>{now}</span>
				</div>
			</div>
		</motion.div>
	);
}
