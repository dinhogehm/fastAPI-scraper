// Main fetch handler for Cloudflare Workers
export default {
    async fetch(request, env, ctx) {
        try {
            const url = new URL(request.url);
            const method = request.method;
            const path = url.pathname;
            
            // CORS headers
            const corsHeaders = {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type, Authorization',
            };
            
            // Handle preflight requests
            if (method === 'OPTIONS') {
                return new Response('', {
                    status: 200,
                    headers: corsHeaders
                });
            }
            
            // Health check endpoint (no auth required)
            if (method === 'GET' && (path === '/' || path.includes('health'))) {
                return jsonResponse(
                    {status: 'healthy', service: 'FastAPI Multi-tenant Scraper'}, 
                    200, 
                    corsHeaders
                );
            }
            
            // Get API key from Authorization header for protected endpoints
            const authHeader = request.headers.get('Authorization') || '';
            if (!authHeader.startsWith('Bearer ')) {
                return jsonResponse(
                    {error: 'Missing or invalid authorization header'}, 
                    401, 
                    corsHeaders
                );
            }
            
            const apiKey = authHeader.substring(7); // Remove 'Bearer ' prefix
            
            // Validate API key
            const tenantInfo = await validateApiKey(apiKey, env);
            if (!tenantInfo) {
                return jsonResponse(
                    {error: 'Invalid API key'}, 
                    401, 
                    corsHeaders
                );
            }
            
            // Route requests
            if (method === 'POST' && path.includes('scrape')) {
                return await handleScrape(request, tenantInfo, env, corsHeaders);
            } else if (method === 'GET' && path.includes('status')) {
                return await handleStatus(request, tenantInfo, env, corsHeaders);
            } else {
                return jsonResponse(
                    {error: 'Endpoint not found'}, 
                    404, 
                    corsHeaders
                );
            }
            
        } catch (error) {
            return jsonResponse(
                {error: `Internal server error: ${error.message}`}, 
                500, 
                {'Access-Control-Allow-Origin': '*'}
            );
        }
    }
};

async function validateApiKey(apiKey, env) {
    try {
        // Get API key info from KV
        const apiInfo = await env.API_KEYS_KV.get(apiKey);
        if (!apiInfo) {
            return null;
        }
        
        // Parse JSON
        const tenantInfo = JSON.parse(apiInfo);
        
        // Check if key is active
        if (!tenantInfo.active) {
            return null;
        }
        
        return tenantInfo;
    } catch (error) {
        return null;
    }
}

async function handleScrape(request, tenantInfo, env, corsHeaders) {
    try {
        // Parse request body
        let data = {};
        const contentType = request.headers.get('content-type');
        
        if (contentType && contentType.includes('application/json')) {
            const body = await request.text();
            if (body) {
                data = JSON.parse(body);
            }
        }
        
        const url = data.url;
        if (!url) {
            return jsonResponse(
                {error: 'URL is required'}, 
                400, 
                corsHeaders
            );
        }
        
        // Generate task ID
        const taskId = crypto.randomUUID();
        
        // Create task record
        const taskData = {
            task_id: taskId,
            tenant_id: tenantInfo.tenant_id,
            url: url,
            status: 'completed', // Simplified - always return completed
            created_at: new Date().toISOString(),
            completed_at: new Date().toISOString(),
            result: {
                title: 'Sample Title',
                content: `Sample scraped content from ${url}`,
                links: ['https://example.com/link1', 'https://example.com/link2'],
                metadata: {
                    scraped_at: new Date().toISOString(),
                    url: url,
                    status_code: 200
                }
            }
        };
        
        // Store task in KV
        await env.TASKS_KV.put(
            `${tenantInfo.tenant_id}:${taskId}`, 
            JSON.stringify(taskData)
        );
        
        return jsonResponse(
            {
                task_id: taskId,
                status: 'completed',
                message: 'Scraping completed successfully'
            }, 
            200, 
            corsHeaders
        );
        
    } catch (error) {
        if (error instanceof SyntaxError) {
            return jsonResponse(
                {error: 'Invalid JSON in request body'}, 
                400, 
                corsHeaders
            );
        }
        return jsonResponse(
            {error: `Scraping failed: ${error.message}`}, 
            500, 
            corsHeaders
        );
    }
}

async function handleStatus(request, tenantInfo, env, corsHeaders) {
    try {
        // Extract task_id from URL
        const url = new URL(request.url);
        const pathParts = url.pathname.split('/');
        let taskId = null;
        
        // Look for task_id in URL path
        for (let i = 0; i < pathParts.length; i++) {
            if (pathParts[i].includes('status') && i + 1 < pathParts.length) {
                taskId = pathParts[i + 1];
                break;
            }
        }
        
        if (!taskId) {
            return jsonResponse(
                {error: 'Task ID is required'}, 
                400, 
                corsHeaders
            );
        }
        
        // Get task from KV with tenant isolation
        const taskKey = `${tenantInfo.tenant_id}:${taskId}`;
        const taskData = await env.TASKS_KV.get(taskKey);
        
        if (!taskData) {
            return jsonResponse(
                {error: 'Task not found'}, 
                404, 
                corsHeaders
            );
        }
        
        // Parse and return task data
        const taskInfo = JSON.parse(taskData);
        
        return jsonResponse(
            {
                task_id: taskInfo.task_id,
                status: taskInfo.status,
                created_at: taskInfo.created_at,
                completed_at: taskInfo.completed_at,
                result: taskInfo.result
            }, 
            200, 
            corsHeaders
        );
        
    } catch (error) {
        return jsonResponse(
            {error: `Status check failed: ${error.message}`}, 
            500, 
            corsHeaders
        );
    }
}

function jsonResponse(data, status, headers) {
    const responseHeaders = {
        'Content-Type': 'application/json',
        ...headers
    };
    
    return new Response(
        JSON.stringify(data), 
        {
            status: status,
            headers: responseHeaders
        }
    );
}