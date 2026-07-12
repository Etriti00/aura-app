export default function WindowsLogo({
	className = 'w-4 h-4',
}: {
	className?: string
}) {
	return (
		<svg viewBox="0 0 24 24" fill="currentColor" className={className} aria-hidden="true">
			<path d="M3 5.5L10.5 4.4V11.5H3V5.5ZM3 18.5L10.5 19.6V12.5H3V18.5ZM11.5 19.8L21 21V12.5H11.5V19.8ZM11.5 4.2V11.5H21V3L11.5 4.2Z" />
		</svg>
	)
}
