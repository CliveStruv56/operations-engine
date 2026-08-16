import { ImageResponse } from "next/og";

/* Shared 1200x630 share-card renderer for the marketing pages, drawn in the
 * Huddle system: paper white, hairline frame, light display type, the three
 * pastel status tiles, burnt-amber domain pill. Runs at build time for
 * static routes; fonts are subset-fetched from Google Fonts during build. */

export const OG_SIZE = { width: 1200, height: 630 };

async function loadFont(weight: number, text: string): Promise<ArrayBuffer> {
  const css = await (
    await fetch(
      `https://fonts.googleapis.com/css2?family=Inter:wght@${weight}&text=${encodeURIComponent(text)}`,
    )
  ).text();
  const url = css.match(/src: url\((.+?)\) format\('(?:opentype|truetype)'\)/)?.[1];
  if (!url) throw new Error("Could not resolve Inter font for OG card");
  return (await fetch(url)).arrayBuffer();
}

export async function ogCard({
  kicker,
  title,
}: {
  kicker: string;
  title: string;
}) {
  const text = `FLOWGRID OS flowgridos.co.uk Built for UK small organisations •${kicker}${title}`;
  const [light, medium] = await Promise.all([
    loadFont(300, text),
    loadFont(500, text),
  ]);

  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          backgroundColor: "#ffffff",
          padding: 28,
        }}
      >
        <div
          style={{
            flex: 1,
            display: "flex",
            flexDirection: "column",
            justifyContent: "space-between",
            border: "1px solid #e5e6e1",
            borderRadius: 8,
            padding: "48px 56px",
          }}
        >
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
            }}
          >
            <div
              style={{
                fontSize: 26,
                fontWeight: 500,
                letterSpacing: -0.3,
                color: "#151515",
              }}
            >
              FLOWGRID OS
            </div>
            <div style={{ display: "flex", gap: 10 }}>
              {["#d3e5e9", "#bbb2ce", "#cb9da2"].map((c) => (
                <div
                  key={c}
                  style={{
                    width: 22,
                    height: 22,
                    borderRadius: 6,
                    backgroundColor: c,
                    border: "1px solid #333333",
                  }}
                />
              ))}
            </div>
          </div>

          <div style={{ display: "flex", flexDirection: "column" }}>
            <div
              style={{
                fontSize: 22,
                fontWeight: 500,
                letterSpacing: 2,
                textTransform: "uppercase",
                color: "#3a4444",
              }}
            >
              {`• ${kicker}`}
            </div>
            <div
              style={{
                marginTop: 20,
                fontSize: 64,
                fontWeight: 300,
                lineHeight: 1.12,
                letterSpacing: -2,
                color: "#151515",
                maxWidth: 1000,
              }}
            >
              {title}
            </div>
          </div>

          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
            }}
          >
            <div
              style={{
                display: "flex",
                alignItems: "center",
                border: "1px solid #65451d",
                borderRadius: 100,
                padding: "10px 24px",
                fontSize: 22,
                fontWeight: 500,
                color: "#65451d",
              }}
            >
              flowgridos.co.uk
            </div>
            <div style={{ fontSize: 20, color: "#3a4444" }}>
              Built for UK small organisations
            </div>
          </div>
        </div>
      </div>
    ),
    {
      ...OG_SIZE,
      fonts: [
        { name: "Inter", data: light, weight: 300 },
        { name: "Inter", data: medium, weight: 500 },
      ],
    },
  );
}
