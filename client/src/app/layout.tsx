import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AuthLens",
  description: "Prior authorization evidence workspace for synthetic or de-identified documents.",
  icons: {
    icon: "/icon.svg"
  }
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
