// 1. 后端地址
const BACKEND_URL = 'https://grateful-meghan-heuristic-2525dfc9.koyeb.app/';

// 2. 根据请求动态生成 CORS 头
function buildCorsHeaders(request) {
  const origin = request.headers.get('Origin') || new URL(request.url).origin;
  return {
    'Access-Control-Allow-Origin': origin,
    'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
  };
}

// 3. 清理后端带过来的 CORS 头，避免重复
function sanitizeBackendHeaders(headers) {
  const h = new Headers(headers);
  ['access-control-allow-origin',
   'access-control-allow-methods',
   'access-control-allow-headers',
   'access-control-allow-credentials',
   'access-control-max-age'
  ].forEach(k => h.delete(k));
  return h;
}

async function handleRequest(request) {
  const url = new URL(request.url);
  const corsHeaders = buildCorsHeaders(request);

  // 预检
  if (request.method === 'OPTIONS') {
    return new Response(null, { headers: corsHeaders });
  }

  // 代理 /api/*
  if (url.pathname.startsWith('/api/')) {
    try {
      const backendUrl = new URL(url.pathname, BACKEND_URL);
      backendUrl.search = url.search;

      const beReq = new Request(backendUrl.toString(), {
        method: request.method,
        headers: request.headers,
        body: request.method !== 'GET' && request.method !== 'HEAD' ? await request.arrayBuffer() : undefined,
      });

      const beRes = await fetch(beReq);

      // 清洗后端 CORS 头 + 合并 Worker CORS 头
      const cleanedHeaders = sanitizeBackendHeaders(beRes.headers);
      Object.entries(corsHeaders).forEach(([k, v]) => cleanedHeaders.set(k, v));

      // 文件流直传（视频、zip等）
      const contentType = beRes.headers.get('Content-Type') || '';
      if (contentType.startsWith('video/') ||
          contentType.startsWith('application/zip') ||
          contentType.startsWith('application/octet-stream')) {
        return new Response(beRes.body, {
          status: beRes.status,
          statusText: beRes.statusText,
          headers: cleanedHeaders,
        });
      }

      // 其它内容
      return new Response(await beRes.arrayBuffer(), {
        status: beRes.status,
        statusText: beRes.statusText,
        headers: cleanedHeaders,
      });
    } catch (err) {
      return Response.json(
        { error: '后端服务连接失败', message: err.message },
        { status: 502, headers: corsHeaders }
      );
    }
  }

  // 代理所有其他请求到后端（包括页面、静态资源等）
  try {
    const backendUrl = new URL(url.pathname + url.search, BACKEND_URL);

    const beReq = new Request(backendUrl.toString(), {
      method: request.method,
      headers: request.headers,
      body: request.method !== 'GET' && request.method !== 'HEAD' ? await request.arrayBuffer() : undefined,
    });

    const beRes = await fetch(beReq);

    // 清洗后端 CORS 头 + 合并 Worker CORS 头
    const cleanedHeaders = sanitizeBackendHeaders(beRes.headers);
    Object.entries(corsHeaders).forEach(([k, v]) => cleanedHeaders.set(k, v));

    // 直接返回响应
    return new Response(beRes.body, {
      status: beRes.status,
      statusText: beRes.statusText,
      headers: cleanedHeaders,
    });
  } catch (err) {
    return Response.json(
      { error: '后端服务连接失败', message: err.message },
      { status: 502, headers: corsHeaders }
    );
  }
}

export default { fetch: handleRequest };
