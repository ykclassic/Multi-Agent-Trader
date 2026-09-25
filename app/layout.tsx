import type { Metadata } from "next";
import "./globals.css";
export const metadata: Metadata={title:"Multi-Agent Trader",description:"AI-powered trading desk, research terminal, and portfolio/risk operating system."};
export default function RootLayout({children}:{children:React.ReactNode}){return <html lang="en"><body>{children}</body></html>;}