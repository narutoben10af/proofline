import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { App, productFixture } from "./App";
import { MAX_REVIEWED_REPORT_PDF_BYTES, requestReviewedPdf } from "./product-contract";

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  window.history.replaceState({}, "", "/");
});

describe("MagicFin product shell", () => {
  it("renders the approved full navigation and truthful Home entry", () => {
    render(<App initialRoute="/" />);
    expect(screen.getByRole("heading", { name: /northstar industrial plc/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /run magic/i })).toBeInTheDocument();
    const nav = screen.getByRole("navigation", { name: /main navigation/i });
    for (const label of ["Home", "Files & Sources", "History", "Review Desk", "Reports"]) {
      expect(within(nav).getByRole("button", { name: label })).toBeInTheDocument();
    }
    expect(within(nav).queryByRole("button", { name: "Source Library" })).not.toBeInTheDocument();
    expect(within(nav).queryByRole("button", { name: "Company" })).not.toBeInTheDocument();
    expect(screen.queryByText(/^Verified fixture$/i)).not.toBeInTheDocument();
    expect(screen.getByText("Demo data · human-checked")).toBeInTheDocument();
    expect(document.title).toBe("Home · MagicFin");
  });

  it("navigates to Company and exposes the source-linked trend table", async () => {
    const user = userEvent.setup();
    render(<App initialRoute="/" />);
    await user.click(screen.getByRole("button", { name: /run magic/i }));
    expect(screen.getByRole("heading", { name: /northstar industrial plc/i })).toBeInTheDocument();
    expect(screen.getByText("Annual_Report_2025.pdf")).toBeInTheDocument();
    const tableToggle = screen.getByRole("button", { name: /view accessible data table/i });
    await user.click(tableToggle);
    expect(screen.getByRole("table", { name: /revenue, usd millions; reported data/i })).toBeVisible();
  });

  it("keeps polished trend controls as labelled keyboard-focusable native selects", async () => {
    const user = userEvent.setup();
    render(<App initialRoute="/" />);
    const metric = screen.getByRole("combobox", { name: /trend metric/i });
    const period = screen.getByRole("combobox", { name: /period range/i });
    expect(metric.tagName).toBe("SELECT");
    expect(period.tagName).toBe("SELECT");
    metric.focus();
    expect(metric).toHaveFocus();
    await user.selectOptions(metric, "operatingMargin");
    expect(metric).toHaveValue("operatingMargin");
    expect(screen.getByText("Operating margin", { selector: ".trend-selection strong" })).toBeInTheDocument();
    period.focus();
    expect(period).toHaveFocus();
    await user.selectOptions(period, "latest-3");
    expect(period).toHaveValue("latest-3");
    expect(screen.getByRole("img", { name: /operating margin, percent, reported history from FY2023 through FY2025/i })).toBeInTheDocument();
  });

  it("updates the selected range with keyboard-compatible native sliders and a table fallback", async () => {
    const user = userEvent.setup();
    render(<App initialRoute="/" />);
    const start = screen.getByRole("slider", { name: /range start/i });
    start.focus();
    await user.keyboard("{ArrowRight}");
    fireEvent.change(start, { target: { value: "1" } });
    expect(start).toHaveAttribute("aria-valuetext", "FY2023");
    expect(screen.getByText(/FY2023 — FY2025/i)).toBeInTheDocument();
    expect(screen.getByText(/3 reported periods selected/i)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /view accessible data table/i }));
    const table = screen.getByRole("table", { name: /revenue, usd millions; reported data/i });
    expect(within(table).queryByText("FY2022")).not.toBeInTheDocument();
    expect(within(table).getAllByText("Reported history")).toHaveLength(3);
  });

  it("enumerates deterministic Run Magic stages and completes truthfully", async () => {
    vi.useFakeTimers();
    try {
      render(<App initialRoute="/company" />);
      fireEvent.click(screen.getByRole("button", { name: /^run magic$/i }));
      expect(screen.getByText(/running deterministic checks/i)).toBeInTheDocument();
      for (const stage of ["Validate sources", "Extract claims", "Calculate metrics", "Link evidence", "Flag discrepancies"]) expect(screen.getAllByText(stage).length).toBeGreaterThan(0);
      await act(async () => { vi.advanceTimersByTime(2200); });
      expect(screen.getByText(/evidence trail ready/i)).toBeInTheDocument();
    } finally {
      vi.useRealTimers();
    }
  });

  it("keeps the populated dashboard visible throughout Run Magic", async () => {
    vi.useFakeTimers();
    try {
      render(<App initialRoute="/" />);
      fireEvent.click(screen.getByRole("button", { name: /^run magic$/i }));
      expect(screen.getByRole("heading", { name: /northstar industrial plc/i })).toBeInTheDocument();
      expect(screen.getByRole("heading", { name: /the four numbers to orient the review/i })).toBeInTheDocument();
      expect(screen.getByText(/running deterministic checks/i)).toBeInTheDocument();
      await act(async () => { vi.advanceTimersByTime(2200); });
      expect(screen.getByText(/evidence trail ready/i)).toBeInTheDocument();
      expect(document.title).toBe("Home · MagicFin");
    } finally {
      vi.useRealTimers();
    }
  });

  it("puts headline metrics and the dominant trend before source cards", () => {
    render(<App initialRoute="/" />);
    const metrics = screen.getByRole("heading", { name: /the four numbers to orient the review/i }).closest("section");
    const trend = screen.getByRole("heading", { name: /performance trend/i }).closest("section");
    const sources = screen.getByRole("heading", { name: /claims stay with their numbers/i }).closest("section");
    expect(metrics.compareDocumentPosition(trend) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(trend.compareDocumentPosition(sources) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    for (const value of ["$2,354.8m", "18.6%", "1.42×", "12.8%"])
      expect(within(metrics).getByText(value)).toBeInTheDocument();
    expect(metrics).toHaveTextContent(/FY2025/);
    expect(metrics).toHaveTextContent(/Source/);
  });

  it("opens the four headline metric definitions by keyboard and restores focus", async () => {
    const user = userEvent.setup();
    render(<App initialRoute="/" />);
    for (const [name, copy] of [
      ["Revenue", /recognized sales and service income/i],
      ["Operating margin", /operating profit ÷ revenue × 100/i],
      ["Current ratio", /may be less meaningful for banks/i],
      ["Free-cash-flow margin", /project-defined metric/i],
    ]) {
      const trigger = screen.getByRole("button", { name: `Define ${name}` });
      trigger.focus();
      await user.keyboard("{Enter}");
      const dialog = screen.getByRole("dialog", { name });
      expect(dialog).toHaveTextContent(copy);
      expect(within(dialog).getByRole("link", { name: /open source or method/i })).toHaveAttribute("href", "/files#sources");
      await user.keyboard("{Escape}");
      expect(dialog).not.toBeInTheDocument();
      expect(trigger).toHaveFocus();
    }
  });

  it("opens and closes the cited assistant with Escape and restores focus", async () => {
    const user = userEvent.setup();
    render(<App initialRoute="/company" />);
    const trigger = screen.getByRole("button", { name: /magic assistant fixture answers/i });
    await user.click(trigger);
    const dialog = screen.getByRole("dialog", { name: /ask the fixture, inspect the evidence/i });
    expect(dialog).toHaveTextContent("Calculated result");
    expect(dialog).toHaveTextContent("Assistant analysis");
    expect(dialog).toHaveTextContent(/provider not configured/i);
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog", { name: /ask the fixture, inspect the evidence/i })).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();
  });

  it("opens a cited source drawer and deep-links to Review Desk evidence", async () => {
    const user = userEvent.setup();
    render(<App initialRoute="/company" initialAssistantOpen />);
    await user.click(screen.getAllByRole("button", { name: /annual report 2025/i }).at(-1));
    const drawer = screen.getByRole("dialog", { name: /annual report 2025/i });
    expect(drawer).toHaveTextContent(/quoted verified fixture/i);
    await user.click(within(drawer).getByRole("button", { name: /open in review desk/i }));
    expect(screen.getByRole("heading", { name: /one claim. every receipt/i })).toBeInTheDocument();
  });

  it("offers working fixture questions and clearly disables free-form chat", async () => {
    const user = userEvent.setup();
    render(<App initialRoute="/" initialAssistantOpen />);
    const dialog = screen.getByRole("dialog", { name: /ask the fixture, inspect the evidence/i });
    expect(within(dialog).getByRole("heading", { name: /try a verified demo question/i })).toBeInTheDocument();
    await user.click(within(dialog).getByRole("button", { name: /which sources/i }));
    expect(dialog).toHaveTextContent(/Annual Report 2025/);
    await user.click(within(dialog).getByRole("button", { name: /what can this demo not do/i }));
    expect(dialog).toHaveTextContent(/does not upload files, persist data, call a live model, or create a live-session report/i);
    expect(within(dialog).getByRole("textbox", { name: /free-form questions unavailable/i })).toBeDisabled();
    expect(dialog).toHaveTextContent(/Connect a server-side model provider/);
  });

  it("renders a validated assistant chart from source values with citations and table fallback", async () => {
    const user = userEvent.setup();
    render(<App initialRoute="/" initialAssistantOpen />);
    const dialog = screen.getByRole("dialog", { name: /ask the fixture/i });
    expect(within(dialog).getByText("Calculated from source data")).toBeInTheDocument();
    expect(within(dialog).getByRole("img", { name: /reported revenue trajectory, calculated from cited source data/i })).toBeInTheDocument();
    await user.click(within(dialog).getByRole("button", { name: /view chart data table/i }));
    const table = within(dialog).getByRole("table", { name: /reported revenue trajectory; calculated from source data/i });
    expect(table).toHaveTextContent("FY2022");
    expect(table).toHaveTextContent("Financials_FY2025.xlsx");
  });

  it("synchronizes a selected generated chart with its cited source drawer", async () => {
    const user = userEvent.setup();
    render(<App initialRoute="/" initialAssistantOpen />);
    const dialog = screen.getByRole("dialog", { name: /ask the fixture/i });
    const marginTab = within(dialog).getByRole("tab", { name: /operating margin/i });
    await user.click(marginTab);
    const drawer = screen.getByRole("dialog", { name: /financials_fy2025.xlsx/i });
    expect(drawer).toHaveTextContent(/income statement b5:c5/i);
    await user.keyboard("{Escape}");
    expect(drawer).not.toBeInTheDocument();
    expect(marginTab).toHaveFocus();
    expect(within(dialog).getByRole("img", { name: /operating-margin trajectory/i })).toBeInTheDocument();
  });

  it("navigates generated charts and opens a keyboard-dismissible focused workspace", async () => {
    const user = userEvent.setup();
    render(<App initialRoute="/" initialAssistantOpen />);
    const dialog = screen.getByRole("dialog", { name: /ask the fixture/i });
    await user.click(within(dialog).getByRole("button", { name: /open focused chart/i }));
    const focused = screen.getByRole("dialog", { name: /reported revenue trajectory/i });
    expect(focused).toBeInTheDocument();
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog", { name: /reported revenue trajectory/i })).not.toBeInTheDocument();
    expect(within(dialog).getByRole("button", { name: /open focused chart/i })).toHaveFocus();
  });

  it("shows an honest error for files outside the narrow fixture contract", async () => {
    const user = userEvent.setup();
    render(<App initialRoute="/files" />);
    const input = document.querySelector('input[type="file"]');
    await user.upload(input, new File(["demo"], "report.pdf", { type: "application/pdf" }));
    expect(screen.getByRole("heading", { name: /source set needs attention/i })).toBeInTheDocument();
    expect(screen.getByText(/nothing was uploaded, read, or retained/i)).toBeInTheDocument();
  });

  it("accepts only the named PDF and XLSX fixture pair and enables the workspace", async () => {
    vi.useFakeTimers();
    try {
      render(<App initialRoute="/files" />);
      const input = document.querySelector('input[type="file"]');
      fireEvent.change(input, { target: { files: [
        new File(["fixture"], "Annual_Report_2025.pdf", { type: "application/pdf" }),
        new File(["fixture"], "Financials_FY2025.xlsx", { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" }),
      ] } });
      expect(screen.getByText(/following the fixture evidence trail/i)).toBeInTheDocument();
      await act(async () => { vi.advanceTimersByTime(1400); });
      expect(screen.getByRole("heading", { name: /sources are ready/i })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /open company workspace/i })).toBeEnabled();
    } finally {
      vi.useRealTimers();
    }
  });

  it("combines upload and a searchable Source Library while preserving old source deep links", async () => {
    const user = userEvent.setup();
    render(<App initialRoute="/files" />);
    expect(screen.getByRole("heading", { name: /bring the report and the numbers together/i })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /evidence with a visible address/i })).toBeInTheDocument();
    await user.type(screen.getByRole("searchbox", { name: /search sources/i }), "earnings");
    expect(screen.getByRole("heading", { name: /earnings_release_q4.pdf/i })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: /management_notes.xlsx/i })).not.toBeInTheDocument();
    await user.clear(screen.getByRole("searchbox", { name: /search sources/i }));
    await user.selectOptions(screen.getByRole("combobox", { name: /filter sources by status/i }), "attention");
    expect(screen.getByRole("heading", { name: /earnings_release_q4.pdf/i })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: /annual_report_2025.pdf/i })).not.toBeInTheDocument();
  });

  it("redirects the old Source Library route to the exact Files & Sources anchor", async () => {
    window.history.replaceState({}, "", "/sources#notes");
    render(<App />);
    await waitFor(() => expect(window.location.pathname).toBe("/files"));
    expect(window.location.hash).toBe("#notes");
    await waitFor(() => expect(document.getElementById("notes")).toHaveFocus());
  });

  it("exports reviewed JSON alongside the deterministic demo PDF", async () => {
    const user = userEvent.setup();
    const createObjectURL = vi.fn(() => "blob:report");
    const revokeObjectURL = vi.fn();
    Object.defineProperty(URL, "createObjectURL", { configurable: true, value: createObjectURL });
    Object.defineProperty(URL, "revokeObjectURL", { configurable: true, value: revokeObjectURL });
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
    render(<App initialRoute="/reports" />);
    await user.click(screen.getByRole("button", { name: /download json/i }));
    expect(createObjectURL).toHaveBeenCalledOnce();
    expect(screen.getByText(/reviewed evidence json downloaded/i).closest('[role="status"]')).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /prepare demo pdf/i }));
    expect(screen.getByRole("button", { name: /preparing pdf/i })).toBeDisabled();
    await waitFor(() => expect(screen.getByText(/demo performance brief downloaded/i)).toBeInTheDocument());
    expect(createObjectURL).toHaveBeenCalledTimes(2);
    expect(screen.queryByText(/endpoint/i)).not.toBeInTheDocument();
  });

  it("downloads a live reviewed PDF from the typed report bundle and cleans up its object URL", async () => {
    const user = userEvent.setup();
    const reportBundle = { schema_version: "1.0.0", company: "Northstar Industrial plc" };
    const live = { ...productFixture, session: { ...productFixture.session, mode: "live" }, reportBundle };
    let resolveFetch;
    const fetchMock = vi.fn(() => new Promise((resolve) => { resolveFetch = resolve; }));
    vi.stubGlobal("fetch", fetchMock);
    const createObjectURL = vi.fn(() => "blob:reviewed-pdf");
    const revokeObjectURL = vi.fn();
    Object.defineProperty(URL, "createObjectURL", { configurable: true, value: createObjectURL });
    Object.defineProperty(URL, "revokeObjectURL", { configurable: true, value: revokeObjectURL });
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
    render(<App initialRoute="/reports" initialProductData={live} />);
    await user.click(screen.getByRole("button", { name: /^download pdf$/i }));
    expect(screen.getByRole("button", { name: /preparing pdf/i })).toBeDisabled();
    resolveFetch(new Response(new Blob(["%PDF-1.7 demo"], { type: "application/pdf" }), { status: 200, headers: { "Content-Type": "application/pdf", "Content-Disposition": 'attachment; filename="northstar-reviewed.pdf"' } }));
    await waitFor(() => expect(screen.getByText(/northstar-reviewed.pdf downloaded/i)).toBeInTheDocument());
    expect(fetchMock).toHaveBeenCalledWith("/api/v1/reports/pdf", expect.objectContaining({ method: "POST", credentials: "same-origin", body: JSON.stringify(reportBundle) }));
    expect(createObjectURL).toHaveBeenCalledOnce();
    expect(click).toHaveBeenCalledOnce();
    expect(revokeObjectURL).toHaveBeenCalledWith("blob:reviewed-pdf");
  });

  it("rejects non-PDF and oversized report responses and exposes retry", async () => {
    const user = userEvent.setup();
    const live = { ...productFixture, session: { ...productFixture.session, mode: "live" }, reportBundle: { schema_version: "1.0.0" } };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("not a pdf", { status: 200, headers: { "Content-Type": "text/html" } })));
    render(<App initialRoute="/reports" initialProductData={live} />);
    await user.click(screen.getByRole("button", { name: /^download pdf$/i }));
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent(/unsupported file/i));
    expect(screen.getByRole("button", { name: /retry pdf/i })).toBeEnabled();
    await expect(requestReviewedPdf({ bundle: live.reportBundle, fetchImpl: vi.fn().mockResolvedValue(new Response(new Blob(["x"], { type: "application/pdf" }), { status: 200, headers: { "Content-Type": "application/pdf", "Content-Length": String(MAX_REVIEWED_REPORT_PDF_BYTES + 1) } })) })).rejects.toThrow(/too large/i);
  });

  it("keeps adjudication workflow out of the board-readable Reports page", () => {
    render(<App initialRoute="/reports" />);
    expect(screen.getByText(/performance at a glance/i)).toBeInTheDocument();
    expect(screen.queryByText(/human review required/i)).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: /review status/i })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /verify this outcome/i })).toBeInTheDocument();
  });

  it("uses the same accessible definition popover for secondary ratio families", async () => {
    const user = userEvent.setup();
    render(<App initialRoute="/reports" />);
    const trigger = screen.getByRole("button", { name: /define gross margin/i });
    await user.click(trigger);
    const dialog = screen.getByRole("dialog", { name: /gross margin/i });
    expect(dialog).toHaveTextContent(/gross profit ÷ revenue/i);
    expect(dialog).toHaveTextContent(/current source \/ method/i);
    await user.keyboard("{Escape}");
    expect(trigger).toHaveFocus();
  });

  it("separates reported history from deterministic forecast ranges and refuses insufficient history", async () => {
    const user = userEvent.setup();
    render(<App initialRoute="/reports" />);
    expect(screen.getByRole("heading", { name: /^board performance brief$/i })).toBeInTheDocument();
    expect(screen.getByRole("table", { name: /illustrative revenue forecast range/i })).toHaveTextContent("Forecast range");
    await user.selectOptions(screen.getByRole("combobox", { name: /forecast history available/i }), "2");
    expect(screen.getByText(/outlook unavailable: insufficient history/i).closest('[role="status"]')).toBeInTheDocument();
    expect(screen.queryByRole("table", { name: /illustrative revenue forecast range/i })).not.toBeInTheDocument();
  });

  it("uses plain-language Review Desk labels with technical details progressively disclosed", () => {
    render(<App initialRoute="/review" />);
    for (const label of ["What was claimed", "What the numbers show", "Why it matters", "Open source"])
      expect(screen.getAllByText(label).length).toBeGreaterThan(0);
    const details = screen.getAllByText("Technical details");
    expect(details).toHaveLength(4);
    expect(details[0].closest("details")).not.toHaveAttribute("open");
  });

  it("clears only demo state and restores focus when deletion is cancelled", async () => {
    const user = userEvent.setup();
    render(<App initialRoute="/review" />);
    const trigger = screen.getByRole("button", { name: /clear session/i });
    await user.click(trigger);
    const dialog = screen.getByRole("dialog", { name: /clear this demo review/i });
    expect(dialog).toHaveTextContent(/does not claim deletion from a database/i);
    await user.keyboard("{Escape}");
    expect(dialog).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();
  });

  it("keeps review decisions visible and clears protected demo routes centrally", async () => {
    const user = userEvent.setup();
    render(<App initialRoute="/review" />);
    await user.click(screen.getByRole("button", { name: /mark for investigation/i }));
    expect(screen.getByText(/review status: marked for investigation/i)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /clear session/i }));
    await user.click(screen.getByRole("button", { name: /clear demo session/i }));
    expect(screen.getByRole("heading", { name: /demo session cleared/i })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /^home$/i }));
    expect(screen.getByRole("heading", { name: /demo session cleared/i })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /restore verified fixture/i }));
    expect(screen.getByRole("heading", { name: /northstar industrial/i })).toBeInTheDocument();
  });

  it("exposes privacy, legal, and provider-offline states without fake claims", async () => {
    const user = userEvent.setup();
    render(<App initialRoute="/company" initialAssistantOpen initialAssistantMode="offline" />);
    expect(screen.getByRole("status")).toHaveTextContent("Offline");
    await user.click(screen.getByRole("button", { name: /close magic assistant/i }));
    await user.click(screen.getByRole("button", { name: /privacy & data/i }));
    expect(screen.getByRole("heading", { name: /what this prototype actually does/i })).toBeInTheDocument();
    expect(screen.getByText(/does not send file contents to a server/i)).toBeInTheDocument();
  });

  it("uses MagicFin in visible product UI without stale visible Proofline branding", () => {
    const { container } = render(<App initialRoute="/company" />);
    expect(container).toHaveTextContent("MagicFin");
    expect(container).not.toHaveTextContent("Proofline");
  });

  it("applies the session-only motion and source-density settings", async () => {
    const user = userEvent.setup();
    const { container } = render(<App initialRoute="/settings" />);
    await user.click(screen.getByRole("checkbox", { name: /reduce interface motion/i }));
    await user.click(screen.getByRole("checkbox", { name: /compact source cards/i }));
    expect(container.querySelector(".product-shell")).toHaveClass("reduced-motion", "compact-sources");
  });

  it("keeps Magic Assistant provider credentials server-side and exposes connection states", async () => {
    vi.useFakeTimers();
    try {
      const { unmount } = render(<App initialRoute="/settings" />);
      expect(screen.getByText("Not configured")).toBeInTheDocument();
      expect(screen.getByText("Google")).toBeInTheDocument();
      expect(screen.getByText("gemma-4-26b-a4b-it")).toBeInTheDocument();
      expect(screen.queryByLabelText(/api key/i)).not.toBeInTheDocument();
      unmount();
      render(<App initialRoute="/settings" initialProviderMode="success" />);
      expect(screen.getByText("Connected")).toBeInTheDocument();
      fireEvent.click(screen.getByRole("button", { name: /test connection/i }));
      expect(screen.getByRole("button", { name: /testing connection/i })).toBeDisabled();
      await act(async () => { vi.advanceTimersByTime(320); });
      expect(screen.getByText("Connected")).toBeInTheDocument();
    } finally {
      vi.useRealTimers();
    }
  });

  it("renders a second synthetic issuer and currency through the same typed routes", async () => {
    const user = userEvent.setup();
    const alternate = JSON.parse(JSON.stringify(productFixture));
    alternate.company = { ...alternate.company, name: "Meridian Components Berhad", shortName: "Meridian", currency: "MYR millions" };
    alternate.session = { ...alternate.session, entity: alternate.company.name, period: "FY2026" };
    alternate.sources[0].name = "Meridian_Report_2026.pdf";
    alternate.sources[1].name = "Meridian_Financials_2026.xlsx";
    alternate.metrics[0] = { ...alternate.metrics[0], value: "MYR 3,180.0m", period: "FY2026", source: "Meridian_Financials_2026.xlsx · B5:C5" };
    alternate.review.claim = { ...alternate.review.claim, text: "Revenue grew 9.0% in FY2026.", value: "9.0%" };
    alternate.review.result = { ...alternate.review.result, value: "7.1%", difference: "1.9 pp" };
    alternate.assistant = { ...alternate.assistant, analysis: "The cited Meridian figures calculate to 7.1%; the demo does not infer a cause." };
    render(<App initialRoute="/" initialProductData={alternate} />);
    expect(screen.getByRole("heading", { name: /meridian components berhad/i })).toBeInTheDocument();
    expect(screen.getByText("MYR 3,180.0m")).toBeInTheDocument();
    expect(screen.getByText("Meridian_Report_2026.pdf")).toBeInTheDocument();
    expect(document.body).not.toHaveTextContent("Northstar Industrial");
    await user.click(screen.getByRole("button", { name: /^review desk$/i }));
    expect(screen.getByRole("heading", { name: /revenue grew 9.0% in FY2026/i })).toBeInTheDocument();
    expect(screen.getAllByText("7.1%").length).toBeGreaterThan(0);
  });

  it("finishes Run Magic quickly when reduced motion is enabled", async () => {
    vi.useFakeTimers();
    try {
      render(<App initialRoute="/settings" />);
      fireEvent.click(screen.getByRole("checkbox", { name: /reduce interface motion/i }));
      fireEvent.click(screen.getByRole("button", { name: /^home$/i }));
      fireEvent.click(screen.getByRole("button", { name: /^run magic$/i }));
      await act(async () => { vi.advanceTimersByTime(150); });
      expect(screen.getByText(/evidence trail ready/i)).toBeInTheDocument();
    } finally {
      vi.useRealTimers();
    }
  });

  it("respects the operating-system reduced-motion preference by default", () => {
    const matchMedia = vi.spyOn(window, "matchMedia").mockReturnValue({ matches: true, addEventListener() {}, removeEventListener() {} });
    const { container } = render(<App initialRoute="/company" />);
    expect(container.querySelector(".product-shell")).toHaveClass("reduced-motion");
    matchMedia.mockRestore();
  });

  it("closes mobile navigation with Escape and restores focus to its trigger", async () => {
    const user = userEvent.setup();
    render(<App initialRoute="/" />);
    const trigger = screen.getByRole("button", { name: /open navigation/i });
    await user.click(trigger);
    await waitFor(() => expect(screen.getByRole("button", { name: /magicfin home/i })).toHaveFocus());
    expect(screen.getByRole("main", { hidden: true })).toHaveAttribute("inert");
    await user.keyboard("{Shift>}{Tab}{/Shift}");
    expect(screen.getByRole("button", { name: /^legal$/i })).toHaveFocus();
    await user.keyboard("{Escape}");
    await waitFor(() => expect(trigger).toHaveFocus());
    expect(screen.getByRole("main")).not.toHaveAttribute("inert");
  });

  it("closes a cited-source drawer before the assistant and restores citation focus", async () => {
    const user = userEvent.setup();
    render(<App initialRoute="/company" initialAssistantOpen />);
    const citation = screen.getAllByRole("button", { name: /annual report 2025/i }).at(-1);
    await user.click(citation);
    expect(screen.getByRole("dialog", { name: /annual report 2025/i })).toBeInTheDocument();
    await user.keyboard("{Escape}");
    await waitFor(() => expect(citation).toHaveFocus());
    expect(screen.queryByRole("dialog", { name: /annual report 2025/i })).not.toBeInTheDocument();
    expect(screen.getByRole("dialog", { name: /ask the fixture, inspect the evidence/i })).toBeInTheDocument();
  });

  it("opens a cited workbook anchor, expands its evidence, and moves focus there", async () => {
    const user = userEvent.setup();
    render(<App initialRoute="/company" initialAssistantOpen />);
    await user.click(screen.getAllByRole("button", { name: /financials fy2025/i }).at(-1));
    const drawer = screen.getByRole("dialog", { name: /financials fy2025/i });
    await user.click(within(drawer).getByRole("button", { name: /open in review desk/i }));
    const target = document.getElementById("financials");
    await waitFor(() => expect(target).toHaveFocus());
    expect(window.location.hash).toBe("#financials");
    expect(within(target).getByRole("button", { name: /financials_fy2025/i })).toHaveAttribute("aria-expanded", "true");
  });

  it("supports browser history and renders all secondary route states", async () => {
    const user = userEvent.setup();
    window.history.replaceState({}, "", "/company");
    render(<App />);
    await user.click(screen.getByRole("button", { name: /^home$/i }));
    expect(document.title).toBe("Home · MagicFin");
    window.history.replaceState({}, "", "/company");
    window.dispatchEvent(new PopStateEvent("popstate"));
    await waitFor(() => expect(screen.getByRole("heading", { name: /northstar industrial/i })).toBeInTheDocument());
    for (const [label, heading] of [
      ["Profile", /local demo identity/i],
      ["Settings", /make the desk comfortable/i],
      ["Sign in", /accounts are not configured/i],
    ]) {
      await user.click(screen.getByRole("button", { name: label }));
      expect(screen.getByRole("heading", { name: heading })).toBeInTheDocument();
    }
    window.history.pushState({}, "", "/missing");
    window.dispatchEvent(new PopStateEvent("popstate"));
    await waitFor(() => expect(screen.getByRole("heading", { name: /this trail stops here/i })).toBeInTheDocument());
  });

  it("opens each new route at the page header and moves focus to main", async () => {
    const user = userEvent.setup();
    render(<App initialRoute="/" />);
    const main = screen.getByRole("main");
    main.scrollTop = 900;
    window.scrollTo.mockClear();
    await user.click(screen.getByRole("button", { name: /^reports$/i }));
    await waitFor(() => expect(main).toHaveFocus());
    expect(window.scrollTo).toHaveBeenCalledWith({ top: 0, left: 0, behavior: "auto" });
    expect(main.scrollTop).toBe(0);
    expect(screen.getByRole("heading", { name: /^board performance brief$/i })).toBeInTheDocument();
  });

  it("describes forecast ranges as illustrative rather than denying their existence", async () => {
    const user = userEvent.setup();
    render(<App initialRoute="/" />);
    await user.click(screen.getByRole("button", { name: /^legal$/i }));
    expect(screen.getByText(/illustrative deterministic forecast ranges are clearly separated from reported history/i)).toBeInTheDocument();
    expect(screen.queryByText(/does not provide investment advice, forecasts/i)).not.toBeInTheDocument();
  });
});
