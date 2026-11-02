import { Box, Stack, Typography } from "@mui/material";
import Reveal from "./Reveal";

export default function SectionTitle({
  label, title, sub, light = false,
}: {
  label: string;
  title: string;
  sub?: string;
  light?: boolean;
}) {
  return (
    <Reveal variant="up">
      <Stack spacing={1} alignItems="center" mb={5}>
        <Typography
          variant="caption"
          sx={{
            background: light ? "rgba(255,255,255,0.2)" : "linear-gradient(135deg,#fde7ec 0%,#f0e6f6 100%)",
            color: light ? "#fff" : "primary.main",
            px: 2.5, py: 0.6, borderRadius: 99, fontWeight: 700,
            border: light ? "none" : "1px solid #f6d7de",
            boxShadow: light ? "none" : "0 4px 14px rgba(168,58,84,.08)",
          }}
        >
          {label}
        </Typography>
        <Typography
          variant="h3"
          fontWeight={800}
          textAlign="center"
          className={light ? "" : "grad-text"}
          color={light ? "#fff" : undefined}
        >
          {title}
        </Typography>
        <Box className="title-rule" sx={light ? { background: "linear-gradient(90deg,#f2cdd5,#c99a5b)" } : undefined} />
        {sub && (
          <Typography
            variant="body1"
            sx={{ maxWidth: 640, textAlign: "center", color: light ? "rgba(255,255,255,0.9)" : "text.secondary", lineHeight: 2 }}
          >
            {sub}
          </Typography>
        )}
      </Stack>
    </Reveal>
  );
}
