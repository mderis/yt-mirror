/**
 * Generated from the OpenAPI schema of the backend. Do not edit by hand.
 * Regenerate with: npm --prefix frontend run gen:api
 */

export interface paths {
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
      | 'INTERNAL'
    /**
     * ErrorResponse
     * @description The one shape of every error response.
     */
    ErrorResponse: {
      error: components['schemas']['ErrorBody']
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
  }
  responses: never
  parameters: never
  requestBodies: never
  headers: never
  pathItems: never
}
export type $defs = Record<string, never>
export interface operations {
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
}
