#!/usr/bin/env node
import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from '@modelcontextprotocol/sdk/types.js';
import axios from 'axios';
import https from 'https';

const OMADA_URL = process.env.OMADA_URL || 'https://localhost:8043';
const OMADA_USERNAME = process.env.OMADA_USERNAME;
const OMADA_PASSWORD = process.env.OMADA_PASSWORD;
const OMADA_SITE_ID = process.env.OMADA_SITE_ID || 'Default';

// Create axios instance with SSL bypass for self-signed certs
const omadaApi = axios.create({
  baseURL: OMADA_URL,
  httpsAgent: new https.Agent({
    rejectUnauthorized: false,
  }),
});

// Authentication token storage
let authToken = null;
let omadaId = null;

// Login to Omada controller
async function login() {
  try {
    const response = await omadaApi.post('/api/v2/login', {
      username: OMADA_USERNAME,
      password: OMADA_PASSWORD,
    });
    authToken = response.data.result.token;
    omadaApi.defaults.headers.common['Csrf-Token'] = authToken;

    // Get controller ID
    const infoResponse = await omadaApi.get('/api/v2/info');
    omadaId = infoResponse.data.result.omadacId;

    return true;
  } catch (error) {
    console.error('Login failed:', error.message);
    return false;
  }
}

// Create MCP server
const server = new Server(
  {
    name: 'omada-mcp-server',
    version: '1.0.0',
  },
  {
    capabilities: {
      tools: {},
    },
  }
);

// Tool definitions
server.setRequestHandler(ListToolsRequestSchema, async () => {
  return {
    tools: [
      {
        name: 'list_sites',
        description: 'List all sites in Omada controller',
        inputSchema: {
          type: 'object',
          properties: {},
        },
      },
      {
        name: 'list_devices',
        description: 'List all network devices (APs, switches, gateways)',
        inputSchema: {
          type: 'object',
          properties: {
            type: {
              type: 'string',
              description: 'Device type filter: ap, switch, gateway (optional)',
              enum: ['ap', 'switch', 'gateway'],
            },
          },
        },
      },
      {
        name: 'get_device_info',
        description: 'Get detailed information about a specific device',
        inputSchema: {
          type: 'object',
          properties: {
            mac: {
              type: 'string',
              description: 'Device MAC address',
            },
          },
          required: ['mac'],
        },
      },
      {
        name: 'list_clients',
        description: 'List connected clients',
        inputSchema: {
          type: 'object',
          properties: {
            online: {
              type: 'boolean',
              description: 'Filter by online status (optional)',
            },
          },
        },
      },
      {
        name: 'get_network_stats',
        description: 'Get network statistics and health',
        inputSchema: {
          type: 'object',
          properties: {},
        },
      },
      {
        name: 'list_ssids',
        description: 'List all wireless SSIDs',
        inputSchema: {
          type: 'object',
          properties: {},
        },
      },
      {
        name: 'reboot_device',
        description: 'Reboot a network device',
        inputSchema: {
          type: 'object',
          properties: {
            mac: {
              type: 'string',
              description: 'Device MAC address',
            },
          },
          required: ['mac'],
        },
      },
      {
        name: 'block_client',
        description: 'Block a client from the network',
        inputSchema: {
          type: 'object',
          properties: {
            mac: {
              type: 'string',
              description: 'Client MAC address',
            },
          },
          required: ['mac'],
        },
      },
      {
        name: 'unblock_client',
        description: 'Unblock a client from the network',
        inputSchema: {
          type: 'object',
          properties: {
            mac: {
              type: 'string',
              description: 'Client MAC address',
            },
          },
          required: ['mac'],
        },
      },
    ],
  };
});

// Dispatch a single tool call; throws on API errors (including 401).
async function dispatch(name, args) {
  const siteId = OMADA_SITE_ID;

  switch (name) {
    case 'list_sites': {
      const response = await omadaApi.get(`/${omadaId}/api/v2/sites`);
      return {
        content: [{ type: 'text', text: JSON.stringify(response.data.result, null, 2) }],
      };
    }

    case 'list_devices': {
      let endpoint = `/${omadaId}/api/v2/sites/${siteId}/devices`;
      if (args.type) {
        endpoint += `?type=${args.type}`;
      }
      const response = await omadaApi.get(endpoint);
      return {
        content: [{ type: 'text', text: JSON.stringify(response.data.result, null, 2) }],
      };
    }

    case 'get_device_info': {
      const response = await omadaApi.get(
        `/${omadaId}/api/v2/sites/${siteId}/devices/${args.mac}`
      );
      return {
        content: [{ type: 'text', text: JSON.stringify(response.data.result, null, 2) }],
      };
    }

    case 'list_clients': {
      let endpoint = `/${omadaId}/api/v2/sites/${siteId}/clients`;
      if (args.online !== undefined) {
        endpoint += `?filters.active=${args.online}`;
      }
      const response = await omadaApi.get(endpoint);
      return {
        content: [{ type: 'text', text: JSON.stringify(response.data.result, null, 2) }],
      };
    }

    case 'get_network_stats': {
      const response = await omadaApi.get(
        `/${omadaId}/api/v2/sites/${siteId}/stat/dashboard`
      );
      return {
        content: [{ type: 'text', text: JSON.stringify(response.data.result, null, 2) }],
      };
    }

    case 'list_ssids': {
      const response = await omadaApi.get(
        `/${omadaId}/api/v2/sites/${siteId}/setting/wlans`
      );
      return {
        content: [{ type: 'text', text: JSON.stringify(response.data.result, null, 2) }],
      };
    }

    case 'reboot_device': {
      await omadaApi.post(
        `/${omadaId}/api/v2/sites/${siteId}/cmd/devices/${args.mac}/reboot`
      );
      return {
        content: [{ type: 'text', text: `Device ${args.mac} reboot initiated successfully` }],
      };
    }

    case 'block_client': {
      await omadaApi.post(
        `/${omadaId}/api/v2/sites/${siteId}/cmd/clients/${args.mac}/block`
      );
      return {
        content: [{ type: 'text', text: `Client ${args.mac} blocked successfully` }],
      };
    }

    case 'unblock_client': {
      await omadaApi.post(
        `/${omadaId}/api/v2/sites/${siteId}/cmd/clients/${args.mac}/unblock`
      );
      return {
        content: [{ type: 'text', text: `Client ${args.mac} unblocked successfully` }],
      };
    }

    default:
      throw new Error(`Unknown tool: ${name}`);
  }
}

// Tool handlers
server.setRequestHandler(CallToolRequestSchema, async (request) => {
  if (!authToken) {
    await login();
  }

  const { name, arguments: args } = request.params;

  try {
    return await dispatch(name, args);
  } catch (error) {
    if (error.response?.status === 401) {
      // Token expired — re-authenticate and retry once.
      authToken = null;
      const ok = await login();
      if (ok) {
        try {
          return await dispatch(name, args);
        } catch (retryError) {
          return {
            content: [{ type: 'text', text: `Error: ${retryError.message}` }],
            isError: true,
          };
        }
      }
    }

    return {
      content: [{ type: 'text', text: `Error: ${error.message}` }],
      isError: true,
    };
  }
});

// Start server
async function main() {
  await login();
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error('Omada MCP server running on stdio');
}

main().catch((error) => {
  console.error('Server error:', error);
  process.exit(1);
});
