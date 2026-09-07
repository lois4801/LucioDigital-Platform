import { useEffect, useRef, useState } from "react";
import axios from "axios";
import { MessageCircle, X, Send, Mic, MicOff, Volume2, VolumeX, Loader2 } from "lucide-react";

const BACKEND = process.env.REACT_APP_BACKEND_URL;

export default function ChatWidget({ token = "studio", brand = "Assistant", accent = "#F97316", light = false }) {
  const [open, setOpen] = useState(false);
  const [msgs, setMsgs] = useState([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [voiceOn, setVoiceOn] = useState(true);
  const [listening, setListening] = useState(false);
  const [sessionId] = useState(() => {
    const k = `chat_sess_${token}`;
    let s = localStorage.getItem(k);
    if (!s) { s = `s_${Math.random().toString(36).slice(2, 14)}`; localStorage.setItem(k, s); }
    return s;
  });
  const audioRef = useRef(null);
  const recRef = useRef(null);
  const endRef = useRef(null);

  useEffect(() => {
    if (!open) return;
    axios.get(`${BACKEND}/api/public/chat/${token}/history/${sessionId}`).then(r => setMsgs(r.data)).catch(() => {});
  }, [open, token, sessionId]);
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [msgs, busy]);

  async function speak(text) {
    if (!voiceOn) return;
    try {
      const { data } = await axios.post(`${BACKEND}/api/public/tts`, { text, voice: "coral" });
      audioRef.current?.pause();
      const a = new Audio(`${BACKEND}${data.audio_url}`);
      audioRef.current = a; a.play().catch(() => {});
    } catch {}
  }

  async function send(text) {
    const msg = (text ?? input).trim();
    if (!msg || busy) return;
    setInput(""); setBusy(true);
    setMsgs(m => [...m, { role: "user", content: msg }]);
    try {
      const { data } = await axios.post(`${BACKEND}/api/public/chat/${token}`, { session_id: sessionId, message: msg });
      setMsgs(m => [...m, { role: "assistant", content: data.reply }]);
      speak(data.reply);
    } catch (e) {
      setMsgs(m => [...m, { role: "assistant", content: "Sorry — I'm unavailable right now. Please try again shortly." }]);
    } finally { setBusy(false); }
  }

  function toggleMic() {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) { setMsgs(m => [...m, { role: "assistant", content: "Voice input isn't supported in this browser — try Chrome or Edge." }]); return; }
    if (listening) { recRef.current?.stop(); setListening(false); return; }
    const rec = new SR(); rec.lang = navigator.language || "en-US"; rec.interimResults = false;
    rec.onresult = (e) => { const t = e.results[0][0].transcript; setListening(false); send(t); };
    rec.onerror = () => setListening(false); rec.onend = () => setListening(false);
    recRef.current = rec; rec.start(); setListening(true);
  }

  const panelBg = light ? "bg-white text-slate-900 border-slate-200" : "bg-[#11131C] text-slate-100 border-white/10";
  const bubbleBot = light ? "bg-slate-100" : "bg-white/8";

  return (
    <>
      {open && (
        <div data-testid="chat-widget-panel" className={`fixed bottom-24 right-5 z-[70] w-[360px] max-w-[calc(100vw-40px)] h-[520px] max-h-[75vh] rounded-3xl border shadow-2xl flex flex-col overflow-hidden ${panelBg}`}>
          <div className="px-5 py-4 flex items-center justify-between text-white" style={{ background: accent }}>
            <div><div className="font-semibold text-sm">{brand} assistant</div><div className="text-[11px] opacity-80 flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-full bg-white animate-pulse" /> Live · voice enabled</div></div>
            <div className="flex items-center gap-1">
              <button data-testid="chat-voice-toggle" onClick={() => { setVoiceOn(!voiceOn); audioRef.current?.pause(); }} className="w-8 h-8 rounded-full hover:bg-white/20 flex items-center justify-center">{voiceOn ? <Volume2 size={15} /> : <VolumeX size={15} />}</button>
              <button data-testid="chat-close-btn" onClick={() => setOpen(false)} className="w-8 h-8 rounded-full hover:bg-white/20 flex items-center justify-center"><X size={15} /></button>
            </div>
          </div>
          <div className="flex-1 overflow-y-auto p-4 space-y-3 text-sm">
            {msgs.length === 0 && <div className={`${bubbleBot} rounded-2xl rounded-tl-md px-4 py-3`}>Hi! I'm the {brand} assistant. Ask me anything about our services, pricing or how to get started — you can also tap the mic and just talk.</div>}
            {msgs.map((m, i) => (
              <div key={i} data-testid={`chat-msg-${m.role}`} className={`max-w-[85%] px-4 py-2.5 rounded-2xl leading-relaxed ${m.role === "user" ? "ml-auto text-white rounded-tr-md" : `${bubbleBot} rounded-tl-md`}`} style={m.role === "user" ? { background: accent } : {}}>{m.content}</div>
            ))}
            {busy && <div className={`${bubbleBot} rounded-2xl px-4 py-3 w-16 flex items-center justify-center`}><Loader2 size={14} className="animate-spin" /></div>}
            <div ref={endRef} />
          </div>
          <div className={`p-3 border-t flex items-center gap-2 ${light ? "border-slate-200" : "border-white/10"}`}>
            <button data-testid="chat-mic-btn" onClick={toggleMic} className={`w-10 h-10 rounded-full flex items-center justify-center shrink-0 ${listening ? "text-white animate-pulse" : light ? "bg-slate-100" : "bg-white/8"}`} style={listening ? { background: accent } : {}}>{listening ? <MicOff size={16} /> : <Mic size={16} />}</button>
            <input data-testid="chat-input" value={input} onChange={e => setInput(e.target.value)} onKeyDown={e => e.key === "Enter" && send()} placeholder={listening ? "Listening…" : "Type your question…"}
              className={`flex-1 rounded-full px-4 py-2.5 text-sm outline-none ${light ? "bg-slate-100" : "bg-white/8"}`} />
            <button data-testid="chat-send-btn" onClick={() => send()} disabled={busy || !input.trim()} className="w-10 h-10 rounded-full text-white flex items-center justify-center shrink-0 disabled:opacity-50" style={{ background: accent }}><Send size={15} /></button>
          </div>
        </div>
      )}
      <button data-testid="chat-widget-fab" onClick={() => setOpen(!open)}
        className="fixed bottom-6 right-5 z-[70] h-14 px-5 rounded-full text-white font-semibold text-sm flex items-center gap-2 shadow-[0_16px_40px_-12px_rgba(0,0,0,0.5)] hover:-translate-y-0.5 transition-transform"
        style={{ background: accent }}>
        {open ? <X size={18} /> : <MessageCircle size={18} />} {open ? "Close" : "Chat with us"}
      </button>
    </>
  );
}
