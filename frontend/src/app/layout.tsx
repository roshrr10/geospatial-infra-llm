import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import NgrokInterceptor from "@/components/NgrokInterceptor";


import { LanguageProvider } from "@/context/LanguageContext";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Meghalaya GeoAI Planning",
  description: "Advanced geospatial intelligence for government planning",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={inter.className}>
        <LanguageProvider>
          <NgrokInterceptor />
          {children}
        </LanguageProvider>
      </body>
    </html>
  );
}
