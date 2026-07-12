import type { LucideIcon } from "lucide-react";
import {
	Bot,
	Hammer,
	History,
	LayoutGrid,
	Mail,
	Search,
	Settings,
	Sparkles,
	TrendingUp,
} from "lucide-react";
import { motion } from "motion/react";
import { useState } from "react";
import LogoMark from "./LogoMark";

const EASE: [number, number, number, number] = [0.22, 1, 0.36, 1];

const TRAFFIC_LIGHTS = ["#ff5f57", "#febc2e", "#28c840"];

const NAV: { icon: LucideIcon; label: string }[] = [
	{ icon: LayoutGrid, label: "Dashboard" },
	{ icon: Search, label: "Hunter" },
	{ icon: Hammer, label: "Forge" },
	{ icon: Mail, label: "Outreach" },
	{ icon: Bot, label: "Fleet" },
	{ icon: History, label: "Kanban" },
	{ icon: TrendingUp, label: "Trends" },
	{ icon: Settings, label: "Settings" },
];

function Card({
	children,
	className = "",
}: {
	children: React.ReactNode;
	className?: string;
}) {
	return (
		<div className={`liquid-glass rounded-lg p-3.5 ${className}`}>{children}</div>
	);
}

function CardTitle({ children }: { children: React.ReactNode }) {
	return <p className="text-xs font-semibold text-white">{children}</p>;
}

function Pill({ children, on = false }: { children: React.ReactNode; on?: boolean }) {
	return (
		<span
			className={`text-[10px] px-2 py-0.5 rounded-full border ${
				on
					? "border-[#00d2ff]/40 text-[#00d2ff] bg-[#00d2ff]/10"
					: "border-white/10 text-white/50"
			}`}
		>
			{children}
		</span>
	);
}

function Dot({ color }: { color: string }) {
	return (
		<span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ backgroundColor: color }} />
	);
}

function DashboardView() {
	return (
		<div className="space-y-3">
			<div className="grid grid-cols-3 gap-3">
				{[
					{ value: "3", label: "CAMPAIGNS", color: "#00d2ff" },
					{ value: "128", label: "TOTAL LEADS", color: "#A4F4FD" },
					{ value: "47", label: "QUALIFIED", color: "#10b981" },
				].map(({ value, label, color }) => (
					<Card key={label}>
						<span className="block w-8 h-0.5 rounded-full" style={{ backgroundColor: color }} />
						<p className="mt-2 text-xl font-bold text-white tracking-tight">{value}</p>
						<p className="text-[10px] font-semibold tracking-widest text-white/40">{label}</p>
					</Card>
				))}
			</div>
			<Card>
				<CardTitle>Pipeline Funnel</CardTitle>
				<div className="mt-2.5 space-y-2">
					{[
						{ label: "Scraped", width: "92%", count: 128 },
						{ label: "Qualified", width: "38%", count: 47 },
						{ label: "Emailed", width: "29%", count: 36 },
						{ label: "Replied", width: "11%", count: 12 },
					].map(({ label, width, count }) => (
						<div key={label} className="flex items-center gap-3">
							<span className="w-16 text-[11px] text-white/50">{label}</span>
							<div className="flex-1 h-2 rounded-full bg-white/[0.06] overflow-hidden">
								<div className="h-full rounded-full bg-[#00d2ff]" style={{ width }} />
							</div>
							<span className="w-8 text-right text-[11px] text-white/40">{count}</span>
						</div>
					))}
				</div>
			</Card>
			<Card>
				<CardTitle>Agent Fleet</CardTitle>
				<div className="mt-2.5 grid grid-cols-2 gap-2">
					{[
						{ name: "Commander", task: "routing work", live: true },
						{ name: "Scout", task: "scraping leads", live: true },
						{ name: "Closer", task: "drafting emails", live: true },
						{ name: "Postman", task: "idle", live: false },
					].map(({ name, task, live }) => (
						<div key={name} className="flex items-center gap-2.5 rounded-md border border-white/10 bg-white/[0.03] px-3 py-2">
							<Dot color={live ? "#28c840" : "#525252"} />
							<div className="min-w-0">
								<p className="text-xs font-medium text-white">{name}</p>
								<p className="text-[10px] text-white/40 truncate">{task}</p>
							</div>
						</div>
					))}
				</div>
			</Card>
		</div>
	);
}

function HunterView() {
	return (
		<div className="space-y-3">
			<Card>
				<CardTitle>New Hunt</CardTitle>
				<div className="mt-2.5 grid grid-cols-2 gap-2">
					<div className="rounded-md border border-white/10 bg-white/[0.03] px-3 py-2 text-xs text-white/70">
						dentists
					</div>
					<div className="rounded-md border border-white/10 bg-white/[0.03] px-3 py-2 text-xs text-white/70">
						Vienna
					</div>
				</div>
				<div className="mt-2.5 flex items-center gap-2">
					<span className="inline-flex items-center gap-1.5 rounded-full bg-white text-black text-[11px] font-semibold px-3.5 py-1.5">
						<Search className="w-3 h-3" />
						Start Hunting
					</span>
					<Pill>DuckDuckGo</Pill>
					<Pill>Google Maps</Pill>
					<Pill>Yelp</Pill>
				</div>
			</Card>
			<Card>
				<CardTitle>Fresh leads</CardTitle>
				<div className="mt-2.5 space-y-1.5">
					{[
						{ name: "Chen Dental", site: "chendental.at", score: 82 },
						{ name: "Smile Studio Wien", site: "smilestudio.wien", score: 74 },
						{ name: "Dr. Berger Praxis", site: "praxis-berger.at", score: 63 },
						{ name: "City Zahn", site: "cityzahn.at", score: 58 },
					].map(({ name, site, score }) => (
						<div key={name} className="flex items-center gap-3 rounded-md border border-white/10 bg-white/[0.03] px-3 py-2">
							<span className="flex-1 text-xs font-medium text-white truncate">{name}</span>
							<span className="text-[10px] text-white/40 truncate">{site}</span>
							<Pill on={score >= 70}>{score}</Pill>
						</div>
					))}
				</div>
			</Card>
		</div>
	);
}

function ForgeView() {
	return (
		<div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
			<Card>
				<CardTitle>Skill library</CardTitle>
				<div className="mt-2.5 space-y-1.5">
					{["The Closer", "Deep Qualifier", "Trend Analyst", "Invoice Architect", "Inbox Triage", "RAG Style Matcher"].map(
						(s, i) => (
							<div
								key={s}
								className={`rounded-md px-3 py-1.5 text-xs ${
									i === 0 ? "bg-white/10 text-white" : "text-white/60 border border-white/5"
								}`}
							>
								{s}
							</div>
						),
					)}
				</div>
			</Card>
			<Card>
				<CardTitle>The Closer</CardTitle>
				<p className="mt-2 text-[11px] text-white/50 leading-relaxed">
					High conversion cold email writer using ROI language and specific
					business observations.
				</p>
				<div className="mt-2.5 flex flex-wrap gap-1.5">
					<Pill on>outreach</Pill>
					<Pill>confident</Pill>
					<Pill>temp 0.7</Pill>
				</div>
				<div className="mt-3 flex items-center gap-1.5 text-[11px] font-semibold" style={{ color: "#A4F4FD" }}>
					<Sparkles className="w-3.5 h-3.5" />
					Forged on demand when a task needs it
				</div>
			</Card>
		</div>
	);
}

function OutreachView() {
	return (
		<div className="grid grid-cols-1 sm:grid-cols-5 gap-3">
			<Card className="sm:col-span-2">
				<CardTitle>Qualified</CardTitle>
				<div className="mt-2.5 space-y-1.5">
					{["Chen Dental", "Smile Studio", "Dr. Berger"].map((n, i) => (
						<div
							key={n}
							className={`rounded-md px-3 py-2 text-xs ${
								i === 0 ? "bg-white/10 text-white" : "text-white/60 border border-white/5"
							}`}
						>
							{n}
						</div>
					))}
				</div>
			</Card>
			<Card className="sm:col-span-3">
				<CardTitle>Draft — Chen Dental</CardTitle>
				<p className="mt-2 text-[11px] text-white/70">
					Subject: Quick question about Chen Dental
				</p>
				<p className="mt-1.5 text-[11px] text-white/50 leading-relaxed">
					Hi Dr. Chen, I noticed patients can only book by phone while your
					competitors fill their calendars online overnight...
				</p>
				<div className="mt-2.5 flex gap-1.5">
					<span className="rounded-full bg-white text-black text-[11px] font-semibold px-3 py-1">Send</span>
					<span className="rounded-full border border-white/15 text-white/70 text-[11px] px-3 py-1">Regenerate</span>
				</div>
			</Card>
		</div>
	);
}

function FleetView() {
	return (
		<div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
			{[
				{ name: "Commander", role: "Orchestrator", live: true },
				{ name: "Scout", role: "Worker", live: true },
				{ name: "Qualifier", role: "Worker", live: true },
				{ name: "Closer", role: "Worker", live: true },
				{ name: "Postman", role: "Worker", live: false },
				{ name: "Observer", role: "Observer", live: true },
			].map(({ name, role, live }) => (
				<Card key={name}>
					<div className="flex items-center gap-2">
						<Dot color={live ? "#28c840" : "#525252"} />
						<p className="text-xs font-semibold text-white">{name}</p>
					</div>
					<p className="mt-1 text-[10px] text-white/40">{role}</p>
					<p className="mt-1.5 text-[10px] text-white/50">
						{live ? "heartbeat 30s ago" : "idle"}
					</p>
				</Card>
			))}
		</div>
	);
}

function KanbanView() {
	return (
		<div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
			{[
				{ col: "Backlog", items: ["Warm up new domain", "Expand to Graz"] },
				{ col: "In progress", items: ["Dentists Vienna wave 2"] },
				{ col: "Review", items: ["Reply: Chen Dental"] },
				{ col: "Done", items: ["Setup SPF and DKIM", "First 100 leads"] },
			].map(({ col, items }) => (
				<Card key={col}>
					<p className="text-[11px] font-semibold text-white/70">{col}</p>
					<div className="mt-2 space-y-1.5">
						{items.map((it) => (
							<div key={it} className="rounded-md border border-white/10 bg-white/[0.03] px-2.5 py-2 text-[10px] text-white/60 leading-snug">
								{it}
							</div>
						))}
					</div>
				</Card>
			))}
		</div>
	);
}

function TrendsView() {
	return (
		<div className="space-y-3">
			<Card>
				<div className="flex items-center justify-between">
					<CardTitle>solar installers</CardTitle>
					<Pill on>breakout +180%</Pill>
				</div>
				<div className="mt-3 flex items-end gap-1 h-16">
					{[18, 22, 20, 26, 31, 29, 38, 44, 41, 52, 66, 84].map((h, i) => (
						<div
							key={i}
							className="flex-1 rounded-sm bg-[#00d2ff]"
							style={{ height: `${h}%`, opacity: 0.35 + (i / 12) * 0.65 }}
						/>
					))}
				</div>
			</Card>
			<Card>
				<CardTitle>Suggested campaign</CardTitle>
				<p className="mt-2 text-[11px] text-white/50 leading-relaxed">
					Search interest for solar installers is rising fast in your region.
					Aura suggests a 50 lead pilot with the Consultant persona.
				</p>
			</Card>
		</div>
	);
}

function SettingsView() {
	return (
		<div className="space-y-3">
			<Card>
				<CardTitle>Model routing</CardTitle>
				<div className="mt-2.5 grid grid-cols-3 gap-2">
					{[
						{ tier: "Qualification", model: "claude-haiku" },
						{ tier: "Email gen", model: "claude-sonnet" },
						{ tier: "Chat", model: "subscription" },
					].map(({ tier, model }) => (
						<div key={tier} className="rounded-md border border-white/10 bg-white/[0.03] px-3 py-2">
							<p className="text-[10px] text-white/40">{tier}</p>
							<p className="text-[11px] text-white/80 truncate">{model}</p>
						</div>
					))}
				</div>
			</Card>
			<Card>
				<CardTitle>API keys</CardTitle>
				<div className="mt-2.5 space-y-1.5">
					{["Anthropic", "OpenAI", "xAI"].map((k) => (
						<div key={k} className="flex items-center gap-3 rounded-md border border-white/10 bg-white/[0.03] px-3 py-2">
							<span className="w-20 text-[11px] text-white/60">{k}</span>
							<span className="flex-1 text-[11px] text-white/30 tracking-widest">sk-****************</span>
							<Pill on>encrypted</Pill>
						</div>
					))}
				</div>
			</Card>
		</div>
	);
}

const VIEWS: Record<string, () => JSX.Element> = {
	Dashboard: DashboardView,
	Hunter: HunterView,
	Forge: ForgeView,
	Outreach: OutreachView,
	Fleet: FleetView,
	Kanban: KanbanView,
	Trends: TrendsView,
	Settings: SettingsView,
};

const SUBTITLES: Record<string, string> = {
	Dashboard: "Your campaign performance at a glance",
	Hunter: "Find and scrape business leads",
	Forge: "Create and manage AI skills",
	Outreach: "Personalized emails that land",
	Fleet: "Multi agent command center",
	Kanban: "Track and manage agent tickets",
	Trends: "Google Trends intelligence",
	Settings: "Keys, models, and delivery",
};

export default function InboxMockup() {
	const [active, setActive] = useState("Dashboard");
	const View = VIEWS[active];
	return (
		<section className="max-w-[1600px] mx-auto px-6 sm:px-8 lg:px-12 py-16 md:py-24">
			<motion.div
				initial={{ opacity: 0, y: 40 }}
				whileInView={{ opacity: 1, y: 0 }}
				viewport={{ once: true, margin: "-100px" }}
				transition={{ duration: 0.8, ease: EASE }}
				className="relative rounded-2xl overflow-hidden border border-white/10 bg-[#0e1014]/90 backdrop-blur-2xl"
			>
				<div className="relative flex items-center h-10 px-4 border-b border-white/10">
					<div className="flex items-center gap-2">
						{TRAFFIC_LIGHTS.map((color) => (
							<span key={color} className="w-3 h-3 rounded-full" style={{ backgroundColor: color }} />
						))}
					</div>
					<span className="absolute left-1/2 -translate-x-1/2 text-xs text-white/50">
						Aura — {active}
					</span>
				</div>

				<div className="md:hidden flex gap-1.5 overflow-x-auto px-3 py-2 border-b border-white/10 [&::-webkit-scrollbar]:hidden">
						{NAV.map(({ icon: Icon, label }) => (
							<button
								key={label}
								type="button"
								onClick={() => setActive(label)}
								className={`shrink-0 inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-[11px] font-medium whitespace-nowrap transition-colors ${
									active === label ? "bg-white/[0.12] text-white" : "text-white/50 bg-white/[0.03]"
								}`}
							>
								<Icon className="w-3 h-3" />
								{label}
							</button>
						))}
					</div>

					<div className="grid grid-cols-12 md:h-[520px]">
					<aside className="hidden md:block md:col-span-3 border-r border-white/[0.07] bg-black/20 p-4">
						<div className="flex items-center gap-2 px-2.5 pb-3">
							<LogoMark className="w-4 h-4 text-white" />
							<span className="text-sm font-bold text-white tracking-tight">Aura</span>
						</div>
						<p className="px-2.5 pb-2 text-[10px] font-semibold uppercase tracking-widest text-white/30">
							Navigation
						</p>
						<nav className="space-y-0.5">
							{NAV.map(({ icon: Icon, label }) => (
								<button
									key={label}
									type="button"
									onClick={() => setActive(label)}
									className={`w-full flex items-center gap-2.5 rounded-md px-2.5 py-1.5 text-xs font-medium transition-colors ${
										active === label
											? "bg-white/10 text-white"
											: "text-white/60 hover:bg-white/5"
									}`}
								>
									<Icon className="w-3.5 h-3.5" />
									<span className="flex-1 text-left">{label}</span>
								</button>
							))}
						</nav>
						
					</aside>

					<div className="col-span-12 md:col-span-9 flex flex-col overflow-hidden">
						<div className="flex items-center justify-between px-4 md:px-5 h-14 border-b border-white/[0.07] shrink-0">
							<div>
								<h3 className="text-sm font-semibold text-white">{active}</h3>
								<p className="text-[11px] text-white/40">{SUBTITLES[active]}</p>
							</div>
							<span className="hidden sm:inline-flex items-center gap-1.5 text-[10px] px-2.5 py-1 rounded-full border border-white/[0.07] text-white/40"><span className="w-1.5 h-1.5 rounded-full bg-[#28c840]" />
								20 agents live
							</span>
						</div>
						<div className="flex-1 p-4 md:p-5 overflow-hidden">
							<View />
						</div>
					</div>
				</div>
			</motion.div>
		</section>
	);
}
