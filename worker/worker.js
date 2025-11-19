// 配置后端 API 地址（部署时替换成真实 Koyeb 域名）
const BACKEND_URL = 'https://grateful-meghan-heuristic-2525dfc9.koyeb.app/';

/**
 * 根据请求生成 CORS 头
 * 1. 有 Origin 就用 Origin
 * 2. 没有就回当前 Worker 自身域名
 */
function buildCorsHeaders(request) {
  const origin = request.headers.get('Origin') || new URL(request.url).origin;
  return {
    'Access-Control-Allow-Origin': origin,
    'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
  };
}

/**
 * 处理请求
 */
async function handleRequest(request) {
  const url = new URL(request.url);
  const corsHeaders = buildCorsHeaders(request);   // ← 每次请求动态生成

  // 1. 预检
  if (request.method === 'OPTIONS') {
    return new Response(null, { headers: corsHeaders });
  }

  // 2. 健康检查
  if (url.pathname === '/' || url.pathname === '/health') {
    return new Response(
      JSON.stringify({
        status: 'ok',
        message: 'Cloudflare Workers Proxy is running',
        backend: BACKEND_URL,
      }),
      { headers: { 'Content-Type': 'application/json', ...corsHeaders } }
    );
  }

  // 3. 代理 /api/* 到 Koyeb
  if (url.pathname.startsWith('/api/')) {
    try {
      const backendUrl = new URL(url.pathname, BACKEND_URL);
      backendUrl.search = url.search;

      const backendRequest = new Request(backendUrl.toString(), {
        method: request.method,
        headers: request.headers,
        body: request.method !== 'GET' && request.method !== 'HEAD'
          ? await request.arrayBuffer()
          : undefined,
      });

      const be = await fetch(backendRequest);

      // 视频流直接透传
      if (be.headers.get('Content-Type')?.startsWith('video/')) {
        return new Response(be.body, {
          status: be.status,
          statusText: be.statusText,
          headers: { ...Object.fromEntries(be.headers), ...corsHeaders },
        });
      }

      // 其它内容
      return new Response(await be.arrayBuffer(), {
        status: be.status,
        statusText: be.statusText,
        headers: { ...Object.fromEntries(be.headers), ...corsHeaders },
      });
    } catch (err) {
      return new Response(
        JSON.stringify({ error: '后端服务连接失败', message: err.message }),
        { status: 502, headers: { 'Content-Type': 'application/json', ...corsHeaders } }
      );
    }
  }

  // 4. 404
  return new Response(
    JSON.stringify({ error: 'Not Found' }),
    { status: 404, headers: { 'Content-Type': 'application/json', ...corsHeaders } }
  );
}

export default {
  async fetch(req, env, ctx) {
    return handleRequest(req);
  },
};
