import { FileText, Paperclip, X } from "lucide-react";
import { useId, useRef, useState } from "react";

export type ResearchSourceAttachment = {
  id: string;
  name: string;
  type: string;
  size: number;
  text: string;
};

const acceptedTypes = ["text/plain", "text/markdown", "text/csv"];
const accept = ".txt,.md,.markdown,.csv,text/plain,text/markdown,text/csv";

function isAcceptedSource(file: File) {
  return acceptedTypes.includes(file.type) || /\.(txt|md|markdown|csv)$/i.test(file.name);
}

function attachmentId(file: File) {
  return `${file.name}-${file.size}-${file.lastModified}`;
}

async function readSourceText(file: File): Promise<string> {
  if (typeof file.text === "function") return file.text();
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(typeof reader.result === "string" ? reader.result : "");
    reader.onerror = () => reject(reader.error ?? new Error("Could not read source file."));
    reader.readAsText(file, "utf-8");
  });
}

export function ResearchSourceAttachments({
  onChange,
  maxFiles = 10,
  maxBytes = 128 * 1024
}: {
  onChange?: (sources: ResearchSourceAttachment[]) => void;
  maxFiles?: number;
  maxBytes?: number;
}) {
  const inputId = useId();
  const inputRef = useRef<HTMLInputElement>(null);
  const [sources, setSources] = useState<ResearchSourceAttachment[]>([]);
  const [error, setError] = useState<string>();

  function updateSources(next: ResearchSourceAttachment[]) {
    setSources(next);
    onChange?.(next);
  }

  async function chooseFiles(files: FileList | null) {
    if (!files?.length) return;
    setError(undefined);
    const candidates = Array.from(files);
    const invalid = candidates.find((file) => !isAcceptedSource(file));
    if (invalid) {
      setError(`${invalid.name} is not a supported text source.`);
      return;
    }
    const tooLarge = candidates.find((file) => file.size > maxBytes);
    if (tooLarge) {
      setError(`${tooLarge.name} is larger than ${Math.round(maxBytes / 1000)} KB.`);
      return;
    }
    const newFiles = candidates.filter((file) => !sources.some((source) => source.id === attachmentId(file)));
    if (sources.length + newFiles.length > maxFiles) {
      setError(`Attach up to ${maxFiles} text sources at a time.`);
      return;
    }
    const readSources = await Promise.all(newFiles.map(async (file) => ({
      id: attachmentId(file),
      name: file.name,
      type: file.type || "text/plain",
      size: file.size,
      text: await readSourceText(file)
    })));
    updateSources([...sources, ...readSources]);
    if (inputRef.current) inputRef.current.value = "";
  }

  function removeSource(id: string) {
    updateSources(sources.filter((source) => source.id !== id));
  }

  return <section className="researchSourceAttachments" aria-labelledby={`${inputId}-label`}>
    <div className="researchSourceAttachments__heading">
      <div><span id={`${inputId}-label`}>OPTIONAL RESEARCH SOURCES</span><p>Attach notes, Markdown, or CSV as immutable evidence alongside the completed research run.</p></div>
      <label className="researchSourceAttachments__add" htmlFor={inputId}><Paperclip size={14} /> Add source</label>
    </div>
    <input ref={inputRef} id={inputId} className="researchSourceAttachments__input" type="file" accept={accept} multiple aria-label="Choose optional research sources" onChange={(event) => void chooseFiles(event.target.files)} />
    <p className="researchSourceAttachments__notice">Sources are reviewed as local research context only. They never place, modify, or authorize trades.</p>
    {error && <p className="researchSourceAttachments__error" role="alert">{error}</p>}
    {sources.length > 0 && <ul className="researchSourceAttachments__list" aria-label="Selected research sources">{sources.map((source) => <li key={source.id}><FileText size={15} /><span><strong>{source.name}</strong><small>{source.type} · {Math.max(1, Math.ceil(source.size / 1000))} KB</small></span><button type="button" onClick={() => removeSource(source.id)} aria-label={`Remove ${source.name}`}><X size={14} /></button></li>)}</ul>}
  </section>;
}
