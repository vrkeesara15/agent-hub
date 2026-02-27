/** @type {import('next').NextConfig} */
const nextConfig = {
  output: process.env.ELECTRON === 'true' ? 'export' : undefined,
  images: {
    unoptimized: process.env.ELECTRON === 'true',
  },
}
module.exports = nextConfig
