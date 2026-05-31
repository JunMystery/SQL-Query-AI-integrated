## Key Technical Implementation Points – Full SELECT Capability Upgrade

This document outlines the core technical implementations required to upgrade the AI Agent so it can autonomously generate **complete SELECT statements** supporting all standard SQL constructs: `BETWEEN`, `IN`, `JOIN`, subqueries, set operations, aggregations, and more. No project timelines or deadlines are imposed – only functional and architectural specifications.

---

### 1. Schema Understanding & Relationship Mapping

The agent must first understand the database structure to generate correct queries involving multiple tables and complex filters.

#### 1.1 Metadata Extraction
- Use `SQLAlchemy`’s introspection API to extract:
  - Table names, column names, data types, nullability
  - Primary keys and foreign keys
  - Indexes, constraints, and column comments (if available)
- Store extracted metadata in an in‑memory graph structure.

#### 1.2 Relationship Graph Construction
- Build a directed graph where:
  - Nodes = tables
  - Edges = foreign key relationships (direction from referencing to referenced table)
- Annotate edges with join condition templates (e.g., `left_table.column = right_table.column`).
- Support composite foreign keys (multiple columns).

#### 1.3 Automatic Join Path Discovery
- Given a set of tables mentioned in the natural language query, compute the minimal join path using graph traversal (BFS).
- If no direct foreign key exists, suggest plausible join conditions using:
  - Same column names across tables
  - Naming conventions (e.g., `user_id` in `orders` referencing `id` in `users`)
- Allow manual override via configuration.

---

### 2. SELECT Clause Generation

Handle column selection, expressions, aliases, and aggregate functions.

#### 2.1 Column Resolution
- Map natural language column references (e.g., “customer name”, “order total”) to actual columns.
- Resolve ambiguous references using:
  - Context from previous clauses (e.g., already determined tables)
  - Heuristics (most frequently used table for that term)
  - User disambiguation via UI (if needed)

#### 2.2 Expressions & Aliases
- Support arithmetic expressions: `quantity * unit_price AS total`
- Support string concatenation / date functions based on dialect (e.g., `CONCAT(first_name, ' ', last_name)`).
- Generate unambiguous aliases automatically when expressions are used.

#### 2.3 Aggregate Functions
- Recognise aggregate keywords: `COUNT`, `SUM`, `AVG`, `MIN`, `MAX`, `GROUP_CONCAT`/`STRING_AGG`.
- When aggregates appear without `GROUP BY`, treat entire result as a single group.
- When `GROUP BY` is needed, automatically determine grouping columns from non‑aggregated selected columns.

---

### 3. WHERE Clause – Full Operator Support

Extend beyond simple equality/inequality to include all major operators.

#### 3.1 Operator Detection from Natural Language
- Build a rule‑based + LLM‑prompted classifier for each operator:
  - `BETWEEN` : “between … and …”, “from … to …”, “in the range …”
  - `IN` : “in (list)”, “one of”, “either … or …”
  - `LIKE` : “contains”, “starts with”, “ends with”, “pattern”, “wildcard”
  - `EXISTS` : “has at least one”, “there exists”, “where any”
  - `IS NULL` / `IS NOT NULL` : “is missing”, “has no value”, “is empty”
- Output a structured condition tree (e.g., `{'operator': 'BETWEEN', 'column': 'price', 'low': 10, 'high': 100}`).

#### 3.2 Condition Chaining (AND/OR)
- Detect logical connectors in the user’s sentence (“and”, “or”, “, but not”).
- Build a proper parenthesised condition tree to preserve precedence.
- Allow nested conditions (e.g., `(A OR B) AND C`).

#### 3.3 Type-Aware Rendering
- Render values according to column data type:
  - Strings wrapped in quotes, escaping internal quotes
  - Numbers without quotes
  - Dates/timestamps using dialect‑appropriate literals
- For `IN` with long lists, consider using `= ANY(...)` for PostgreSQL or `IN` with subqueries.

---

### 4. JOIN Handling

Generate correct JOIN clauses for multi‑table queries.

#### 4.1 Join Type Selection
- Determine join type based on user intent:
  - **INNER JOIN** : default, when only matching rows are needed
  - **LEFT/RIGHT JOIN** : when user says “all records from X, even if no match in Y”
  - **FULL OUTER JOIN** : “both sides”, “all records from both tables”
- For ambiguous cases, default to INNER JOIN and allow manual adjustment.

#### 4.2 Condition Generation
- Use the relationship graph to obtain the correct join condition.
- If multiple possible join paths exist (e.g., two different foreign keys between tables), ask the user or apply heuristics (most recent / most selective).
- Support non‑equi joins if needed (e.g., `ON A.start <= B.end`), though these are rare.

#### 4.3 Table Aliasing
- Automatically generate short aliases (e.g., `c`, `o`, `p`) to keep SQL readable.
- Use consistent aliases across the query (avoid conflicts).

---

### 5. Subquery Support

Support subqueries in `SELECT`, `FROM`, and `WHERE` clauses.

#### 5.1 Subquery Intent Detection
- Phrases indicating a subquery:
  - “whose average salary is greater than the overall average” → subquery inside `WHERE` or `HAVING`
  - “companies that have at least one employee earning more than 100k” → `EXISTS` subquery
  - “the highest paid employee in each department” → correlated subquery
- Classify into three types:
  - Scalar subquery (returns one value)
  - Row subquery (rare)
  - Table subquery (used in `FROM`)

#### 5.2 Subquery Generation Pipeline
1. Decompose the main question into two parts: inner and outer.
2. Generate the inner SQL independently (can reuse the same engine).
3. Wrap it appropriately (e.g., `WHERE salary > (SELECT AVG(salary) …)`).
4. Ensure correlation columns are correctly referenced (e.g., `WHERE dept_id = outer.dept_id`).

#### 5.3 Optimisation & Readability
- For `NOT IN` subqueries, consider rewriting as `NOT EXISTS` (handles NULLs correctly) – the agent can offer both versions.
- Flatten simple subqueries into joins when possible for better performance (e.g., `SELECT ... FROM (SELECT ...) AS sub` can often be a join).

---

### 6. GROUP BY & HAVING

Handle grouping and post‑aggregation filtering.

#### 6.1 Automatic GROUP BY Detection
- When a query contains both aggregate functions and non‑aggregated columns, those non‑aggregated columns become the `GROUP BY` list.
- If the user explicitly mentions “group by X”, honour that grouping.

#### 6.2 HAVING Clause Generation
- Detect filter conditions that refer to aggregate results (e.g., “total sales > 10000” after `SUM(sales)`).
- Move such conditions from `WHERE` to `HAVING`.
- Combine with regular `WHERE` conditions correctly (WHERE applies before grouping, HAVING after).

#### 6.3 Complex Grouping
- Support grouping by expressions (e.g., `YEAR(order_date)`).
- Support `ROLLUP`, `CUBE`, `GROUPING SETS` if explicitly requested (advanced).

---

### 7. ORDER BY, LIMIT, OFFSET

#### 7.1 Sorting
- Detect ascending/descending intent (“highest first”, “oldest to newest”).
- Support multiple sort columns (“sort by department, then by salary descending”).
- For expressions, sort by the expression or its alias.

#### 7.2 Pagination
- Recognise “top N”, “first N”, “limit N” → generate `LIMIT N`.
- Recognise “skip N”, “after the first N” → add `OFFSET N`.
- Dialect handling: SQLite/PostgreSQL use `LIMIT ... OFFSET`, SQL Server uses `OFFSET ... FETCH`, MySQL supports `LIMIT offset, count`.

---

### 8. Set Operations (UNION, INTERSECT, EXCEPT)

#### 8.1 Intent Recognition
- Phrases: “combine results from A and B” (UNION), “common to both” (INTERSECT), “in A but not in B” (EXCEPT/MINUS).
- Determine if duplicates should be removed (`UNION` vs `UNION ALL`). Default to `UNION ALL` when user says “include duplicates” or uses “all”.

#### 8.2 Generation Process
1. Split the user request into two (or more) independent sub‑queries.
2. Generate each sub‑query separately.
3. Ensure the same number and compatible types of columns.
4. Combine them with the appropriate set operator.
5. Apply a final `ORDER BY` / `LIMIT` on the whole result.

---

### 9. Self‑Correction & Validation

The agent must be able to verify and fix its own SQL.

#### 9.1 Syntax Validation
- Use `sqlglot` to parse the generated SQL against the target dialect (PostgreSQL, MySQL, SQLite).
- Capture parse errors and feed them back to the LLM for correction.

#### 9.2 Semantic Validation
- Execute the query in a test transaction with `ROLLBACK` (safe mode) to detect runtime errors (e.g., column not found, type mismatch, ambiguous column).
- Parse the database error message, extract the exact problem (e.g., `column "xyz" is ambiguous`), and ask the agent to fix it.

#### 9.3 Result‑Based Correction
- For queries that execute but return obviously wrong results (e.g., zero rows when expected many, unexpected number of columns), the agent can:
  - Compare with a simplified manual query (if the user provides one)
  - Ask clarifying questions to correct the intent
- Implement an iterative loop: generate → validate → correct → re‑validate (max 3 attempts).

#### 9.4 Performance Validation (optional)
- Run `EXPLAIN` (or `EXPLAIN ANALYZE`) on the generated query to detect full table scans or missing indexes.
- Suggest index creation or query rewriting to the user.

---

### 10. Query Optimisation & Rewriting

Improve the quality of generated SQL without changing its semantics.

#### 10.1 Dialect‑Specific Optimisations
- Convert `IN (SELECT ...)` to `EXISTS` when the subquery is large.
- Replace `OR` chains with `IN` where applicable.
- Use `WITH` (CTE) for repeated subqueries to improve readability and performance.

#### 10.2 Join Reordering
- If the generated SQL has `A JOIN B JOIN C` with a poor join order, reorder based on estimated cardinality (heuristic: smaller table first, or follow foreign key direction).

#### 10.3 Index Recommendations
- Analyse the `WHERE`, `JOIN`, and `ORDER BY` clauses to identify columns that would benefit from indexing.
- Generate `CREATE INDEX` statements and present them to the user.

---

### 11. RAG & Few‑Shot Learning for Complex Constructs

To improve accuracy for rare operators (`BETWEEN`, `EXISTS`, set operations), the agent can retrieve similar examples.

#### 11.1 Example Storage
- Store pairs of (natural language description, SQL query) in a vector database (Chroma, FAISS).
- Include metadata: database schema fingerprint, operator types used, complexity level.

#### 11.2 Retrieval Augmentation
- For a new user question, find the top‑k most similar previous questions (cosine similarity on embeddings).
- Inject the corresponding SQL examples into the LLM prompt as few‑shot demonstrations.
- This is especially effective for `JOIN` patterns and `GROUP BY` with having.

#### 11.3 Continuous Learning
- Allow the user to correct generated SQL and store the correction as a new example.
- Periodically re‑embed and update the vector store.

---

### 12. Multi‑Agent Orchestration (Optional but Recommended)

For very complex queries, split responsibilities among specialised agents.

- **Router Agent** – determines which SQL features are needed (joins, aggregations, subqueries, etc.)
- **Join Planner Agent** – computes the minimal join path and join types
- **Filter Agent** – builds the WHERE clause with all operators
- **Aggregation Agent** – handles GROUP BY and HAVING
- **Validator Agent** – runs syntax and semantic checks
- **Assembler Agent** – combines all pieces into final SQL

This decomposition reduces the cognitive load on a single LLM call and improves reliability.

---

### 13. Integration with Existing SQLBot Desktop Application

The new engine must fit seamlessly into the current PySide6 application.

#### 13.1 API / Service Layer
- Expose the enhanced agent as a Python class `AdvancedSQLAgent` with a method `generate_sql(user_input: str, db_connection) -> str`.
- Maintain backward compatibility: fallback to simple generation if advanced features not required.

#### 13.2 UI Enhancements (minimal)
- Add a “Explain SQL” button that shows the agent’s reasoning steps (join path, operator detection, etc.)
- Display warnings for potential performance issues (e.g., no index on filtered column).
- Provide a “Simplify” suggestion that rewrites complex SQL into easier form.

#### 13.3 Configuration
- Allow the user to enable/disable advanced operators (e.g., disable subqueries if the database is very slow).
- Set per‑database dialect (MySQL, PostgreSQL, SQLite) either automatically from the connection or manually.

---

### 14. Testing & Quality Assurance

To ensure the agent handles all SELECT constructs correctly.

#### 14.1 Unit Test Suite
- For each operator (`BETWEEN`, `IN`, `JOIN`, etc.), create a set of natural language inputs and expected SQL outputs.
- Use a lightweight test database (SQLite in memory) with known schema and data.

#### 14.2 Integration Tests
- Test multi‑clause queries combining joins, aggregations, and subqueries.
- Verify self‑correction loops by injecting intentional errors.

#### 14.3 Benchmark Against Public Datasets
- Use the **Spider** or **BIRD** text‑to‑SQL benchmark to measure execution accuracy.
- Aim for ≥85% exact matching on queries that involve the implemented operators.

---

### Summary of Technical Deliverables

| Component | Implementation Artifact |
|-----------|------------------------|
| Schema graph | `schema_graph.py` – builds and queries foreign key relationships |
| Operator detector | `operator_classifier.py` – rule+LLM based detection of BETWEEN, IN, LIKE, EXISTS |
| Join planner | `join_planner.py` – minimal join path & join type selection |
| Subquery engine | `subquery_generator.py` – decomposes and nests queries |
| Aggregation handler | `grouping_handler.py` – GROUP BY + HAVING logic |
| Set operation handler | `setop_handler.py` – UNION/INTERSECT/EXCEPT generation |
| Self‑correction loop | `correction_loop.py` – validate + repair iterations |
| RAG example store | `example_store.py` – vector DB for few‑shot learning |
| Multi‑agent orchestrator | `orchestrator.py` – dispatches sub‑tasks to specialised agents |

This technical foundation enables the AI Agent to generate **any valid SELECT statement**, fully covering `BETWEEN`, `IN`, `JOIN`, subqueries, set operations, and all other SQL clauses – without artificial time constraints.