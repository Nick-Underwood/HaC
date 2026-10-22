#!/usr/bin/env node
import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from '@modelcontextprotocol/sdk/types.js';
import axios from 'axios';

const HOMEBOX_URL = process.env.HOMEBOX_URL || 'http://localhost:7745';
const HOMEBOX_EMAIL = process.env.HOMEBOX_EMAIL;
const HOMEBOX_PASSWORD = process.env.HOMEBOX_PASSWORD;

let authToken = null;

async function login() {
  const response = await axios.post(`${HOMEBOX_URL}/api/v1/users/login`, {
    username: HOMEBOX_EMAIL,
    password: HOMEBOX_PASSWORD,
  });
  authToken = response.data.token;
  homeboxApi.defaults.headers.Authorization = authToken;
}

// Create axios instance
const homeboxApi = axios.create({
  baseURL: `${HOMEBOX_URL}/api/v1`,
});

// Interceptor: re-authenticate on 401
homeboxApi.interceptors.response.use(
  (res) => res,
  async (error) => {
    if (error.response?.status === 401 && !error.config._retried) {
      error.config._retried = true;
      await login();
      error.config.headers.Authorization = authToken;
      return homeboxApi.request(error.config);
    }
    throw error;
  }
);

// Create MCP server
const server = new Server(
  {
    name: 'homebox-mcp-server',
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
        name: 'list_items',
        description: 'List all inventory items',
        inputSchema: {
          type: 'object',
          properties: {
            search: {
              type: 'string',
              description: 'Search query (optional)',
            },
            locationId: {
              type: 'string',
              description: 'Filter by location ID (optional)',
            },
            labelId: {
              type: 'string',
              description: 'Filter by label ID (optional)',
            },
          },
        },
      },
      {
        name: 'get_item',
        description: 'Get details of a specific item',
        inputSchema: {
          type: 'object',
          properties: {
            itemId: {
              type: 'string',
              description: 'The item ID',
            },
          },
          required: ['itemId'],
        },
      },
      {
        name: 'create_item',
        description: 'Create a new inventory item',
        inputSchema: {
          type: 'object',
          properties: {
            name: {
              type: 'string',
              description: 'Item name',
            },
            description: {
              type: 'string',
              description: 'Item description',
            },
            locationId: {
              type: 'string',
              description: 'Location ID',
            },
            quantity: {
              type: 'number',
              description: 'Quantity',
            },
          },
          required: ['name'],
        },
      },
      {
        name: 'update_item',
        description: 'Update an existing item',
        inputSchema: {
          type: 'object',
          properties: {
            itemId: {
              type: 'string',
              description: 'The item ID',
            },
            name: {
              type: 'string',
              description: 'Item name (optional)',
            },
            description: {
              type: 'string',
              description: 'Item description (optional)',
            },
            quantity: {
              type: 'number',
              description: 'Quantity (optional)',
            },
          },
          required: ['itemId'],
        },
      },
      {
        name: 'delete_item',
        description: 'Delete an inventory item',
        inputSchema: {
          type: 'object',
          properties: {
            itemId: {
              type: 'string',
              description: 'The item ID to delete',
            },
          },
          required: ['itemId'],
        },
      },
      {
        name: 'list_locations',
        description: 'List all storage locations',
        inputSchema: {
          type: 'object',
          properties: {},
        },
      },
      {
        name: 'create_location',
        description: 'Create a new storage location',
        inputSchema: {
          type: 'object',
          properties: {
            name: {
              type: 'string',
              description: 'Location name',
            },
            description: {
              type: 'string',
              description: 'Location description (optional)',
            },
          },
          required: ['name'],
        },
      },
      {
        name: 'list_labels',
        description: 'List all labels/tags',
        inputSchema: {
          type: 'object',
          properties: {},
        },
      },
      {
        name: 'create_label',
        description: 'Create a new label/tag',
        inputSchema: {
          type: 'object',
          properties: {
            name: {
              type: 'string',
              description: 'Label name',
            },
            description: {
              type: 'string',
              description: 'Label description (optional)',
            },
            color: {
              type: 'string',
              description: 'Label color (hex code, optional)',
            },
          },
          required: ['name'],
        },
      },
      {
        name: 'search_items',
        description: 'Search items by various criteria',
        inputSchema: {
          type: 'object',
          properties: {
            query: {
              type: 'string',
              description: 'Search query',
            },
          },
          required: ['query'],
        },
      },
    ],
  };
});

// Tool handlers
server.setRequestHandler(CallToolRequestSchema, async (request) => {
  try {
    const { name, arguments: args } = request.params;

    switch (name) {
      case 'list_items': {
        const params = {};
        if (args.search) params.q = args.search;
        if (args.locationId) params.locations = args.locationId;
        if (args.labelId) params.labels = args.labelId;
        const response = await homeboxApi.get('/items', { params });
        return {
          content: [
            {
              type: 'text',
              text: JSON.stringify(response.data, null, 2),
            },
          ],
        };
      }

      case 'get_item': {
        const response = await homeboxApi.get(`/items/${args.itemId}`);
        return {
          content: [
            {
              type: 'text',
              text: JSON.stringify(response.data, null, 2),
            },
          ],
        };
      }

      case 'create_item': {
        const response = await homeboxApi.post('/items', args);
        return {
          content: [
            {
              type: 'text',
              text: JSON.stringify(response.data, null, 2),
            },
          ],
        };
      }

      case 'update_item': {
        const { itemId, ...updateData } = args;
        const response = await homeboxApi.put(`/items/${itemId}`, updateData);
        return {
          content: [
            {
              type: 'text',
              text: JSON.stringify(response.data, null, 2),
            },
          ],
        };
      }

      case 'delete_item': {
        await homeboxApi.delete(`/items/${args.itemId}`);
        return {
          content: [
            {
              type: 'text',
              text: `Item ${args.itemId} deleted successfully`,
            },
          ],
        };
      }

      case 'list_locations': {
        const response = await homeboxApi.get('/locations');
        return {
          content: [
            {
              type: 'text',
              text: JSON.stringify(response.data, null, 2),
            },
          ],
        };
      }

      case 'create_location': {
        const response = await homeboxApi.post('/locations', args);
        return {
          content: [
            {
              type: 'text',
              text: JSON.stringify(response.data, null, 2),
            },
          ],
        };
      }

      case 'list_labels': {
        const response = await homeboxApi.get('/labels');
        return {
          content: [
            {
              type: 'text',
              text: JSON.stringify(response.data, null, 2),
            },
          ],
        };
      }

      case 'create_label': {
        const response = await homeboxApi.post('/labels', args);
        return {
          content: [
            {
              type: 'text',
              text: JSON.stringify(response.data, null, 2),
            },
          ],
        };
      }

      case 'search_items': {
        const response = await homeboxApi.get('/items', {
          params: { q: args.query },
        });
        return {
          content: [
            {
              type: 'text',
              text: JSON.stringify(response.data, null, 2),
            },
          ],
        };
      }

      default:
        throw new Error(`Unknown tool: ${name}`);
    }
  } catch (error) {
    return {
      content: [
        {
          type: 'text',
          text: `Error: ${error.message}`,
        },
      ],
      isError: true,
    };
  }
});

// Start server
async function main() {
  await login();
  console.error('HomeBox MCP server authenticated');
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error('HomeBox MCP server running on stdio');
}

main().catch((error) => {
  console.error('Server error:', error);
  process.exit(1);
});
