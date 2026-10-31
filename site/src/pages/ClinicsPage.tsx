// فاز ۶۶ - نقشهٔ کلینیک‌های شرکت رز
//
// نقشهٔ Leaflet (کاشی OpenStreetMap) با نشانگر هر کلینیک استانی؛ با کلیک روی
// هر نشانگر، کارتِ کامل مشخصات کلینیک (نشانی، کدپستی، تلفن، مدیر، مسئول
// اجرایی، ساعات کاری و لینک مسیریابی نشان) به‌همراه فهرست مشاورانِ همان
// کلینیک نمایش داده می‌شود. انتخاب از فهرست استانی هم همان کار را می‌کند.
import "leaflet/dist/leaflet.css";
import L from "leaflet";
import {
  Box, Chip, CircularProgress, Container, Divider, Grid, Link, Paper,
  Stack, Typography, Button,
} from "@mui/material";
import { useEffect, useMemo, useRef, useState } from "react";
import Header from "../components/Header";
import Footer from "../components/Footer";
import { fetchClinicsMap } from "../api";
import type { MapClinic } from "../api";

const faNum = (n: number) => n.toLocaleString("fa-IR");

function pinIcon(count: number) {
  return L.divIcon({
    className: "rose-pin",
    html:
      `<div style="position:relative;width:34px;height:46px;transform:translate(-3px,-40px);">` +
      `<svg width="34" height="46" viewBox="0 0 34 46" xmlns="http://www.w3.org/2000/svg">` +
      `<path d="M17 1C8.2 1 1 8.1 1 16.8 1 28.6 17 45 17 45s16-16.4 16-28.2C33 8.1 25.8 1 17 1z" fill="#a83a54" stroke="#fff" stroke-width="2"/>` +
      `</svg>` +
      `<span style="position:absolute;top:6px;left:0;right:0;text-align:center;color:#fff;font-size:12px;font-weight:700;font-family:Vazirmatn,sans-serif;">${faNum(count)}</span>` +
      `</div>`,
    iconSize: [34, 46],
    iconAnchor: [14, 44],
    popupAnchor: [0, -40],
  });
}

function ClinicCard({ c }: { c: MapClinic }) {
  const Row = ({ icon, label, value, href }: { icon: string; label: string; value: string | null; href?: string | null }) =>
    value ? (
      <Stack direction="row" spacing={1} alignItems="flex-start" sx={{ py: 0.4 }}>
        <Box component="span" sx={{ fontSize: 15, lineHeight: 1.5 }}>{icon}</Box>
        <Typography variant="body2" sx={{ lineHeight: 1.9 }}>
          <b>{label}: </b>
          {href ? <Link href={href} sx={{ fontWeight: 600, direction: "ltr", unicodeBidi: "isolate" }}>{value}</Link> : value}
        </Typography>
      </Stack>
    ) : null;

  return (
    <Paper elevation={3} sx={{ p: { xs: 2, md: 2.5 }, borderRadius: 3, border: "1px solid #f3dce2" }}>
      <Stack direction="row" justifyContent="space-between" alignItems="center" flexWrap="wrap" gap={1}>
        <Typography variant="h6" fontWeight={800} color="primary">
          کلینیک رز — استان {c.province || c.city}
        </Typography>
        <Chip size="small" color="primary" label={`${faNum(c.counselor_count)} مشاور`} />
      </Stack>

      <Box sx={{ mt: 1 }}>
        <Row icon="🏥" label="نشانی" value={c.address} />
        <Row icon="📮" label="کدپستی" value={c.postal_code} />
        <Row icon="☎️" label="شماره کلینیک" value={c.phone} href={c.phone ? `tel:${c.phone}` : null} />
        <Row icon="👤" label="مدیر کلینیک" value={c.manager_name ? `${c.manager_name}${c.manager_phone ? ` — ${c.manager_phone}` : ""}` : null}
          href={c.manager_phone ? `tel:${c.manager_phone}` : null} />
        <Row icon="📋" label="مسئول اجرایی" value={c.exec_name ? `${c.exec_name}${c.exec_phone ? ` — ${c.exec_phone}` : ""}` : null}
          href={c.exec_phone ? `tel:${c.exec_phone}` : null} />
        <Row icon="🕗" label="ساعات کاری" value={c.working_hours} />
        {c.map_url && (
          <Stack direction="row" spacing={1} alignItems="center" sx={{ py: 0.4 }}>
            <Box component="span" sx={{ fontSize: 15 }}>📍</Box>
            <Link href={c.map_url} target="_blank" rel="noopener" sx={{ fontWeight: 700 }}>
              مسیریابی در نشان
            </Link>
          </Stack>
        )}
      </Box>

      <Divider sx={{ my: 1.5 }} />
      <Typography variant="subtitle1" fontWeight={800} sx={{ mb: 0.5 }}>
        مشاوران این کلینیک ({faNum(c.counselor_count)})
      </Typography>
      {/* فاز ۶۷: موبایل و رتبه از نمایش عمومی حذف شد (کسی نباید ببیند)؛
          برای مشاوران واجد شرط رزرو، دکمهٔ «رزرو نوبت» نمایش داده می‌شود. */}
      {c.counselors.length === 0 ? (
        <Typography variant="body2" color="text.secondary">مشاوری برای این کلینیک ثبت نشده است.</Typography>
      ) : (
        <Stack spacing={0.8} sx={{ mt: 1 }}>
          {c.counselors.map((x, i) => (
            <Stack key={i} direction="row" justifyContent="space-between" alignItems="center" flexWrap="wrap" gap={0.5}
              sx={{ bgcolor: "#faf5f7", borderRadius: 2, px: 1.4, py: 0.7 }}>
              <Typography variant="body2" fontWeight={700}>{x.name}</Typography>
              <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap">
                {x.degree && <Chip size="small" label={x.degree} sx={{ bgcolor: "#efe3ee", height: 24 }} />}
                {x.bookable && (
                  <Button
                    size="small"
                    variant="contained"
                    href={`/specialist/${encodeURIComponent(x.id)}`}
                    sx={{ height: 26, minWidth: 0, px: 1.2, fontSize: 12, whiteSpace: "nowrap" }}
                  >
                    رزرو نوبت
                  </Button>
                )}
              </Stack>
            </Stack>
          ))}
          <Typography variant="caption" color="text.secondary" sx={{ mt: 0.5 }}>
            دکمهٔ «رزرو نوبت» فقط برای مشاوران دارای مجوز معتبر فعال است؛ برای هماهنگی با سایر مشاوران با خود کلینیک تماس بگیرید.
          </Typography>
        </Stack>
      )}
    </Paper>
  );
}

export default function ClinicsPage() {
  const [items, setItems] = useState<MapClinic[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<MapClinic | null>(null);
  const mapDivRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<L.Map | null>(null);
  const markersRef = useRef<L.LayerGroup | null>(null);

  // بارگذاری داده
  useEffect(() => {
    fetchClinicsMap().then((xs) => setItems(xs)).catch(() => setError("خطا در دریافت کلینیک‌ها"));
  }, []);

  // ساخت نقشه + نشانگرها (به‌محض در دست بودن داده — div نقشه شرطی است)
  useEffect(() => {
    if (!items || !mapDivRef.current || mapRef.current) return;
    const map = L.map(mapDivRef.current, {
      center: [32.6, 52.5],
      zoom: 5,
      scrollWheelZoom: true,
    });
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 18,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    }).addTo(map);
    const group = L.layerGroup().addTo(map);
    for (const c of items) {
      if (c.latitude == null || c.longitude == null) continue;
      const m = L.marker([c.latitude, c.longitude], { icon: pinIcon(c.counselor_count) });
      m.on("click", () => setSelected(c));
      m.bindTooltip(`کلینیک رز — ${c.province || c.city}`, { direction: "top" });
      m.addTo(group);
    }
    mapRef.current = map;
    markersRef.current = group;
    return () => {
      map.remove();
      mapRef.current = null;
      markersRef.current = null;
    };
  }, [items]);

  // پرواز به نشانگر انتخاب‌شده
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !selected || selected.latitude == null || selected.longitude == null) return;
    map.flyTo([selected.latitude, selected.longitude], 10, { duration: 0.8 });
  }, [selected]);

  const list = useMemo(() => items || [], [items]);

  return (
    <>
      <Header />
      <Container maxWidth="lg" sx={{ py: { xs: 3, md: 5 } }}>
        <Typography variant="h4" fontWeight={900} color="primary" textAlign="center" gutterBottom>
          شبکهٔ کلینیک‌های شرکت رز
        </Typography>
        <Typography variant="body1" color="text.secondary" textAlign="center" sx={{ mb: 3 }}>
          روی نشانگر هر استان کلیک کنید تا مشخصات کامل کلینیک و مشاوران آن نمایش داده شود.
        </Typography>

        {error && <Typography color="error" textAlign="center">{error}</Typography>}
        {!items && !error && (
          <Stack alignItems="center" py={8}><CircularProgress color="primary" /></Stack>
        )}

        {items && (
          <Grid container spacing={3}>
            <Grid item xs={12} md={7}>
              <Box
                ref={mapDivRef}
                sx={{
                  height: { xs: 380, md: 560 },
                  borderRadius: 3,
                  overflow: "hidden",
                  border: "1px solid #f3dce2",
                  zIndex: 0,
                }}
              />
              <Stack direction="row" spacing={1} useFlexGap flexWrap="wrap" sx={{ mt: 2, justifyContent: "center" }}>
                {list.map((c) => (
                  <Chip
                    key={c.id}
                    label={c.province || c.city}
                    onClick={() => setSelected(c)}
                    variant={selected?.id === c.id ? "filled" : "outlined"}
                    sx={{
                      borderColor: "#d9a7b5",
                      bgcolor: selected?.id === c.id ? "primary.main" : "#fff",
                      color: selected?.id === c.id ? "#fff" : "text.primary",
                      "&:hover": { bgcolor: selected?.id === c.id ? "primary.main" : "#faf0f3" },
                    }}
                  />
                ))}
              </Stack>
            </Grid>
            <Grid item xs={12} md={5}>
              {selected ? (
                <ClinicCard c={selected} />
              ) : (
                <Paper elevation={0} sx={{ p: 4, textAlign: "center", border: "1px dashed #e0c3cd", borderRadius: 3, bgcolor: "#fdf7f9" }}>
                  <Typography variant="h6" fontWeight={800} color="primary" gutterBottom>
                    یک کلینیک انتخاب کنید
                  </Typography>
                  <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                    روی نشانگر روی نقشه یا نام استان از فهرست کلیک کنید؛ کارت کامل مشخصات کلینیک و
                    مشاوران آن در همین قسمت نمایش داده می‌شود.
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    مجموع مشاوران فعال: {faNum(items.reduce((s, x) => s + x.counselor_count, 0))} نفر در {faNum(items.length)} استان
                  </Typography>
                </Paper>
              )}
            </Grid>
          </Grid>
        )}

        <Stack alignItems="center" sx={{ mt: 5 }}>
          <Button href="/booking" variant="contained" size="large" sx={{ px: 4 }}>
            رزرو نوبت آنلاین
          </Button>
        </Stack>
      </Container>
      <Footer />
    </>
  );
}
