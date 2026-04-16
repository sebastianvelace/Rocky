export const metadata = {
    title: 'Rocky Core',
    description: 'Engineering Assistant',
  }
  
  export default function RootLayout({
    children,
  }: {
    children: React.ReactNode
  }) {
    return (
      <html lang="es">
        <body style={{ margin: 0, background: '#0a0a0a', color: '#00ff41' }}>
          {children}
        </body>
      </html>
    )
  }