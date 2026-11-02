import { Box, Card, CardContent, Container, Stack, Typography } from "@mui/material";
import Reveal from "./Reveal";
import SectionTitle from "./SectionTitle";
import { texts } from "../content/texts";

export default function Services() {
  return (
    <Box id="services" sx={{ py: { xs: 6, md: 9 }, bgcolor: "#fff" }}>
      <Container maxWidth="lg">
        <SectionTitle label="خدمات" title={texts.servicesTitle} sub={texts.servicesSub} />
        <Box
          sx={{
            display: "grid",
            gridTemplateColumns: { xs: "1fr", sm: "repeat(2,1fr)", lg: "repeat(4,1fr)" },
            gap: { xs: 2, md: 2.6 },
          }}
        >
          {texts.services.map((s, i) => (
            <Reveal key={s.title} delay={(i % 4) * 90} variant="up" sx={{ height: "100%" }}>
            <Card
              className="hover-lift card-shine"
              elevation={0}
              sx={{
                height: "100%",
                border: "1px solid #f3e2e7",
                borderRadius: "18px",
                position: "relative",
                overflow: "hidden",
                "&::before": {
                  content: '""',
                  position: "absolute",
                  inset: "auto 0 0 0",
                  height: 4,
                  background: "linear-gradient(90deg,#a83a54,#c99a5b)",
                  opacity: 0,
                  transition: "opacity .25s ease",
                },
                "&:hover::before": { opacity: 1 },
              }}
            >
              <CardContent sx={{ p: { xs: 2.4, md: 3 } }}>
                <Box
                  sx={{
                    width: 54, height: 54, borderRadius: "16px", display: "flex",
                    alignItems: "center", justifyContent: "center", fontSize: 27, mb: 2,
                    background: i % 2 === 0 ? "linear-gradient(135deg,#fbe9ee,#f6e3e9)" : "linear-gradient(135deg,#efe9f5,#e9e0f0)",
                  }}
                >
                  {s.emoji}
                </Box>
                <Typography variant="h6" fontWeight={800} gutterBottom>{s.title}</Typography>
                <Typography variant="body2" color="text.secondary" sx={{ lineHeight: 2 }}>
                  {s.desc}
                </Typography>
              </CardContent>
            </Card>
            </Reveal>
          ))}
        </Box>

        <Stack direction="row" justifyContent="center" mt={5}>
          <Typography variant="body2" color="text.secondary" sx={{ maxWidth: 560, textAlign: "center", lineHeight: 2 }}>
            مطمئن نیستید کدام خدمت برای شما مناسب است؟ فرم درخواست مشاوره را تکمیل کنید؛
            کارشناسان پذیرش شما را به بهترین گزینه هدایت می‌کنند.
          </Typography>
        </Stack>
      </Container>
    </Box>
  );
}
