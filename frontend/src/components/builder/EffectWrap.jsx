import { useRef } from "react";
import { motion, useScroll, useTransform } from "framer-motion";

// Wraps a block with built-in effects: scroll reveal, parallax, hover lift, floating.
export default function EffectWrap({ effects = {}, motionOn = true, children, ...rest }) {
  const ref = useRef(null);
  const { scrollYProgress } = useScroll({ target: ref, offset: ["start end", "end start"] });
  const y = useTransform(scrollYProgress, [0, 1], [effects.parallax && motionOn ? 40 : 0, effects.parallax && motionOn ? -40 : 0]);
  const reveal = motionOn && effects.reveal !== false;
  return (
    <motion.div ref={ref} {...rest} style={{ y }}
      initial={reveal ? { opacity: 0, y: 24 } : false} whileInView={reveal ? { opacity: 1, y: 0 } : undefined} viewport={{ once: true, margin: "-60px" }}
      transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
      whileHover={motionOn && effects.hover ? { scale: 1.01, transition: { duration: 0.25 } } : undefined}
      animate={motionOn && effects.float ? { y: [0, -8, 0], transition: { duration: 4, repeat: Infinity, ease: "easeInOut" } } : undefined}
      className={`${motionOn && effects.hover ? "[&_img]:transition-transform [&_img]:duration-500 hover:[&_img]:scale-[1.03]" : ""} ${rest.className || ""}`}>
      {children}
    </motion.div>
  );
}
