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

/**
 * Helper: Calculates payroll for a single worker for a specified pay_period (YYYY-MM).
 * Aggregates attendance hours/days from 'attendance' and non-waived fines from 'fines'.
 * Rule 1, 3 & 11: Server-side business logic.
 */
async function calculateWorkerPayroll(worker_id, pay_period) {
    // 1. Fetch worker wage details
    const [workers] = await db.query(
        'SELECT worker_id, name, wage_type, wage_rate FROM workers WHERE worker_id = ?',
        [worker_id]
    );

    if (workers.length === 0) {
        throw new Error(`Worker with ID '${worker_id}' not found`);
    }

    const worker = workers[0];
    const wageRate = parseFloat(worker.wage_rate) || 0;

    // 2. Aggregate attendance for pay_period (YYYY-MM)
    const [attendanceRows] = await db.query(`
        SELECT 
            COUNT(*) as days_worked,
            SUM(COALESCE(working_hours, 8)) as hours_worked
        FROM attendance
        WHERE worker_id = ? 
          AND strftime('%Y-%m', attendance_date) = ?
          AND status IN ('present', 'late')
    `, [worker_id, pay_period]);

    const daysWorked = parseInt(attendanceRows[0]?.days_worked) || 0;
    const hoursWorked = parseFloat(attendanceRows[0]?.hours_worked) || 0;

    // 3. Calculate gross salary based on wage type
    let grossSalary = 0;
    if (worker.wage_type === 'hourly') {
        grossSalary = hoursWorked * wageRate;
    } else {
        grossSalary = daysWorked * wageRate;
    }

    // 4. Aggregate active fines for pay_period
    const [fineRows] = await db.query(`
        SELECT 
            SUM(fine_amount) as total_fines,
            SUM(CASE WHEN fine_type = 'violation' THEN fine_amount ELSE 0 END) as violation_fines,
            SUM(CASE WHEN fine_type = 'absence' THEN fine_amount ELSE 0 END) as absence_fines,
            SUM(CASE WHEN fine_type = 'late' THEN fine_amount ELSE 0 END) as late_fines,
            SUM(CASE WHEN fine_type = 'other' THEN fine_amount ELSE 0 END) as other_fines
        FROM fines
        WHERE worker_id = ? 
          AND strftime('%Y-%m', fine_date) = ?
          AND status != 'waived'
    `, [worker_id, pay_period]);

    const violationFines = parseFloat(fineRows[0]?.violation_fines) || 0;
    const absenceFines = parseFloat(fineRows[0]?.absence_fines) || 0;
    const lateFines = parseFloat(fineRows[0]?.late_fines) || 0;
    const otherFines = parseFloat(fineRows[0]?.other_fines) || 0;
    const totalFines = parseFloat(fineRows[0]?.total_fines) || 0;

    // 5. Calculate net salary
    const netSalary = Math.max(0, grossSalary - totalFines);

    return {
        worker_id,
        name: worker.name,
        pay_period,
        wage_type: worker.wage_type,
        rate_per_day_hour: wageRate,
        days_worked: daysWorked,
        hours_worked: hoursWorked,
        gross_salary: Math.round(grossSalary * 100) / 100,
        violation_fines: violationFines,
        absence_fines: absenceFines,
        late_fines: lateFines,
        other_fines: otherFines,
        total_fines: totalFines,
        net_salary: Math.round(netSalary * 100) / 100
    };
}

// Calculate payroll for a single worker (Server-side calculation)
router.post('/calculate/:worker_id', authenticateToken, authorizeRoles('admin', 'accounts'), async (req, res) => {
    try {
        const { pay_period, auto_save = true } = req.body;
        const period = pay_period || new Date().toISOString().slice(0, 7);
        const calculation = await calculateWorkerPayroll(req.params.worker_id, period);

        if (auto_save) {
            await db.query(`
                INSERT INTO salary (
                    worker_id, pay_period, days_worked, hours_worked, rate_per_day_hour,
                    gross_salary, violation_fines, absence_fines, late_fines, other_fines,
                    total_fines, net_salary, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending')
                ON CONFLICT(worker_id, pay_period) DO UPDATE SET
                    days_worked = excluded.days_worked,
                    hours_worked = excluded.hours_worked,
                    rate_per_day_hour = excluded.rate_per_day_hour,
                    gross_salary = excluded.gross_salary,
                    violation_fines = excluded.violation_fines,
                    absence_fines = excluded.absence_fines,
                    late_fines = excluded.late_fines,
                    other_fines = excluded.other_fines,
                    total_fines = excluded.total_fines,
                    net_salary = excluded.net_salary,
                    updated_at = datetime('now', 'localtime')
            `, [
                calculation.worker_id,
                calculation.pay_period,
                calculation.days_worked,
                calculation.hours_worked,
                calculation.rate_per_day_hour,
                calculation.gross_salary,
                calculation.violation_fines,
                calculation.absence_fines,
                calculation.late_fines,
                calculation.other_fines,
                calculation.total_fines,
                calculation.net_salary
            ]);
        }

        res.json({ success: true, calculation, saved: !!auto_save });
    } catch (error) {
        console.error('Error calculating worker payroll:', error);
        res.status(500).json({ error: error.message || 'Failed to calculate worker payroll' });
    }
});

// Bulk server-side payroll generation for all active workers
router.post('/generate-period', authenticateToken, authorizeRoles('admin', 'accounts'), async (req, res) => {
    try {
        const { pay_period } = req.body;
        const period = pay_period || new Date().toISOString().slice(0, 7);

        const [activeWorkers] = await db.query(
            "SELECT worker_id FROM workers WHERE status = 'active'"
        );

        if (activeWorkers.length === 0) {
            return res.json({ message: 'No active workers found', processed: 0 });
        }

        const results = [];
        for (const w of activeWorkers) {
            const calc = await calculateWorkerPayroll(w.worker_id, period);
            await db.query(`
                INSERT INTO salary (
                    worker_id, pay_period, days_worked, hours_worked, rate_per_day_hour,
                    gross_salary, violation_fines, absence_fines, late_fines, other_fines,
                    total_fines, net_salary, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending')
                ON CONFLICT(worker_id, pay_period) DO UPDATE SET
                    days_worked = excluded.days_worked,
                    hours_worked = excluded.hours_worked,
                    rate_per_day_hour = excluded.rate_per_day_hour,
                    gross_salary = excluded.gross_salary,
                    violation_fines = excluded.violation_fines,
                    absence_fines = excluded.absence_fines,
                    late_fines = excluded.late_fines,
                    other_fines = excluded.other_fines,
                    total_fines = excluded.total_fines,
                    net_salary = excluded.net_salary,
                    updated_at = datetime('now', 'localtime')
            `, [
                calc.worker_id,
                calc.pay_period,
                calc.days_worked,
                calc.hours_worked,
                calc.rate_per_day_hour,
                calc.gross_salary,
                calc.violation_fines,
                calc.absence_fines,
                calc.late_fines,
                calc.other_fines,
                calc.total_fines,
                calc.net_salary
            ]);
            results.push(calc);
        }

        res.json({
            success: true,
            message: `Payroll successfully generated for period ${period}`,
            processed: results.length,
            records: results
        });
    } catch (error) {
        console.error('Error generating period payroll:', error);
        res.status(500).json({ error: 'Failed to generate period payroll' });
    }
});

module.exports = router;