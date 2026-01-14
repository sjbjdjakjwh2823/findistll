/** @type {import('next').NextConfig} */
const nextConfig = {
    reactStrictMode: true,
    swcMinify: true,
    images: {
        remotePatterns: [],
    },
    // Rewrite requests to /api/* to the Python backend
    async rewrites() {
        return [
            {
                source: '/api/:path*',
                destination: process.env.NODE_ENV === 'development'
                    ? 'http://127.0.0.1:8000/api/:path*' // Local development
                    : '/api/:path*', // Production (handled by Vercel functions)
            },
        ];
    },
};

module.exports = nextConfig;
