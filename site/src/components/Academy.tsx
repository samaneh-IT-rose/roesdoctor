import { Box, Card, CardContent, Chip, Container, Typography } from "@mui/material";
import Reveal from "./Reveal";
import SectionTitle from "./SectionTitle";
import { texts } from "../content/texts";

export default function Academy() {
  return (
    <Box id="academy" sx={{ py: { xs: 6, md: 9 }, bgcolor: "#fff" }}>
      <Container maxWidth="lg">
        <SectionTitle label="آموزش" title={texts.academyTitle} sub={texts.academySub} />
        <Box
          sx={{
            display: "grid",
            gridTemplateColumns: { xs: "1fr", sm: "repeat(3,1fr)" },
            gap: { xs: 2, md: 3 },
          }}
        >
          {texts.academy.map((a, i) => (
            <Reveal key={a.title} delay={i * 120} variant="up" sx={{ height: "100%" }}>
            <Card
              className="hover-lift card-shine"
              elevation={0}
              sx={{
                height: "100%",
                borderRadius: "18px",
                border: "1px solid #f3e2e7",
                position: "relative",
                overflow: "hidden",
                background: i === 1 ? "linear-gradient(165deg,#faf1f3,#f3eef7)" : "#fff",
              }}
            >
              <CardContent sx={{ p: { xs: 2.4, md: 3.2 } }}>
                <Chip
                  size="small"
                  label={a.tag}
                  sx={{
                    mb: 2, fontWeight: 700,
                    background: "linear-gradient(135deg,#fbe9ee,#efe9f5)",
                    color: "primary.main",
                  }}
                />
                <Typography variant="h6" fontWeight={800} gutterBottom>{a.title}</Typography>
                <Typography variant="body2" color="text.secondary" sx={{ lineHeight: 2 }}>
                  {a.desc}
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
