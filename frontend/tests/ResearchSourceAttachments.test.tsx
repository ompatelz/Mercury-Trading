import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ResearchSourceAttachments } from "../src/components/ResearchSourceAttachments";

afterEach(cleanup);

describe("ResearchSourceAttachments", () => {
  it("reads accepted text sources and exposes them as local research context", async () => {
    const onChange = vi.fn();
    render(<ResearchSourceAttachments onChange={onChange} />);
    const file = new File(["strategy notes"], "notes.md", { type: "text/markdown" });
    fireEvent.change(screen.getByLabelText(/choose optional research sources/i), { target: { files: [file] } });
    await waitFor(() => expect(screen.getByText("notes.md")).toBeInTheDocument());
    expect(onChange).toHaveBeenLastCalledWith(expect.arrayContaining([expect.objectContaining({ name: "notes.md", text: "strategy notes" })]));
    expect(screen.getByText(/never place, modify, or authorize trades/i)).toBeInTheDocument();
  });

  it("rejects unsupported source types", () => {
    render(<ResearchSourceAttachments />);
    const file = new File(["binary"], "chart.png", { type: "image/png" });
    fireEvent.change(screen.getByLabelText(/choose optional research sources/i), { target: { files: [file] } });
    expect(screen.getByRole("alert")).toHaveTextContent("chart.png is not a supported text source.");
  });
});
