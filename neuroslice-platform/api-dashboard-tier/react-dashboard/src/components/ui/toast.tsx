import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { CheckCircle2, Info, TriangleAlert, XCircle, X } from "lucide-react";

import { cn } from "@/lib/cn";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type ToastType = "success" | "error" | "info" | "warning";

interface ToastItem {
  id: string;
  message: string;
  type: ToastType;
}

interface ToastContextValue {
  toast: {
    success: (message: string) => void;
    error: (message: string) => void;
    info: (message: string) => void;
    warning: (message: string) => void;
  };
}

// ---------------------------------------------------------------------------
// Context
// ---------------------------------------------------------------------------

const ToastContext = createContext<ToastContextValue | null>(null);

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used within ToastProvider");
  return ctx;
}

// ---------------------------------------------------------------------------
// Single toast item
// ---------------------------------------------------------------------------

const ICON: Record<ToastType, ReactNode> = {
  success: <CheckCircle2 size={16} className="shrink-0 text-emerald-400" />,
  error:   <XCircle     size={16} className="shrink-0 text-red-400" />,
  info:    <Info        size={16} className="shrink-0 text-blue-400" />,
  warning: <TriangleAlert size={16} className="shrink-0 text-amber-400" />,
};

const BAR_COLOR: Record<ToastType, string> = {
  success: "bg-emerald-400",
  error:   "bg-red-400",
  info:    "bg-blue-400",
  warning: "bg-amber-400",
};

const DURATION_MS = 4000;

function ToastItem({
  item,
  onDismiss,
}: {
  item: ToastItem;
  onDismiss: (id: string) => void;
}) {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    // mount → slide in
    const show = requestAnimationFrame(() => setVisible(true));
    // auto-dismiss
    const hide = setTimeout(() => onDismiss(item.id), DURATION_MS);
    return () => {
      cancelAnimationFrame(show);
      clearTimeout(hide);
    };
  }, [item.id, onDismiss]);

  return (
    <div
      className={cn(
        "relative flex w-80 items-start gap-3 overflow-hidden rounded-2xl border border-white/8 bg-card px-4 py-3 shadow-xl transition-all duration-300",
        visible ? "translate-x-0 opacity-100" : "translate-x-8 opacity-0",
      )}
    >
      {/* progress bar */}
      <div
        className={cn(
          "absolute bottom-0 left-0 h-0.5 rounded-full",
          BAR_COLOR[item.type],
        )}
        style={{
          width: "100%",
          animation: `toast-shrink ${DURATION_MS}ms linear forwards`,
        }}
      />

      {ICON[item.type]}

      <p className="flex-1 text-sm text-slate-200 leading-5">{item.message}</p>

      <button
        className="shrink-0 rounded-lg p-0.5 text-mutedText hover:text-slate-200 transition-colors"
        onClick={() => onDismiss(item.id)}
        aria-label="Dismiss"
      >
        <X size={14} />
      </button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Provider + container
// ---------------------------------------------------------------------------

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const counterRef = useRef(0);

  const add = useCallback((message: string, type: ToastType) => {
    const id = `toast-${++counterRef.current}`;
    setToasts((prev) => [...prev, { id, message, type }]);
  }, []);

  const dismiss = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const toast = {
    success: (m: string) => add(m, "success"),
    error:   (m: string) => add(m, "error"),
    info:    (m: string) => add(m, "info"),
    warning: (m: string) => add(m, "warning"),
  };

  return (
    <ToastContext.Provider value={{ toast }}>
      {children}

      {/* Fixed container — bottom-right, above everything */}
      <div className="fixed bottom-6 right-6 z-[9999] flex flex-col gap-2 items-end pointer-events-none">
        {toasts.map((item) => (
          <div key={item.id} className="pointer-events-auto">
            <ToastItem item={item} onDismiss={dismiss} />
          </div>
        ))}
      </div>

      {/* keyframe injected once */}
      <style>{`
        @keyframes toast-shrink {
          from { width: 100%; }
          to   { width: 0%; }
        }
      `}</style>
    </ToastContext.Provider>
  );
}
