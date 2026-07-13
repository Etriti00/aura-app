import { Cpu, Download, Monitor, Server } from 'lucide-react'
import AppleLogo from './AppleLogo'
import WindowsLogo from './WindowsLogo'
import {
	detectedLabel,
	detectPlatform,
	MAC_BUILDS,
	PACKAGE_FILES,
	RELEASES,
} from '../lib/downloads'

type Pkg = {
	key: string
	label: string
	Icon: (props: { className?: string }) => JSX.Element
}

const PACKAGES: Pkg[] = [
	{ key: 'windows', label: 'Windows', Icon: WindowsLogo },
	{ key: 'mac-arm', label: 'macOS (Apple Silicon)', Icon: AppleLogo },
	{ key: 'mac-intel', label: 'macOS (Intel)', Icon: AppleLogo },
	{
		key: 'linux',
		label: 'Linux',
		Icon: ({ className = 'w-4 h-4' }) => <Monitor className={className} />,
	},
	{
		key: 'pi',
		label: 'Raspberry Pi',
		Icon: ({ className = 'w-4 h-4' }) => <Cpu className={className} />,
	},
	{
		key: 'vps',
		label: 'VPS Server',
		Icon: ({ className = 'w-4 h-4' }) => <Server className={className} />,
	},
]

const PRIMARY =
	'group inline-flex items-center justify-center gap-2 rounded-full bg-white text-black font-semibold text-sm px-6 py-3.5 transition-all hover:bg-white/90 active:scale-[0.98]'

export default function DownloadRow() {
	const primary = detectPlatform()
	const onMac = primary === 'mac'
	const others = PACKAGES.filter((p) =>
		onMac ? !p.key.startsWith('mac') : p.key !== primary,
	)
	return (
		<div className="flex flex-col items-center gap-4">
			{onMac ? (
				// Two native builds, and the browser cannot tell the chips apart, so
				// the visitor picks instead of being handed one that will not launch.
				<div className="flex flex-col items-center gap-2.5">
					<div className="flex flex-wrap items-center justify-center gap-2">
						{MAC_BUILDS.map((b) => (
							<a
								key={b.key}
								href={RELEASES + PACKAGE_FILES[b.key]}
								className={PRIMARY}
							>
								<Download className="w-4 h-4" />
								<span>{b.label}</span>
								<span className="font-normal text-black/45">{b.hint}</span>
							</a>
						))}
					</div>
					<p className="text-xs text-white/40">
						Download for macOS — not sure which? Apple menu → About This Mac.
					</p>
				</div>
			) : (
				/* One prominent, OS-aware download button. No platform mark. */
				<a href={RELEASES + PACKAGE_FILES[primary]} className={PRIMARY}>
					<Download className="w-4 h-4" />
					<span>Download for {detectedLabel()}</span>
				</a>
			)}
			{/* Every other platform, quietly available. */}
			<div className="flex flex-wrap items-center justify-center gap-2">
				{others.map((p) => (
					<a
						key={p.key}
						href={RELEASES + PACKAGE_FILES[p.key]}
						className="inline-flex items-center justify-center gap-1.5 rounded-full border border-white/12 bg-white/[0.03] text-white/70 text-xs font-medium px-3.5 py-2 hover:bg-white/10 hover:text-white transition-colors"
					>
						<p.Icon className="w-3.5 h-3.5" />
						<span>{p.label}</span>
					</a>
				))}
			</div>
		</div>
	)
}
