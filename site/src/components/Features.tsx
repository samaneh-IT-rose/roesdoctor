import { Box, Container, Paper, Stack, Typography } from "@mui/material";
import Reveal from "./Reveal";
import SectionTitle from "./SectionTitle";
import { texts } from "../content/texts";

export default function Features() {
  return (
    <Box sx={{ py: { xs: 6, md: 9 } }}>
      <Container maxWidth="lg">
        <SectionTitle label="چرا ما" title={texts.featuresTitle} sub={texts.featuresSub} />
        <Box
          sx={{
            display: "grid",
            gridTemplateColumns: { xs: "1fr", sm: "repeat(2,1fr)", lg: "repeat(4,1fr)" },
            gap: { xs: 2, md: 2.6 },
          }}
        >
          {texts.features.map((f, i) => (
            <Reveal key={f.title} delay={(i % 4) * 90} variant="up" sx={{ height: "100%" }}>
            <Paper
              elevation={0}
              className="hover-lift card-shine"
              sx={{
                p: { xs: 2.4, md: 3 },
                borderRadius: "18px",
                background: i % 2 === 0
                  ? "linear-gradient(160deg,#ffffff 0%,#faf1f3 100%)"
                  : "linear-gradient(160deg,#ffffff 0%,#f3eef7 100%)",
                border: "1px solid #f3e2e7",
              }}
            >
              <Stack direction="row" alignItems="center" spacing={1.4} mb={1.4}>
                <Box
                  sx={{
                    width: 46, height: 46, borderRadius: "14px", flexShrink: 0,
                    display: "flex", alignItems: "center", justifyContent: "center", fontSize: 23,
                    bgcolor: "#fff", border: "1px solid #f0d9df",
                  }}
                >
                  {f.icon}
                </Box>
                <Typography variant="subtitle1" fontWeight={800} sx={{ lineHeight: 1.7 }}>
                  {f.title}
                </Typography>
              </Stack>
              <Typography variant="body2" color="text.secondary" sx={{ lineHeight: 2 }}>
                {f.desc}
              </Typography>
            </Paper>
            </Reveal>
          ))}
        </Box>
      </Container>
    </Box>
  );
}
