export const RELEASES =
	'https://github.com/Etriti00/aura-app/releases/latest/download/'

export function detectPlatform(): string {
	const p = (
		typeof navigator !== 'undefined' ? navigator.platform || '' : ''
	).toLowerCase()
	if (p.includes('mac')) return 'mac'
	if (p.includes('linux')) return 'linux'
	return 'windows'
}

// Guided installers for desktop; tarballs for the headless server targets.
export const PACKAGE_FILES: Record<string, string> = {
	windows: 'AuraSetup.exe',
	mac: 'Aura-macOS-Installer.dmg',
	linux: 'Aura-Linux-Installer.run',
	pi: 'Aura-RaspberryPi-arm64.tar.gz',
	vps: 'Aura-Server-Linux-x64.tar.gz',
}

export const SERVER_INSTALL_CMD =
	'curl -fsSL https://raw.githubusercontent.com/Etriti00/aura-app/main/installers/server/install.sh | bash'

export function downloadHref(): string {
	return RELEASES + PACKAGE_FILES[detectPlatform()]
}

export const PLATFORM_LABEL: Record<string, string> = {
	windows: 'Windows',
	mac: 'macOS',
	linux: 'Linux',
}

export function detectedLabel(): string {
	return PLATFORM_LABEL[detectPlatform()] || 'your device'
}
