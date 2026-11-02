import { Box, Container, Paper, Typography } from "@mui/material";
import { TESTIMONIAL_SHOTS } from "../content/assets";
import { texts } from "../content/texts";
import Reveal from "./Reveal";
import SectionTitle from "./SectionTitle";

export default function Testimonials() {
  return (
    <Box sx={{ bgcolor: "#faf1f4", py: { xs: 6, md: 9 } }}>
      <Container>
        <SectionTitle label="بازخورد" title={texts.testimonialsTitle} sub={texts.testimonialsSub} />
        <Box display="grid" gridTemplateColumns={{ xs: "1fr", sm: "1fr 1fr" }} gap={3}>
          {TESTIMONIAL_SHOTS.map((src, i) => (
            <Reveal key={src} delay={i * 130} variant="zoom">
            <Paper
              className="hover-lift"
              elevation={2}
              sx={{ p: 1.5, borderRadius: 4, border: "1px solid #f6e3e8" }}
            >
              <Box
                component="img"
                src={src}
                alt={texts.testimonialsTitle}
                sx={{ width: "100%", height: 300, objectFit: "contain", borderRadius: 2, bgcolor: "#fff" }}
              />
            </Paper>
            </Reveal>
          ))}
        </Box>
        <Typography variant="caption" color="text.secondary" display="block" textAlign="center" mt={2}>
          نمونه بازخوردهای دریافتی — قابل به‌روزرسانی از پنل مدیریت
        </Typography>
      </Container>
    </Box>
  );
}
