// فاز ۶۹ - صفحهٔ رزرو: فهرست متخصصان (الگوی اسنپ‌داکتر)
//
// پیش‌تر این صفحه یک ویزارد ۳ مرحله‌ای داخل خودش بود؛ با اضافه‌شدن پروفایل
// متخصص (/specialist/:id) و پرداخت آنلاین، این صفحه حالا «فهرست انتخاب
// مشاور» است: کارت هر مشاور با عکس، عنوان تخصص، امتیاز ستاره‌دار و تعداد
// نظرات نمایش داده می‌شود و با کلیک، پروفایل کامل (تقویم نوبت + پرداخت +
// نظرات) باز می‌شود. لینک‌های قدیمی /booking?counselor=<id> به پروفایل
// منتقل می‌شوند (سازگاری با کارت‌های کلینیک و لینک‌های پخش‌شده).
import {
  Avatar, Box, Button, Card, CardContent, Chip, CircularProgress, Container,
  FormControl, InputLabel, MenuItem, Select, Stack, Typography,
} from "@mui/material";
import { useEffect, useMemo, useState } from "react";
import { Link as RouterLink, useNavigate, useSearchParams } from "react-router-dom";
import { fetchPublicCounselors } from "../api";
import type { PublicCounselor } from "../api";
import Header from "../components/Header";
import Footer from "../components/Footer";

function faNum(n: number | string): string {
  return Number(n).toLocaleString("fa-IR");
}

function Stars({ value, size = 16 }: { value: number | null; size?: number }) {
  const v = value ?? 0;
  return (
    <Stack direction="row" spacing={0.25} alignItems="center" aria-label={`امتیاز ${faNum(v)} از ۵`}>
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

export default function BookingPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [counselors, setCounselors] = useState<PublicCounselor[] | null>(null);
  // فاز ۶۷: فیلتر استان روی فهرست مشاوران قابل رزرو
  const [province, setProvince] = useState<string>("");

  useEffect(() => {
    fetchPublicCounselors()
      .then((list) => {
        setCounselors(list);
        // سازگاری با لینک‌های قدیمی: /booking?counselor=<id> → پروفایل متخصص
        const wanted = searchParams.get("counselor");
        if (wanted) navigate(`/specialist/${encodeURIComponent(wanted)}`, { replace: true });
      })
      .catch(() => setCounselors([]));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const provinces = useMemo(() => {
    const names = new Set<string>();
    for (const c of counselors ?? []) if (c.province_name) names.add(c.province_name);
    return Array.from(names).sort((a, b) => a.localeCompare(b, "fa"));
  }, [counselors]);
  const visibleCounselors = useMemo(
    () => (province ? (counselors ?? []).filter((c) => c.province_name === province) : (counselors ?? [])),
    [counselors, province],
  );

  return (
    <Box>
      <Header />
      <Box sx={{ background: "linear-gradient(180deg,#fdf3f5 0%,#ffffff 100%)", pb: 6 }}>
        <Container sx={{ py: { xs: 4, md: 6 }, minHeight: "60vh" }}>
          <Typography variant="h4" fontWeight={800} color="primary.main" textAlign="center">
            رزرو نوبت مشاوره
          </Typography>
          <Typography variant="body1" color="text.secondary" textAlign="center" mb={{ xs: 3, md: 4 }}>
            متخصص دلخواه خود را انتخاب کنید؛ در پروفایل او، روز و ساعت و خدمت را انتخاب و آنلاین پرداخت کنید.
          </Typography>

          <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5} alignItems={{ sm: "center" }} sx={{ mb: 3 }}>
            <FormControl size="small" sx={{ minWidth: 240 }}>
              <InputLabel>فیلتر استان</InputLabel>
              <Select value={province} label="فیلتر استان" onChange={(e) => setProvince(e.target.value)}>
                <MenuItem value="">همهٔ استان‌ها</MenuItem>
                {provinces.map((p) => (
                  <MenuItem key={p} value={p}>{p}</MenuItem>
                ))}
              </Select>
            </FormControl>
            <Typography variant="body2" color="text.secondary">
              {counselors === null ? "…" : `${faNum(visibleCounselors.length)} مشاور قابل رزرو`}
            </Typography>
          </Stack>

          {counselors === null && (
            <Stack alignItems="center" py={6} role="status" aria-label="در حال بارگذاری مشاوران">
              <CircularProgress sx={{ color: "primary.main" }} />
            </Stack>
          )}

          {counselors !== null && visibleCounselors.length === 0 && (
            <Typography textAlign="center" color="text.secondary" py={3}>
              در حال حاضر مشاوری برای رزرو در این استان موجود نیست.
            </Typography>
          )}

          <Box
            sx={{
              display: "grid",
              gridTemplateColumns: { xs: "1fr", sm: "repeat(2,1fr)", md: "repeat(3,1fr)" },
              gap: { xs: 2, md: 2.5 },
            }}
          >
            {visibleCounselors.map((c) => (
              <Card
                key={c.id}
                className="hover-lift"
                elevation={0}
                sx={{
                  borderRadius: "18px",
                  border: "1px solid #f3e2e7",
                  background: "linear-gradient(170deg,#ffffff 0%,#fbf3f5 100%)",
                  overflow: "hidden",
                  display: "flex",
                  flexDirection: "column",
                }}
              >
                <Box sx={{ height: 5, background: "linear-gradient(90deg,#a83a54,#c99a5b)" }} />
                <CardContent sx={{ textAlign: "center", p: 2.5, display: "flex", flexDirection: "column", flex: 1 }}>
                  {c.photo_url ? (
                    <Box
                      component="img"
                      src={c.photo_url}
                      alt={c.name}
                      sx={{
                        width: 84, height: 84, borderRadius: "50%", objectFit: "cover",
                        mx: "auto", mb: 1.2, border: "4px solid #fff",
                        boxShadow: "0 8px 22px rgba(168,58,84,.18)",
                      }}
                    />
                  ) : (
                    <Avatar
                      sx={{
                        width: 84, height: 84, mx: "auto", mb: 1.2, fontSize: 34,
                        background: "linear-gradient(135deg,#b34460,#8a2f47)",
                        border: "4px solid #fff", boxShadow: "0 8px 22px rgba(168,58,84,.18)",
                      }}
                    >
                      {c.name.charAt(0)}
                    </Avatar>
                  )}
                  <Typography variant="h6" fontWeight={800}>{c.name}</Typography>
                  {c.professional_title && (
                    <Typography variant="body2" color="text.secondary" sx={{ mt: 0.4 }}>{c.professional_title}</Typography>
                  )}
                  <Stack direction="row" spacing={1} justifyContent="center" flexWrap="wrap" useFlexGap sx={{ mt: 1 }}>
                    {c.specialty && (
                      <Chip size="small" label={c.specialty} sx={{ bgcolor: "#faeef1", color: "primary.main", fontWeight: 700, border: "1px solid #f0d9df" }} />
                    )}
                    {c.province_name && (
                      <Chip size="small" variant="outlined" label={`رز — ${c.province_name}`} sx={{ fontSize: 11.5 }} />
                    )}
                  </Stack>
                  <Stack direction="row" spacing={0.75} alignItems="center" justifyContent="center" sx={{ mt: 1.2 }}>
                    <Stars value={c.rating_avg ?? null} />
                    <Typography variant="body2" fontWeight={700} color="text.primary">
                      {c.rating_avg ? faNum(c.rating_avg) : "جدید"}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      ({faNum(c.review_count)} نظر)
                    </Typography>
                  </Stack>
                  <Box sx={{ flex: 1 }} />
                  <Button
                    component={RouterLink}
                    to={`/specialist/${encodeURIComponent(c.id)}`}
                    variant="contained"
                    size="small"
                    sx={{ mt: 1.8, borderRadius: 99, fontWeight: 800, px: 3 }}
                  >
                    رزرو نوبت
                  </Button>
                </CardContent>
              </Card>
            ))}
          </Box>
        </Container>
      </Box>
      <Footer />
    </Box>
  );
}
