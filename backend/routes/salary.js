// File: backend/routes/salary.js
const express = require('express');
const router = express.Router();
const db = require('../config/database');
const { authenticateToken, authorizeRoles } = require('../middleware/auth');

// Get salary records (Restricted to Admin, Accounts, HR - Rule 3)
router.get('/', authenticateToken, authorizeRoles('admin', 'accounts', 'hr'), async (req, res) => {
    try {
        const { pay_period, worker_id, status } = req.query;
        const limit = Math.min(Math.max(parseInt(req.query.limit) || 50, 1), 100);
        const offset = Math.max(parseInt(req.query.offset) || 0, 0);

        let query = `
            SELECT s.*, w.name, w.wage_type, w.wage_rate
            FROM salary s
            JOIN workers w ON s.worker_id = w.worker_id
            WHERE 1=1
        `;
        const params = [];

        if (pay_period) {
            query += ' AND s.pay_period = ?';
            params.push(pay_period);
        }
        if (worker_id) {
            query += ' AND s.worker_id = ?';
            params.push(worker_id);
        }
        if (status) {
            query += ' AND s.status = ?';
            params.push(status);
        }

        query += ' ORDER BY s.worker_id ASC LIMIT ? OFFSET ?';
        params.push(limit, offset);

        const [rows] = await db.query(query, params);
        res.json(rows);
    } catch (error) {
        console.error('Error fetching salary records:', error);
        res.status(500).json({ error: 'Failed to retrieve salary records' });
    }
});

// Get salary summary (Restricted to Admin, Accounts, HR)
router.get('/stats/summary', authenticateToken, authorizeRoles('admin', 'accounts', 'hr'), async (req, res) => {
    try {
        const { pay_period } = req.query;
        const period = pay_period || new Date().toISOString().slice(0, 7); // YYYY-MM

        const [summary] = await db.query(`
            SELECT 
                SUM(gross_salary) as total_gross,
                SUM(total_fines) as total_fines,
                SUM(net_salary) as total_net,
                AVG(net_salary) as avg_salary,
                COUNT(*) as worker_count
            FROM salary
            WHERE pay_period = ?
        `, [period]);

        res.json(summary[0] || {});
    } catch (error) {
        console.error('Error fetching salary summary:', error);
        res.status(500).json({ error: 'Failed to retrieve salary summary' });
    }
});

// Get salary detail for a specific worker (Worker can view their own, or Admin/HR)
router.get('/worker/:worker_id', authenticateToken, async (req, res) => {
    try {
        const targetWorkerId = req.params.worker_id;
        const { pay_period } = req.query;
        const period = pay_period || new Date().toISOString().slice(0, 7);

        // Rule 3: Data ownership
        if (req.user.role === 'worker' && req.user.username !== targetWorkerId) {
            return res.status(403).json({ error: 'Forbidden. You can only view your own salary.' });
        }

        const [salary] = await db.query(`
            SELECT s.*, w.name, w.wage_type, w.wage_rate
            FROM salary s
            JOIN workers w ON s.worker_id = w.worker_id
            WHERE s.worker_id = ? AND s.pay_period = ?
        `, [targetWorkerId, period]);

        // Get violations/fines for this worker in SQLite syntax (strftime)
        const [fines] = await db.query(`
            SELECT violation_id, timestamp, violation_type, fine_amount
            FROM violations
            WHERE worker_id = ? 
            AND strftime('%Y-%m', timestamp) = ?
            ORDER BY timestamp DESC
        `, [targetWorkerId, period]);

        res.json({
            salary: salary[0] || null,
            fines: fines || []
        });
    } catch (error) {
        console.error('Error fetching worker salary:', error);
        res.status(500).json({ error: 'Failed to retrieve worker salary' });
    }
});

// Create or update salary record (Admin / Accounts only)
router.post('/', authenticateToken, authorizeRoles('admin', 'accounts'), async (req, res) => {
    try {
        const { worker_id, pay_period, days_worked, hours_worked, gross_salary, total_fines, net_salary } = req.body;

        if (!worker_id || !pay_period || gross_salary === undefined || net_salary === undefined) {
            return res.status(400).json({ error: 'Missing required salary fields' });
        }

        // SQLite ON CONFLICT UPSERT syntax
        await db.query(
            `INSERT INTO salary (worker_id, pay_period, days_worked, hours_worked, rate_per_day_hour, gross_salary, total_fines, net_salary)
             VALUES (?, ?, ?, ?, ?, ?, ?, ?)
             ON CONFLICT(worker_id, pay_period) DO UPDATE SET
             days_worked = excluded.days_worked,
             hours_worked = excluded.hours_worked,
             gross_salary = excluded.gross_salary,
             total_fines = excluded.total_fines,
             net_salary = excluded.net_salary`,
            [
                worker_id,
                pay_period,
                parseInt(days_worked) || 0,
                parseFloat(hours_worked) || 0,
                parseFloat(gross_salary) / (parseInt(days_worked) || 1),
                parseFloat(gross_salary),
                parseFloat(total_fines) || 0,
                parseFloat(net_salary)
            ]
        );

        res.status(201).json({ message: 'Salary record saved successfully' });
    } catch (error) {
        console.error('Error saving salary:', error);
        res.status(500).json({ error: 'Failed to save salary record' });
    }
});

// Update salary status (for payment processing - Admin / Accounts only)
router.put('/:salary_id/status', authenticateToken, authorizeRoles('admin', 'accounts'), async (req, res) => {
    try {
        const { status } = req.body;
        if (!['pending', 'processing', 'paid'].includes(status)) {
            return res.status(400).json({ error: "Invalid status. Must be 'pending', 'processing', or 'paid'" });
        }

        const payment_date = status === 'paid' ? new Date().toISOString().slice(0, 10) : null;

        const [result] = await db.query(
            'UPDATE salary SET status = ?, payment_date = ? WHERE salary_id = ?',
            [status, payment_date, req.params.salary_id]
        );

        if (result.affectedRows === 0) {
            return res.status(404).json({ error: 'Salary record not found' });
        }

        res.json({ message: 'Salary status updated successfully' });
    } catch (error) {
        console.error('Error updating salary status:', error);
        res.status(500).json({ error: 'Failed to update salary status' });
    }
});

// Process payroll for all pending salaries (Admin / Accounts only)
router.post('/process-payroll', authenticateToken, authorizeRoles('admin', 'accounts'), async (req, res) => {
    try {
        const { pay_period } = req.body;
        if (!pay_period) {
            return res.status(400).json({ error: 'pay_period is required' });
        }

        const [result] = await db.query(
            `UPDATE salary 
             SET status = 'processing'
             WHERE pay_period = ? AND status = 'pending'`,
            [pay_period]
        );

        res.json({ 
            message: 'Payroll processing initiated',
            affected_records: result.affectedRows
        });
    } catch (error) {
        console.error('Error processing payroll:', error);
        res.status(500).json({ error: 'Failed to process payroll' });
    }
});

module.exports = router;