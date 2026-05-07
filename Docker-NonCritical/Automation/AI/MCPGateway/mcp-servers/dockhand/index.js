import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { CallToolRequestSchema, ListToolsRequestSchema } from '@modelcontextprotocol/sdk/types.js';

const DOCKHAND_URL = (process.env.DOCKHAND_URL || '').replace(/\/$/, '');
const DOCKHAND_USERNAME = process.env.DOCKHAND_USERNAME;
const DOCKHAND_PASSWORD = process.env.DOCKHAND_PASSWORD;

if (!DOCKHAND_URL || !DOCKHAND_USERNAME || !DOCKHAND_PASSWORD) {
  console.error('Missing required env vars: DOCKHAND_URL, DOCKHAND_USERNAME, DOCKHAND_PASSWORD');
  process.exit(1);
}

let sessionCookie = null;
const REQUEST_TIMEOUT_MS = Number(process.env.DOCKHAND_REQUEST_TIMEOUT_MS || 8000);
const ENV_CACHE_TTL_MS = Number(process.env.DOCKHAND_ENV_CACHE_TTL_MS || 10000);
let environmentsCache = { value: null, expiresAt: 0 };

async function fetchWithTimeout(url, options = {}, timeoutMs = REQUEST_TIMEOUT_MS) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, { ...options, signal: controller.signal });
  } finally {
    clearTimeout(timer);
  }
}

async function login() {
  const res = await fetchWithTimeout(`${DOCKHAND_URL}/api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: DOCKHAND_USERNAME, password: DOCKHAND_PASSWORD }),
  });
  if (!res.ok) throw new Error(`Dockhand login failed: ${await res.text()}`);
  const setCookie = res.headers.get('set-cookie') || '';
  const match = setCookie.match(/dockhand_session=([^;]+)/);
  if (!match) throw new Error('No session cookie in Dockhand login response');
  sessionCookie = match[1];
}

async function request(method, path, body) {
  if (!sessionCookie) await login();
  const opts = {
    method,
    headers: {
      Cookie: `dockhand_session=${sessionCookie}`,
      ...(body ? { 'Content-Type': 'application/json' } : {}),
    },
    ...(body ? { body: JSON.stringify(body) } : {}),
  };
  let res = await fetchWithTimeout(`${DOCKHAND_URL}${path}`, opts);
  if (res.status === 401) {
    sessionCookie = null;
    await login();
    opts.headers.Cookie = `dockhand_session=${sessionCookie}`;
    res = await fetchWithTimeout(`${DOCKHAND_URL}${path}`, opts);
  }
  const text = await res.text();
  try { return JSON.parse(text); } catch { return text; }
}

// Fetch all environments and return array of {id, name}
async function getEnvironments() {
  if (environmentsCache.value && Date.now() < environmentsCache.expiresAt) {
    return environmentsCache.value;
  }
  const envs = await request('GET', '/api/environments');
  const normalized = Array.isArray(envs) ? envs : [];
  environmentsCache = {
    value: normalized,
    expiresAt: Date.now() + ENV_CACHE_TTL_MS,
  };
  return normalized;
}

// Query a path across all environments and aggregate results, tagging each item with envId/envName
async function queryAllEnvs(pathFn) {
  const envs = await getEnvironments();
  const perEnvResults = await Promise.allSettled(envs.map(async (env) => {
    const data = await request('GET', pathFn(env.id));
    if (!Array.isArray(data)) return [];
    return data.map((item) => ({ ...item, _envId: env.id, _envName: env.name }));
  }));

  const results = [];
  for (const settled of perEnvResults) {
    if (settled.status === 'fulfilled') {
      results.push(...settled.value);
    }
  }
  return results;
}

function envParam(envId) {
  return envId ? `?env=${encodeURIComponent(envId)}` : '';
}

const TOOLS = [
  {
    name: 'list_environments',
    description: 'List all Docker environments (hosts) managed by Dockhand, including their IDs, names, and connection status',
    inputSchema: { type: 'object', properties: {} },
  },
  {
    name: 'list_containers',
    description: 'List Docker containers. Provide envId to query a specific environment; omit to aggregate across all environments.',
    inputSchema: {
      type: 'object',
      properties: {
        envId: { type: 'number', description: 'Environment ID from list_environments. Omit to query all environments.' },
      },
    },
  },
  {
    name: 'get_container',
    description: 'Get details for a specific container by ID',
    inputSchema: {
      type: 'object',
      properties: {
        id: { type: 'string', description: 'Container ID' },
        envId: { type: 'number', description: 'Environment ID (recommended for accuracy)' },
      },
      required: ['id'],
    },
  },
  {
    name: 'get_container_logs',
    description: 'Get logs from a container',
    inputSchema: {
      type: 'object',
      properties: {
        id: { type: 'string', description: 'Container ID' },
        envId: { type: 'number', description: 'Environment ID' },
        tail: { type: 'number', description: 'Number of log lines to return (default 100)' },
      },
      required: ['id'],
    },
  },
  {
    name: 'restart_container',
    description: 'Restart a Docker container by ID',
    inputSchema: {
      type: 'object',
      properties: {
        id: { type: 'string' },
        envId: { type: 'number', description: 'Environment ID' },
      },
      required: ['id'],
    },
  },
  {
    name: 'start_container',
    description: 'Start a stopped Docker container by ID',
    inputSchema: {
      type: 'object',
      properties: {
        id: { type: 'string' },
        envId: { type: 'number', description: 'Environment ID' },
      },
      required: ['id'],
    },
  },
  {
    name: 'stop_container',
    description: 'Stop a running Docker container by ID',
    inputSchema: {
      type: 'object',
      properties: {
        id: { type: 'string' },
        envId: { type: 'number', description: 'Environment ID' },
      },
      required: ['id'],
    },
  },
  {
    name: 'list_stacks',
    description: 'List Docker Compose stacks. Provide envId to query a specific environment; omit to aggregate across all environments.',
    inputSchema: {
      type: 'object',
      properties: {
        envId: { type: 'number', description: 'Environment ID from list_environments. Omit to query all environments.' },
      },
    },
  },
  {
    name: 'get_stack',
    description: 'Get details of a specific stack by name',
    inputSchema: {
      type: 'object',
      properties: {
        name: { type: 'string', description: 'Stack name as shown in Dockhand' },
        envId: { type: 'number', description: 'Environment ID' },
      },
      required: ['name'],
    },
  },
  {
    name: 'get_stack_compose',
    description: 'Get the compose file content for a stack',
    inputSchema: {
      type: 'object',
      properties: {
        name: { type: 'string' },
        envId: { type: 'number', description: 'Environment ID' },
      },
      required: ['name'],
    },
  },
  {
    name: 'restart_stack',
    description: 'Restart all containers in a Dockhand stack',
    inputSchema: {
      type: 'object',
      properties: {
        name: { type: 'string' },
        envId: { type: 'number', description: 'Environment ID' },
      },
      required: ['name'],
    },
  },
  {
    name: 'start_stack',
    description: 'Start a stopped Dockhand stack',
    inputSchema: {
      type: 'object',
      properties: {
        name: { type: 'string' },
        envId: { type: 'number', description: 'Environment ID' },
      },
      required: ['name'],
    },
  },
  {
    name: 'stop_stack',
    description: 'Stop a running Dockhand stack (docker compose down)',
    inputSchema: {
      type: 'object',
      properties: {
        name: { type: 'string' },
        envId: { type: 'number', description: 'Environment ID' },
      },
      required: ['name'],
    },
  },
  {
    name: 'get_pending_updates',
    description: 'List containers that have available image updates. Provide envId for a specific environment or omit to check all.',
    inputSchema: {
      type: 'object',
      properties: {
        envId: { type: 'number', description: 'Environment ID. Omit to check all environments.' },
      },
    },
  },
];

async function callTool(name, args) {
  switch (name) {
    case 'list_environments':
      return request('GET', '/api/environments');

    case 'list_containers':
      if (args?.envId) return request('GET', `/api/containers?env=${args.envId}`);
      return queryAllEnvs((id) => `/api/containers?env=${id}`);

    case 'get_container':
      return request('GET', `/api/containers/${encodeURIComponent(args.id)}${envParam(args?.envId)}`);

    case 'get_container_logs':
      return request('GET', `/api/containers/${encodeURIComponent(args.id)}/logs?tail=${args.tail ?? 100}${args?.envId ? `&env=${args.envId}` : ''}`);

    case 'restart_container':
      return request('POST', `/api/containers/${encodeURIComponent(args.id)}/restart${envParam(args?.envId)}`);

    case 'start_container':
      return request('POST', `/api/containers/${encodeURIComponent(args.id)}/start${envParam(args?.envId)}`);

    case 'stop_container':
      return request('POST', `/api/containers/${encodeURIComponent(args.id)}/stop${envParam(args?.envId)}`);

    case 'list_stacks':
      if (args?.envId) return request('GET', `/api/stacks?env=${args.envId}`);
      return queryAllEnvs((id) => `/api/stacks?env=${id}`);

    case 'get_stack':
      return request('GET', `/api/stacks/${encodeURIComponent(args.name)}${envParam(args?.envId)}`);

    case 'get_stack_compose':
      return request('GET', `/api/stacks/${encodeURIComponent(args.name)}/compose${envParam(args?.envId)}`);

    case 'restart_stack':
      return request('POST', `/api/stacks/${encodeURIComponent(args.name)}/restart${envParam(args?.envId)}`);

    case 'start_stack':
      return request('POST', `/api/stacks/${encodeURIComponent(args.name)}/start${envParam(args?.envId)}`);

    case 'stop_stack':
      return request('POST', `/api/stacks/${encodeURIComponent(args.name)}/down${envParam(args?.envId)}`);

    case 'get_pending_updates':
      if (args?.envId) return request('GET', `/api/containers/pending-updates?env=${args.envId}`);
      return queryAllEnvs((id) => `/api/containers/pending-updates?env=${id}`);

    default:
      throw new Error(`Unknown tool: ${name}`);
  }
}

const server = new Server(
  { name: 'dockhand-mcp', version: '1.0.0' },
  { capabilities: { tools: {} } }
);

server.setRequestHandler(ListToolsRequestSchema, async () => ({ tools: TOOLS }));

server.setRequestHandler(CallToolRequestSchema, async (req) => {
  const { name, arguments: args } = req.params;
  try {
    const data = await callTool(name, args);
    return {
      content: [{ type: 'text', text: typeof data === 'string' ? data : JSON.stringify(data, null, 2) }],
    };
  } catch (err) {
    return {
      content: [{ type: 'text', text: `Error: ${err.message}` }],
      isError: true,
    };
  }
});

const transport = new StdioServerTransport();
await server.connect(transport);
