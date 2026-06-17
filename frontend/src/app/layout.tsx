import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AuthLens",
  description: "Document question workspace for synthetic or de-identified PDFs."
};

export default function RootLayout({
  children
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
