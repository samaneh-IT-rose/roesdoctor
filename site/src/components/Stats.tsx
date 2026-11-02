import { Box, Container, Stack, Typography } from "@mui/material";
import { useEffect, useRef, useState } from "react";
import { texts } from "../content/texts";
import Reveal from "./Reveal";

const FA_DIGITS = "۰۱۲۳۴۵۶۷۸۹";

function faDigits(s: string): string {
  return s.replace(/[0-9]/g, (d) => FA_DIGITS[Number(d)]);
}

function toLatin(s: string): number {
  const latin = s.replace(/[۰-۹]/g, (d) => String("۰۱۲۳۴۵۶۷۸۹".indexOf(d)))
    .replace(/[٠-٩]/g, (d) => String("٠١٢٣٤٥٦٧٨٩".indexOf(d)));
  const m = latin.replace(/[^0-9]/g, "");
  return m ? parseInt(m, 10) : 0;
}

function suffixOf(s: string): string {
  if (s.includes("٪") || s.includes("%")) return "٪";
  if (s.includes("+")) return "+";
  return "";
}

/** شمارندهٔ متحرک — از صفر تا عدد هدف هنگام دیده‌شدن */
function CountUp({ target, suffix, duration = 1600 }: { target: number; suffix: string; duration?: number }) {
  const [val, setVal] = useState(0);
  const ref = useRef<HTMLSpanElement | null>(null);
  const started = useRef(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (typeof IntersectionObserver === "undefined") {
      setVal(target);
      return;
    }
    const io = new IntersectionObserver(
      (entries) => {
        for (const e of entries) {
          if (!e.isIntersecting || started.current) continue;
          started.current = true;
          const t0 = performance.now();
          const tick = (now: number) => {
            const p = Math.min(1, (now - t0) / duration);
            const eased = 1 - Math.pow(1 - p, 3); // easeOutCubic
            setVal(Math.round(target * eased));
            if (p < 1) requestAnimationFrame(tick);
          };
          requestAnimationFrame(tick);
        }
      },
      { threshold: 0.4 },
    );
    io.observe(el);
    return () => io.disconnect();
  }, [target, duration]);

  return <span ref={ref}>{faDigits(val.toLocaleString("en-US"))}{suffix}</span>;
}

export default function Stats() {
  return (
    <Box
      sx={{
        position: "relative",
        overflow: "hidden",
        background: "linear-gradient(135deg,#3d1e26 0%,#5a2a35 60%,#4d3a52 100%)",
        py: { xs: 5, md: 6 },
      }}
    >
      {/* بافت نقطه‌ای تزئینی */}
      <Box
        aria-hidden
        sx={{
          position: "absolute", inset: 0, opacity: 0.10,
          backgroundImage: "radial-gradient(rgba(255,255,255,.8) 1px, transparent 1.6px)",
          backgroundSize: "26px 26px",
        }}
      />
      <Box className="aurora" aria-hidden>
        <span style={{ width: 320, height: 320, background: "rgba(201,154,91,.20)", top: -120, left: "12%" }} />
        <span style={{ width: 360, height: 360, background: "rgba(208,107,128,.22)", bottom: -160, right: "6%" }} />
      </Box>

      <Container sx={{ position: "relative" }}>
        <Stack direction="row" spacing={{ xs: 3, md: 6 }} justifyContent="center" flexWrap="wrap" useFlexGap>
          {texts.stats.map((s, i) => (
            <Reveal key={s.label} delay={i * 110} variant="up" sx={{ textAlign: "center", minWidth: 150 }}>
              <Typography
                variant="h3"
                fontWeight={800}
                sx={{
                  color: "#f2cdd5",
                  fontSize: { xs: 30, md: 40 },
                  textShadow: "0 6px 24px rgba(0,0,0,.25)",
                }}
              >
                <CountUp target={toLatin(s.n)} suffix={suffixOf(s.n)} />
              </Typography>
              <Typography variant="body2" sx={{ color: "rgba(255,255,255,0.85)" }}>{s.label}</Typography>
            </Reveal>
          ))}
        </Stack>
      </Container>
    </Box>
  );
}
