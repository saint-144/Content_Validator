/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  images: { unoptimized: true },
  async rewrites() {
    return [
      { source: '/api/:path*', destination: 'http://localhost:8084/api/:path*' }
    ];
  }
};
module.exports = nextConfig;
