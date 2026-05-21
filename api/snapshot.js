// Vercel serverless proxy: HTTPS page → HTTP camera (bypass mixed-content)
// GET /api/snapshot?host=arenahoangsaoshop.cameraddns.net&port=80&user=admin&pass=Ktsmart2025&ch=101
const http = require('http');

module.exports = async (req, res) => {
  const { host, port = 80, user = 'admin', pass, ch = 101 } = req.query;

  if (!host || !pass) {
    return res.status(400).json({ error: 'Missing host or pass' });
  }

  const url = `http://${user}:${pass}@${host}:${port}/ISAPI/Streaming/channels/${ch}01/picture`;

  try {
    await new Promise((resolve, reject) => {
      const request = http.get(url, { timeout: 5000 }, (camRes) => {
        if (camRes.statusCode !== 200) {
          reject(new Error(`Camera returned ${camRes.statusCode}`));
          return;
        }
        res.setHeader('Content-Type', camRes.headers['content-type'] || 'image/jpeg');
        res.setHeader('Cache-Control', 'no-store');
        res.setHeader('Access-Control-Allow-Origin', '*');
        camRes.pipe(res);
        camRes.on('end', resolve);
      });
      request.on('error', reject);
      request.on('timeout', () => { request.destroy(); reject(new Error('Timeout')); });
    });
  } catch (err) {
    res.status(502).json({ error: err.message });
  }
};
