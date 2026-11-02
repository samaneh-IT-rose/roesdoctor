import {
  AppBar, Box, Button, Container, Drawer, IconButton, List, ListItem,
  Stack, Toolbar, Typography, useScrollTrigger,
} from "@mui/material";
import { useEffect, useState } from "react";
import { SUGGESTED } from "../content/assets";
import { texts } from "../content/texts";

/** نوار پیشرفت اسکرول بالای صفحه */
function ScrollProgress() {
  const [w, setW] = useState(0);
  useEffect(() => {
    const onScroll = () => {
      const h = document.documentElement;
      const max = h.scrollHeight - h.clientHeight;
      setW(max > 0 ? (h.scrollTop / max) * 100 : 0);
    };
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);
  return <Box className="scroll-progress" sx={{ width: `${w}%` }} aria-hidden />;
}

export default function Header() {
  const [open, setOpen] = useState(false);
  const raised = useScrollTrigger({ disableHysteresis: true, threshold: 8 });

  return (
    <>
      <ScrollProgress />
      {/* نوار اطلاع‌رسانی بالای سایت */}
      <Box sx={{ background: "linear-gradient(90deg,#7c2740,#a83a54 55%,#5c4a6e)", color: "#fff", py: 0.7, textAlign: "center" }}>
        <Typography variant="caption" sx={{ fontWeight: 600, letterSpacing: 0.2 }}>
          ✦ {texts.topbar}
        </Typography>
      </Box>

      <AppBar
        position="sticky"
        elevation={0}
        sx={{
          bgcolor: raised ? "rgba(255,255,255,0.97)" : "rgba(255,255,255,0.88)",
          backdropFilter: "blur(12px)",
          borderBottom: "1px solid #f3dce2",
          boxShadow: raised ? "0 10px 30px rgba(124,39,64,.08)" : "none",
          transition: "background .25s ease, box-shadow .25s ease",
        }}
      >
        <Container maxWidth="lg">
          <Toolbar disableGutters sx={{ gap: 1, minHeight: { xs: 64, md: 72 } }}>
            <Stack direction="row" alignItems="center" spacing={1.2} sx={{ flexGrow: 1 }}>
              {SUGGESTED.logo ? (
                <Box component="img" src={SUGGESTED.logo} alt={texts.brand} sx={{ height: 44 }} />
              ) : (
                <Typography variant="h6" fontWeight={800} color="primary">
                  {texts.brand}
                </Typography>
              )}
              <Typography variant="caption" color="text.secondary" sx={{ display: { xs: "none", lg: "block" } }}>
                {texts.brandSub}
              </Typography>
            </Stack>

            {texts.nav.map((n) => (
              <Button
                key={n.id}
                href={`#${n.id}`}
                className="nav-link"
                sx={{
                  color: "text.primary",
                  display: { xs: "none", lg: "inline-flex" },
                  fontWeight: 600,
                  fontSize: 14.5,
                  "&:hover": { color: "primary.main", bgcolor: "transparent" },
                }}
              >
                {n.label}
              </Button>
            ))}

            <Button
              href="/clinics"
              className="nav-link"
              sx={{
                color: "text.primary",
                display: { xs: "none", lg: "inline-flex" },
                fontWeight: 600,
                fontSize: 14.5,
                "&:hover": { color: "primary.main", bgcolor: "transparent" },
              }}
            >
              کلینیک‌ها
            </Button>

            <Button
              href="/panel/"
              variant="outlined"
              size="small"
              sx={{
                display: { xs: "none", md: "inline-flex" },
                borderColor: "#d9c9e2",
                color: "secondary.main",
                fontWeight: 700,
                "&:hover": { borderColor: "secondary.main", bgcolor: "rgba(92,74,110,.06)", transform: "translateY(-1px)" },
                transition: "all .2s ease",
              }}
            >
              ورود به سامانه
            </Button>
            <Button href="/booking" variant="contained" size="small" className="shine-btn" sx={{ display: { xs: "none", sm: "inline-flex" }, px: 2.2 }}>
              رزرو نوبت
            </Button>

            {/* دکمه همبرگری — بدون وابستگی به @mui/icons-material */}
            <IconButton
              onClick={() => setOpen(true)}
              sx={{ display: { lg: "none" }, color: "primary.main" }}
              aria-label="باز کردن منو"
            >
              <Box sx={{ display: "flex", flexDirection: "column", gap: "4px" }}>
                <Box sx={{ width: 20, height: 2, bgcolor: "currentColor", borderRadius: 2 }} />
                <Box sx={{ width: 20, height: 2, bgcolor: "currentColor", borderRadius: 2 }} />
                <Box sx={{ width: 14, height: 2, bgcolor: "currentColor", borderRadius: 2 }} />
              </Box>
            </IconButton>
          </Toolbar>
        </Container>
      </AppBar>

      <Drawer anchor="left" open={open} onClose={() => setOpen(false)} PaperProps={{ sx: { width: 300, p: 2 } }}>
        <Stack direction="row" justifyContent="space-between" alignItems="center" mb={2}>
          <Typography variant="h6" fontWeight={800} color="primary">{texts.brand}</Typography>
          <IconButton onClick={() => setOpen(false)} aria-label="بستن منو">
            <Box component="span" sx={{ fontSize: 20, lineHeight: 1 }}>✕</Box>
          </IconButton>
        </Stack>
        <List sx={{ mb: 2 }}>
          <ListItem component="a" href="/clinics" onClick={() => setOpen(false)}
            sx={{ borderRadius: 2, color: "text.primary", fontWeight: 600, mb: 0.5, "&:hover": { bgcolor: "#faf0f3" } }}>
            کلینیک‌ها
          </ListItem>
          {texts.nav.map((n) => (
            <ListItem key={n.id} component="a" href={`#${n.id}`} onClick={() => setOpen(false)}
              sx={{ borderRadius: 2, color: "text.primary", fontWeight: 600, mb: 0.5, "&:hover": { bgcolor: "#faf0f3" } }}>
              {n.label}
            </ListItem>
          ))}
        </List>
        <Stack spacing={1.2}>
          <Button href="/booking" variant="contained" fullWidth>رزرو نوبت</Button>
          <Button href="/panel/" variant="outlined" fullWidth sx={{ borderColor: "secondary.main", color: "secondary.main" }}>
            ورود به سامانه
          </Button>
        </Stack>
      </Drawer>
    </>
  );
}
