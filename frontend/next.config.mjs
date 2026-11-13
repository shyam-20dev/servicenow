const backend = `http://127.0.0.1:${process.env.BACKEND_PORT || 8000}`;

export default {
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${backend}/api/:path*` }];
  },
};
