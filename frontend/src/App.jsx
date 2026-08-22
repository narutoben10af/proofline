import { useEffect, useId, useRef, useState } from "react";
import {
  ArrowRight, CaretDown, Check, CheckCircle, FilePdf, Flag, Info,
  MagnifyingGlass, Question, Table, Trash, Warning, X,
} from "@phosphor-icons/react";
import { reviewFixture } from "./mock-contract";

export { reviewFixture } from "./mock-contract";

const statusItems = [
  { key: "supported", label: "Supported", icon: CheckCircle },
  { key: "uncertain", label: "Uncertain", icon: Question },
  { key: "contradicted", label: "Contradicted", icon: X },
];

function Header({ onDelete, onNewReview, deleteButtonRef }) {
  return (
    <header className="topbar">
      <button className="wordmark" type="button" onClick={onNewReview} aria-label="Proofline home">Proofline</button>
      <span className="topbar-divider" aria-hidden="true" />
      <span className="desk-label">Review Desk</span>
      <div className="review-context" aria-label="Current review">
        <span>{reviewFixture.meta.entity}</span><span aria-hidden="true">·</span><span>{reviewFixture.meta.period}</span>
      </div>
      <button ref={deleteButtonRef} className="text-button danger" type="button" onClick={onDelete}>
        <Trash size={17} aria-hidden="true" />Delete session
      </button>
    </header>
  );
}

function StatusSummary() {
  return (
    <section className="status-summary" aria-label="Finding summary">
      {statusItems.map(({ key, label, icon: Icon }) => (
        <div className={`status-item ${key}`} key={key}>
          <Icon size={25} aria-hidden="true" /><span>{label}</span><strong>{reviewFixture.summary[key]}</strong>
        </div>
      ))}
    </section>
  );
}

function VisualVerdict() {
  return (
    <section className="verdict" aria-labelledby="verdict-title">
      <p className="eyebrow contradicted-text">Contradicted claim</p>
      <h1 id="verdict-title">{reviewFixture.claim.text}</h1>
      <p className="verdict-intro">{reviewFixture.result.rationale}</p>
      <div className="section-label-row"><span>Visual verdict</span></div>
      <div className="comparison" aria-label="Claimed growth 8.2 percent; calculated growth 5.4 percent; discrepancy 2.8 percentage points">
        <div className="comparison-side claim-side"><span>Report narrative</span><strong>{reviewFixture.claim.value}</strong><small>Stated revenue growth (FY2024 → FY2025)</small></div>
        <div className="difference"><span className="difference-mark" aria-hidden="true"><X size={23} weight="bold" /></span><b>Contradicted</b><strong>{reviewFixture.result.difference}</strong><small>percentage points</small></div>
        <div className="comparison-side"><span>Deterministic evidence</span><strong>{reviewFixture.result.value}</strong><small>Calculated revenue growth (FY2024 → FY2025)</small></div>
      </div>
    </section>
  );
}

function ProofTrail() {
  const steps = [
    { title: "Claim", body: reviewFixture.claim.text, note: reviewFixture.claim.source },
    { title: "Cited inputs", body: `${reviewFixture.inputs[1].period} revenue ${reviewFixture.inputs[1].value}; ${reviewFixture.inputs[0].period} revenue ${reviewFixture.inputs[0].value}`, note: "Audited Consolidated Statements of Income" },
    { title: "Deterministic formula", body: "Revenue growth = (current-period revenue − prior-period revenue) ÷ prior-period revenue", note: reviewFixture.meta.registryVersion },
    { title: "Result", body: reviewFixture.formula, note: `Tolerance ${reviewFixture.result.tolerance}` },
  ];
  return (
    <section className="proof" aria-labelledby="proof-title">
      <div className="section-label-row"><span id="proof-title">Proof trail</span></div>
      <ol>{steps.map((step, index) => (
        <li key={step.title}><span className="step-number" aria-hidden="true">{index + 1}</span><div><h2>{step.title}</h2><p>{step.body}</p></div><small>{step.note}</small></li>
      ))}</ol>
    </section>
  );
}

function EvidenceDisclosure({ type, title, subtitle, children, defaultOpen = false }) {
  const [open, setOpen] = useState(defaultOpen);
  const panelId = useId();
  const Icon = type === "pdf" ? FilePdf : Table;
  return (
    <section className={`evidence-block ${open ? "open" : ""}`}>
      <button className="evidence-toggle" type="button" aria-expanded={open} aria-controls={panelId} onClick={() => setOpen((value) => !value)}>
        <Icon size={21} aria-hidden="true" /><span><strong>{title}</strong><small>{subtitle}</small></span><CaretDown size={17} className="caret" aria-hidden="true" />
      </button>
      <div className="evidence-content" id={panelId} hidden={!open}>{children}</div>
    </section>
  );
}

function EvidenceRail() {
  return (
    <aside className="evidence-rail" aria-labelledby="evidence-title">
      <div className="rail-heading"><div><p className="eyebrow" id="evidence-title">Evidence</p><span>Open only what you need</span></div><Info size={18} aria-label="Evidence retains source locations from the demo fixture" /></div>
      <EvidenceDisclosure type="pdf" title="Annual Report 2025" subtitle="Page 14 · native text" defaultOpen>
        <div className="pdf-excerpt"><span className="page-kicker">Management discussion</span><blockquote>“For the year, revenue growth was <mark>8.2%</mark>, reflecting continued demand across our core markets.”</blockquote><small>Highlighted claim · Page 14</small></div>
      </EvidenceDisclosure>
      <EvidenceDisclosure type="sheet" title="Financials_FY2025.xlsx" subtitle="Income Statement · B5:C5">
        <div className="table-wrap"><table><caption>Audited revenue inputs, USD millions</caption><thead><tr><th scope="col">Line item</th><th scope="col">FY2024</th><th scope="col">FY2025</th></tr></thead><tbody><tr><th scope="row">Revenue</th><td>2,234.2</td><td>2,354.8</td></tr></tbody></table><p className="cell-note">Cells {reviewFixture.inputs[0].cell} and {reviewFixture.inputs[1].cell}</p></div>
      </EvidenceDisclosure>
      <div className="fixture-note"><Info size={17} aria-hidden="true" /><p><strong>Demo data boundary</strong>This interface uses a human-verified mock contract. No issuer PDF or workbook is bundled.</p></div>
    </aside>
  );
}

function exportReviewedReport() {
  const report = {
    exportedAt: "2026-08-22T10:24:00+08:00",
    reviewStatus: "human_review_required",
    finding: reviewFixture,
    limitations: ["Demo fixture only", "Economic context is not evidence of cause", "No issuer documents are included"],
  };
  const blob = new Blob([JSON.stringify(report, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = "proofline-reviewed-report.json";
  anchor.click();
  URL.revokeObjectURL(url);
}

function ReviewActions({ onDecision }) {
  return (
    <div className="review-actions" aria-label="Review actions">
      <p><span>Human review required</span>Proofline identifies the disagreement; it does not infer its cause.</p>
      <div><button className="button quiet" type="button" onClick={() => { exportReviewedReport(); onDecision("Reviewed report exported"); }}>Export report</button><button className="button secondary" type="button" onClick={() => onDecision("Marked for investigation")}><Flag size={18} aria-hidden="true" />Mark for investigation</button><button className="button primary" type="button" onClick={() => onDecision("Finding confirmed")}><Check size={18} weight="bold" aria-hidden="true" />Confirm finding</button></div>
    </div>
  );
}

function ReviewDesk({ onDelete, onNewReview, deleteButtonRef, cached = false }) {
  const [announcement, setAnnouncement] = useState("");
  return (
    <div className="app-shell"><a className="skip-link" href="#review-content">Skip to review</a><Header onDelete={onDelete} onNewReview={onNewReview} deleteButtonRef={deleteButtonRef} />{cached && <div className="cache-banner" role="status"><Info size={18} aria-hidden="true" /><span><strong>Verified fallback loaded.</strong> Live extraction was unavailable, so this review uses the versioned cached demo result.</span></div>}<main id="review-content" className="review-layout" tabIndex="-1"><div className="review-main"><StatusSummary /><VisualVerdict /><ProofTrail /><ReviewActions onDecision={setAnnouncement} /></div><EvidenceRail /></main>
      {announcement && <div className="toast" role="status"><CheckCircle size={20} weight="fill" aria-hidden="true" /><span><strong>{announcement}</strong><small>Recorded for this demo session.</small></span><button type="button" onClick={() => setAnnouncement("")} aria-label="Dismiss notification"><X size={16} /></button></div>}
    </div>
  );
}

function EmptyState({ onFilesSelected }) {
  const inputRef = useRef(null);
  return (
    <main className="state-page"><div className="state-wordmark">Proofline <span>Review Desk</span></div><section className="state-panel empty-panel" tabIndex="-1"><p className="eyebrow">New review</p><h1>Every financial claim needs a receipt.</h1><p>Select one allowlisted public PDF and its matching workbook. This prototype accepts filenames only and loads a verified mock result; it does not upload document contents.</p><input ref={inputRef} className="visually-hidden" type="file" multiple accept=".pdf,.xlsx" onChange={(event) => onFilesSelected([...event.target.files])} /><button autoFocus className="button primary" type="button" onClick={() => inputRef.current?.click()}>Select demo files <ArrowRight size={18} aria-hidden="true" /></button><div className="public-notice"><Info size={18} aria-hidden="true" /><span><strong>Public demo data only.</strong> Do not select confidential or personal documents.</span></div></section></main>
  );
}

function LoadingState() {
  const stages = ["Checking file types", "Validating mock contract", "Calculating registered metrics"];
  return (
    <main className="state-page" aria-live="polite" aria-busy="true"><div className="state-wordmark">Proofline <span>Review Desk</span></div><section className="state-panel" tabIndex="-1"><span className="loader" aria-hidden="true" /><p className="eyebrow">Preparing review</p><h1>Following the evidence trail.</h1><ul className="progress-list">{stages.map((stage, index) => <li key={stage} className={index < 2 ? "done" : "active"}>{index < 2 ? <Check size={16} /> : <MagnifyingGlass size={16} />} {stage}</li>)}</ul><p className="state-note">This mock processing state never implies that every page or cell was successfully parsed.</p></section></main>
  );
}

function ErrorState({ onRetry }) {
  return (
    <main className="state-page" role="alert"><div className="state-wordmark">Proofline <span>Review Desk</span></div><section className="state-panel"><span className="state-icon error"><Warning size={28} weight="fill" aria-hidden="true" /></span><p className="eyebrow contradicted-text">Files not accepted</p><h1>Choose one PDF and one workbook.</h1><p>The selected files did not match this prototype’s narrow input contract. Nothing was uploaded or retained.</p><button autoFocus className="button primary" type="button" onClick={onRetry}>Choose different files</button></section></main>
  );
}

function DeleteDialog({ onCancel, onConfirm }) {
  const titleId = useId();
  const cancelRef = useRef(null);
  useEffect(() => {
    cancelRef.current?.focus();
    const handleKeyDown = (event) => { if (event.key === "Escape") onCancel(); };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onCancel]);
  return (
    <div className="modal-backdrop" role="presentation"><section className="dialog" role="dialog" aria-modal="true" aria-labelledby={titleId}><span className="state-icon error"><Trash size={24} aria-hidden="true" /></span><p className="eyebrow contradicted-text">Delete session</p><h1 id={titleId}>Remove this review?</h1><p>This clears the in-browser demo state. The prototype has no database and does not claim deletion from systems it does not use.</p><div className="dialog-actions"><button ref={cancelRef} className="button secondary" type="button" onClick={onCancel}>Keep review</button><button className="button danger-button" type="button" onClick={onConfirm}>Delete session</button></div></section></div>
  );
}

function Receipt({ onStart }) {
  return (
    <main className="state-page" aria-live="polite"><div className="state-wordmark">Proofline <span>Review Desk</span></div><section className="state-panel receipt"><span className="state-icon success"><Check size={26} weight="bold" aria-hidden="true" /></span><p className="eyebrow supported-text">Deletion receipt</p><h1>Session cleared.</h1><dl><div><dt>Scope</dt><dd>In-browser demo review state</dd></div><div><dt>Completed</dt><dd>22 August 2026 · 10:24 MYT</dd></div><div><dt>Receipt</dt><dd>PL-DEMO-0822-1024</dd></div></dl><button autoFocus className="button primary" type="button" onClick={onStart}>Start a new review</button></section></main>
  );
}

export function App({ initialScreen = "review", processingDelay = 850 }) {
  const [screen, setScreen] = useState(initialScreen);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const deleteButtonRef = useRef(null);
  useEffect(() => {
    if (screen !== "loading") return undefined;
    const timer = window.setTimeout(() => setScreen("cached"), processingDelay);
    return () => window.clearTimeout(timer);
  }, [screen, processingDelay]);
  function handleFiles(files) {
    const extensions = files.map((file) => file.name.split(".").pop()?.toLowerCase());
    setScreen(files.length === 2 && extensions.includes("pdf") && extensions.includes("xlsx") ? "loading" : "error");
  }
  if (screen === "empty") return <EmptyState onFilesSelected={handleFiles} />;
  if (screen === "loading") return <LoadingState />;
  if (screen === "error") return <ErrorState onRetry={() => setScreen("empty")} />;
  if (screen === "receipt") return <Receipt onStart={() => setScreen("empty")} />;
  const closeDelete = () => { setDeleteOpen(false); window.setTimeout(() => deleteButtonRef.current?.focus(), 0); };
  return <><ReviewDesk cached={screen === "cached"} deleteButtonRef={deleteButtonRef} onDelete={() => setDeleteOpen(true)} onNewReview={() => setScreen("empty")} />{deleteOpen && <DeleteDialog onCancel={closeDelete} onConfirm={() => { setDeleteOpen(false); setScreen("receipt"); }} />}</>;
}
