import type { Metadata } from "next";
import "@xyflow/react/dist/style.css";
import "./globals.css";

export const metadata: Metadata = {
  title: "Ripple · Engineering change impact",
  description: "See what a design change touches, what it breaks, and what it costs — before you build it.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" data-theme="dark" suppressHydrationWarning>
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: `try{var t=localStorage.getItem("ripple-theme");if(t)document.documentElement.dataset.theme=t;else if(window.matchMedia("(prefers-color-scheme: light)").matches)document.documentElement.dataset.theme="light"}catch(e){}`,
          }}
        />
      </head>
      <body>{children}</body>
    </html>
  );
}
