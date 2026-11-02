import { Box, Button, Container, Paper, Stack, Typography } from "@mui/material";
import Reveal from "./Reveal";
import SectionTitle from "./SectionTitle";
import { texts } from "../content/texts";

export default function BookingSteps() {
  return (
    <Box id="steps" sx={{ py: { xs: 6, md: 9 }, bgcolor: "#fff", position: "relative", overflow: "hidden" }}>
      <Box className="decor-blob" sx={{ width: 300, height: 300, background: "rgba(201,154,91,.12)", top: -80, left: -80 }} />
      <Container maxWidth="lg">
        <SectionTitle label="نوبت‌دهی" title={texts.stepsTitle} sub={texts.stepsSub} />

        <Stack
          direction={{ xs: "column", md: "row" }}
          spacing={{ xs: 2, md: 2.4 }}
          sx={{ position: "relative" }}
        >
          {/* خط اتصال گام‌ها (دسکتاپ) */}
          <Box
            sx={{
              display: { xs: "none", md: "block" },
              position: "absolute", top: 38, right: "12%", left: "12%", height: 2,
              background: "repeating-linear-gradient(90deg,#e8c4ce 0 10px,transparent 10px 20px)",
            }}
          />
          {texts.steps.map((s, i) => (
            <Reveal key={s.n} delay={i * 130} variant="up" sx={{ flex: 1, position: "relative", zIndex: 1 }}>
            <Paper
              elevation={0}
              className="hover-lift card-shine"
              sx={{
                flex: 1, p: { xs: 2.4, md: 3 }, borderRadius: "18px",
                border: "1px solid #f3e2e7", textAlign: "center", position: "relative", height: "100%",
              }}
            >
              <Box
                sx={{
                  width: 76, height: 76, mx: "auto", mb: 2, borderRadius: "50%",
                  display: "flex", alignItems: "center", justifyContent: "center",
                  background: "linear-gradient(135deg,#b34460,#8a2f47)",
                  color: "#fff", fontSize: 30, fontWeight: 800,
                  boxShadow: "0 10px 24px rgba(168,58,84,.30)",
                  transition: "transform .3s ease",
                  "&:hover": { transform: "scale(1.08) rotate(4deg)" },
                }}
              >
                {s.n}
              </Box>
              <Typography variant="subtitle1" fontWeight={800} gutterBottom>{s.title}</Typography>
              <Typography variant="body2" color="text.secondary" sx={{ lineHeight: 2 }}>
                {s.desc}
              </Typography>
            </Paper>
            </Reveal>
          ))}
        </Stack>

        <Stack direction="row" justifyContent="center" mt={5}>
          <Button href="/booking" variant="contained" size="large" className="shine-btn" sx={{ px: 4, py: 1.5, fontSize: 15.5 }}>
            شروع رزرو نوبت
          </Button>
        </Stack>
      </Container>
    </Box>
  );
}
