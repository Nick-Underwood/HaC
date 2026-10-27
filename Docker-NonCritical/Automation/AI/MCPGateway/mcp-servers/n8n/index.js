#!/usr/bin/env node
import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from '@modelcontextprotocol/sdk/types.js';
import axios from 'axios';

const N8N_URL = process.env.N8N_URL || 'http://localhost:5678';
const N8N_API_KEY = process.env.N8N_API_KEY;

// Create axios instance with auth
const n8nApi = axios.create({
  baseURL: N8N_URL,
  headers: {
    'X-N8N-API-KEY': N8N_API_KEY,
  },
});

// Create MCP server
const server = new Server(
  {
    name: 'n8n-mcp-server',
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
        name: 'list_workflows',
        description: 'List all workflows in n8n',
        inputSchema: {
          type: 'object',
          properties: {
            active: {
              type: 'boolean',
              description: 'Filter by active status (optional)',
            },
          },
        },
      },
      {
        name: 'get_workflow',
        description: 'Get details of a specific workflow',
        inputSchema: {
          type: 'object',
          properties: {
            workflowId: {
              type: 'string',
              description: 'The workflow ID',
            },
          },
          required: ['workflowId'],
        },
      },
      {
        name: 'activate_workflow',
        description: 'Activate a workflow',
        inputSchema: {
          type: 'object',
          properties: {
            workflowId: {
              type: 'string',
              description: 'The workflow ID to activate',
            },
          },
          required: ['workflowId'],
        },
      },
      {
        name: 'deactivate_workflow',
        description: 'Deactivate a workflow',
        inputSchema: {
          type: 'object',
          properties: {
            workflowId: {
              type: 'string',
              description: 'The workflow ID to deactivate',
            },
          },
          required: ['workflowId'],
        },
      },
      {
        name: 'execute_workflow',
        description: 'Execute a workflow',
        inputSchema: {
          type: 'object',
          properties: {
            workflowId: {
              type: 'string',
              description: 'The workflow ID to execute',
            },
            data: {
              type: 'object',
              description: 'Input data for the workflow (optional)',
            },
          },
          required: ['workflowId'],
        },
      },
      {
        name: 'list_executions',
        description: 'List workflow executions',
        inputSchema: {
          type: 'object',
          properties: {
            workflowId: {
              type: 'string',
              description: 'Filter by workflow ID (optional)',
            },
            status: {
              type: 'string',
              description: 'Filter by status: success, error, waiting (optional)',
              enum: ['success', 'error', 'waiting'],
            },
          },
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
      case 'list_workflows': {
        const params = {};
        if (args.active !== undefined) {
          params.active = args.active;
        }
        const response = await n8nApi.get('/workflows', { params });
        return {
          content: [
            {
              type: 'text',
              text: JSON.stringify(response.data, null, 2),
            },
          ],
        };
      }

      case 'get_workflow': {
        const response = await n8nApi.get(`/workflows/${args.workflowId}`);
        return {
          content: [
            {
              type: 'text',
              text: JSON.stringify(response.data, null, 2),
            },
          ],
        };
      }

      case 'activate_workflow': {
        const response = await n8nApi.patch(`/workflows/${args.workflowId}`, {
          active: true,
        });
        return {
          content: [
            {
              type: 'text',
              text: `Workflow ${args.workflowId} activated successfully`,
            },
          ],
        };
      }

      case 'deactivate_workflow': {
        const response = await n8nApi.patch(`/workflows/${args.workflowId}`, {
          active: false,
        });
        return {
          content: [
            {
              type: 'text',
              text: `Workflow ${args.workflowId} deactivated successfully`,
            },
          ],
        };
      }

      case 'execute_workflow': {
        const response = await n8nApi.post(
          `/workflows/${args.workflowId}/execute`,
          args.data || {}
        );
        return {
          content: [
            {
              type: 'text',
              text: JSON.stringify(response.data, null, 2),
            },
          ],
        };
      }

      case 'list_executions': {
        const params = {};
        if (args.workflowId) params.workflowId = args.workflowId;
        if (args.status) params.status = args.status;
        const response = await n8nApi.get('/executions', { params });
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
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error('n8n MCP server running on stdio');
}

main().catch((error) => {
  console.error('Server error:', error);
  process.exit(1);
});
