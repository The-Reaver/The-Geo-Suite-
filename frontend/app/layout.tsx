import type { Metadata, Viewport } from "next";
import "./globals.css";

// Root layout for GEO Suite. Every page renders inside this layout, so
// keep it lean and fast. The manifest and icon paths point at the files
// this repo ships in frontend/public, so the installed PWA picks up GEO
// Suite branding (not the tool-set product's "Platform"/Toolbox branding
// this was split out of).

export const metadata: Metadata = {
  title: {
    default: "GEO Suite",
    template: "%s | GEO Suite",
  },
  description:
    "AI-search-visibility auditing, compliance checking, and prospecting for client websites.",
  applicationName: "GEO Suite",
  manifest: "/manifest.json",
  appleWebApp: {
    capable: true,
    statusBarStyle: "default",
    title: "GEO Suite",
  },
  icons: {
    icon: [
      { url: "/icons/icon-192.png", sizes: "192x192", type: "image/png" },
      { url: "/icons/icon-512.png", sizes: "512x512", type: "image/png" },
    ],
    apple: "/icons/icon-192.png",
  },
};

export const viewport: Viewport = {
  themeColor: "#0f172a",
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="app-body">
        <div className="app-shell">{children}</div>
      </body>
    </html>
  );
}
