/** @type {import('next').NextConfig} */
const nextConfig = {
    // Indica a Next.js que debe generar archivos estáticos (HTML/CSS/JS) 
    // en lugar de requerir un servidor Node.js corriendo.
    output: 'export',
    
    // Desactiva la optimización de imágenes de Next.js, ya que 
    // requiere un servidor activo para funcionar.
    images: {
      unoptimized: true,
    },
  };
  
  export default nextConfig;