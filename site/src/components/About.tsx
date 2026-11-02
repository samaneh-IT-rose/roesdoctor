import { Box, Container, Paper, Stack, Typography } from "@mui/material";
import { useState } from "react";
import { SUGGESTED } from "../content/assets";
import { texts } from "../content/texts";
import Reveal from "./Reveal";
import SectionTitle from "./SectionTitle";

export default function About() {
  const [imgOk, setImgOk] = useState(true);
  const img = SUGGESTED.about;

  return (
    <Container id="about" sx={{ py: 9 }}>
      <SectionTitle label="ما که هستیم" title={texts.aboutTitle} />
      <Reveal variant="up">
      <Stack direction={{ xs: "column", md: "row" }} spacing={4} alignItems="center">
        {img && imgOk && (
          <Box
            component="img"
            src={img}
            alt={texts.aboutTitle}
            onError={() => setImgOk(false)}
            sx={{ width: { xs: "100%", md: 360 }, borderRadius: "20px", boxShadow: "0 18px 44px rgba(168,58,84,.16)", border: "1px solid #f3e2e7" }}
          />
        )}
        <Stack spacing={2}>
          {texts.about.map((p, i) => (
            <Typography key={i} variant="body1" color="text.primary" sx={{ lineHeight: 2 }}>
              {p}
            </Typography>
          ))}
          <Stack direction="row" spacing={2} mt={2} flexWrap="wrap" useFlexGap>
            {texts.stats.map((s) => (
              <Paper key={s.label} elevation={1} sx={{ p: 2, minWidth: 130, textAlign: "center", borderRadius: 3 }}>
                <Typography variant="h5" fontWeight={800} color="primary.main">{s.n}</Typography>
                <Typography variant="caption" color="text.secondary">{s.label}</Typography>
              </Paper>
            ))}
          </Stack>
        </Stack>
      </Stack>
      </Reveal>
    </Container>
  );
}
