import "./globals.css";
import Shell from "../components/Shell";

export const metadata = { title: "ProblemLens", description: "AI-assisted IT service management" };

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body><Shell>{children}</Shell></body>
    </html>
  );
}
