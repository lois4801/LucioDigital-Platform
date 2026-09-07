import { Paperclip, FileText, FileSpreadsheet, FileArchive, File } from "lucide-react";

const IMG_EXT = /\.(png|jpe?g|webp|gif|svg)$/i;
const ICON = { pdf: FileText, doc: FileText, docx: FileText, txt: FileText, csv: FileSpreadsheet, xls: FileSpreadsheet, xlsx: FileSpreadsheet, zip: FileArchive };
const BACKEND = process.env.REACT_APP_BACKEND_URL;

const abs = (u) => (u.startsWith("http") ? u : `${BACKEND}${u}`);

// Pulls "[attachment] name — url" lines (and bare file URLs) out of a lead/chat body.
export function parseAttachments(text = "") {
  const out = [];
  const seen = new Set();
  const labelled = /\[attachment\]\s*([^\n—]+?)\s*—\s*(\S+\/api\/public\/files\/\S+)/gi;
  let m;
  while ((m = labelled.exec(text))) {
    const url = m[2];
    if (seen.has(url)) continue;
    seen.add(url);
    out.push({ name: m[1].trim(), url });
  }
  const bare = /(\S*\/api\/public\/files\/\S+)/gi;
  while ((m = bare.exec(text))) {
    const url = m[1];
    if (seen.has(url)) continue;
    seen.add(url);
    out.push({ name: decodeURIComponent(url.split("/").pop()), url });
  }
  return out;
}

export const attachmentCount = (text) => parseAttachments(text).length;

export function AttachmentPill({ count }) {
  if (!count) return null;
  return (
    <span data-testid="lead-attachment-pill" title={`${count} attachment${count === 1 ? "" : "s"}`}
      className="chip inline-flex items-center gap-1" style={{ padding: "1px 6px" }}>
      <Paperclip size={10} /> {count}
    </span>
  );
}

// Thumbnail grid for files a visitor sent with their message.
export function Attachments({ body, testid = "lead-attachments" }) {
  const files = parseAttachments(body);
  if (files.length === 0) return null;
  return (
    <div data-testid={testid} className="mt-4">
      <div className="overline mb-2 flex items-center gap-1.5"><Paperclip size={11} className="text-[var(--acc)]" /> Attachments · {files.length}</div>
      <div className="flex flex-wrap gap-2">
        {files.map((f) => {
          const ext = (f.name.split(".").pop() || "").toLowerCase();
          const Icon = ICON[ext] || File;
          const isImg = IMG_EXT.test(f.name) || IMG_EXT.test(f.url);
          return (
            <a key={f.url} data-testid="lead-attachment-item" href={abs(f.url)} target="_blank" rel="noreferrer" title={f.name}
              className="w-28 rounded-xl border border-[var(--line)] bg-[var(--bg-2)] overflow-hidden hover:border-[var(--acc)]/60 transition-colors">
              <span className="block h-20 bg-black/30 flex items-center justify-center overflow-hidden">
                {isImg
                  ? <img src={abs(f.url)} alt={f.name} className="w-full h-full object-cover" />
                  : <Icon size={22} className="text-[var(--acc)]" />}
              </span>
              <span className="block px-2 py-1.5 text-[10px] font-mono truncate text-[var(--mut)]">{f.name}</span>
            </a>
          );
        })}
      </div>
    </div>
  );
}
