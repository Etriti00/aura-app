export const RELEASES =
	'https://github.com/Etriti00/aura-app/releases/latest/download/'

export const RELEASES_PAGE =
	'https://github.com/Etriti00/aura-app/releases/latest'

export function detectPlatform(): string {
	const p = (
		typeof navigator !== 'undefined' ? navigator.platform || '' : ''
	).toLowerCase()
	if (p.includes('mac')) return 'mac'
	if (p.includes('linux')) return 'linux'
	return 'windows'
}

// Guided installers for desktop; tarballs for the headless server targets.
// macOS ships one native build per chip — there is no universal binary — and
// browsers report "MacIntel" on Apple Silicon too, so a Mac visitor is asked to
// pick rather than handed a build that may not launch.
export const PACKAGE_FILES: Record<string, string> = {
	windows: 'AuraSetup.exe',
	'mac-arm': 'Aura-macOS-AppleSilicon.dmg',
	'mac-intel': 'Aura-macOS-Intel.dmg',
	linux: 'Aura-Linux-Installer.run',
	pi: 'Aura-RaspberryPi-arm64.tar.gz',
	vps: 'Aura-Server-Linux-x64.tar.gz',
}

export const MAC_BUILDS: { key: string; label: string; hint: string }[] = [
	{ key: 'mac-arm', label: 'Apple Silicon', hint: 'M1 and newer' },
	{ key: 'mac-intel', label: 'Intel', hint: '2020 and earlier' },
]

export const SERVER_INSTALL_CMD =
	'curl -fsSL https://raw.githubusercontent.com/Etriti00/aura-app/main/installers/server/install.sh | bash'

// A Mac has no single file to point at, so send those visitors to the releases
// page where both builds are listed.
export function downloadHref(): string {
	const platform = detectPlatform()
	if (platform === 'mac') return RELEASES_PAGE
	return RELEASES + PACKAGE_FILES[platform]
}

export const PLATFORM_LABEL: Record<string, string> = {
	windows: 'Windows',
	mac: 'macOS',
	linux: 'Linux',
}

export function detectedLabel(): string {
	return PLATFORM_LABEL[detectPlatform()] || 'your device'
}
