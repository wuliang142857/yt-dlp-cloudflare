/**
 * Cloudflare Workers - YouTube Downloader Proxy
 *
 * 此 Worker 作为代理层，将请求转发到 Koyeb 后端
 * 解决中国访问 Koyeb 的连通性问题
 */

// 配置后端 API 地址（部署时需要替换为实际的 Koyeb URL）
const BACKEND_URL = 'https://grateful-meghan-heuristic-2525dfc9.koyeb.app/';  // 例如: https://your-app.koyeb.app

// CORS 头配置
const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type',
};

/**
 * 处理请求
 */
async function handleRequest(request) {
  const url = new URL(request.url);

  // 处理 OPTIONS 请求（CORS 预检）
  if (request.method === 'OPTIONS') {
    return new Response(null, {
      headers: corsHeaders,
    });
  }

  // 健康检查
  if (url.pathname === '/' || url.pathname === '/health') {
    return new Response(JSON.stringify({
      status: 'ok',
      message: 'Cloudflare Workers Proxy is running',
      backend: BACKEND_URL,
    }), {
      headers: {
        'Content-Type': 'application/json',
        ...corsHeaders,
      },
    });
  }

  // 代理 API 请求到后端
  if (url.pathname.startsWith('/api/')) {
    try {
      // 构建后端 URL
      const backendUrl = new URL(url.pathname, BACKEND_URL);
      backendUrl.search = url.search;

      // 转发请求到后端
      const backendRequest = new Request(backendUrl.toString(), {
        method: request.method,
        headers: request.headers,
        body: request.method !== 'GET' && request.method !== 'HEAD' ? await request.arrayBuffer() : undefined,
      });

      // 获取后端响应
      const backendResponse = await fetch(backendRequest);

      // 如果是文件下载（视频），需要流式传输
      if (backendResponse.headers.get('Content-Type')?.startsWith('video/')) {
        return new Response(backendResponse.body, {
          status: backendResponse.status,
          statusText: backendResponse.statusText,
          headers: {
            ...Object.fromEntries(backendResponse.headers),
            ...corsHeaders,
          },
        });
      }

      // 其他响应（JSON 等）
      const responseData = await backendResponse.arrayBuffer();
      return new Response(responseData, {
        status: backendResponse.status,
        statusText: backendResponse.statusText,
        headers: {
          ...Object.fromEntries(backendResponse.headers),
          ...corsHeaders,
        },
      });

    } catch (error) {
      return new Response(JSON.stringify({
        error: '后端服务连接失败',
        message: error.message,
      }), {
        status: 502,
        headers: {
          'Content-Type': 'application/json',
          ...corsHeaders,
        },
      });
    }
  }

  // 其他路径返回 404
  return new Response(JSON.stringify({
    error: 'Not Found',
  }), {
    status: 404,
    headers: {
      'Content-Type': 'application/json',
      ...corsHeaders,
    },
  });
}

// 导出 fetch 事件监听器
export default {
  async fetch(request, env, ctx) {
    return handleRequest(request);
  },
};
