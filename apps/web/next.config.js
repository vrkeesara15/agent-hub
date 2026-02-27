/** @type {import('next').NextConfig} */
const nextConfig = {
  output: process.env.ELECTRON === 'true' ? 'export' : 'standalone',
  images: {
    unoptimized: process.env.ELECTRON === 'true',
  },
}
module.exports = nextConfig
