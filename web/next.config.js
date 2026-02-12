/** @type {import('next').NextConfig} */
const nextConfig = {
  // Prevent Turbopack from picking an unrelated workspace root when multiple lockfiles exist.
  turbopack: {
    root: __dirname,
  },
};

module.exports = nextConfig;

