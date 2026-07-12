import { Download } from 'lucide-react'
import { detectedLabel, downloadHref } from '../lib/downloads'

// Kept as AppleButton for import compatibility, but it is now a neutral,
// OS-aware download button: no Apple mark, and it downloads the build that
// matches the visitor's operating system.
export default function AppleButton({
	label,
	full = false,
}: {
	label?: string
	full?: boolean
}) {
	return (
		<a
			href={downloadHref()}
			className={`group inline-flex items-center justify-center gap-2 rounded-full bg-white text-black font-medium text-sm px-5 py-3 transition-all hover:bg-white/90 active:scale-[0.98]${full ? ' w-full' : ''}`}
		>
			<Download className="w-4 h-4" />
			<span>{label ?? `Download for ${detectedLabel()}`}</span>
		</a>
	)
}
