import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { App } from "./App";

describe("Proofline Review Desk", () => {
  it("keeps the verdict dominant and progressively reveals spreadsheet evidence", async () => {
    const user = userEvent.setup();
    render(<App />);
    expect(screen.getByRole("heading", { name: /revenue growth was 8.2%/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/claimed growth 8.2 percent/i)).toHaveTextContent("Contradicted");
    const sheetToggle = screen.getByRole("button", { name: /financials_fy2025.xlsx/i });
    expect(sheetToggle).toHaveAttribute("aria-expanded", "false");
    await user.click(sheetToggle);
    expect(sheetToggle).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("table", { name: /audited revenue inputs/i })).toBeVisible();
  });

  it("records a human review decision in a live region", async () => {
    const user = userEvent.setup();
    render(<App />);
    await user.click(screen.getByRole("button", { name: /mark for investigation/i }));
    expect(screen.getByRole("status")).toHaveTextContent("Marked for investigation");
  });

  it("closes deletion with Escape and restores focus", async () => {
    const user = userEvent.setup();
    render(<App />);
    const trigger = screen.getByRole("button", { name: /delete session/i });
    await user.click(trigger);
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /keep review/i })).toHaveFocus();
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();
  });

  it("returns an honest deletion receipt after confirmation", async () => {
    const user = userEvent.setup();
    render(<App />);
    await user.click(screen.getByRole("button", { name: /delete session/i }));
    const dialog = screen.getByRole("dialog");
    expect(dialog).toHaveTextContent(/in-browser demo state/i);
    await user.click(within(dialog).getByRole("button", { name: /delete session/i }));
    expect(screen.getByRole("heading", { name: /session cleared/i })).toBeInTheDocument();
    expect(screen.getByText("PL-DEMO-0822-1024")).toBeInTheDocument();
  });

  it("shows a clear error for files outside the narrow mock contract", async () => {
    const user = userEvent.setup();
    render(<App initialScreen="empty" />);
    const input = document.querySelector('input[type="file"]');
    await user.upload(input, new File(["demo"], "report.pdf", { type: "application/pdf" }));
    expect(screen.getByRole("heading", { name: /choose one pdf and one workbook/i })).toBeInTheDocument();
    expect(screen.getByText(/nothing was uploaded or retained/i)).toBeInTheDocument();
  });

  it("exposes the cached fallback as a labeled state", () => {
    render(<App initialScreen="cached" />);
    expect(screen.getByRole("status")).toHaveTextContent(/verified fallback loaded/i);
  });

  it("exports a reviewed report through the explicit action", async () => {
    const user = userEvent.setup();
    const createObjectURL = vi.fn(() => "blob:report");
    const revokeObjectURL = vi.fn();
    Object.defineProperty(URL, "createObjectURL", { configurable: true, value: createObjectURL });
    Object.defineProperty(URL, "revokeObjectURL", { configurable: true, value: revokeObjectURL });
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
    render(<App />);
    await user.click(screen.getByRole("button", { name: /export report/i }));
    expect(createObjectURL).toHaveBeenCalledOnce();
    expect(screen.getByRole("status")).toHaveTextContent(/reviewed report exported/i);
  });
});
