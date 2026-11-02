import { Box, type BoxProps } from "@mui/material";
import { useEffect, useRef, useState, type ReactNode } from "react";

/**
 * Reveal — افکت ظهور هنگام اسکرول (شبیه افکت‌های ravanclass).
 * با IntersectionObserver هر بار که عنصر وارد دید شود کلاس visible می‌گیرد.
 * delay: تأخیر بر حسب میلی‌ثانیه برای افکت آبشاری (stagger).
 */
export default function Reveal({
  children,
  delay = 0,
  variant = "up",
  once = true,
  sx,
  ...rest
}: {
  children: ReactNode;
  /** تأخیر شروع انیمیشن (ms) */
  delay?: number;
  /** نوع ورود: up | down | right | left | zoom */
  variant?: "up" | "down" | "right" | "left" | "zoom";
  /** فقط یک بار اجرا شود؟ */
  once?: boolean;
} & Omit<BoxProps, "children">) {
  const ref = useRef<HTMLDivElement | null>(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (typeof IntersectionObserver === "undefined") {
      setVisible(true);
      return;
    }
    const io = new IntersectionObserver(
      (entries) => {
        for (const e of entries) {
          if (e.isIntersecting) {
            setVisible(true);
            if (once) io.unobserve(e.target);
          } else if (!once) {
            setVisible(false);
          }
        }
      },
      { threshold: 0.12, rootMargin: "0px 0px -40px 0px" },
    );
    io.observe(el);
    return () => io.disconnect();
  }, [once]);

  return (
    <Box
      ref={ref}
      className={`reveal reveal-${variant}${visible ? " visible" : ""}`}
      sx={{ ...sx, "&.reveal": { transitionDelay: visible ? `${delay}ms` : "0ms" } }}
      {...rest}
    >
      {children}
    </Box>
  );
}
