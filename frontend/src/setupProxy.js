const {createProxyMiddleware} = require("http-proxy-middleware");
const fs = require('fs');
const path = require('path');

const API_URL = "https://munichways-radlnavi-api-melvpv5saa-ey.a.run.app";
const FRONTEND_URL = "https://radlnavi.munichways.de";

module.exports = function setupProxy(app) {
  app.use(
    ["/route", "/tag_distribution", "/version", "/shared_routes"],
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
  // Locally generated data is served by CRA's public directory. Before the
  // first deployment this is also the way to test without production data.
  if (!fs.existsSync(path.join(__dirname, '../public/street-details/manifest.json'))) {
    app.use('/street-details', createProxyMiddleware({ target: FRONTEND_URL, changeOrigin: true }));
  }
};
