import { Box, Button, Container, Stack, Typography } from "@mui/material";
import { texts } from "../content/texts";
import Reveal from "./Reveal";

export default function CtaBand() {
  return (
    <Box
      sx={{
        position: "relative",
        overflow: "hidden",
        background: "linear-gradient(135deg,#a83a54 0%,#7c2740 55%,#5c4a6e 100%)",
        py: { xs: 7, md: 9 },
      }}
    >
      <Box className="decor-blob" sx={{ width: 260, height: 260, background: "rgba(255,255,255,.10)", top: -90, left: -60 }} />
      <Box className="decor-ring" sx={{ width: 180, height: 180, bottom: -70, right: "8%", borderColor: "rgba(255,255,255,.18)" }} />
      <Container>
        <Reveal variant="zoom">
        <Stack spacing={2} alignItems="center" textAlign="center">
          <Typography variant="h3" fontWeight={800} color="#fff" sx={{ fontSize: { xs: 26, md: 38 } }}>
            {texts.ctaBand.title}
          </Typography>
          <Typography variant="body1" sx={{ maxWidth: 560, color: "rgba(255,255,255,0.92)", lineHeight: 2 }}>
            {texts.ctaBand.sub}
          </Typography>
          <Stack direction={{ xs: "column", sm: "row" }} spacing={1.6} mt={1.5}>
            <Button
              href="#consult"
              size="large"
              sx={{ bgcolor: "#fff", color: "primary.main", fontWeight: 800, px: 4, "&:hover": { bgcolor: "#fbe9ee" } }}
            >
              {texts.ctaBand.button}
            </Button>
            <Button
              href="/booking"
              size="large"
              variant="outlined"
              sx={{ px: 4, color: "#fff", borderColor: "rgba(255,255,255,.5)", "&:hover": { borderColor: "#fff", bgcolor: "rgba(255,255,255,.08)" } }}
            >
              رزرو نوبت آنلاین
            </Button>
          </Stack>
        </Stack>
        </Reveal>
      </Container>
    </Box>
  );
}
