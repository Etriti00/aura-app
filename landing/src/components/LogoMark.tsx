export default function LogoMark({
	className = "w-8 h-8",
}: {
	className?: string;
}) {
	return (
		<svg viewBox="0 0 256 256" className={className} aria-label="Aura">
			<g fill="none" stroke="currentColor" strokeLinecap="round">
				<path
					d="M 68 216 L 128 44 L 188 216"
					strokeWidth="26"
					strokeLinejoin="round"
				/>
				<ellipse
					cx="128"
					cy="150"
					rx="94"
					ry="30"
					strokeWidth="13"
					transform="rotate(-18 128 150)"
				/>
			</g>
			<circle cx="217.4" cy="121" r="14" fill="#00d2ff" />
		</svg>
	);
}
