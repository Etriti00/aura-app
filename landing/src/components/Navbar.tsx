import { Menu, X } from "lucide-react";
import { motion, AnimatePresence } from "motion/react";
import { useState } from "react";
import GitHubStar from "./GitHubStar";
import LogoMark from "./LogoMark";

const LINKS: { label: string; href: string; external?: boolean }[] = [
	{ label: "Features", href: "#features" },
	{ label: "The Fleet", href: "#fleet" },
	{ label: "Downloads", href: "#downloads" },
	{ label: "Documentation", href: "#docs" },
	{ label: "GitHub", href: "https://github.com/Etriti00/aura-app", external: true },
];

export default function Navbar() {
	const [open, setOpen] = useState(false);
	return (
		<motion.nav
			initial={{ opacity: 0, y: -10 }}
			animate={{ opacity: 1, y: 0 }}
			transition={{ duration: 0.6, ease: "easeOut" }}
			className="relative z-30"
		>
			<div className="relative max-w-[1440px] mx-auto px-6 sm:px-8 lg:px-12 h-20 flex items-center justify-between">
				<a href="#" aria-label="Aura home" onClick={() => setOpen(false)}>
					<LogoMark />
				</a>

				<div className="hidden md:flex gap-8 absolute left-1/2 -translate-x-1/2">
					{LINKS.map((link, i) => (
						<motion.a
							key={link.label}
							href={link.href}
							target={link.external ? "_blank" : undefined}
							rel={link.external ? "noopener" : undefined}
							initial={{ opacity: 0, y: -8 }}
							animate={{ opacity: 1, y: 0 }}
							transition={{ duration: 0.5, delay: 0.1 + i * 0.05, ease: "easeOut" }}
							className="text-white/70 text-sm font-medium hover:text-white transition-colors"
						>
							{link.label}
						</motion.a>
					))}
				</div>

				<div className="hidden md:block">
					<GitHubStar />
				</div>

				<button
					type="button"
					aria-label={open ? "Close menu" : "Open menu"}
					onClick={() => setOpen((v) => !v)}
					className="md:hidden w-10 h-10 rounded-full border border-white/10 bg-white/5 inline-flex items-center justify-center"
				>
					{open ? <X className="w-4 h-4 text-white" /> : <Menu className="w-4 h-4 text-white" />}
				</button>
			</div>

			<AnimatePresence>
				{open && (
					<motion.div
						initial={{ opacity: 0, y: -8 }}
						animate={{ opacity: 1, y: 0 }}
						exit={{ opacity: 0, y: -8 }}
						transition={{ duration: 0.2, ease: "easeOut" }}
						className="md:hidden absolute inset-x-4 top-[76px] rounded-2xl border border-white/10 bg-[#0e0e10]/95 backdrop-blur-xl p-4 shadow-2xl"
					>
						<div className="flex flex-col">
							{LINKS.map((link) => (
								<a
									key={link.label}
									href={link.href}
									target={link.external ? "_blank" : undefined}
									rel={link.external ? "noopener" : undefined}
									onClick={() => setOpen(false)}
									className="py-3 px-2 text-[15px] font-medium text-white/80 hover:text-white border-b border-white/5 last:border-0"
								>
									{link.label}
								</a>
							))}
							<div className="pt-3">
								<GitHubStar full />
							</div>
						</div>
					</motion.div>
				)}
			</AnimatePresence>
		</motion.nav>
	);
}
