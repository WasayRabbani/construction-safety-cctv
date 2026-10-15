// File: backend/middleware/auth.js
const jwt = require('jsonwebtoken');

const JWT_SECRET = process.env.JWT_SECRET || 'x9f8b2d7k4m1n5p0q3v6';

/**
 * Middleware: Verifies the JWT Bearer token on incoming requests.
 * Rule 2 (Authentication)
 */
function authenticateToken(req, res, next) {
    const authHeader = req.headers['authorization'] || req.headers['Authorization'];

    if (!authHeader || !authHeader.startsWith('Bearer ')) {
        return res.status(401).json({
            success: false,
            error: 'Access denied. No Bearer token provided.'
        });
    }

    const token = authHeader.split(' ')[1];

    jwt.verify(token, JWT_SECRET, (err, decodedUser) => {
        if (err) {
            return res.status(403).json({
                success: false,
                error: 'Invalid or expired authentication token.'
            });
        }

        // Attach verified user payload { user_id, username, role, full_name } to request object
        req.user = decodedUser;
        next();
    });
}

/**
 * Middleware: Role-Based Access Control (RBAC).
 * Rule 3 (Authorization)
 * Example usage: authorizeRoles('admin', 'supervisor')
 */
function authorizeRoles(...allowedRoles) {
    return (req, res, next) => {
        if (!req.user) {
            return res.status(401).json({
                success: false,
                error: 'Unauthorized. Please log in first.'
            });
        }

        const userRole = (req.user.role || '').toLowerCase();
        const normalizedAllowed = allowedRoles.map(r => r.toLowerCase());

        if (!normalizedAllowed.includes(userRole)) {
            return res.status(403).json({
                success: false,
                error: `Forbidden. Role '${req.user.role}' is not authorized to access this resource.`
            });
        }

        next();
    };
}

const INTERNAL_API_KEY = process.env.INTERNAL_API_KEY || 'ppe_internal_ai_secret_key_2026';

/**
 * Middleware: Requires either a valid x-api-key header (for Python AI services)
 * OR a valid Bearer JWT token (for logged-in staff).
 * Rule 1 & Rule 2 (Security First & Authentication)
 */
function requireApiKeyOrAuth(req, res, next) {
    const apiKey = req.headers['x-api-key'];

    if (apiKey && apiKey === INTERNAL_API_KEY) {
        req.isInternalService = true;
        req.user = { role: 'ai_service', username: 'internal_ai' };
        return next();
    }

    // Fall back to Bearer JWT authentication
    authenticateToken(req, res, next);
}

module.exports = {
    authenticateToken,
    authorizeRoles,
    requireApiKeyOrAuth
};
