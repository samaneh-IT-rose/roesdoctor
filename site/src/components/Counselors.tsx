import {
  Avatar, Box, Button, Chip, CircularProgress, Container, IconButton, Paper,
  Stack, Tooltip, Typography,
} from "@mui/material";
import { useEffect, useMemo, useState } from "react";
import { Link as RouterLink } from "react-router-dom";
import { fetchPublicCounselors } from "../api";
import type { PublicCounselor } from "../api";
import { texts } from "../content/texts";
import Reveal from "./Reveal";
import SectionTitle from "./SectionTitle";
import {
  IRAN_PROVINCE_CENTER, IRAN_PROVINCE_META, IRAN_PROVINCE_PATHS, IRAN_SEA_PATHS, IRAN_VIEWBOX,
} from "./iranMapData";

/* ------------------------------------------------------------------ */
/* کمکی‌ها                                                             */
/* ------------------------------------------------------------------ */

const PAGE_SIZE = 6;

function faNum(n: number | string): string {
  return Number(n).toLocaleString("fa-IR");
}

function Stars({ value, size = 15 }: { value: number | null; size?: number }) {
  const v = value ?? 0;
  return (
    <Stack direction="row" spacing={0.25} alignItems="center">
      {[1, 2, 3, 4, 5].map((i) => (
        <Box key={i} component="svg" viewBox="0 0 24 24" sx={{ width: size, height: size, display: "block" }} aria-hidden>
          <path
            d="M12 2.6l2.9 5.9 6.5.95-4.7 4.6 1.1 6.5L12 17.5l-5.8 3.05 1.1-6.5-4.7-4.6 6.5-.95z"
            fill={i <= Math.round(v) ? "#f0b429" : "#eadfe3"}
          />
        </Box>
      ))}
    </Stack>
  );
}

/** رنگ استان بر اساس تعداد مشاور (طیف رز) */
function mixRose(t: number): string {
  // از #f0c9d3 (کم‌رنگ) تا #a83a54 (اشباع)
  const a = [240, 201, 211];
  const b = [168, 58, 84];
  const c = a.map((v, i) => Math.round(v + (b[i] - v) * t));
  return `rgb(${c[0]},${c[1]},${c[2]})`;
}

/* ------------------------------------------------------------------ */
/* کارت مشاور                                                          */
/* ------------------------------------------------------------------ */

function CounselorCard({ c }: { c: PublicCounselor }) {
  return (
    <Paper
      className="hover-lift card-shine"
      elevation={0}
      sx={{
        borderRadius: "20px",
        border: "1px solid #f3e2e7",
        background: "linear-gradient(170deg,#ffffff 0%,#fbf3f5 100%)",
        overflow: "hidden",
        position: "relative",
        height: "100%",
        display: "flex",
        flexDirection: "column",
      }}
    >
      <Box sx={{ height: 5, background: "linear-gradient(90deg,#a83a54,#c99a5b)" }} />
      <Box sx={{ p: { xs: 2.2, md: 2.6 }, textAlign: "center", display: "flex", flexDirection: "column", flexGrow: 1 }}>
        {c.photo_url ? (
          <Box
            component="img"
            src={c.photo_url}
            alt={c.name}
            className="avatar-pulse"
            sx={{
              width: 96, height: 96, borderRadius: "50%", objectFit: "cover",
              mx: "auto", mb: 1.5, border: "4px solid #fff",
              boxShadow: "0 8px 22px rgba(168,58,84,.18)",
            }}
          />
        ) : (
          <Avatar
            className="avatar-pulse"
            sx={{
              width: 96, height: 96, mx: "auto", mb: 1.5, fontSize: 36,
              background: "linear-gradient(135deg,#b34460,#8a2f47)",
              border: "4px solid #fff", boxShadow: "0 8px 22px rgba(168,58,84,.18)",
            }}
          >
            {c.name.charAt(0)}
          </Avatar>
        )}
        <Typography variant="h6" fontWeight={800} sx={{ fontSize: 17 }}>{c.name}</Typography>
        {c.professional_title && (
          <Typography variant="body2" color="text.secondary" sx={{ mt: 0.4, fontSize: 13 }}>
            {c.professional_title}
          </Typography>
        )}
        <Stack direction="row" spacing={0.8} justifyContent="center" flexWrap="wrap" useFlexGap sx={{ mt: 1.2 }}>
          {c.specialty && (
            <Chip size="small" label={c.specialty} sx={{ bgcolor: "#faeef1", color: "primary.main", fontWeight: 700, border: "1px solid #f0d9df", fontSize: 12 }} />
          )}
          {c.branch_name && (
            <Chip size="small" label={`📍 ${c.branch_name}`} sx={{ bgcolor: "#f4f0f8", color: "secondary.main", fontWeight: 700, fontSize: 12 }} />
          )}
        </Stack>
        <Stack sx={{ mt: "auto", pt: 1.6 }}>
          <Stack direction="row" spacing={0.75} alignItems="center" justifyContent="center">
            <Stars value={c.rating_avg ?? null} />
            <Typography variant="body2" fontWeight={700}>
              {c.rating_avg ? faNum(c.rating_avg) : "جدید"}
            </Typography>
            <Typography variant="caption" color="text.secondary">({faNum(c.review_count)} نظر)</Typography>
          </Stack>
          <Button
            component={RouterLink}
            to={`/specialist/${encodeURIComponent(c.id)}`}
            variant="contained"
            size="small"
            className="shine-btn"
            sx={{ mt: 1.6, borderRadius: 99, fontWeight: 800, px: 3 }}
          >
            رزرو نوبت
          </Button>
        </Stack>
      </Box>
    </Paper>
  );
}

/* ------------------------------------------------------------------ */
/* صفحه‌بندی فارسی                                                      */
/* ------------------------------------------------------------------ */

function FaPagination({ page, pages, onChange }: { page: number; pages: number; onChange: (p: number) => void }) {
  if (pages <= 1) return null;
  const nums: (number | "…")[] = [];
  for (let i = 1; i <= pages; i++) {
    if (i === 1 || i === pages || Math.abs(i - page) <= 1) nums.push(i);
    else if (nums[nums.length - 1] !== "…") nums.push("…");
  }
  return (
    <Stack direction="row" spacing={0.6} alignItems="center" justifyContent="center" sx={{ mt: 3.5 }} className="fade-in">
      <IconButton
        size="small" aria-label="صفحه قبل"
        disabled={page === 1}
        onClick={() => onChange(page - 1)}
        sx={{ border: "1px solid #f0d9df", "&:hover": { bgcolor: "#faf0f3" }, "&.Mui-disabled": { opacity: 0.35 } }}
      >
        ❮
      </IconButton>
      {nums.map((n, i) =>
        n === "…" ? (
          <Typography key={`e${i}`} variant="body2" color="text.secondary" px={0.4}>…</Typography>
        ) : (
          <Box
            key={n}
            component="button"
            onClick={() => onChange(n)}
            sx={{
              minWidth: 36, height: 36, borderRadius: "12px", cursor: "pointer",
              border: n === page ? "none" : "1px solid #f0d9df",
              background: n === page ? "linear-gradient(135deg,#b34460,#8a2f47)" : "#fff",
              color: n === page ? "#fff" : "text.primary",
              fontWeight: 800, fontSize: 14, fontFamily: "inherit",
              boxShadow: n === page ? "0 8px 18px rgba(168,58,84,.30)" : "none",
              transition: "all .2s ease",
              "&:hover": { borderColor: "primary.main", transform: "translateY(-2px)" },
            }}
          >
            {faNum(n)}
          </Box>
        ),
      )}
      <IconButton
        size="small" aria-label="صفحه بعد"
        disabled={page === pages}
        onClick={() => onChange(page + 1)}
        sx={{ border: "1px solid #f0d9df", "&:hover": { bgcolor: "#faf0f3" }, "&.Mui-disabled": { opacity: 0.35 } }}
      >
        ❯
      </IconButton>
    </Stack>
  );
}

/* ------------------------------------------------------------------ */
/* بخش مشاوران — نقشهٔ تعاملی ایران + کارت به تفکیک استان              */
/* ------------------------------------------------------------------ */

const ALL = "all";

export default function Counselors() {
  const [items, setItems] = useState<PublicCounselor[] | null>(null);
  const [selected, setSelected] = useState<string>(ALL); // ALL | کد استان | "none"
  const [hover, setHover] = useState<string | null>(null); // slug نقشه
  const [page, setPage] = useState(1);

  useEffect(() => {
    fetchPublicCounselors()
      .then((d) => setItems(d))
      .catch(() => setItems([]));
  }, []);

  // گروه‌بندی بر اساس کد استان
  const byProvince = useMemo(() => {
    const m = new Map<string, PublicCounselor[]>();
    for (const c of items ?? []) {
      const key = c.province_code || "none";
      if (!m.has(key)) m.set(key, []);
      m.get(key)!.push(c);
    }
    // مرتب‌سازی داخل هر گروه: امتیاز بیشتر اول، سپس تعداد نظر
    for (const list of m.values()) {
      list.sort((a, b) => (b.rating_avg ?? -1) - (a.rating_avg ?? -1) || b.review_count - a.review_count);
    }
    return m;
  }, [items]);

  const maxCount = useMemo(
    () => Math.max(1, ...[...byProvince.entries()].filter(([k]) => k !== "none").map(([, v]) => v.length)),
    [byProvince],
  );

  // فهرست نمایشی فعلی + صفحه‌بندی
  const filtered = useMemo(() => {
    if (!items) return [];
    if (selected === ALL) {
      const sorted = [...items].sort(
        (a, b) => (b.rating_avg ?? -1) - (a.rating_avg ?? -1) || b.review_count - a.review_count,
      );
      return sorted;
    }
    return byProvince.get(selected) ?? [];
  }, [items, selected, byProvince]);

  const pages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  useEffect(() => setPage(1), [selected]);
  const pageItems = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  const selectedName =
    selected === ALL
      ? "همه استان‌ها"
      : selected === "none"
        ? "سایر استان‌ها"
        : [...byProvince.values()].flat().find((c) => c.province_code === selected)?.province_name
          || Object.values(IRAN_PROVINCE_META).find((m) => m.code === selected)?.fa
          || "استان انتخابی";

  // فهرست نمایشی فعلی + صفحه‌بندی

  const handleSelect = (code: string) => setSelected((s) => (s === code ? ALL : code));

  return (
    <Box sx={{ py: { xs: 6, md: 9 }, position: "relative", overflow: "hidden" }}>
      {/* تزئین پس‌زمینهٔ بخش */}
      <Box className="decor-blob" sx={{ width: 380, height: 380, background: "rgba(208,107,128,.10)", top: 80, left: -140 }} />

      <Container id="counselors">
        <Reveal><SectionTitle label="تیم ما" title={texts.counselorsTitle} sub={texts.counselorsSub} /></Reveal>

        {items === null && (
          <Stack alignItems="center" py={6}>
            <CircularProgress sx={{ color: "primary.main" }} />
          </Stack>
        )}

        {items !== null && items.length === 0 && (
          <Typography textAlign="center" color="text.secondary">
            به‌زودی پروفایل مشاوران در این بخش نمایش داده می‌شود.
          </Typography>
        )}

        {items !== null && items.length > 0 && (
          <Box
            sx={{
              display: "grid",
              gridTemplateColumns: { xs: "minmax(0,1fr)", md: "minmax(0,460px) minmax(0,1fr)", lg: "minmax(0,520px) minmax(0,1fr)" },
              gap: { xs: 3, md: 4 },
              alignItems: "start",
            }}
          >
            {/* ---------------- نقشهٔ ایران ---------------- */}
            <Reveal variant="right">
              <Paper
                elevation={0}
                className="grad-border"
                sx={{
                  p: { xs: 2, md: 2.5 },
                  borderRadius: "24px",
                  background: "linear-gradient(170deg,#ffffff 0%,#fdf6f8 60%,#f6f1f9 100%)",
                  position: { md: "sticky" },
                  top: { md: 96 },
                  minWidth: 0,
                  overflow: "hidden",
                }}
              >
                <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ mb: 1 }}>
                  <Stack direction="row" alignItems="center" spacing={1}>
                    <Box sx={{ fontSize: 22 }}>🗺️</Box>
                    <Typography fontWeight={800} sx={{ fontSize: 15.5 }}>نقشهٔ مشاوران ایران</Typography>
                  </Stack>
                  <Chip
                    size="small"
                    label={`${faNum(items.length)} مشاور`}
                    sx={{ background: "linear-gradient(135deg,#b34460,#8a2f47)", color: "#fff", fontWeight: 800, fontSize: 12 }}
                  />
                </Stack>
                <Typography variant="caption" color="text.secondary" display="block" sx={{ mb: 1, lineHeight: 1.9 }}>
                  روی استان موردنظر بروید یا کلیک کنید تا مشاوران همان استان نمایش داده شود
                </Typography>

                <Box
                  component="svg"
                  viewBox={`0 0 ${IRAN_VIEWBOX.w} ${IRAN_VIEWBOX.h}`}
                  sx={{
                    width: "100%", maxWidth: "100%", height: "auto", display: "block",
                    "& .province": { cursor: "pointer", transition: "fill .25s ease, filter .25s ease" },
                    "& .province:hover": { filter: "brightness(1.08) drop-shadow(0 4px 10px rgba(124,39,64,.35))" },
                    "& .sea": { pointerEvents: "none" },
                  }}
                  role="group"
                  aria-label="نقشهٔ استان‌های ایران"
                >
                  {/* دریاها — تزئینی */}
                  {IRAN_SEA_PATHS.map((d, i) => (
                    <path key={`sea${i}`} className="sea" d={d} fill="#d8ecf4" />
                  ))}

                  {/* استان‌ها */}
                  {Object.entries(IRAN_PROVINCE_PATHS).map(([slug, d]) => {
                    const meta = IRAN_PROVINCE_META[slug];
                    const count = byProvince.get(meta.code)?.length ?? 0;
                    const isActive = selected === meta.code;
                    const isHover = hover === slug;
                    const t = count === 0 ? 0 : 0.22 + 0.78 * (count / maxCount);
                    const fill = isActive ? "#7c2740" : count === 0 ? "#ece5e9" : mixRose(t);
                    const center = IRAN_PROVINCE_CENTER[slug] ?? [600, 535];
                    return (
                      <Tooltip
                        key={slug}
                        title={
                          <Box sx={{ textAlign: "center", p: 0.3 }}>
                            <Typography sx={{ fontWeight: 800, fontSize: 13.5 }}>{meta.fa}</Typography>
                            <Typography sx={{ fontSize: 12, opacity: 0.9 }}>
                              {count > 0 ? `${faNum(count)} مشاور — برای مشاهده کلیک کنید` : "فعلاً بدون مشاور"}
                            </Typography>
                          </Box>
                        }
                        arrow
                        placement="top"
                        enterTouchDelay={0}
                      >
                        <g className="province">
                          <path
                            d={d}
                            fill={fill}
                            stroke={isActive ? "#4d1223" : isHover ? "#7c2740" : "#c9a9b4"}
                            strokeWidth={isActive ? 2.6 : isHover ? 2 : 0.8}
                            onMouseEnter={() => setHover(slug)}
                            onMouseLeave={() => setHover((h) => (h === slug ? null : h))}
                            onClick={() => handleSelect(meta.code)}
                            style={{ filter: isActive ? "drop-shadow(0 0 14px rgba(168,58,84,.55))" : undefined }}
                          />
                          {count > 0 && (
                            <g
                              onClick={() => handleSelect(meta.code)}
                              onMouseEnter={() => setHover(slug)}
                              onMouseLeave={() => setHover((h) => (h === slug ? null : h))}
                              style={{ pointerEvents: "visiblePainted" }}
                            >
                              <circle
                                cx={center[0]} cy={center[1]}
                                r={isActive || isHover ? 15 : 13}
                                fill={isActive ? "#fff" : "#fff"}
                                stroke={isActive ? "#a83a54" : "#d9a9b6"}
                                strokeWidth={isActive || isHover ? 2.4 : 1.4}
                                style={{ transition: "r .2s ease" }}
                              />
                              <text
                                x={center[0]} y={center[1] + 4.5}
                                textAnchor="middle"
                                fontSize={12.5}
                                fontWeight={800}
                                fill={isActive ? "#a83a54" : "#7c2740"}
                                style={{ pointerEvents: "none", userSelect: "none" }}
                              >
                                {faNum(count)}
                              </text>
                            </g>
                          )}
                        </g>
                      </Tooltip>
                    );
                  })}
                </Box>

                {/* راهنمای رنگ */}
                <Stack direction="row" alignItems="center" spacing={1} justifyContent="center" sx={{ mt: 1.2 }}>
                  <Typography variant="caption" color="text.secondary">کم</Typography>
                  <Box sx={{ width: 110, height: 8, borderRadius: 99, background: `linear-gradient(90deg,${mixRose(0.22)},${mixRose(1)})` }} />
                  <Typography variant="caption" color="text.secondary">زیاد</Typography>
                  <Box sx={{ width: 14, height: 14, borderRadius: "5px", bgcolor: "#ece5e9", border: "1px solid #d9c9d1", mx: 0.6 }} />
                  <Typography variant="caption" color="text.secondary">بدون مشاور</Typography>
                </Stack>
              </Paper>
            </Reveal>

            {/* ---------------- فهرست مشاوران ---------------- */}
            <Reveal variant="left">
              <Box>
                {/* سربرگ انتخاب استان */}
                <Paper
                  elevation={0}
                  sx={{
                    p: { xs: 1.6, md: 2 }, borderRadius: "18px", border: "1px solid #f3e2e7",
                    background: "linear-gradient(135deg,#ffffff,#fdf4f6)", mb: 2.4,
                    display: "flex", alignItems: "center", gap: 1.4, flexWrap: "wrap",
                  }}
                >
                  <Box sx={{ fontSize: 24 }}>{selected === ALL ? "✨" : "📍"}</Box>
                  <Box sx={{ flexGrow: 1 }}>
                    <Typography fontWeight={800} sx={{ fontSize: 16.5 }}>{selectedName}</Typography>
                    <Typography variant="caption" color="text.secondary">
                      {filtered.length > 0
                        ? `${faNum(filtered.length)} مشاور — صفحهٔ ${faNum(page)} از ${faNum(pages)}`
                        : "مشاوری برای نمایش نیست"}
                    </Typography>
                  </Box>
                  {selected !== ALL && (
                    <Button
                      size="small"
                      onClick={() => setSelected(ALL)}
                      sx={{ borderRadius: 99, fontWeight: 700, color: "primary.main", border: "1px solid #f0d9df" }}
                    >
                      نمایش همه
                    </Button>
                  )}
                </Paper>

                {/* انتخاب سریع استان */}
                <Stack
                  direction="row"
                  spacing={0.8}
                  sx={{
                    mb: 2.6, overflowX: "auto", pb: 1, flexWrap: { xs: "nowrap", sm: "wrap" },
                    maxWidth: "100%", minWidth: 0,
                    "&::-webkit-scrollbar": { height: 6 },
                    "&::-webkit-scrollbar-thumb": { background: "#ecd7de", borderRadius: 99 },
                  }}
                >
                  <Chip
                    label="همه"
                    onClick={() => setSelected(ALL)}
                    sx={{
                      fontWeight: 800, flexShrink: 0, cursor: "pointer", fontSize: 13,
                      background: selected === ALL ? "linear-gradient(135deg,#b34460,#8a2f47)" : "#fff",
                      color: selected === ALL ? "#fff" : "text.primary",
                      border: "1px solid #f0d9df",
                      "&:hover": { bgcolor: selected === ALL ? undefined : "#faf0f3" },
                    }}
                  />
                  {[...byProvince.entries()]
                    .filter(([code]) => code !== "none")
                    .sort((a, b) => b[1].length - a[1].length)
                    .map(([code, list]) => {
                      const fa = list[0]?.province_name || Object.values(IRAN_PROVINCE_META).find((m) => m.code === code)?.fa || code;
                      const on = selected === code;
                      return (
                        <Chip
                          key={code}
                          label={`${fa} (${faNum(list.length)})`}
                          onClick={() => setSelected(on ? ALL : code)}
                          sx={{
                            fontWeight: 700, flexShrink: 0, cursor: "pointer", fontSize: 13,
                            background: on ? "linear-gradient(135deg,#b34460,#8a2f47)" : "#fff",
                            color: on ? "#fff" : "text.primary",
                            border: "1px solid #f0d9df",
                            "&:hover": { bgcolor: on ? undefined : "#faf0f3" },
                          }}
                        />
                      );
                    })}
                  {byProvince.has("none") && (
                    <Chip
                      label={`سایر (${faNum(byProvince.get("none")!.length)})`}
                      onClick={() => setSelected(selected === "none" ? ALL : "none")}
                      sx={{
                        fontWeight: 700, flexShrink: 0, cursor: "pointer", fontSize: 13,
                        background: selected === "none" ? "linear-gradient(135deg,#b34460,#8a2f47)" : "#fff",
                        color: selected === "none" ? "#fff" : "text.primary",
                        border: "1px solid #f0d9df",
                      }}
                    />
                  )}
                </Stack>

                {/* کارت‌ها */}
                {pageItems.length === 0 ? (
                  <Paper
                    elevation={0}
                    sx={{ p: 5, textAlign: "center", border: "1.5px dashed #e8ccd4", borderRadius: "20px", bgcolor: "#fdf8fa" }}
                  >
                    <Box sx={{ fontSize: 42, mb: 1 }}>🌿</Box>
                    <Typography fontWeight={700} color="text.secondary">
                      هنوز مشاوری در «{selectedName}» ثبت نشده است
                    </Typography>
                    <Typography variant="body2" color="text.secondary" sx={{ mt: 0.8, lineHeight: 2 }}>
                      استان دیگری را از نقشه انتخاب کنید یا «نمایش همه» را بزنید.
                    </Typography>
                  </Paper>
                ) : (
                  <Box
                    key={`${selected}-${page}`}
                    className="stagger-grid"
                    sx={{
                      display: "grid",
                      gridTemplateColumns: { xs: "1fr", sm: "repeat(2,1fr)" },
                      gap: { xs: 2, md: 2.6 },
                    }}
                  >
                    {pageItems.map((c) => (
                      <CounselorCard key={c.id} c={c} />
                    ))}
                  </Box>
                )}

                <FaPagination page={page} pages={pages} onChange={setPage} />
              </Box>
            </Reveal>
          </Box>
        )}
      </Container>
    </Box>
  );
}
