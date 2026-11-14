/**
 * Generated from the OpenAPI schema of the backend. Do not edit by hand.
 * Regenerate with: npm --prefix frontend run gen:api
 */

export interface paths {
  '/api/events': {
    parameters: {
      query?: never
      header?: never
      path?: never
      cookie?: never
    }
    /**
     * Get Events
     * @description Open the event stream of this window.
     */
    get: operations['getEvents']
    put?: never
    post?: never
    delete?: never
    options?: never
    head?: never
    patch?: never
    trace?: never
  }
  '/api/health': {
    parameters: {
      query?: never
      header?: never
      path?: never
      cookie?: never
    }
    /**
     * Get Health
     * @description Return the app version and the database schema version.
     */
    get: operations['getHealth']
    put?: never
    post?: never
    delete?: never
    options?: never
    head?: never
    patch?: never
    trace?: never
  }
  '/api/tools': {
    parameters: {
      query?: never
      header?: never
      path?: never
      cookie?: never
    }
    /**
     * Get Tools
     * @description Return the state of every tool, and whether the first-run screen is needed.
     */
    get: operations['getTools']
    put?: never
    post?: never
    delete?: never
    options?: never
    head?: never
    patch?: never
    trace?: never
  }
  '/api/tools/{name}/install': {
    parameters: {
      query?: never
      header?: never
      path?: never
      cookie?: never
    }
    get?: never
    put?: never
    /**
     * Install Tool
     * @description Start installing a tool in the background and return its state.
     */
    post: operations['installTool']
    delete?: never
    options?: never
    head?: never
    patch?: never
    trace?: never
  }
}
export type webhooks = Record<string, never>
export interface components {
  schemas: {
    /**
     * ErrorBody
     * @description The content of every error response.
     *
     *     Attributes:
     *         code: The stable error code (docs/LOGGING.md section 4). Typed, so that the
     *             generated frontend types know every code.
     *         message: A short technical sentence. User text is written per code in the frontend.
     *         details: Extra facts for the technical details.
     */
    ErrorBody: {
      code: components['schemas']['ErrorCode']
      /** Details */
      details: {
        [key: string]: string
      }
      /** Message */
      message: string
    }
    /**
     * ErrorCode
     * @description Stable error codes. The value is what appears in logs and API responses.
     * @enum {string}
     */
    ErrorCode:
      | 'UNAUTHORIZED'
      | 'ORIGIN_REJECTED'
      | 'NOT_FOUND'
      | 'INVALID_REQUEST'
      | 'LOCAL_SERVER_UNREACHABLE'
      | 'NETWORK_UNREACHABLE'
      | 'CHECKSUM_MISMATCH'
      | 'DISK_FULL'
      | 'TOOL_MISSING'
      | 'INTERNAL'
    /**
     * ErrorResponse
     * @description The one shape of every error response.
     */
    ErrorResponse: {
      error: components['schemas']['ErrorBody']
    }
    /** HTTPValidationError */
    HTTPValidationError: {
      /** Detail */
      detail?: components['schemas']['ValidationError'][]
    }
    /**
     * HealthResponse
     * @description The answer of ``GET /api/health``.
     *
     *     Attributes:
     *         status: Always ``ok`` when the server answers.
     *         version: The app version.
     *         schema_version: The database schema version.
     */
    HealthResponse: {
      /** Schema Version */
      schema_version: string | null
      /**
       * Status
       * @constant
       */
      status: 'ok'
      /** Version */
      version: string
    }
    /**
     * Tool
     * @description The state of one tool the app needs (R-IN-03, R-IN-04).
     *
     *     Attributes:
     *         name: The tool.
     *         status: What is known about it right now.
     *         version: Its version, when it is installed.
     *         source: The source it was downloaded from, for a downloaded tool.
     *         progress: How much of its download is done, from 0 to 1, while it installs.
     *         error_code: Why the last installation failed, when it did.
     *         installable: Whether the app can install it by itself.
     */
    Tool: {
      error_code: components['schemas']['ErrorCode'] | null
      /** Installable */
      installable: boolean
      name: components['schemas']['ToolName']
      /** Progress */
      progress: number | null
      /** Source */
      source: string | null
      status: components['schemas']['ToolStatus']
      /** Version */
      version: string | null
    }
    /**
     * ToolName
     * @description The tools the app needs, in the order the first-run screen shows them (R-IN-03).
     * @enum {string}
     */
    ToolName: 'python' | 'ytdlp' | 'ffmpeg' | 'deno'
    /**
     * ToolStatus
     * @description What is known about a tool right now (R-IN-03, R-IN-04).
     * @enum {string}
     */
    ToolStatus: 'ok' | 'missing' | 'broken' | 'installing' | 'failed'
    /**
     * ToolUpdatedEvent
     * @description The data of the ``tool.updated`` event of ``GET /api/events``.
     *
     *     Attributes:
     *         tool: The new state of the tool.
     *         setup_required: Whether the first-run screen is still needed.
     */
    ToolUpdatedEvent: {
      /** Setup Required */
      setup_required: boolean
      tool: components['schemas']['Tool']
    }
    /**
     * ToolsResponse
     * @description The answer of ``GET /api/tools``.
     *
     *     Attributes:
     *         tools: Every tool, in the order of the first-run screen.
     *         setup_required: Whether the interface must show the first-run screen.
     */
    ToolsResponse: {
      /** Setup Required */
      setup_required: boolean
      /** Tools */
      tools: components['schemas']['Tool'][]
    }
    /** ValidationError */
    ValidationError: {
      /** Context */
      ctx?: Record<string, never>
      /** Input */
      input?: unknown
      /** Location */
      loc: (string | number)[]
      /** Message */
      msg: string
      /** Error Type */
      type: string
    }
  }
  responses: never
  parameters: never
  requestBodies: never
  headers: never
  pathItems: never
}
export type $defs = Record<string, never>
export interface operations {
  getEvents: {
    parameters: {
      query?: never
      header?: never
      path?: never
      cookie?: never
    }
    requestBody?: never
    responses: {
      /** @description A stream of Server-Sent Events. The event ``tool.updated`` carries this data. */
      200: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ToolUpdatedEvent']
        }
      }
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
    }
  }
  getHealth: {
    parameters: {
      query?: never
      header?: never
      path?: never
      cookie?: never
    }
    requestBody?: never
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['HealthResponse']
        }
      }
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
    }
  }
  getTools: {
    parameters: {
      query?: never
      header?: never
      path?: never
      cookie?: never
    }
    requestBody?: never
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ToolsResponse']
        }
      }
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
    }
  }
  installTool: {
    parameters: {
      query?: never
      header?: never
      path: {
        name: components['schemas']['ToolName']
      }
      cookie?: never
    }
    requestBody?: never
    responses: {
      /** @description Successful Response */
      202: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['Tool']
        }
      }
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
      /** @description Validation Error */
      422: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['HTTPValidationError']
        }
      }
      /** @description Internal Server Error */
      500: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['ErrorResponse']
        }
      }
    }
  }
}
