/** @type {import('next').NextConfig} */
const nextConfig = {
    // Proxy to backend API URL.
    async rewrites() {
        // Default to `localhost:8000`.
        const backendApiURL =
            process.env.BACKEND_API_URL || "http://localhost:8000";

        return [
            {
                source: "/backend/:path*",
                destination: `${backendApiURL}/:path*`,
            },
        ];
    },
};

export default nextConfig;
