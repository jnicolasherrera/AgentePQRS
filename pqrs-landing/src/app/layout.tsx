import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
  weight: ["300", "400", "500", "600", "700", "800", "900"],
});

const BASE_URL = "https://flexpqr.com";

export const metadata: Metadata = {
  metadataBase: new URL(BASE_URL),
  title: {
    default: "FlexPQR — Gestión Inteligente de PQRS",
    template: "%s — FlexPQR",
  },
  description:
    "Gestión de PQRs sin fricción y sin límites. Clasificación IA en tiempo real, alertas de vencimiento y trazabilidad completa.",
  keywords: ["PQRS", "PQR", "gestión documental", "multi-tenant", "IA", "FlexPQR", "FlexFintech"],
  authors: [{ name: "FlexFintech" }],
  openGraph: {
    type: "website",
    locale: "es_CO",
    url: BASE_URL,
    siteName: "FlexPQR",
    title: "FlexPQR — Gestión Inteligente de PQRS",
    description:
      "Gestión de PQRs sin fricción. Clasificación IA, alertas y trazabilidad en tiempo real.",
    images: [{ url: "/og-image.png", width: 1200, height: 630, alt: "FlexPQR" }],
  },
  twitter: {
    card: "summary_large_image",
    title: "FlexPQR — Gestión Inteligente de PQRS",
    description: "Gestión de PQRs sin fricción. Clasificación IA y trazabilidad en tiempo real.",
    images: ["/og-image.png"],
  },
  robots: {
    index: true,
    follow: true,
    googleBot: { index: true, follow: true },
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="es" className="dark">
      <head></head>
      <body
        className={`${inter.variable} antialiased relative min-h-screen bg-background-dark text-white selection:bg-primary selection:text-white`}
      >
        {children}
      </body>
    </html>
  );
}
