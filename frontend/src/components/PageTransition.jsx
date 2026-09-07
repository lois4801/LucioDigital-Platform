import { motion } from "framer-motion";

export function PageTransition({ children, testid }) {
  return (
    <motion.div data-testid={testid} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }} transition={{ duration: 0.28, ease: [0.22, 1, 0.36, 1] }}>
      {children}
    </motion.div>
  );
}

export function Skeleton({ className = "" }) {
  return <div className={`skeleton ${className}`} />;
}

export function PageSkeleton({ testid = "page-skeleton" }) {
  return (
    <div data-testid={testid} className="min-h-screen px-6 lg:px-10 py-6 space-y-6">
      <div className="flex items-center justify-between"><Skeleton className="h-10 w-56 rounded-full" /><Skeleton className="h-10 w-40 rounded-full" /></div>
      <Skeleton className="h-48 w-full rounded-2xl" />
      <div className="grid md:grid-cols-3 gap-5">{[0, 1, 2].map(i => <Skeleton key={i} className="h-40 rounded-2xl" />)}</div>
      <div className="grid md:grid-cols-2 gap-5">{[0, 1].map(i => <Skeleton key={i} className="h-56 rounded-2xl" />)}</div>
    </div>
  );
}
