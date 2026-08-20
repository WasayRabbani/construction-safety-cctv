const express = require('express');
const router = express.Router();
const db = require('../config/database');

// Get salary records
router.get('/', async (req, res) => {
    try {
        const { pay_period, worker_id, status } = req.query;
        
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
        
        query += ' ORDER BY s.worker_id ASC';
        
        const [rows] = await db.query(query, params);
        res.json(rows);
    } catch (error) {
        console.error('Error fetching salary records:', error);
        res.status(500).json({ error: error.message });
    }
});

// Get salary summary
router.get('/stats/summary', async (req, res) => {
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
        
        res.json(summary[0]);
    } catch (error) {
        console.error('Error fetching salary summary:', error);
        res.status(500).json({ error: error.message });
    }
});

// Get salary detail for a worker
router.get('/worker/:worker_id', async (req, res) => {
    try {
        const { pay_period } = req.query;
        
        const [salary] = await db.query(`
            SELECT s.*, w.name, w.wage_type, w.wage_rate
            FROM salary s
            JOIN workers w ON s.worker_id = w.worker_id
            WHERE s.worker_id = ? AND s.pay_period = ?
        `, [req.params.worker_id, pay_period]);
        
        // Get violations/fines for this worker
        const [fines] = await db.query(`
            SELECT violation_id, timestamp, violation_type, fine_amount
            FROM violations
            WHERE worker_id = ? 
            AND DATE_FORMAT(timestamp, '%Y-%m') = ?
            ORDER BY timestamp DESC
        `, [req.params.worker_id, pay_period]);
        
        res.json({
            salary: salary[0] || null,
            fines: fines
        });
    } catch (error) {
        console.error('Error fetching worker salary:', error);
        res.status(500).json({ error: error.message });
    }
});

// Create or update salary record
router.post('/', async (req, res) => {
    try {
        const { worker_id, pay_period, days_worked, hours_worked, gross_salary, total_fines, net_salary } = req.body;
        
        const [result] = await db.query(
            `INSERT INTO salary (worker_id, pay_period, days_worked, hours_worked, gross_salary, total_fines, net_salary)
             VALUES (?, ?, ?, ?, ?, ?, ?)
             ON DUPLICATE KEY UPDATE
             days_worked = VALUES(days_worked),
             hours_worked = VALUES(hours_worked),
             gross_salary = VALUES(gross_salary),
             total_fines = VALUES(total_fines),
             net_salary = VALUES(net_salary)`,
            [worker_id, pay_period, days_worked, hours_worked, gross_salary, total_fines, net_salary]
        );
        
        res.status(201).json({ message: 'Salary record saved successfully' });
    } catch (error) {
        console.error('Error saving salary:', error);
        res.status(500).json({ error: error.message });
    }
});

// Update salary status (for payment processing)
router.put('/:salary_id/status', async (req, res) => {
    try {
        const { status } = req.body;
        const payment_date = status === 'paid' ? new Date() : null;
        
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
        res.status(500).json({ error: error.message });
    }
});

// Process payroll for all pending salaries
router.post('/process-payroll', async (req, res) => {
    try {
        const { pay_period } = req.body;
        
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
        res.status(500).json({ error: error.message });
    }
});

module.exports = router;