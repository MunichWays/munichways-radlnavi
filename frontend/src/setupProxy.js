const {createProxyMiddleware} = require("http-proxy-middleware");

const API_URL = "https://munichways-radlnavi-api-melvpv5saa-ey.a.run.app";
const FRONTEND_URL = "https://radlnavi.munichways.de";

module.exports = function setupProxy(app) {
  app.use(
    ["/route", "/tag_distribution", "/version"],
    createProxyMiddleware({
      target: API_URL,
      changeOrigin: true,
    }),
  );

  app.use(
    "/layers/munichways",
    createProxyMiddleware({
      target: FRONTEND_URL,
      changeOrigin: true,
    }),
  );
};
