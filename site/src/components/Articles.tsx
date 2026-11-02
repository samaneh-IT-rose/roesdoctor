import { Box, Card, CardContent, Chip, Container, Stack, Typography } from "@mui/material";
import Reveal from "./Reveal";
import SectionTitle from "./SectionTitle";
import { texts } from "../content/texts";

const TAG_COLORS = ["#a83a54", "#5c4a6e", "#c99a5b"];

export default function Articles() {
  return (
    <Box sx={{ py: { xs: 6, md: 9 } }}>
      <Container maxWidth="lg">
        <SectionTitle label="مجله" title={texts.articlesTitle} sub={texts.articlesSub} />
        <Box
          sx={{
            display: "grid",
            gridTemplateColumns: { xs: "1fr", sm: "repeat(3,1fr)" },
            gap: { xs: 2, md: 3 },
          }}
        >
          {texts.articles.map((a, i) => (
            <Reveal key={a.title} delay={i * 110} variant="up" sx={{ height: "100%" }}>
            <Card
              className="hover-lift card-shine"
              elevation={0}
              sx={{
                height: "100%",
                borderRadius: "18px",
                border: "1px solid #f3e2e7",
                display: "flex",
                flexDirection: "column",
              }}
            >
              {/* سربرگ تزئینی کارت مقاله — بدون تصویر خارجی */}
              <Box
                sx={{
                  height: 96,
                  background: [
                    "linear-gradient(135deg,#fbe9ee 0%,#f6dfdF 100%)",
                    "linear-gradient(135deg,#efe9f5 0%,#e4dbec 100%)",
                    "linear-gradient(135deg,#f9efe2 0%,#f3e3cd 100%)",
                  ][i % 3],
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontSize: 40,
                }}
              >
                {["🌿", "💞", "🧩"][i % 3]}
              </Box>
              <CardContent sx={{ p: { xs: 2.4, md: 3 }, display: "flex", flexDirection: "column", flex: 1 }}>
                <Stack direction="row" alignItems="center" justifyContent="space-between" mb={1.4}>
                  <Chip
                    size="small"
                    label={a.tag}
                    sx={{ bgcolor: "transparent", border: `1.5px solid ${TAG_COLORS[i % 3]}`, color: TAG_COLORS[i % 3], fontWeight: 700 }}
                  />
                  <Typography variant="caption" color="text.secondary">{a.read}</Typography>
                </Stack>
                <Typography variant="subtitle1" fontWeight={800} gutterBottom sx={{ lineHeight: 1.8 }}>
                  {a.title}
                </Typography>
                <Typography variant="body2" color="text.secondary" sx={{ lineHeight: 2, flex: 1 }}>
                  {a.desc}
                </Typography>
                <Typography variant="caption" fontWeight={700} color="primary.main" mt={1.5} sx={{ cursor: "pointer" }}>
                  ادامه مطلب ›
                </Typography>
              </CardContent>
            </Card>
            </Reveal>
          ))}
        </Box>
      </Container>
    </Box>
  );
}
