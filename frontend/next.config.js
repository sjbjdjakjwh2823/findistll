/** @type {import('next').NextConfig} */
const nextConfig = {
    reactStrictMode: true,
    swcMinify: true,
    // Enable if you need standalone output for Docker/custom deployments
    // output: 'standalone',
    images: {
        // Add allowed image domains if using next/image with external URLs
        remotePatterns: [],
    },
    // Environment variables that can be accessed in the browser
    env: {
        // NEXT_PUBLIC_API_URL is automatically available via process.env
    },
};

module.exports = nextConfig;
