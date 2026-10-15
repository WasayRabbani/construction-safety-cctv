1. Security first: Never assume a request or user is trustworthy.

2. Authentication: Verify identity on every protected route. Hash passwords securely; never store plaintext passwords.

3. Authorization: Check permissions and data ownership on the backend. Users must not access another user's data by changing an ID.

4. Validate all inputs: Check types, required fields, lengths, formats, and business rules before processing data.

5. Prevent injection: Always use parameterized database queries. Never concatenate untrusted input into SQL.

6. Protect secrets: Keep API keys, database credentials, and JWT secrets out of source code, GitHub, logs, and frontend code.

7. Handle errors safely: Return clear, consistent error responses. Never expose stack traces, SQL errors, or internal paths to clients.

8. Limit resource usage: Apply rate limits, request-size limits, timeouts, and bounded concurrency to prevent abuse and resource exhaustion.

9. Write efficient database queries: Fetch only necessary columns, use appropriate indexes, avoid N+1 queries, and paginate large results.

10. Maintain data integrity: Use database constraints and transactions where needed. Handle duplicate requests and concurrent updates safely.

11. Keep code organized: Separate routes/controllers, business logic, database access, validation, and configuration where appropriate.

12. Handle failures: Expect databases, external APIs, and AI providers to fail. Use appropriate timeouts, bounded retries, and graceful error handling.

13. Test before deploying: Test authentication, authorization, invalid inputs, database operations, edge cases, and failure scenarios.

14. Monitor production: Use structured logs, request IDs, health checks, and alerts. Never log passwords or access tokens.

15. Deploy securely: Use HTTPS, production configuration, restricted database access, managed secrets, backups, dependency updates, and a rollback plan.