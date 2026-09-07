import { useEffect, useState } from "react";
import { motion } from "framer-motion";

export const fast = [0.22, 1, 0.36, 1];

export function Words({ text, className, delay = 0, as: Tag = "h1", testid }) {
  const words = String(text).split(" ");
  return (
    <Tag className={className} data-testid={testid}>
      {words.map((w, i) => (
        <motion.span key={i} className="inline-block mr-[0.25em]" initial={{ opacity: 0, y: 18 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }}
          transition={{ delay: delay + i * 0.05, duration: 0.45, ease: fast }}>{w}</motion.span>
      ))}
    </Tag>
  );
}

export function CountUp({ value, duration = 900 }) {
  const [n, setN] = useState(0);
  useEffect(() => {
    const num = typeof value === "number" ? value : parseFloat(String(value).replace(/[^0-9.]/g, "")) || 0;
    const suffix = typeof value === "string" ? value.replace(/[0-9.,]/g, "") : "";
    const start = performance.now();
    let raf;
    const tick = (t) => { const p = Math.min(1, (t - start) / duration); const e = 1 - Math.pow(1 - p, 3); setN({ v: num * e, suffix, dec: String(num).includes(".") ? 1 : 0 }); if (p < 1) raf = requestAnimationFrame(tick); };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [value, duration]);
  if (!n || typeof n !== "object") return <>{value}</>;
  return <>{n.v.toLocaleString(undefined, { maximumFractionDigits: n.dec, minimumFractionDigits: n.dec })}{n.suffix}</>;
}

export function Spotlight() {
  useEffect(() => {
    const move = (e) => { document.documentElement.style.setProperty("--spot-x", e.clientX + "px"); document.documentElement.style.setProperty("--spot-y", e.clientY + "px"); };
    window.addEventListener("mousemove", move, { passive: true });
    return () => window.removeEventListener("mousemove", move);
  }, []);
  return <div aria-hidden className="spotlight pointer-events-none fixed inset-0 z-0" />;
}

export const stagger = { hidden: {}, show: { transition: { staggerChildren: 0.07 } } };
export const fadeUp = { hidden: { opacity: 0, y: 22 }, show: { opacity: 1, y: 0, transition: { duration: 0.5, ease: fast } } };
