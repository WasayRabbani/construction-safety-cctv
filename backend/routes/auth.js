// File: backend/routes/auth.js
const express = require('express');
const router = express.Router();
const db = require('../config/database');
const bcrypt = require('bcrypt');
const jwt = require('jsonwebtoken');

const JWT_SECRET = process.env.JWT_SECRET || 'your_secret_key_change_this';

const ADMIN_REGISTER_CREDENTIALS = {
    username: 'maliksaad',
    password: 'maliksaad123'
};

const ALLOWED_ROLES = ['admin', 'safety officer', 'hr', 'monitor', 'accounts', 'supervisor', 'worker'];

// Register Route
router.post('/register', async (req, res) => {
    try {
        const {
            username,
            password,
            full_name,
            department,
            phone,
            role = 'worker',
            admin_username,
            admin_password
        } = req.body;

        const normalizedRole = String(role || 'worker').trim().toLowerCase();

        // Validate input
        if (!username || !password || !full_name || !admin_username || !admin_password) {
            return res.status(400).json({
                success: false,
                error: 'Username, password, full name, and admin credentials are required.'
            });
        }

        if (!ALLOWED_ROLES.includes(normalizedRole)) {
            return res.status(400).json({
                success: false,
                error: 'The selected role is not allowed. Please choose a valid role.'
            });
        }

        if (
            admin_username !== ADMIN_REGISTER_CREDENTIALS.username ||
            admin_password !== ADMIN_REGISTER_CREDENTIALS.password
        ) {
            return res.status(401).json({
                success: false,
                error: 'Invalid admin credentials. New account creation requires administration login.'
            });
        }

        // Validate username length
        if (username.length < 3) {
            return res.status(400).json({
                success: false,
                error: 'Username must be at least 3 characters'
            });
        }

        // Validate username length
        if (username.length < 3) {
            return res.status(400).json({
                success: false,
                error: 'Username must be at least 3 characters'
            });
        }

        // Validate password length
        if (password.length < 6) {
            return res.status(400).json({
                success: false,
                error: 'Password must be at least 6 characters'
            });
        }

        // Check if user already exists
        const [existingUsers] = await db.query(
            'SELECT * FROM users WHERE username = ?',
            [username]
        );

        if (existingUsers.length > 0) {
            return res.status(400).json({
                success: false,
                error: 'Username already exists. Please choose a different one.'
            });
        }

        // Hash password
        const hashedPassword = await bcrypt.hash(password, 10);

        // Insert new user
        const [result] = await db.query(
            'INSERT INTO users (username, password_hash, full_name, role, phone, department, status) VALUES (?, ?, ?, ?, ?, ?, ?)',
            [username, hashedPassword, full_name, normalizedRole, phone || null, department || null, 'active']
        );

        res.status(201).json({
            success: true,
            message: 'Account created successfully. You can now login.',
            user_id: result.insertId
        });

    } catch (error) {
        console.error('Register error:', error);
        res.status(500).json({
            success: false,
            error: 'Server error during registration. Please try again.'
        });
    }
});

// Login Route
router.post('/login', async (req, res) => {
    try {
        const { username, password } = req.body;

        // Validate input
        if (!username || !password) {
            return res.status(400).json({
                success: false,
                error: 'Username and password are required'
            });
        }

        // Query user from database
        const [users] = await db.query(
            'SELECT * FROM users WHERE username = ?',
            [username]
        );

        if (users.length === 0) {
            return res.status(401).json({
                success: false,
                error: 'Invalid username or password'
            });
        }

        const user = users[0];

        // Check user status
        if (user.status !== 'active') {
            return res.status(401).json({
                success: false,
                error: 'Your account has been deactivated. Contact administrator.'
            });
        }

        // Compare passwords
        const passwordMatch = await bcrypt.compare(password, user.password_hash);

        if (!passwordMatch) {
            return res.status(401).json({
                success: false,
                error: 'Invalid username or password'
            });
        }

        // Update last login
        await db.query(
            'UPDATE users SET last_login = NOW() WHERE user_id = ?',
            [user.user_id]
        );

        // Create JWT token
        const token = jwt.sign(
            {
                user_id: user.user_id,
                username: user.username,
                role: user.role,
                full_name: user.full_name
            },
            JWT_SECRET,
            { expiresIn: '24h' }
        );

        // Return success response
        res.json({
            success: true,
            message: 'Login successful',
            token: token,
            user: {
                user_id: user.user_id,
                username: user.username,
                full_name: user.full_name,
                role: user.role,
                department: user.department,
                phone: user.phone
            }
        });

    } catch (error) {
        console.error('Login error:', error);
        res.status(500).json({
            success: false,
            error: 'Server error during login. Please try again.'
        });
    }
});

// Verify Token Route
router.post('/verify', (req, res) => {
    try {
        const token = req.headers.authorization?.split(' ')[1];

        if (!token) {
            return res.status(401).json({
                success: false,
                error: 'No token provided'
            });
        }

        const decoded = jwt.verify(token, JWT_SECRET);
        res.json({
            success: true,
            user: decoded
        });

    } catch (error) {
        res.status(401).json({
            success: false,
            error: 'Invalid token'
        });
    }
});

// Get Current User Info
router.get('/user', (req, res) => {
    try {
        const token = req.headers.authorization?.split(' ')[1];

        if (!token) {
            return res.status(401).json({
                success: false,
                error: 'No token provided'
            });
        }

        const decoded = jwt.verify(token, JWT_SECRET);
        res.json({
            success: true,
            user: decoded
        });

    } catch (error) {
        res.status(401).json({
            success: false,
            error: 'Invalid token'
        });
    }
});

// Logout (optional - just clear client-side token)
router.post('/logout', (req, res) => {
    res.json({
        success: true,
        message: 'Logout successful'
    });
});

// IMPORTANT: Export the router
module.exports = router;