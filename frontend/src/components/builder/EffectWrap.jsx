import { useRef, useState } from "react";
import { motion, useScroll, useTransform } from "framer-motion";

// Wraps a block with built-in effects: scroll reveal, parallax, hover lift, floating.
// In design_v2 sites, reveals and staggered children are on by default.
export default function EffectWrap({ effects = {}, motionOn = true, v2 = false, children, ...rest }) {
  const ref = useRef(null);
  const [seen, setSeen] = useState(false);
  const { scrollYProgress } = useScroll({ target: ref, offset: ["start end", "end start"] });
  const par = effects.parallax && motionOn ? 40 : 0;
  const y = useTransform(scrollYProgress, [0, 1], [par, -par]);
  const reveal = motionOn && effects.reveal !== false;
  return (
    <motion.div ref={ref} {...rest} style={{ y }}
      initial={reveal ? { opacity: 0, y: v2 ? 32 : 24 } : false} whileInView={reveal ? { opacity: 1, y: 0 } : undefined} viewport={{ once: true, margin: "-60px" }}
      onViewportEnter={() => setSeen(true)}
      transition={{ duration: v2 ? 0.75 : 0.6, ease: [0.22, 1, 0.36, 1] }}
      whileHover={motionOn && effects.hover ? { scale: 1.01, transition: { duration: 0.25 } } : undefined}
      animate={motionOn && effects.float ? { y: [0, -8, 0], transition: { duration: 4, repeat: Infinity, ease: "easeInOut" } } : undefined}
      className={`${seen && motionOn ? "tstagger-in" : ""} ${motionOn && effects.hover ? "[&_img]:transition-transform [&_img]:duration-500 hover:[&_img]:scale-[1.03]" : ""} ${rest.className || ""}`}>
      {children}
    </motion.div>
  );
}
