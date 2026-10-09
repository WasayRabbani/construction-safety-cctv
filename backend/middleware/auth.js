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

module.exports = {
    authenticateToken,
    authorizeRoles
};
