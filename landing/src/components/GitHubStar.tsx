import { Star } from "lucide-react";
import { useEffect, useState } from "react";

const REPO = "Etriti00/aura-app";

function formatCount(n: number): string {
	if (n >= 1000) return (n / 1000).toFixed(1).replace(/\.0$/, "") + "k";
	return String(n);
}

export default function GitHubStar({ full = false }: { full?: boolean }) {
	const [count, setCount] = useState<number | null>(null);
	useEffect(() => {
		let alive = true;
		fetch(`https://api.github.com/repos/${REPO}`)
			.then((r) => (r.ok ? r.json() : null))
			.then((d) => {
				if (alive && d && typeof d.stargazers_count === "number" && d.stargazers_count > 0)
					setCount(d.stargazers_count);
			})
			.catch(() => {});
		return () => {
			alive = false;
		};
	}, []);

	return (
		<a
			href={`https://github.com/${REPO}`}
			target="_blank"
			rel="noopener"
			className={`group inline-flex items-center justify-center gap-2 rounded-full border border-white/15 bg-white/[0.04] px-4 py-2.5 text-sm font-medium text-white/90 transition-colors hover:bg-white/10 hover:border-white/25${full ? " w-full" : ""}`}
		>
			<Star className="w-4 h-4 text-[#FFD666] group-hover:fill-[#FFD666] transition-all" />
			<span>Star on GitHub</span>
			{count !== null && (
				<span className="ml-0.5 rounded-full bg-white/10 px-2 py-0.5 text-xs tabular-nums text-white/70">
					{formatCount(count)}
				</span>
			)}
		</a>
	);
}
