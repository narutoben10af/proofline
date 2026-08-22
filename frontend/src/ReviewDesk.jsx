import { useEffect, useId, useRef, useState } from "react";
import {
  CaretDown, Check, CheckCircle, FilePdf, Flag, Info, Question, Table, Trash, X,
} from "@phosphor-icons/react";
import { buildReviewedReport } from "./product-contract";
import { reviewFixture } from "./mock-contract";

const statusItems = [
  { key: "supported", label: "Supported", icon: CheckCircle },
  { key: "uncertain", label: "Uncertain", icon: Question },
  { key: "contradicted", label: "Contradicted", icon: X },
];

export function downloadReviewedReport(onComplete = () => {}, productData) {
  const blob = new Blob([JSON.stringify(buildReviewedReport(productData), null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = "magicfin-reviewed-report.json";
  anchor.click();
  URL.revokeObjectURL(url);
  onComplete("Reviewed evidence JSON downloaded");
}

function StatusSummary({ review }) {
  return (
    <section className="status-summary" aria-label="Finding summary">
      {statusItems.map(({ key, label, icon: Icon }) => (
        <div className={`status-item ${key}`} key={key}>
          <Icon size={24} aria-hidden="true" /><span>{label}</span><strong>{review.summary[key]}</strong>
        </div>
      ))}
    </section>
  );
}

function VisualVerdict({ review }) {
  return (
    <section className="verdict" aria-labelledby="verdict-title">
      <p className="eyebrow contradicted-text">What was claimed</p>
      <h1 id="verdict-title">{review.claim.text}</h1>
      <p className="verdict-intro">{review.result.rationale}</p>
      <div className="section-label-row"><span>Visual verdict</span></div>
      <div className="comparison" aria-label="Claimed growth 8.2 percent; calculated growth 5.4 percent; discrepancy 2.8 percentage points">
        <div className="comparison-side claim-side"><span>What was claimed</span><strong>{review.claim.value}</strong><small>Stated result for the reviewed period</small></div>
        <div className="difference"><span className="difference-mark" aria-hidden="true"><X size={22} weight="bold" /></span><b>Why it matters</b><strong>{review.result.difference}</strong><small>difference requiring review</small></div>
        <div className="comparison-side"><span>What the numbers show</span><strong>{review.result.value}</strong><small>Calculated result from cited inputs</small></div>
      </div>
    </section>
  );
}

function ProofTrail({ review }) {
  const steps = [
    { title: "What was claimed", body: review.claim.text, note: review.claim.source },
    { title: "What the numbers show", body: `${review.inputs[1].period} revenue ${review.inputs[1].value}; ${review.inputs[0].period} revenue ${review.inputs[0].value}`, note: "Cited financial statement inputs" },
    { title: "How it was calculated", body: "Revenue growth = (current-period revenue − prior-period revenue) ÷ prior-period revenue", note: review.meta.registryVersion },
    { title: "Why it matters", body: review.formula, note: `Difference threshold ${review.result.tolerance}` },
  ];
  return (
    <section className="proof" aria-labelledby="proof-title">
      <div className="section-label-row"><span id="proof-title">Proof trail</span></div>
      <ol>{steps.map((step, index) => (
        <li key={step.title}><span className="step-number" aria-hidden="true">{index + 1}</span><div><h2>{step.title}</h2><p>{step.body}</p><details><summary>Technical details</summary><small>{step.note}</small></details></div></li>
      ))}</ol>
    </section>
  );
}

function EvidenceDisclosure({ type, title, subtitle, id, children, defaultOpen = false }) {
  const [open, setOpen] = useState(defaultOpen);
  const generatedId = useId();
  const panelId = `${id || generatedId}-panel`;
  const Icon = type === "pdf" ? FilePdf : Table;
  return (
    <section className={`evidence-block ${open ? "open" : ""}`} id={id} tabIndex="-1">
      <button className="evidence-toggle" type="button" aria-expanded={open} aria-controls={panelId} onClick={() => setOpen((value) => !value)}>
        <Icon size={21} aria-hidden="true" /><span><strong>{title}</strong><small>{subtitle}</small></span><CaretDown size={17} className="caret" aria-hidden="true" />
      </button>
      <div className="evidence-content" id={panelId} hidden={!open}>{children}</div>
    </section>
  );
}

function EvidenceRail({ review, sources }) {
  const reportSource = sources?.[0];
  const workbookSource = sources?.[1];
  return (
    <aside className="evidence-rail" aria-labelledby="evidence-title">
      <div className="rail-heading"><div><p className="eyebrow" id="evidence-title">Open source</p><span>Open only when you need the original wording or numbers</span></div><Info size={18} aria-label="Sources retain their quoted page or cell locations" /></div>
      <EvidenceDisclosure id="annual-report" type="pdf" title={reportSource?.name || "Annual report"} subtitle={`Quoted source · ${reportSource?.anchor || "cited page"}`} defaultOpen>
        <div className="pdf-excerpt"><span className="page-kicker">Quoted narrative</span><blockquote>“{review.claim.text}”</blockquote><small>Highlighted claim · {reportSource?.anchor || review.claim.source}</small></div>
      </EvidenceDisclosure>
      <EvidenceDisclosure id="financials" type="sheet" title={workbookSource?.name || "Financial workbook"} subtitle={workbookSource?.anchor || "Cited cells"} defaultOpen={window.location.hash === "#financials"}>
        <div className="table-wrap"><table><caption>Cited revenue inputs</caption><thead><tr><th scope="col">Line item</th><th scope="col">{review.inputs[0].period}</th><th scope="col">{review.inputs[1].period}</th></tr></thead><tbody><tr><th scope="row">Revenue</th><td>{review.inputs[0].value}</td><td>{review.inputs[1].value}</td></tr></tbody></table><p className="cell-note">Cells {review.inputs[0].cell} and {review.inputs[1].cell}</p></div>
      </EvidenceDisclosure>
      <div className="fixture-note"><Info size={17} aria-hidden="true" /><p><strong>Demo data boundary</strong>This interface uses a human-verified mock contract. No issuer PDF or workbook is bundled.</p></div>
    </aside>
  );
}

function DeleteDialog({ onCancel, onConfirm, returnRef }) {
  const titleId = useId();
  const cancelRef = useRef(null);
  const confirmRef = useRef(null);
  useEffect(() => {
    cancelRef.current?.focus();
    const handleKeyDown = (event) => {
      if (event.key === "Escape") onCancel();
      if (event.key === "Tab") {
        const next = event.shiftKey ? confirmRef.current : cancelRef.current;
        if ((event.shiftKey && document.activeElement === cancelRef.current) || (!event.shiftKey && document.activeElement === confirmRef.current)) {
          event.preventDefault();
          next?.focus();
        }
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => { window.removeEventListener("keydown", handleKeyDown); returnRef?.current?.focus(); };
  }, [onCancel, returnRef]);
  return (
    <div className="modal-backdrop" role="presentation"><section className="dialog" role="dialog" aria-modal="true" aria-labelledby={titleId}><span className="state-icon error"><Trash size={24} aria-hidden="true" /></span><p className="eyebrow contradicted-text">Delete session</p><h1 id={titleId}>Clear this demo review?</h1><p>This removes session-local interface state only. MagicFin does not claim deletion from a database or storage service it does not use.</p><div className="dialog-actions"><button ref={cancelRef} className="button secondary" type="button" onClick={onCancel}>Keep review</button><button ref={confirmRef} className="button danger-button" type="button" onClick={onConfirm}>Clear demo session</button></div></section></div>
  );
}

export function ReviewDesk({ onClearSession, productData }) {
  const review = productData?.review || reviewFixture;
  const [announcement, setAnnouncement] = useState("");
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [decision, setDecision] = useState("Human review required");
  const deleteRef = useRef(null);
  const recordDecision = (next) => { setDecision(next); setAnnouncement(`${next} for this demo session`); };

  return (
    <>
      <div className="review-route-header"><div><p className="eyebrow">Review Desk</p><h1>One claim. Every receipt.</h1><p>Compare the narrative with cited inputs and a deterministic formula.</p></div><button ref={deleteRef} className="text-button danger" type="button" onClick={() => setDeleteOpen(true)}><Trash size={17} aria-hidden="true" />Clear session</button></div>
      <div className="cache-banner" role="status"><Info size={18} aria-hidden="true" /><span><strong>Verified fixture loaded.</strong> No issuer document contents are uploaded or retained.</span></div>
      <div className="review-layout"><div className="review-main"><StatusSummary review={review} /><VisualVerdict review={review} /><ProofTrail review={review} /><div className="review-actions" aria-label="Review actions"><p className="review-decision" aria-live="polite"><span>Review status: {decision}</span>MagicFin identifies the disagreement; it does not infer its cause.</p><div><button className="button quiet" type="button" onClick={() => downloadReviewedReport(setAnnouncement, productData)}>Export JSON</button><button className="button secondary" type="button" aria-pressed={decision === "Marked for investigation"} onClick={() => recordDecision("Marked for investigation")}><Flag size={18} aria-hidden="true" />Mark for investigation</button><button className="button primary" type="button" aria-pressed={decision === "Finding confirmed"} onClick={() => recordDecision("Finding confirmed")}><Check size={18} weight="bold" aria-hidden="true" />Confirm finding</button></div></div></div><EvidenceRail review={review} sources={productData?.sources} /></div>
      {announcement && <div className="toast" role="status"><CheckCircle size={20} weight="fill" aria-hidden="true" /><span><strong>{announcement}</strong><small>Visible until this demo session is cleared.</small></span><button type="button" onClick={() => setAnnouncement("")} aria-label="Dismiss notification"><X size={16} /></button></div>}
      {deleteOpen && <DeleteDialog returnRef={deleteRef} onCancel={() => setDeleteOpen(false)} onConfirm={() => { setDeleteOpen(false); onClearSession(); }} />}
    </>
  );
}
