import type { Metadata } from 'next';
import { Navbar } from '@/components/layout/Navbar';
import { Providers } from '@/components/layout/Providers';
import '@/styles/globals.css';

export const metadata: Metadata = {
  title: 'Agent Hub',
  description: 'Multi-agent platform for data engineering',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="bg-surface-bg min-h-screen">
        <Providers>
          <Navbar />
          <main className="pt-16">
            {children}
          </main>
        </Providers>
      </body>
    </html>
  );
}
