import {
  Avatar, Box, Button, Card, CardContent, Chip, CircularProgress, Container, Stack, Typography,
} from "@mui/material";
import { useEffect, useState } from "react";
import { Link as RouterLink } from "react-router-dom";
import { fetchPublicCounselors } from "../api";
import type { PublicCounselor } from "../api";
import { texts } from "../content/texts";
import SectionTitle from "./SectionTitle";

function faNum(n: number | string): string {
  return Number(n).toLocaleString("fa-IR");
}

function Stars({ value, size = 15 }: { value: number | null; size?: number }) {
  const v = value ?? 0;
  return (
    <Stack direction="row" spacing={0.25} alignItems="center">
      {[1, 2, 3, 4, 5].map((i) => (
        <Box key={i} component="svg" viewBox="0 0 24 24" sx={{ width: size, height: size, display: "block" }} aria-hidden>
          <path
            d="M12 2.6l2.9 5.9 6.5.95-4.7 4.6 1.1 6.5L12 17.5l-5.8 3.05 1.1-6.5-4.7-4.6 6.5-.95z"
            fill={i <= Math.round(v) ? "#f0b429" : "#eadfe3"}
          />
        </Box>
      ))}
    </Stack>
  );
}

export default function Counselors() {
  const [items, setItems] = useState<PublicCounselor[] | null>(null);

  useEffect(() => {
    fetchPublicCounselors()
      .then((d) => setItems(d))
      .catch(() => setItems([]));
  }, []);

  return (
    <Box sx={{ py: { xs: 6, md: 9 } }}>
      <Container id="counselors">
        <SectionTitle label="تیم ما" title={texts.counselorsTitle} sub={texts.counselorsSub} />

        {items === null && (
          <Stack alignItems="center" py={4}>
            <CircularProgress sx={{ color: "primary.main" }} />
          </Stack>
        )}

        {items !== null && items.length === 0 && (
          <Typography textAlign="center" color="text.secondary">
            به‌زودی پروفایل مشاوران در این بخش نمایش داده می‌شود.
          </Typography>
        )}

        <Box
          sx={{
            display: "grid",
            gridTemplateColumns: { xs: "1fr", sm: "repeat(2,1fr)", md: "repeat(3,1fr)" },
            gap: { xs: 2, md: 3 },
          }}
        >
          {items?.map((c) => (
            <Card
              key={c.id}
              className="hover-lift"
              elevation={0}
              sx={{
                borderRadius: "18px",
                border: "1px solid #f3e2e7",
                background: "linear-gradient(170deg,#ffffff 0%,#fbf3f5 100%)",
                overflow: "hidden",
              }}
            >
              <Box sx={{ height: 5, background: "linear-gradient(90deg,#a83a54,#c99a5b)" }} />
              <CardContent sx={{ textAlign: "center", p: 3 }}>
                {c.photo_url ? (
                  <Box
                    component="img"
                    src={c.photo_url}
                    alt={c.name}
                    sx={{
                      width: 108, height: 108, borderRadius: "50%", objectFit: "cover",
                      mx: "auto", mb: 1.5, border: "4px solid #fff",
                      boxShadow: "0 8px 22px rgba(168,58,84,.18)",
                    }}
                  />
                ) : (
                  <Avatar
                    sx={{
                      width: 108, height: 108, mx: "auto", mb: 1.5, fontSize: 40,
                      background: "linear-gradient(135deg,#b34460,#8a2f47)",
                      border: "4px solid #fff", boxShadow: "0 8px 22px rgba(168,58,84,.18)",
                    }}
                  >
                    {c.name.charAt(0)}
                  </Avatar>
                )}
                <Typography variant="h6" fontWeight={800}>{c.name}</Typography>
                {c.professional_title && (
                  <Typography variant="body2" color="text.secondary" sx={{ mt: 0.4 }}>{c.professional_title}</Typography>
                )}
                {c.specialty && (
                  <Chip
                    size="small"
                    label={c.specialty}
                    sx={{ mt: 1.4, bgcolor: "#faeef1", color: "primary.main", fontWeight: 700, border: "1px solid #f0d9df" }}
                  />
                )}
                {/* فاز ۶۹: امتیاز ستاره‌دار + دکمهٔ رزرو (فهرست بر اساس امتیاز مرتب است) */}
                <Stack direction="row" spacing={0.75} alignItems="center" justifyContent="center" sx={{ mt: 1.2 }}>
                  <Stars value={c.rating_avg ?? null} />
                  <Typography variant="body2" fontWeight={700}>
                    {c.rating_avg ? faNum(c.rating_avg) : "جدید"}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">({faNum(c.review_count)} نظر)</Typography>
                </Stack>
                <Button
                  component={RouterLink}
                  to={`/specialist/${encodeURIComponent(c.id)}`}
                  variant="contained"
                  size="small"
                  sx={{ mt: 1.8, borderRadius: 99, fontWeight: 800, px: 3 }}
                >
                  رزرو نوبت
                </Button>
              </CardContent>
            </Card>
          ))}
        </Box>
      </Container>
    </Box>
  );
}
