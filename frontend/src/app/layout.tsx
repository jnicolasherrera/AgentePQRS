import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import './globals.css';
import { SessionGuardProvider } from '@/components/ui/SessionGuardProvider';

const inter = Inter({
  variable: '--font-inter',
  subsets: ['latin'],
  weight: ['300', '400', '500', '600', '700', '800', '900'],
});

export const metadata: Metadata = {
  title: 'FlexPQR — Sistema de Gestión de PQRs',
  description: 'Plataforma enterprise para gestión de peticiones, quejas y reclamos',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="es">
      <body className={`${inter.variable} font-sans antialiased`}>
        <SessionGuardProvider>
          {children}
        </SessionGuardProvider>
      </body>
    </html>
  );
}
