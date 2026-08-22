import { lazy, Suspense, useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import {
  ArrowRight, ArrowsIn, ArrowsOut, Books, CaretDown, CaretLeft, CaretRight, Check, CheckCircle,
  ClockCounterClockwise, DownloadSimple, FileArrowUp, FilePdf, Files, Gear,
  House, Info, List, LockKey, MagicWand, MagnifyingGlass, PaperPlaneTilt, Receipt, ShieldCheck,
  SignIn, Sparkle, Table, UserCircle, Warning, X,
} from "@phosphor-icons/react";
import { ReviewDesk, downloadReviewedReport } from "./ReviewDesk";
import { createMagicFinAuthHandoff } from "./auth";
import { adaptProductContract, buildDeterministicDemoPdf, getAssistantAdapter, getAssistantChartSpecs, getProviderConnectionAdapter, getReviewedReportBundle, metricDefinitionRegistry, productFixture, requestReviewedPdf } from "./product-contract";
import { analyzeSourceSession, createSourceSession, uploadSource } from "./session-api";
import { buildAssistantEvidence, buildAssistantRequest, getModelProviderStatus, requestAssistant, testModelProvider, toIdentifier } from "./provider-api";

const TrendChart = lazy(() => import("./TrendChart"));

export { reviewFixture } from "./mock-contract";
export { productFixture } from "./product-contract";

const primaryNav = [
  { route: "/", label: "Home", icon: House },
  { route: "/files", label: "Files & Sources", icon: Books },
  { route: "/history", label: "History", icon: ClockCounterClockwise },
  { route: "/review", label: "Review Desk", icon: ShieldCheck },
  { route: "/reports", label: "Reports", icon: Receipt },
];

const utilityNav = [
  { route: "/profile", label: "Profile", icon: UserCircle },
  { route: "/settings", label: "Settings", icon: Gear },
  { route: "/sign-in", label: "Sign in", icon: SignIn },
];

function routeTitle(route) {
  if (route === "/company") return "Home";
  if (route === "/auth/callback") return "Completing sign in";
  return [...primaryNav, ...utilityNav].find((item) => item.route === route)?.label || (route === "/privacy" ? "Privacy & data" : route === "/legal" ? "Legal" : "Not found");
}

function canonicalRoute(value) {
  const [rawPath, rawHash] = String(value || "/").split("#");
  const path = rawPath === "/sources" ? "/files" : rawPath || "/";
  const hash = rawPath === "/sources" ? rawHash || "sources" : rawHash || "";
  return { path, hash, href: `${path}${hash ? `#${hash}` : ""}` };
}

function useRoute(initialRoute) {
  const [route, setRoute] = useState(() => canonicalRoute(initialRoute || `${window.location.pathname}${window.location.hash}`).path);
  useEffect(() => {
    const onPopState = () => {
      const resolved = canonicalRoute(`${window.location.pathname}${window.location.hash}`);
      if (resolved.href !== `${window.location.pathname}${window.location.hash}`) window.history.replaceState({}, "", resolved.href);
      setRoute(resolved.path);
      window.setTimeout(() => {
        const hash = resolved.hash;
        const main = document.getElementById("main-content");
        const target = document.getElementById(hash || "main-content");
        if (hash) {
          target?.focus({ preventScroll: false });
          target?.scrollIntoView({ block: "start" });
        } else {
          window.scrollTo({ top: 0, left: 0, behavior: "auto" });
          document.documentElement.scrollTop = 0;
          document.body.scrollTop = 0;
          if (main) main.scrollTop = 0;
          target?.focus({ preventScroll: true });
        }
      }, 0);
    };
    window.addEventListener("popstate", onPopState);
    if (!initialRoute) onPopState();
    return () => window.removeEventListener("popstate", onPopState);
  }, [initialRoute]);
  const navigate = (nextRoute) => {
    const { path, hash, href } = canonicalRoute(nextRoute);
    if (`${window.location.pathname}${window.location.hash}` !== href) window.history.pushState({}, "", href);
    setRoute(path);
    window.setTimeout(() => {
      const main = document.getElementById("main-content");
      const target = document.getElementById(hash || "main-content");
      if (hash) {
        target?.focus({ preventScroll: false });
        target?.scrollIntoView({ block: "start" });
      } else {
        window.scrollTo({ top: 0, left: 0, behavior: "auto" });
        document.documentElement.scrollTop = 0;
        document.body.scrollTop = 0;
        if (main) main.scrollTop = 0;
        target?.focus({ preventScroll: true });
      }
    }, 0);
  };
  return [route, navigate];
}

function useDismissible(open, onClose, returnRef, panelRef) {
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;
  useEffect(() => {
    if (!open) return undefined;
    const prior = document.activeElement;
    window.setTimeout(() => {
      const first = panelRef.current?.querySelector('button:not([disabled]), a[href], input:not([disabled]), [tabindex="0"]');
      (first || panelRef.current)?.focus();
    }, 0);
    const onKeyDown = (event) => {
      if (event.key === "Escape") { event.preventDefault(); onCloseRef.current(); }
      if (event.key !== "Tab" || !panelRef.current) return;
      const focusable = [...panelRef.current.querySelectorAll('button:not([disabled]), a[href], input:not([disabled]), [tabindex="0"]')];
      if (!focusable.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && (document.activeElement === first || document.activeElement === panelRef.current)) { event.preventDefault(); last.focus(); }
      if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
      window.setTimeout(() => (returnRef?.current || prior)?.focus?.(), 0);
    };
  }, [open, panelRef, returnRef]);
}

function StatusTag({ tone = "neutral", children }) {
  const Icon = tone === "success" ? CheckCircle : tone === "warning" ? Warning : Info;
  return <span className={`status-tag ${tone}`}><Icon size={14} weight={tone === "success" ? "fill" : "regular"} aria-hidden="true" />{children}</span>;
}

function MetricDefinitionButton({ metricId, source }) {
  const [open, setOpen] = useState(false);
  const triggerRef = useRef(null);
  const panelRef = useRef(null);
  const titleId = `metric-definition-${metricId}`;
  const dialogId = `${titleId}-dialog`;
  const definition = metricDefinitionRegistry[metricId];
  useDismissible(open, () => setOpen(false), triggerRef, panelRef);
  useEffect(() => {
    if (!open) return undefined;
    const previousOverflow = document.body.style.overflow;
    const previousPaddingRight = document.body.style.paddingRight;
    const scrollbarWidth = Math.max(0, window.innerWidth - document.documentElement.clientWidth);
    document.body.style.overflow = "hidden";
    if (scrollbarWidth) document.body.style.paddingRight = `${scrollbarWidth}px`;
    return () => {
      document.body.style.overflow = previousOverflow;
      document.body.style.paddingRight = previousPaddingRight;
    };
  }, [open]);
  if (!definition) return null;
  const dialog = open && createPortal(
    <div className="metric-definition-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) setOpen(false); }}>
      <section id={dialogId} ref={panelRef} className="metric-definition-dialog" role="dialog" aria-modal="true" aria-labelledby={titleId} tabIndex="-1">
        <div className="panel-title metric-definition-header">
          <div><p className="eyebrow">Metric definition</p><h2 id={titleId}>{definition.name}</h2></div>
          <button type="button" onClick={() => setOpen(false)} aria-label={`Close ${definition.name} definition`}><X size={19} /></button>
        </div>
        <div className="metric-definition-body">
          <p>{definition.definition}</p>
          <dl><div><dt>Formula</dt><dd>{definition.formula}</dd></div><div><dt>Unit</dt><dd>{definition.unit}</dd></div><div><dt>How to read it</dt><dd>{definition.interpretation}</dd></div><div><dt>Caveat</dt><dd>{definition.caveat}</dd></div><div><dt>Current source / method</dt><dd>{source}</dd></div></dl>
          <a className="inline-link" href="/files#sources">Open source or method <ArrowRight size={14} /></a>
        </div>
      </section>
    </div>,
    document.body,
  );
  return <><button ref={triggerRef} className="metric-info-button" type="button" aria-haspopup="dialog" aria-controls={open ? dialogId : undefined} aria-label={`Define ${definition.name}`} aria-expanded={open} onClick={() => setOpen(true)}><Info size={14} weight="bold" aria-hidden="true" /></button>{dialog}</>;
}

function Sidebar({ route, onNavigate, onOpenAssistant, assistantButtonRef, mobileOpen, onCloseMobile, panelRef, backgroundInert }) {
  const go = (next) => { onNavigate(next); onCloseMobile(); };
  return (
    <aside ref={panelRef} className={`sidebar ${mobileOpen ? "mobile-open" : ""}`} aria-label="Product navigation" tabIndex="-1" inert={backgroundInert} aria-hidden={backgroundInert ? "true" : undefined}>
      <div className="brand-lockup"><button type="button" onClick={() => go("/")} aria-label="MagicFin home"><span className="brand-spark" aria-hidden="true"><Sparkle size={16} weight="fill" /></span><span><strong>MagicFin</strong><small>Financial evidence, made clear</small></span></button><button className="mobile-close" type="button" onClick={onCloseMobile} aria-label="Close navigation"><X size={20} /></button></div>
      <nav className="primary-nav" aria-label="Main navigation">{primaryNav.map(({ route: itemRoute, label, icon: Icon }) => <button key={itemRoute} type="button" className={route === itemRoute ? "active" : ""} aria-label={label} aria-current={route === itemRoute ? "page" : undefined} onClick={() => go(itemRoute)}><Icon size={18} aria-hidden="true" /><span>{label}</span></button>)}</nav>
      <div className="sidebar-spacer" />
      <button ref={assistantButtonRef} className="assistant-entry" type="button" onClick={(event) => { onOpenAssistant(event.currentTarget); onCloseMobile(); }}><MagicWand size={18} aria-hidden="true" /><span><strong>Magic Assistant</strong><small>Fixture answers with citations</small></span><CaretRight size={15} aria-hidden="true" /></button>
      <nav className="utility-nav" aria-label="Account and settings">{utilityNav.map(({ route: itemRoute, label, icon: Icon }) => <button key={itemRoute} type="button" className={route === itemRoute ? "active" : ""} aria-label={label} aria-current={route === itemRoute ? "page" : undefined} onClick={() => go(itemRoute)}><Icon size={17} aria-hidden="true" /><span>{label}</span></button>)}</nav>
      <div className="sidebar-legal"><button type="button" onClick={() => go("/privacy")}>Privacy & data</button><span aria-hidden="true">·</span><button type="button" onClick={() => go("/legal")}>Legal</button><small>Demo data · human-checked</small></div>
    </aside>
  );
}

function MobileHeader({ onOpenNav, onOpenAssistant, menuButtonRef, backgroundInert }) {
  return <header className="mobile-header" inert={backgroundInert} aria-hidden={backgroundInert ? "true" : undefined}><button ref={menuButtonRef} type="button" onClick={onOpenNav} aria-label="Open navigation"><List size={22} /></button><span className="mobile-wordmark">MagicFin</span><button type="button" onClick={(event) => onOpenAssistant(event.currentTarget)} aria-label="Open Magic Assistant"><MagicWand size={21} /></button></header>;
}

function PageHeader({ eyebrow, title, description, actions, children }) {
  return <header className="page-header"><div><p className="eyebrow">{eyebrow}</p><h1>{title}</h1>{description && <p>{description}</p>}{children}</div>{actions && <div className="page-actions">{actions}</div>}</header>;
}

function SourceCard({ source, onOpen }) {
  const warning = source.status !== "Validated";
  return <article className="source-card" id={source.id} tabIndex="-1"><div className="source-card-top"><span className="file-kind">{source.kind === "PDF" ? <FilePdf size={18} /> : <Table size={18} />}{source.kind}</span><StatusTag tone={warning ? "warning" : "success"}>{source.status}</StatusTag></div><h3>{source.name}</h3><p>{source.date}</p><dl><div><dt>Provenance</dt><dd>{source.provenance}</dd></div><div><dt>Anchor</dt><dd>{source.anchor}</dd></div></dl><button className="inline-link" type="button" onClick={(event) => onOpen(source, event.currentTarget)}>Open source <ArrowRight size={15} /></button></article>;
}

function TrendFigure({ data, onNavigate }) {
  const [showTable, setShowTable] = useState(false);
  const trend = data.trend;
  const currencyCode = data.company.currency.split(" ")[0];
  const sourceName = data.sources.find((source) => source.kind === "Workbook")?.name || "Financials source";
  const metrics = {
    revenue: { key: "revenue", label: "Revenue", unit: data.company.currency, color: "#2f704c", format: (value) => `${currencyCode} ${value.toLocaleString()}m` },
    operatingMargin: { key: "operatingMargin", label: "Operating margin", unit: "Percent", color: "#5e4b8b", format: (value) => `${value.toFixed(1)}%` },
    currentRatio: { key: "currentRatio", label: "Current ratio", unit: "Ratio", color: "#815000", format: (value) => `${value.toFixed(2)}×` },
    fcfMargin: { key: "fcfMargin", label: "Free-cash-flow margin", unit: "Percent · project-defined", color: "#195f8c", format: (value) => `${value.toFixed(1)}%` },
  };
  const [metricKey, setMetricKey] = useState("revenue");
  const [startIndex, setStartIndex] = useState(0);
  const [endIndex, setEndIndex] = useState(trend.length - 1);
  const metric = metrics[metricKey];
  const visibleTrend = trend.slice(startIndex, endIndex + 1);
  const setPreset = (value) => {
    if (value === "latest-3") setStartIndex(Math.max(0, trend.length - 3));
    else setStartIndex(0);
    setEndIndex(trend.length - 1);
  };
  return (
    <section className="trend-card" aria-labelledby="trend-title">
      <div className="trend-header"><div><p className="eyebrow">Company trajectory</p><h2 id="trend-title">Performance trend</h2><p>Explore the same four headline metrics across the reported periods.</p></div><div className="trend-controls"><label className="select-control">Metric<span className="select-shell"><select aria-label="Trend metric" value={metricKey} onChange={(event) => setMetricKey(event.target.value)}>{Object.entries(metrics).map(([key, item]) => <option key={key} value={key}>{item.label}</option>)}</select><CaretDown size={15} weight="bold" aria-hidden="true" /></span></label><label className="select-control">Reporting period<span className="select-shell"><select aria-label="Period range" value={startIndex === Math.max(0, trend.length - 3) ? "latest-3" : "all"} onChange={(event) => setPreset(event.target.value)}><option value="all">All reported periods</option><option value="latest-3">Latest 3 periods</option></select><CaretDown size={15} weight="bold" aria-hidden="true" /></span></label></div></div>
      <div className="trend-selection" aria-live="polite"><div><span>Current selection</span><strong>{metric.label}</strong><small>{metric.unit}</small></div><div className="chart-legend" aria-label="Chart legend"><span><i className="reported-key" aria-hidden="true" />Reported history</span><span><i className="forecast-key" aria-hidden="true" />Illustrative ranges appear only in Deep analysis</span></div></div>
      <div className="range-scrubber" aria-label="Adjust reported-period range"><div className="range-summary"><strong>{trend[startIndex].period} — {trend[endIndex].period}</strong><span>{visibleTrend.length} reported periods selected</span></div><label>Start period: {trend[startIndex].period}<input aria-label="Range start" aria-valuetext={trend[startIndex].period} type="range" min="0" max={Math.max(0, endIndex - 1)} value={startIndex} onChange={(event) => setStartIndex(Number(event.target.value))} /></label><label>End period: {trend[endIndex].period}<input aria-label="Range end" aria-valuetext={trend[endIndex].period} type="range" min={Math.min(trend.length - 1, startIndex + 1)} max={trend.length - 1} value={endIndex} onChange={(event) => setEndIndex(Number(event.target.value))} /></label></div>
      <div className="trend-chart" role="img" tabIndex="0" aria-label={`${metric.label}, ${metric.unit}, reported history from ${visibleTrend[0].period} through ${visibleTrend[visibleTrend.length - 1].period}. Use the data-table control for exact values.`}><Suspense fallback={<div className="chart-loading" role="status">Loading accessible chart…</div>}><TrendChart trend={visibleTrend} metric={metric} /></Suspense></div>
      <div className="trend-footer"><span>Source: {sourceName} · reported series</span><div>{onNavigate && <button className="inline-link" type="button" onClick={() => onNavigate("/reports")}>Open Deep analysis <ArrowRight size={14} /></button>}<button className="inline-link" type="button" aria-expanded={showTable} onClick={() => setShowTable((value) => !value)}>{showTable ? "Hide" : "View"} accessible data table</button></div></div>
      {showTable && <div className="table-wrap trend-table"><table><caption>{metric.label}, {metric.unit}; reported data</caption><thead><tr><th scope="col">Period</th><th scope="col">{metric.label}</th><th scope="col">History type</th><th scope="col">Source</th></tr></thead><tbody>{visibleTrend.map((row) => <tr key={row.period}><th scope="row">{row.period}</th><td>{metric.format(row[metric.key])}</td><td>Reported history</td><td>{sourceName}</td></tr>)}</tbody></table></div>}
    </section>
  );
}

function DashboardSignals({ data }) {
  const revenue = data.metrics.find((item) => item.id === "revenue");
  const liquidity = data.metrics.find((item) => item.id === "current-ratio");
  const signals = [
    ["Trend", `${revenue.label} changed ${revenue.delta} in ${revenue.period}.`],
    ["Pattern", `All ${data.trend.length} reported demo periods are shown for comparison.`],
    ["Exception", `${data.review.claim.value} was claimed; the cited calculation shows ${data.review.result.value}.`],
    ["Evidence flag", `${liquidity.label} changed ${liquidity.delta} ${liquidity.deltaLabel}.`],
  ];
  return <section className="signal-strip" aria-labelledby="signals-title"><div className="section-heading"><div><p className="eyebrow">Review signals</p><h2 id="signals-title">Trend, pattern, exception, and evidence flag.</h2></div></div><div>{signals.map(([label, text]) => <article key={label}><span>{label}</span><p>{text}</p></article>)}</div></section>;
}

function HeadlineMetrics({ metrics, context = "review" }) {
  const title = context === "brief" ? "Four primary measures of reported performance." : "The four numbers to orient the review.";
  const meanings = {
    revenue: "Growth shows whether sales are expanding compared with the prior year.",
    "operating-margin": "Profitability shows how much operating profit remains from each dollar of revenue.",
    "current-ratio": "Liquidity indicates the ability to cover near-term obligations with current assets.",
    "fcf-margin": "Cash flow shows how much revenue becomes free cash after operations and capital spending.",
  };
  return <section className="headline-metrics" aria-labelledby="headline-metrics-title"><div className="section-heading"><div><p className="eyebrow">Primary metrics</p><h2 id="headline-metrics-title">{title}</h2></div><small>{metrics[0]?.period} · reported period</small></div><div className="metric-grid">{metrics.map((metric, index) => <article className="metric-card" key={metric.id} style={{ "--reveal-order": index }}><div><span className="metric-label">{metric.label}<MetricDefinitionButton metricId={metric.id} source={metric.source} /></span><StatusTag tone={metric.tone === "caution" ? "warning" : "success"}>{metric.period}</StatusTag></div><strong>{metric.value}</strong><p className={metric.tone === "caution" ? "metric-delta caution" : "metric-delta"}>{metric.delta} <small>{metric.deltaLabel}</small></p><p className="metric-meaning">{meanings[metric.id] || metricDefinitionRegistry[metric.id]?.interpretation}</p><dl><div><dt>Unit</dt><dd>{metric.unit}</dd></div><div><dt>Source</dt><dd>{metric.source}</dd></div></dl></article>)}</div></section>;
}

function CompanyPage({ data, onNavigate, onOpenAssistant, onOpenSource }) {
  return (
    <div className="route-page company-page">
      <PageHeader eyebrow="Home · Company dashboard" title={data.company.name} description={`${data.company.description} · ${data.session.period}`} actions={<><button className="button secondary" type="button" onClick={() => onNavigate("/files#sources")}><Files size={17} />View sources</button><button className="button secondary" type="button" onClick={() => onNavigate("/reports")}><Receipt size={17} />Open report</button><button className="button magic" type="button" onClick={() => onNavigate("/files#upload")}><FileArrowUp size={17} />Analyze files</button></>}><small className="page-disclosure">{data.session.persistence} · last updated {data.session.lastUpdated}</small></PageHeader>
      <HeadlineMetrics metrics={data.metrics} />
      <TrendFigure data={data} onNavigate={onNavigate} />
      <DashboardSignals data={data} />
      <div className="company-bottom"><section className="summary-card"><p className="eyebrow">Factual summary</p><h2>Reported performance and narrative need one clear review.</h2><p>{data.summary}</p><div className="compact-statuses"><span><CheckCircle size={18} />6 <small>Supported</small></span><span><Info size={18} />2 <small>Uncertain</small></span><span><Warning size={18} />1 <small>Contradicted</small></span></div><div className="summary-actions"><button className="button primary" type="button" onClick={() => onNavigate("/review")}>Open Review Desk</button><button className="button secondary" type="button" onClick={(event) => onOpenAssistant(event.currentTarget)}><MagicWand size={17} />Open Magic Assistant</button></div></section><section className="priorities-card"><p className="eyebrow">Review priorities</p><h2>Where human judgment matters.</h2><ol>{data.reviewPriorities.map((item, index) => <li key={item.id}><span>{index + 1}</span><div><strong>{item.label}</strong><small>{item.status}</small></div></li>)}</ol><div className="evidence-flag"><Warning size={18} weight="fill" /><p><strong>Evidence flag</strong>The report states {data.review.claim.value}; cited figures calculate to {data.review.result.value}.</p></div><div className="report-row"><button className="inline-link" type="button" onClick={() => downloadReviewedReport(undefined, data)}>Export JSON evidence <DownloadSimple size={15} /></button><button className="inline-link disabled-link" type="button" disabled aria-describedby="pdf-help">PDF unavailable</button></div><small id="pdf-help">Server PDF export is not configured.</small></section></div>
      <section className="source-section" aria-labelledby="source-set-title"><div className="section-heading"><div><p className="eyebrow">Source set</p><h2 id="source-set-title">Claims stay with their numbers.</h2></div><button className="inline-link" type="button" onClick={() => onNavigate("/files#sources")}>Open Files & Sources <ArrowRight size={15} /></button></div><div className="source-grid">{data.sources.map((source) => <SourceCard source={source} key={source.id} onOpen={onOpenSource} />)}</div></section>
    </div>
  );
}

function FilesPage({ data = productFixture, onNavigate, onOpenSource, onFixtureReady, onAnalysisReady }) {
  const inputRef = useRef(null);
  const [state, setState] = useState("empty");
  const [files, setFiles] = useState([]);
  const [session, setSession] = useState(null);
  const [sessionMessage, setSessionMessage] = useState("");
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState("all");
  const sources = Array.isArray(data?.sources) ? data.sources : [];
  const query = search.trim().toLowerCase();
  const visibleSources = sources.filter((source) => (filter === "all" || (filter === "ready" ? source.status === "Validated" : source.status !== "Validated")) && (!query || `${source.name} ${source.kind} ${source.date} ${source.provenance} ${source.anchor}`.toLowerCase().includes(query)));
  const expected = [sources[0]?.name, sources[1]?.name].filter(Boolean);
  const choose = async (selected) => {
    const names = selected.map((file) => file.name);
    setFiles(names);
    if (session) {
      if (selected.length !== 2 || !selected.some((file) => file.name.toLowerCase().endsWith(".pdf")) || !selected.some((file) => file.name.toLowerCase().endsWith(".xlsx"))) {
        setState("error");
        setSessionMessage("Choose one PDF financial report and one XLSX evidence workbook.");
        return;
      }
      setState("server-loading");
      setSessionMessage("Uploading and checking both files in the temporary private session.");
      try {
        const results = await Promise.all(selected.map((file) => uploadSource(session, file.name.toLowerCase().endsWith(".pdf") ? "report_pdf" : "workbook", file)));
        setFiles(results.map((item, index) => item?.display_name || item?.file?.display_name || selected[index]?.name).filter(Boolean));
        setSessionMessage("Files passed validation. Building the source-cited analysis…");
        const analysis = await analyzeSourceSession(session);
        onAnalysisReady?.(analysis);
        setState("ready");
        setSessionMessage("Source-cited analysis ready. Open the company workspace to review it.");
      } catch (error) {
        setState("error");
        setSessionMessage(error instanceof Error ? error.message : "The files could not be checked safely.");
      }
      return;
    }
    setState("error");
    setSessionMessage("A live file session is required before local files can be uploaded or analyzed.");
  };
  const startPrivateSession = async () => {
    setState("connecting");
    setSessionMessage("Starting a temporary private session…");
    try {
      const next = await createSourceSession();
      setSession(next);
      setState("empty");
      setFiles([]);
      setSessionMessage("Temporary session ready. Files expire after 30 minutes idle or two hours absolute in this running process.");
    } catch (error) {
      setState("error");
      setSessionMessage(error instanceof Error ? error.message : "A private session is not available in this deployment.");
    }
  };
  const liveRole = state === "error" ? "alert" : "status";
  const heading = state === "ready" ? "Live analysis complete." : state === "sample" ? "Sample sources loaded." : state === "error" ? "The source set needs attention." : state === "connecting" ? "Connecting the live file service." : state === "server-loading" ? "Validating and analyzing uploaded files." : session ? "Choose the report and workbook." : "Connect the live file service.";
  const detail = sessionMessage || (state === "error" ? "The previous dashboard remains unchanged. Correct the issue and try again." : state === "sample" ? "Sample data is clearly labelled and does not represent an uploaded analysis." : session ? "Choose one PDF financial report and one XLSX evidence workbook; analysis starts only after both pass validation." : "Connect a temporary live session to upload and analyze your own source set.");
  const slotStatus = state === "error" ? "Needs attention" : state === "server-loading" ? "Checking" : state === "ready" ? "Analyzed" : state === "sample" ? "Sample" : "Waiting";
  return (
    <div className="route-page files-sources-page">
      <PageHeader eyebrow="Files & Sources" title="Upload, validate, analyze, then inspect every source." description="One source set feeds the dashboard, report, and Review Desk." actions={<StatusTag tone={session ? "success" : "neutral"}>{session ? "Live file session" : state === "sample" ? "Sample data" : "Live upload"}</StatusTag>} />
      <section className="upload-panel" id="upload" tabIndex="-1" aria-labelledby="files-review-title">
        <div className="upload-icon"><Files size={28} /></div>
        <div role={liveRole} aria-live={state === "error" ? "assertive" : "polite"}>
          <p className="eyebrow">1 · Upload & analyze</p>
          <h2 id="files-review-title">{heading}</h2>
          <p>{detail}</p>
        </div>
        <input ref={inputRef} className="visually-hidden" tabIndex="-1" aria-label="Select financial report PDF and evidence workbook" type="file" multiple accept=".pdf,.xlsx" onChange={(event) => choose([...event.target.files])} />
        {state === "server-loading" && <div className="source-validation" role="status"><span className="loader" aria-hidden="true" /><strong>Upload → validate → analyze</strong><small>The dashboard and report update only after the server returns a complete source-cited analysis.</small></div>}
        <div className="file-slot-grid" aria-label="Required review files">
          {[{ role: "report_pdf", label: "Financial report", kind: "PDF", name: files.find((name) => name.toLowerCase().endsWith(".pdf")) || expected.find((name) => name.toLowerCase().endsWith(".pdf")) }, { role: "workbook", label: "Evidence workbook", kind: "XLSX", name: files.find((name) => name.toLowerCase().endsWith(".xlsx")) || expected.find((name) => name.toLowerCase().endsWith(".xlsx")) }].map((slot) => <article className="file-slot" key={slot.role}><span className="file-kind">{slot.kind === "PDF" ? <FilePdf size={18} /> : <Table size={18} />}{slot.kind}</span><div><h3>{slot.label}</h3><p>{slot.name || "No file selected"}</p></div><StatusTag tone={state === "ready" ? "success" : state === "error" ? "warning" : "neutral"}>{slotStatus}</StatusTag></article>)}
        </div>
        <div className="upload-actions">
          <button className="button primary" type="button" disabled={state === "server-loading" || state === "connecting"} onClick={() => state === "ready" ? onNavigate("/") : session ? inputRef.current?.click() : startPrivateSession()}>{state === "connecting" ? "Connecting…" : state === "server-loading" ? "Analyzing uploaded files…" : state === "ready" ? "View updated dashboard" : session ? "Select files to analyze" : "Connect live file service"}</button>
          <button className="button secondary" type="button" disabled={state === "server-loading" || state === "connecting" || expected.length !== 2} onClick={() => { setSession(null); setSessionMessage(""); setFiles(expected); setState("sample"); onFixtureReady?.(); }}>Try sample data</button>
        </div>
        <details className="privacy-details"><summary>{state === "sample" ? "About sample data" : "Privacy and retention"}</summary><p>{state === "sample" ? "The sample option restores MagicFin’s preloaded, human-checked dataset. It never reads or uploads files from your device and is not presented as a live analysis." : session ? "This temporary session uploads only the files you choose. It expires after 30 minutes idle or two hours absolute; deletion guarantees require a server receipt." : "The live service creates a temporary session before the file picker opens. Use it only for documents you are authorized to process."}</p></details>
      </section>
      <section className="source-library-section" id="sources" tabIndex="-1" aria-labelledby="source-library-title">
        <div className="section-heading"><div><p className="eyebrow">2 · Sources</p><h2 id="source-library-title">Evidence with a visible address.</h2><p>Search each validated source by filename, period, provenance, or exact anchor.</p></div><StatusTag tone="success">{visibleSources.length} of {sources.length} sources</StatusTag></div>
        <div className="source-tools"><label><span className="visually-hidden">Search sources</span><MagnifyingGlass size={17} aria-hidden="true" /><input type="search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search filename, period, anchor…" aria-label="Search sources" /></label><label className="select-control">Status<span className="select-shell"><select aria-label="Filter sources by status" value={filter} onChange={(event) => setFilter(event.target.value)}><option value="all">All statuses</option><option value="ready">Validated</option><option value="attention">Needs attention</option></select><CaretDown size={15} weight="bold" aria-hidden="true" /></span></label></div>
        {visibleSources.length ? <div className="library-list">{visibleSources.map((source, index) => <article key={source.id} id={source.id} tabIndex="-1" style={{ "--reveal-order": index }}><span className="library-icon">{source.kind === "PDF" ? <FilePdf size={22} /> : <Table size={22} />}</span><div><h3>{source.name}</h3><p>{source.date} · {source.anchor}</p><small>{source.provenance}</small></div><StatusTag tone={source.status === "Validated" ? "success" : "warning"}>{source.status}</StatusTag><button className="button secondary" type="button" onClick={(event) => onOpenSource(source, event.currentTarget)}>Open evidence</button></article>)}</div> : <div className="source-empty" role="status"><MagnifyingGlass size={24} /><strong>No sources match this view.</strong><button className="inline-link" type="button" onClick={() => { setSearch(""); setFilter("all"); }}>Clear search and filter</button></div>}
        <p className="source-library-note">Citations across the dashboard, report, assistant, and Review Desk return to these exact source cards.</p>
      </section>
    </div>
  );
}

function SourceLibraryPage({ data, onOpenSource }) {
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState("all");
  const query = search.trim().toLowerCase();
  const visible = data.sources.filter((source) => (filter === "all" || (filter === "ready" ? source.status === "Validated" : source.status !== "Validated")) && (!query || `${source.name} ${source.kind} ${source.date} ${source.provenance} ${source.anchor}`.toLowerCase().includes(query)));
  return <div className="route-page"><PageHeader eyebrow="Source Library" title="Evidence with a visible address." description="Search source status, period, provenance, and anchors from the current analysis contract." actions={<StatusTag tone="success">{visible.length} of {data.sources.length} sources</StatusTag>} /><div className="source-tools"><label><span className="visually-hidden">Search sources</span><MagnifyingGlass size={17} aria-hidden="true" /><input type="search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search filename, period, anchor…" aria-label="Search sources" /></label><label className="select-control">Status<span className="select-shell"><select aria-label="Filter sources by status" value={filter} onChange={(event) => setFilter(event.target.value)}><option value="all">All statuses</option><option value="ready">Validated</option><option value="attention">Needs attention</option></select><CaretDown size={15} weight="bold" aria-hidden="true" /></span></label></div>{visible.length ? <div className="library-list">{visible.map((source, index) => <article key={source.id} id={source.id} tabIndex="-1" style={{ "--reveal-order": index }}><span className="library-icon">{source.kind === "PDF" ? <FilePdf size={22} /> : <Table size={22} />}</span><div><h2>{source.name}</h2><p>{source.date} · {source.anchor}</p><small>{source.provenance}</small></div><StatusTag tone={source.status === "Validated" ? "success" : "warning"}>{source.status}</StatusTag><button className="button secondary" type="button" onClick={(event) => onOpenSource(source, event.currentTarget)}>Open evidence</button></article>)}</div> : <section className="route-state compact" role="status"><MagnifyingGlass size={24} /><h2>No sources match this view.</h2><button className="inline-link" type="button" onClick={() => { setSearch(""); setFilter("all"); }}>Clear search and filter</button></section>}<div className="fixture-note wide"><Info size={17} /><p><strong>Stable evidence IDs</strong>These cards render from the typed analysis/session adapter and keep source anchors one click away.</p></div></div>;
}

function HistoryPage({ data, onNavigate }) {
  return <div className="route-page"><PageHeader eyebrow="History" title="Verified demo activity." description="These scripted entries demonstrate the history layout. They do not update, sync, or persist." actions={<StatusTag>Static fixture</StatusTag>} /><section className="history-list">{data.history.map((item) => <button type="button" key={item.id} onClick={() => onNavigate(item.route)}><span className="history-dot" aria-hidden="true" /><span><strong>{item.label}</strong><small>{item.time}</small></span><StatusTag tone={item.status === "Contradicted" ? "warning" : "neutral"}>{item.status}</StatusTag><ArrowRight size={17} /></button>)}</section><section className="route-state compact"><ClockCounterClockwise size={26} /><h2>No live history is connected.</h2><p>A storage service is required before MagicFin can show activity from real sessions.</p></section></div>;
}

function ForecastPanel({ forecast, currency = "USD millions" }) {
  const [historyCount, setHistoryCount] = useState(4);
  const available = historyCount >= forecast.minimumHistory;
  const currencyCode = currency.split(" ")[0];
  return <section className="forecast-panel" aria-labelledby="forecast-title"><div className="section-heading"><div><p className="eyebrow">Guarded outlook</p><h2 id="forecast-title">Bounded revenue scenarios, separated from reported history.</h2></div><label className="select-control">History available<span className="select-shell"><select aria-label="Forecast history available" value={historyCount} onChange={(event) => setHistoryCount(Number(event.target.value))}><option value="4">4 reported periods</option><option value="2">2 reported periods</option></select><CaretDown size={15} weight="bold" aria-hidden="true" /></span></label></div><p className="forecast-warning"><Warning size={17} />Illustrative deterministic range—not reported history, a recommendation, or a causal forecast.</p>{available ? <><dl className="forecast-method"><div><dt>Method</dt><dd>{forecast.method}</dd></div><div><dt>Inputs</dt><dd>{forecast.inputs}</dd></div><div><dt>Assumptions</dt><dd>{forecast.assumptions}</dd></div></dl><div className="table-wrap forecast-table"><table><caption>Illustrative revenue forecast range, {currency}</caption><thead><tr><th scope="col">Forecast period</th><th scope="col">Low</th><th scope="col">Baseline</th><th scope="col">High</th><th scope="col">History type</th></tr></thead><tbody>{forecast.ranges.map((row) => <tr key={row.period}><th scope="row">{row.period}</th><td>{currencyCode} {row.low.toLocaleString()}m</td><td>{currencyCode} {row.base.toLocaleString()}m</td><td>{currencyCode} {row.high.toLocaleString()}m</td><td>Forecast range</td></tr>)}</tbody></table></div></> : <div className="forecast-refusal" role="status"><Warning size={25} /><div><strong>Outlook unavailable: insufficient history.</strong><p>At least {forecast.minimumHistory} reported periods are required. MagicFin will not invent missing history.</p></div></div>}</section>;
}

function ReportsPage({ data, onNavigate }) {
  const [message, setMessage] = useState("");
  const [pdfState, setPdfState] = useState({ mode: "idle", message: "" });
  const isDemo = data.session.mode === "verified_fixture";
  const downloadPdf = async () => {
    setPdfState({ mode: "preparing", message: "Preparing the performance brief…" });
    try {
      const result = await requestReviewedPdf({ bundle: getReviewedReportBundle(data) });
      setPdfState({ mode: "success", message: `${result.filename} downloaded.` });
    } catch (error) {
      setPdfState({ mode: "error", message: error instanceof Error ? error.message : "The reviewed PDF could not be prepared. Please try again." });
    }
  };
  const downloadDemoPdf = () => {
    setPdfState({ mode: "preparing", message: "Preparing the demo performance brief…" });
    window.setTimeout(() => {
      try {
        const url = URL.createObjectURL(buildDeterministicDemoPdf(data));
        const anchor = document.createElement("a");
        anchor.href = url;
        anchor.download = "magicfin-demo-performance-brief.pdf";
        anchor.hidden = true;
        document.body.appendChild(anchor);
        anchor.click();
        anchor.remove();
        URL.revokeObjectURL(url);
        setPdfState({ mode: "success", message: "Demo performance brief downloaded." });
      } catch (error) {
        setPdfState({ mode: "error", message: error instanceof Error ? error.message : "The demo PDF could not be prepared. Please try again." });
      }
    }, 180);
  };
  const pdfAction = isDemo
    ? <button className="button secondary" type="button" onClick={downloadDemoPdf} disabled={pdfState.mode === "preparing"}><FilePdf size={17} />{pdfState.mode === "preparing" ? "Preparing PDF…" : pdfState.mode === "error" ? "Retry demo PDF" : "Prepare demo PDF"}</button>
    : <button className="button secondary" type="button" onClick={downloadPdf} disabled={pdfState.mode === "preparing"}><FilePdf size={17} />{pdfState.mode === "preparing" ? "Preparing PDF…" : pdfState.mode === "error" ? "Retry PDF" : "Download PDF"}</button>;
  return (
    <div className="route-page deep-analysis-page">
      <PageHeader eyebrow="Reports · Board / CFO / investor" title="Board performance brief" description={`Decision-useful reported performance for ${data.company.name}, with material variances, context, and a guarded outlook.`} actions={<><button className="button primary" type="button" onClick={() => downloadReviewedReport(setMessage, data)}><DownloadSimple size={17} />Download JSON</button>{pdfAction}</>}><small className="page-disclosure" role={pdfState.mode === "error" ? "alert" : "status"} aria-live="polite">{pdfState.message || (isDemo ? "The demo PDF is generated from the same reviewed fixture snapshot." : "Reviewed reports are prepared from the current validated analysis snapshot.")}</small></PageHeader>
      <section className="executive-brief" aria-labelledby="executive-brief-title"><div><p className="eyebrow">Performance at a glance</p><h2 id="executive-brief-title">Growth and operating margin improved; liquidity softened.</h2><p>{data.summary}</p></div><dl><div><dt>Reported period</dt><dd>{data.session.period}</dd></div><div><dt>Audience</dt><dd>Board, finance leadership, and informed investors</dd></div><div><dt>Boundary</dt><dd>Reported data plus bounded scenarios; no recommendation or causal claim</dd></div></dl></section>
      <HeadlineMetrics metrics={data.metrics} context="brief" />
      <TrendFigure data={data} />
      <section className="ratio-section" aria-labelledby="ratio-title"><div className="section-heading"><div><p className="eyebrow">Financial ratios</p><h2 id="ratio-title">Profitability, liquidity, leverage, cash flow, and efficiency.</h2></div></div><div className="table-wrap"><table><caption>Secondary {data.session.period} ratios with period, change, and source</caption><thead><tr><th scope="col">Category</th><th scope="col">Metric</th><th scope="col">Period</th><th scope="col">Value</th><th scope="col">Change</th><th scope="col">Source</th></tr></thead><tbody>{data.secondaryRatios.map((item) => <tr key={item.label}><th scope="row">{item.category}</th><td><span className="metric-label">{item.label}<MetricDefinitionButton metricId={item.id} source={item.source} /></span></td><td>{item.period}</td><td>{item.value}</td><td>{item.delta}</td><td>{item.source}</td></tr>)}</tbody></table></div></section>
      <section className="narrative-outcome" aria-labelledby="narrative-outcome-title"><div><p className="eyebrow">Narrative vs numbers</p><h2 id="narrative-outcome-title">The growth statement does not reconcile with the cited inputs.</h2><p>The report states <strong>{data.review.claim.value}</strong>; the calculation from the reported periods is <strong>{data.review.result.value}</strong>, a <strong>{data.review.result.difference}</strong> variance.</p></div><button className="inline-link" type="button" onClick={() => onNavigate("/review#annual-report")}>Verify this outcome <ArrowRight size={14} /></button></section>
      <section className="material-signals" aria-labelledby="material-signals-title"><div className="section-heading"><div><p className="eyebrow">Material variances & risks</p><h2 id="material-signals-title">Items that may change the discussion.</h2></div></div><div>{data.analysisSignals.slice(1).map((item) => <article key={item.label}><span>{item.label}</span><strong>{item.value}</strong><p>{item.detail}</p></article>)}</div></section>
      <ForecastPanel forecast={data.forecast} currency={data.company.currency} />
      <section className="economic-context" aria-labelledby="economic-title"><div className="section-heading"><div><p className="eyebrow">Sourced economic context</p><h2 id="economic-title">Background indicators, not explanations.</h2></div></div><p className="context-caveat"><Info size={17} />Context only; no causal relationship is asserted.</p><div className="context-list">{data.economicContext.map((item) => <article key={item.label}><div><h3>{item.label}</h3><strong>{item.value}</strong></div><dl><div><dt>Geography</dt><dd>{item.geography}</dd></div><div><dt>Period / unit</dt><dd>{item.period} · {item.unit}</dd></div><div><dt>Source date</dt><dd>{item.source} · {item.sourceDate}</dd></div><div><dt>Comparability</dt><dd>{item.comparability}</dd></div></dl></article>)}</div></section>
      <section className="management-questions" aria-labelledby="management-questions-title"><p className="eyebrow">Board agenda</p><h2 id="management-questions-title">Questions for the next performance discussion.</h2><ol>{data.managementQuestions.map((question, index) => <li key={question}><span>{index + 1}</span><p>{question}</p></li>)}</ol><small>Questions are generated from the bounded analysis contract. They are not recommendations or financial advice.</small></section>
      <section className="report-methodology" aria-labelledby="methodology-title"><div><p className="eyebrow">Methodology & limitations</p><h2 id="methodology-title">A brief with a visible decision boundary.</h2><p>Reported values and ratios retain their periods, units, and source methods. Illustrative ranges use {data.forecast.method.toLowerCase()} and do not include acquisitions, currency remeasurement, or macroeconomic causality.</p></div><dl><div><dt>Coverage</dt><dd>{data.trend.length} reported periods; {data.metrics.length} primary metrics; {data.secondaryRatios.length} secondary ratios</dd></div><div><dt>Economic context</dt><dd>Contextual comparison only; not evidence of company-specific cause</dd></div><div><dt>Exports</dt><dd>{isDemo ? "Deterministic demo PDF and JSON" : "Validated service PDF and JSON"}</dd></div><div><dt>Limitations</dt><dd>No investment recommendation, assurance opinion, persistence claim, or live-model inference</dd></div></dl></section>
      {message && <div className="toast" role="status"><CheckCircle size={20} /><span><strong>{message}</strong><small>Generated from the verified fixture.</small></span><button type="button" onClick={() => setMessage("")} aria-label="Dismiss notification"><X size={16} /></button></div>}
    </div>
  );
}

function ProfilePage() { return <div className="route-page"><PageHeader eyebrow="Profile" title="A local demo identity." description="No account exists in this frontend prototype." /><section className="settings-card"><div className="profile-mark" aria-hidden="true">DR</div><div><h2>Demo reviewer</h2><p>Local fixture workspace · not signed in</p></div><StatusTag>Not persisted</StatusTag></section><section className="route-state compact"><UserCircle size={28} /><h2>Profile syncing is unavailable.</h2><p>Connect a real authentication and profile service before enabling saved names, teams, or preferences.</p></section></div>; }

function SettingsPage({ reducedMotion, compactSources, onReducedMotion, onCompactSources, initialProviderMode = "not_configured" }) {
  const [providerMode, setProviderMode] = useState(initialProviderMode);
  const provider = getProviderConnectionAdapter(providerMode);
  const [providerDetail, setProviderDetail] = useState(null);
  const testConnection = () => {
    setProviderMode("loading");
    testModelProvider()
      .then((result) => {
        setProviderDetail(result.disclosure || null);
        setProviderMode(result.reachable ? "success" : result.state === "not_configured" ? "not_configured" : "error");
      })
      .catch((error) => {
        setProviderDetail(error.message);
        setProviderMode("error");
      });
  };
  return <div className="route-page"><PageHeader eyebrow="Settings" title="Make the desk comfortable." description="Display preferences affect this browser session only. Provider credentials remain server-side." /><section className="settings-list"><label><span><strong>Reduce interface motion</strong><small>Minimize panel, progress, and route transitions. Your system preference is respected by default.</small></span><input aria-label="Reduce interface motion" type="checkbox" checked={reducedMotion} onChange={(event) => onReducedMotion(event.target.checked)} /></label><label><span><strong>Compact source cards</strong><small>Use a tighter reading density on large screens.</small></span><input aria-label="Compact source cards" type="checkbox" checked={compactSources} onChange={(event) => onCompactSources(event.target.checked)} /></label></section><section className="provider-settings" aria-labelledby="provider-settings-title"><div className="section-heading"><div><p className="eyebrow">Magic Assistant</p><h2 id="provider-settings-title">Provider connection</h2></div><StatusTag tone={provider.tone}>{provider.status}</StatusTag></div><dl><div><dt>Provider</dt><dd>Google</dd></div><div><dt>Model</dt><dd><code>gemma-4-26b-a4b-it</code></dd></div><div><dt>Last successful test</dt><dd>{provider.lastSuccessfulTest}</dd></div></dl><div className="provider-status" role={providerMode === "error" ? "alert" : "status"} aria-live="polite" aria-busy={providerMode === "loading"}><p>{providerDetail || provider.description}</p><button className="button secondary" type="button" onClick={testConnection} disabled={providerMode === "loading"}>{providerMode === "loading" ? "Testing connection…" : providerMode === "error" ? "Retry connection" : "Test connection"}</button></div><div className="fixture-note wide"><LockKey size={17} /><p><strong>No browser API key</strong>The deployment owner sets the key server-side. This frontend calls only MagicFin’s authenticated, provider-neutral endpoint and never stores a key in the client bundle, local storage, or logs.</p></div></section><div className="fixture-note wide"><Info size={17} /><p><strong>Session-only preference</strong>These working display settings are not saved after reload.</p></div></div>;
}

const authMessages = {
  AUTH_CANCELLED: "Google sign-in was cancelled. Nothing changed in this browser.",
  AUTH_CONFIGURATION_INVALID: "The public sign-in configuration is invalid. The deployment owner must correct it.",
  AUTH_EXCHANGE_FAILED: "Google returned, but the session could not be verified. Try again.",
  AUTH_SESSION_INVALID: "The saved session could not be verified. Sign in again.",
  AUTH_SIGN_OUT_FAILED: "This browser could not sign out. Try again.",
  AUTH_START_FAILED: "Google sign-in could not start. Try again.",
  GOOGLE_SIGN_IN_NOT_CONFIGURED: "Google sign-in is prepared but not enabled for this deployment.",
};

function SignInPage({ authState, returnTo, onSignIn, onSignOut }) {
  const configured = authState.status !== "unauthenticated" || authState.configured;
  const authenticated = authState.status === "authenticated";
  const loading = authState.status === "loading";
  const tone = authenticated ? "success" : authState.status === "error" || authState.status === "cancelled" ? "warning" : "neutral";
  const status = authenticated ? "Authenticated" : loading ? "Checking session" : authState.status === "cancelled" ? "Cancelled" : authState.status === "error" ? "Needs attention" : configured ? "Ready" : "Not configured";
  const message = authMessages[authState.reasonCode] || (authenticated ? "Your verified Google session is active in this browser." : configured ? "Continue with Google to return to your current MagicFin work." : authMessages.GOOGLE_SIGN_IN_NOT_CONFIGURED);
  return <div className="route-page auth-page"><PageHeader eyebrow="Sign in" title={authenticated ? "You’re signed in to MagicFin." : "Continue with Google."} description="Authentication uses a narrow Supabase session boundary; provider credentials never enter this interface." actions={<StatusTag tone={tone}>{status}</StatusTag>} /><section className="sign-in-panel" aria-labelledby="auth-panel-title" aria-busy={loading}><span className="google-mark" aria-hidden="true">G</span><h2 id="auth-panel-title">{authenticated ? "Verified browser session" : "A direct route back to your review"}</h2><p role={authState.status === "error" ? "alert" : "status"} aria-live="polite">{message}</p>{authenticated ? <><dl className="auth-session"><div><dt>Session owner</dt><dd>{authState.ownerId}</dd></div><div><dt>Scope</dt><dd>Current browser session</dd></div></dl><button className="button secondary" type="button" onClick={onSignOut}>Sign out</button></> : <><button className="button primary google-button" type="button" disabled={!configured || loading} onClick={onSignIn}><span aria-hidden="true">G</span>{loading ? "Checking sign-in…" : authState.status === "error" ? "Try Google sign-in again" : "Continue with Google"}</button><small>After sign-in, return to <code>{returnTo}</code>.</small></>}<div className="auth-boundary"><LockKey size={17} /><span>Only a verified user identifier reaches the UI. Tokens remain inside the authentication adapter.</span></div></section></div>;
}

function AuthCallbackPage() { return <div className="route-page"><section className="route-state" role="status" aria-live="polite"><span className="loader" aria-hidden="true" /><p className="eyebrow">Google sign in</p><h1>Verifying this browser session.</h1><p>MagicFin will return to the requested local route after the session owner is verified.</p></section></div>; }

function PrivacyPage() { return <div className="route-page prose-page"><PageHeader eyebrow="Privacy & data" title="What this prototype actually does." /><section><h2>Files</h2><p>The public fixture checks selected filenames in your browser and does not send file contents to a server. A configured private session sends only files you explicitly choose to the temporary source service.</p><h2>Session data</h2><p>Fixture review state is browser-local. Configured private sessions expire after 30 minutes idle or two hours absolute in the running service; no durable persistence is claimed.</p><h2>Deletion</h2><p>“Clear demo session” clears the in-browser state shown by this prototype. It does not claim deletion from services that are not configured.</p><h2>Magic Assistant</h2><p>Magic Assistant uses verified scripted responses with citations unless a server-side provider is configured. No browser API key is used.</p></section></div>; }

function LegalPage() { return <div className="route-page prose-page"><PageHeader eyebrow="Legal & limitations" title="Evidence support, not financial advice." /><section><h2>Prototype scope</h2><p>MagicFin is a demonstration interface using synthetic, human-checked demo data. It does not contain issuer documents.</p><h2>Human judgment</h2><p>Calculated discrepancies require reviewer confirmation. Illustrative deterministic forecast ranges are clearly separated from reported history; they are not investment advice, recommendations, causal explanations, or model predictions.</p><h2>Exports</h2><p>The static demo includes a deterministic fixture PDF and JSON evidence export. Live reviewed PDFs are prepared only from a validated report snapshot.</p></section></div>; }

function NotFoundPage({ onNavigate }) { return <div className="route-page"><section className="route-state"><Warning size={32} /><p className="eyebrow">Page not found</p><h1>This trail stops here.</h1><p>The requested MagicFin route is not part of this prototype.</p><button className="button primary" type="button" onClick={() => onNavigate("/")}>Return home</button></section></div>; }

function CitationDrawer({ source, onClose, onNavigate, returnRef }) {
  const panelRef = useRef(null);
  useDismissible(Boolean(source), onClose, returnRef, panelRef);
  if (!source) return null;
  const destination = source.reviewRoute || source.route || "/review";
  const destinationLabel = destination.startsWith("/review") ? "Open in Review Desk" : "Open in Files & Sources";
  return <div className="drawer-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}><aside ref={panelRef} className="citation-drawer" role="dialog" aria-modal="true" aria-labelledby="citation-title" tabIndex="-1"><div className="panel-title"><div><p className="eyebrow">Cited source</p><h2 id="citation-title">{source.name || source.label}</h2></div><button type="button" onClick={onClose} aria-label="Close source drawer"><X size={20} /></button></div><StatusTag tone={source.status === "Review needed" ? "warning" : "success"}>{source.status || "Source-linked"}</StatusTag><dl className="citation-details"><div><dt>Location</dt><dd>{source.anchor}</dd></div><div><dt>Period</dt><dd>{source.period || source.date || productFixture.session.period}</dd></div><div><dt>Provenance</dt><dd>{source.provenance || "Verified fixture citation"}</dd></div></dl><blockquote>{source.detail || `This fixture source anchors the reviewed evidence at ${source.anchor}. No original issuer file is bundled.`}</blockquote><button className="button primary" type="button" onClick={() => { onClose(); onNavigate(destination); }}>{destinationLabel} <ArrowRight size={16} /></button></aside></div>;
}

function AssistantChart({ data, onOpenCitation }) {
  const [showTable, setShowTable] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [focused, setFocused] = useState(false);
  const expandRef = useRef(null);
  const focusedRef = useRef(null);
  const specs = getAssistantChartSpecs(data);
  const spec = specs[selectedIndex] || specs[0];
  useEffect(() => {
    if (!focused) return undefined;
    window.setTimeout(() => focusedRef.current?.focus(), 0);
    return () => window.setTimeout(() => expandRef.current?.focus(), 0);
  }, [focused]);
  if (!spec) return <div className="assistant-chart-state" role="status"><Info size={18} /><span><strong>No validated chart proposal.</strong><small>The cited answer remains available without a visual.</small></span></div>;
  const currencyCode = spec.currency.split(" ")[0];
  const metric = { key: "value", label: spec.label, unit: spec.unit, color: "#5e4b8b", format: (value) => spec.metricKey === "revenue" ? `${currencyCode} ${Number(value).toLocaleString()}m` : `${Number(value).toLocaleString()}${spec.unit.includes("Percent") ? "%" : ""}` };
  const selectChart = (index, trigger) => {
    setSelectedIndex(index);
    setShowTable(false);
    const next = specs[index];
    if (next?.sources[0]) onOpenCitation(next.sources[0], trigger);
  };
  const move = (delta, trigger) => selectChart((selectedIndex + delta + specs.length) % specs.length, trigger);
  const onFocusedKeyDown = (event) => {
    if (!focused) return;
    if (event.key === "Escape") { event.preventDefault(); event.stopPropagation(); setFocused(false); return; }
    if (event.key !== "Tab") return;
    const focusable = [...focusedRef.current.querySelectorAll('button:not([disabled]), [tabindex="0"]')];
    if (!focusable.length) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && (document.activeElement === first || document.activeElement === focusedRef.current)) { event.preventDefault(); last.focus(); }
    if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
  };
  const card = <section ref={focused ? focusedRef : undefined} className={`assistant-chart-card ${focused ? "focused" : ""}`} role={focused ? "dialog" : undefined} aria-modal={focused ? "true" : undefined} aria-labelledby="assistant-chart-title" tabIndex={focused ? -1 : undefined} onKeyDown={onFocusedKeyDown}><div className="assistant-chart-toolbar"><div><span>Calculated from source data</span><h3 id="assistant-chart-title">{spec.title}</h3><small>{spec.series[0].period}–{spec.series[spec.series.length - 1].period} · {spec.unit}</small></div><button ref={expandRef} type="button" className="chart-focus-button" onClick={() => setFocused((current) => !current)} aria-label={focused ? "Close focused chart" : "Open focused chart"}>{focused ? <ArrowsIn size={17} /> : <ArrowsOut size={17} />}<span>{focused ? "Close focus" : "Focus chart"}</span></button></div>{specs.length > 1 && <div className="assistant-chart-nav"><div role="tablist" aria-label="Generated charts">{specs.map((item, index) => <button key={item.id} type="button" role="tab" aria-selected={index === selectedIndex} tabIndex={index === selectedIndex ? 0 : -1} onClick={(event) => selectChart(index, event.currentTarget)}>{item.label}</button>)}</div><span><button type="button" onClick={(event) => move(-1, event.currentTarget)} aria-label="Previous generated chart"><CaretLeft size={16} /></button><small>{selectedIndex + 1} / {specs.length}</small><button type="button" onClick={(event) => move(1, event.currentTarget)} aria-label="Next generated chart"><CaretRight size={16} /></button></span></div>}<div className="assistant-chart" role="img" tabIndex="0" aria-label={`${spec.title}, calculated from cited source data`}><Suspense fallback={<div className="chart-loading" role="status">Loading cited chart…</div>}><TrendChart trend={spec.series} metric={metric} /></Suspense></div><div className="assistant-chart-sources" aria-label="Chart sources">{spec.sources.map((source) => <button key={source.id} type="button" onClick={(event) => onOpenCitation(source, event.currentTarget)}><Files size={14} />{source.name}</button>)}</div><div className="assistant-chart-footer"><span>Validated chart proposal · deterministic values</span><button className="inline-link" type="button" aria-expanded={showTable} onClick={() => setShowTable((current) => !current)}>{showTable ? "Hide" : "View"} chart data table</button></div>{showTable && <div className="table-wrap"><table><caption>{spec.title}; calculated from source data</caption><thead><tr><th scope="col">Period</th><th scope="col">{spec.label}</th><th scope="col">Source</th></tr></thead><tbody>{spec.series.map((row) => <tr key={row.period}><th scope="row">{row.period}</th><td>{metric.format(row.value)}</td><td>{spec.sources[0].name}</td></tr>)}</tbody></table></div>}</section>;
  return focused ? <div className="focused-chart-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) setFocused(false); }}>{card}</div> : card;
}

const LIVE_STATE_LABELS = { not_configured: "Provider not configured", offline: "Provider offline", error: "Assistant error", loading: "Working…" };

function resolveLiveCitation(citation, data) {
  const fixtureCitation = data?.assistant?.citations?.find((item) => toIdentifier(item.id, "") === citation.evidence_id);
  if (fixtureCitation) return fixtureCitation;
  const source = data?.sources?.find((item) => toIdentifier(item.id, "") === citation.evidence_id);
  if (source) return source;
  return { id: citation.evidence_id, label: citation.label, anchor: citation.source_span_id, provenance: "Live provider citation", route: `/files#${citation.evidence_id}` };
}

function LiveTurn({ turn, data, onOpenCitation }) {
  if (turn.pending) return <div className="assistant-message" aria-live="polite" aria-busy="true"><div className="answer-block"><span className="loader" aria-hidden="true" /><p>Asking the configured provider…</p></div></div>;
  if (turn.error) return <div className="assistant-message"><div className="answer-block" role="alert"><span>Assistant unavailable</span><p>{turn.error}</p></div></div>;
  const result = turn.result || {};
  const answered = result.state === "completed" || result.state === "fallback";
  if (!answered) return <div className="assistant-message"><div className="answer-block" role="status"><span>{LIVE_STATE_LABELS[result.state] || "Assistant unavailable"}</span><p>{result.error?.message || result.disclosure || "The assistant could not answer this question."}</p></div></div>;
  return <div className="assistant-message" aria-live="polite"><div className="answer-block"><span>Assistant analysis</span><p>{result.content}</p></div>{Boolean(result.citations?.length) && <div className="assistant-source-pills" aria-label="Response sources">{result.citations.map((citation) => <button key={`${turn.id}-${citation.evidence_id}-${citation.source_span_id}`} type="button" onClick={(event) => onOpenCitation(resolveLiveCitation(citation, data), event.currentTarget)}><Files size={13} />{citation.label}</button>)}</div>}<small className="assistant-disclosure">{result.disclosure}</small></div>;
}

function AssistantPanel({ open, onClose, onOpenCitation, returnRef, data, initialMode = "verified_demo", sourceOpen = false }) {
  const panelRef = useRef(null);
  const conversationRef = useRef(null);
  const [mode, setMode] = useState(initialMode);
  const [suggestionId, setSuggestionId] = useState("growth");
  const [draft, setDraft] = useState("");
  const [turns, setTurns] = useState([]);
  const [sending, setSending] = useState(false);
  const [providerStatus, setProviderStatus] = useState(null);
  const response = useMemo(() => getAssistantAdapter(mode, data), [mode, data]);
  const selectedSuggestion = response.suggestions?.find((item) => item.id === suggestionId);
  const answer = selectedSuggestion ? { ...response, ...selectedSuggestion } : response;
  const evidence = useMemo(() => buildAssistantEvidence(data), [data]);
  const composerReady = evidence.length > 0;
  const canSend = composerReady && draft.trim().length > 0 && !sending;
  useDismissible(open, onClose, returnRef, panelRef);
  useEffect(() => {
    if (!open) return undefined;
    let cancelled = false;
    getModelProviderStatus().then((status) => { if (!cancelled) setProviderStatus(status); }).catch(() => { if (!cancelled) setProviderStatus({ state: "offline" }); });
    return () => { cancelled = true; };
  }, [open]);
  useEffect(() => {
    if (!open || !conversationRef.current) return;
    conversationRef.current.scrollTop = conversationRef.current.scrollHeight;
  }, [open, suggestionId, mode, turns]);
  const sendQuestion = async () => {
    const prompt = draft.trim();
    if (!prompt || sending || !composerReady) return;
    const id = `turn-${turns.length + 1}`;
    setSending(true);
    setDraft("");
    setTurns((current) => [...current, { id, prompt, pending: true }]);
    try {
      const result = await requestAssistant(buildAssistantRequest(prompt, data));
      setTurns((current) => current.map((turn) => (turn.id === id ? { ...turn, pending: false, result } : turn)));
    } catch (error) {
      setTurns((current) => current.map((turn) => (turn.id === id ? { ...turn, pending: false, error: error.message } : turn)));
    } finally {
      setSending(false);
    }
  };
  if (!open) return null;
  const liveTone = providerStatus?.state === "ready" ? "success" : providerStatus?.state === "offline" ? "warning" : "neutral";
  const liveLabel = providerStatus?.state === "ready" ? `Live provider ready · ${providerStatus.model}` : providerStatus ? LIVE_STATE_LABELS[providerStatus.state] || "Provider unavailable" : "Checking provider…";
  return <aside ref={panelRef} className="assistant-panel" role="dialog" aria-modal={sourceOpen ? undefined : "true"} aria-hidden={sourceOpen ? "true" : undefined} inert={sourceOpen} aria-labelledby="assistant-title" tabIndex="-1"><div className="panel-title"><div><p className="eyebrow">Magic Assistant</p><h2 id="assistant-title">Ask the fixture, inspect the evidence.</h2></div><button type="button" onClick={onClose} aria-label="Close Magic Assistant"><X size={20} /></button></div><StatusTag tone={mode === "verified_demo" ? "success" : mode === "error" || mode === "offline" ? "warning" : "neutral"}>{response.notice}</StatusTag><StatusTag tone={liveTone}>{liveLabel}</StatusTag>{mode === "verified_demo" ? <div ref={conversationRef} className="assistant-conversation"><section className="suggested-questions" aria-labelledby="suggested-title"><h3 id="suggested-title">Try a verified demo question</h3>{response.suggestions.map((item) => <button key={item.id} type="button" aria-pressed={suggestionId === item.id} onClick={() => setSuggestionId(item.id)}>{item.label}</button>)}</section><div className="user-message"><span>Selected question</span><p>{answer.label || answer.prompt}</p></div><div className="assistant-message" aria-live="polite"><div className="answer-block calculated"><span>Calculated result</span><strong>{answer.calculated}</strong><small>{answer.formula}</small></div><div className="answer-block"><span>Assistant analysis</span><p>{answer.analysis}</p></div><div className="assistant-source-pills" aria-label="Response sources">{response.citations.map((citation) => <button key={citation.id} type="button" onClick={(event) => onOpenCitation(citation, event.currentTarget)}><Files size={13} />{citation.label}</button>)}</div><AssistantChart data={data} onOpenCitation={onOpenCitation} /><div className="assistant-citations"><div><span>Cited sources</span><small>{response.citations.length} linked anchors</small></div>{response.citations.map((citation) => <button key={citation.id} type="button" onClick={(event) => onOpenCitation(citation, event.currentTarget)}><Files size={17} /><span><strong>{citation.label}</strong><small>{citation.detail}</small></span><CaretRight size={15} /></button>)}</div></div>{turns.map((turn) => <div key={turn.id} className="assistant-turn"><div className="user-message"><span>Your question</span><p>{turn.prompt}</p></div><LiveTurn turn={turn} data={data} onOpenCitation={onOpenCitation} /></div>)}</div> : <section className="assistant-state" role={mode === "error" ? "alert" : "status"} aria-busy={mode === "loading"}>{mode === "loading" ? <span className="loader" aria-hidden="true" /> : <Warning size={28} />}<h3>{response.notice}</h3><p>{response.analysis}</p>{mode === "error" && <button className="button secondary" type="button" onClick={() => setMode("verified_demo")}>Retry fixture demo</button>}</section>}<div className={`assistant-composer ${composerReady ? "" : "unavailable"}`}>{composerReady ? <p>Questions are answered only from the cited evidence on this session. No browser API key is used.</p> : <><strong>Free-form questions unavailable</strong><p>No cited evidence is loaded for this session, so a grounded question cannot be sent.</p></>}<div><textarea id="assistant-input" aria-label={composerReady ? "Ask a question about the cited evidence" : "Free-form questions unavailable"} rows="2" placeholder={composerReady ? "Ask about the cited evidence…" : "No cited evidence loaded"} disabled={!composerReady || sending} value={draft} onChange={(event) => setDraft(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); sendQuestion(); } }} onInput={(event) => { event.currentTarget.style.height = "auto"; event.currentTarget.style.height = `${event.currentTarget.scrollHeight}px`; }} /><button type="button" disabled={!canSend} onClick={sendQuestion} aria-label={sending ? "Sending message" : "Send message"}><PaperPlaneTilt size={18} /></button></div><small>Preview provider boundary states:</small><div className="state-switcher" aria-label="Assistant demo states">{["verified_demo", "not_configured", "offline", "loading", "error"].map((item) => <button type="button" key={item} aria-pressed={mode === item} onClick={() => setMode(item)}>{item.replaceAll("_", " ")}</button>)}</div></div></aside>;
}

function DeletedSessionState({ onRestore }) {
  return <section className="route-state receipt" aria-live="polite" tabIndex="-1"><span className="state-icon success"><Check size={24} weight="bold" aria-hidden="true" /></span><p className="eyebrow supported-text">Deletion receipt</p><h1>Demo session cleared.</h1><p>The Company, Sources, History, Review Desk, and Reports fixture views are cleared for this browser session. No server data existed.</p><button autoFocus className="button primary" type="button" onClick={onRestore}>Restore verified fixture</button></section>;
}

function AppShell({ route, onNavigate, assistantOpen, setAssistantOpen, assistantMode, initialProviderMode, productData, authState, authReturnTo, onAuthSignIn, onAuthSignOut }) {
  const [mobileOpen, setMobileOpen] = useState(false);
  const [source, setSource] = useState(null);
  const [sessionCleared, setSessionCleared] = useState(false);
  const [reducedMotion, setReducedMotion] = useState(() => window.matchMedia?.("(prefers-reduced-motion: reduce)").matches || false);
  const [compactSources, setCompactSources] = useState(false);
  const [analysisData, setAnalysisData] = useState(productData);
  const assistantButtonRef = useRef(null);
  const assistantReturnRef = useRef(null);
  const sourceReturnRef = useRef(null);
  const mobileMenuButtonRef = useRef(null);
  const mobilePanelRef = useRef(null);
  useDismissible(mobileOpen, () => setMobileOpen(false), mobileMenuButtonRef, mobilePanelRef);
  const data = adaptProductContract(analysisData);
  const openSource = (item, trigger) => { sourceReturnRef.current = trigger || document.activeElement; setSource(item); };
  const openAssistant = (trigger) => { assistantReturnRef.current = trigger || document.activeElement; setMobileOpen(false); setAssistantOpen(true); };
  const restoreFixture = () => { setSessionCleared(false); onNavigate("/company"); };
  const pages = {
    "/": <CompanyPage data={data} onNavigate={onNavigate} onOpenAssistant={openAssistant} onOpenSource={openSource} />,
    "/company": <CompanyPage data={data} onNavigate={onNavigate} onOpenAssistant={openAssistant} onOpenSource={openSource} />,
    "/files": <FilesPage data={data} onNavigate={onNavigate} onOpenSource={openSource} onFixtureReady={() => { setAnalysisData(productData); setSessionCleared(false); }} onAnalysisReady={(analysis) => { setAnalysisData(analysis); setSessionCleared(false); }} />,
    "/history": <HistoryPage data={data} onNavigate={onNavigate} />,
    "/review": <ReviewDesk onClearSession={() => setSessionCleared(true)} productData={data} />,
    "/reports": <ReportsPage data={data} onNavigate={onNavigate} />,
    "/profile": <ProfilePage />,
    "/settings": <SettingsPage reducedMotion={reducedMotion} compactSources={compactSources} onReducedMotion={setReducedMotion} onCompactSources={setCompactSources} initialProviderMode={initialProviderMode} />,
    "/sign-in": <SignInPage authState={authState} returnTo={authReturnTo} onSignIn={onAuthSignIn} onSignOut={onAuthSignOut} />,
    "/auth/callback": <AuthCallbackPage />,
    "/privacy": <PrivacyPage />,
    "/legal": <LegalPage />,
  };
  const protectedRoutes = new Set(["/", "/company", "/files", "/history", "/review", "/reports"]);
  const content = sessionCleared && protectedRoutes.has(route) ? <DeletedSessionState onRestore={restoreFixture} /> : pages[route] || <NotFoundPage onNavigate={onNavigate} />;
  const sourceOpen = Boolean(source);
  const navigateFromCitation = (destination) => { setAssistantOpen(false); onNavigate(destination); };
  return <div className={`product-shell ${assistantOpen ? "assistant-is-open" : ""} ${reducedMotion ? "reduced-motion" : ""} ${compactSources ? "compact-sources" : ""}`}><a className="skip-link" href="#main-content">Skip to content</a><MobileHeader backgroundInert={mobileOpen || assistantOpen || sourceOpen} menuButtonRef={mobileMenuButtonRef} onOpenNav={() => setMobileOpen(true)} onOpenAssistant={openAssistant} /><Sidebar backgroundInert={assistantOpen || sourceOpen} panelRef={mobilePanelRef} route={route} onNavigate={onNavigate} onOpenAssistant={openAssistant} assistantButtonRef={assistantButtonRef} mobileOpen={mobileOpen} onCloseMobile={() => setMobileOpen(false)} />{mobileOpen && <button className="nav-scrim" type="button" aria-label="Close navigation" onClick={() => setMobileOpen(false)} />}<main id="main-content" className="workspace" tabIndex="-1" aria-label={routeTitle(route)} inert={mobileOpen || assistantOpen || sourceOpen} aria-hidden={mobileOpen || assistantOpen || sourceOpen ? "true" : undefined}><div className="route-transition" key={route}>{content}</div></main><AssistantPanel data={data} open={assistantOpen} onClose={() => { if (!source) setAssistantOpen(false); }} onOpenCitation={openSource} returnRef={assistantReturnRef} initialMode={assistantMode} sourceOpen={sourceOpen} /><CitationDrawer source={source} onClose={() => setSource(null)} onNavigate={navigateFromCitation} returnRef={sourceReturnRef} /></div>;
}

export function App({ initialRoute, initialAssistantOpen = false, initialAssistantMode = "verified_demo", initialProviderMode = "not_configured", initialProductData = productFixture, authHandoffFactory = createMagicFinAuthHandoff }) {
  const [route, navigate] = useRoute(initialRoute);
  const [assistantOpen, setAssistantOpen] = useState(initialAssistantOpen);
  const authHandoffRef = useRef(null);
  if (!authHandoffRef.current) authHandoffRef.current = authHandoffFactory();
  const authHandoff = authHandoffRef.current;
  const [authState, setAuthState] = useState(authHandoff.auth.state);
  const authReturnToRef = useRef("/");
  useEffect(() => {
    const unsubscribe = authHandoff.auth.subscribe(setAuthState);
    void authHandoff.auth.initialize();
    return () => { unsubscribe(); authHandoff.auth.destroy(); };
  }, [authHandoff]);
  useEffect(() => {
    if (!["/sign-in", "/auth/callback"].includes(route)) authReturnToRef.current = route;
  }, [route]);
  useEffect(() => {
    if (route !== "/auth/callback") return undefined;
    let active = true;
    void authHandoff.handleCallback(window.location.href).then(({ returnTo }) => { if (active) navigate(returnTo); });
    return () => { active = false; };
  }, [authHandoff, route]);
  useEffect(() => {
    document.title = `${routeTitle(route)} · MagicFin`;
    const hash = window.location.hash.slice(1);
    if (!hash) return undefined;
    const timer = window.setTimeout(() => {
      const target = document.getElementById(hash);
      target?.focus({ preventScroll: false });
      target?.scrollIntoView({ block: "start" });
    }, 0);
    return () => window.clearTimeout(timer);
  }, [route]);
  return <AppShell route={route} onNavigate={navigate} assistantOpen={assistantOpen} setAssistantOpen={setAssistantOpen} assistantMode={initialAssistantMode} initialProviderMode={initialProviderMode} productData={initialProductData} authState={authState} authReturnTo={authReturnToRef.current} onAuthSignIn={() => authHandoff.auth.signInWithGoogle(authReturnToRef.current)} onAuthSignOut={() => authHandoff.auth.signOut()} />;
}
