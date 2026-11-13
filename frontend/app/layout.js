export const metadata = { title: "ProblemLens", description: "AI-assisted IT service desk" };

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body style={{ margin: 0, fontFamily: "system-ui, sans-serif", background: "#f4f6f8", color: "#1b2733" }}>
        {children}
      </body>
    </html>
  );
}
