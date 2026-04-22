# Databricks SQL API reference

How to authenticate and execute SQL queries against Databricks from the CLI or shell. Covers the statement execution API, warehouse discovery, and known gotchas.

## Authentication

Uses the Databricks CLI with a named profile. The profile `production` is configured in `~/.databrickscfg`.

```bash
# Check current auth status
databricks auth status -p production

# Re-authenticate when the token has expired
databricks auth login --profile production
```

Auth tokens expire and need to be refreshed mid-session. The error when expired is not always obvious; if an API call fails with an auth-related message, re-run the login command above before retrying.

## Discovering the warehouse ID

List available SQL warehouses and find the one to use:

```bash
databricks warehouses list --profile production \
  | python3 -c "
import sys, json
for w in json.load(sys.stdin):
    print(w['id'], w['name'], w.get('state',''))
"
```

The warehouse ID is a hex string (e.g. `abc123def456`). Find it once and reuse it. Store it in a variable or note it for reuse across queries.

## Executing SQL queries

Use the statement execution REST API. The Databricks CLI `databricks api post` command wraps this.

```bash
databricks api post /api/2.0/sql/statements \
  --profile production \
  --body '{
    "warehouse_id": "WAREHOUSE_ID",
    "statement": "SELECT 1",
    "wait_timeout": "50s"
  }' > /tmp/db_result.json
```

Then parse the result:

```bash
python3 -c "
import json
data = json.load(open('/tmp/db_result.json'))
cols = [c['name'] for c in data['manifest']['schema']['columns']]
rows = data['result']['data_array']
print(cols)
for r in rows[:10]:
    print(dict(zip(cols, r)))
"
```

### wait_timeout limits

The `wait_timeout` field must be either `0s` (disables waiting, returns immediately with a statement ID to poll) or between `5s` and `50s`. Values above `50s` return an error. Use `50s` as the practical maximum for synchronous queries.

### Large result output

When piping `databricks api post` output to another command, large responses may be written to a temp file instead of stdout, causing the pipe to receive empty input. Always redirect to a file explicitly:

```bash
databricks api post ... > /tmp/db_result.json
# then parse /tmp/db_result.json separately
```

### Result format

The response JSON has this shape:

```
{
  "status": { "state": "SUCCEEDED" },
  "manifest": {
    "schema": {
      "columns": [ { "name": "col1" }, ... ]
    }
  },
  "result": {
    "data_array": [ ["val1", "val2", ...], ... ]
  }
}
```

All values in `data_array` are strings regardless of column type. Cast as needed in Python.

## Running multi-line SQL

Pass the SQL as a string value in the JSON body. For longer queries, write the body to a temp file and use `--body-file` if supported, or construct it with Python:

```bash
python3 -c "
import json, subprocess

sql = '''
SELECT
  col1,
  COUNT(*) AS cnt
FROM my_table
WHERE date_col >= CURRENT_DATE - INTERVAL 7 DAY
GROUP BY col1
ORDER BY cnt DESC
'''

body = {
    'warehouse_id': 'WAREHOUSE_ID',
    'statement': sql,
    'wait_timeout': '50s'
}

with open('/tmp/db_body.json', 'w') as f:
    json.dump(body, f)
"

databricks api post /api/2.0/sql/statements \
  --profile production \
  --body "$(cat /tmp/db_body.json)" > /tmp/db_result.json
```

## Databricks SQL dialect notes

- Use `DATE_TRUNC('hour', timestamp_col)` for hourly bucketing.
- Use `CURRENT_DATE` and `CURRENT_TIMESTAMP` for relative date filters.
- `INTERVAL` syntax: `INTERVAL 7 DAY`, `INTERVAL 2 HOUR`, `INTERVAL 10 WEEK`.
- `CONVERT_TIMEZONE('UTC', 'America/Los_Angeles', ts)` for timezone conversion.
- `DATE_FORMAT(ts, 'MMM dd HH:mm')` formats a timestamp as a string (forces discrete axis labels in Databricks charts).
- `DAYOFWEEK(date)` returns 1 (Sunday) through 7 (Saturday).
- `SELECT DISTINCT col FROM table ORDER BY col` — `ORDER BY` must come after `FROM`, not after `DISTINCT`.

## External links

- [Databricks CLI tutorial](https://docs.databricks.com/aws/en/dev-tools/cli/tutorial)
- [Databricks Statement Execution API](https://docs.databricks.com/api/workspace/statementexecution)
- [Databricks SQL language reference](https://docs.databricks.com/sql/language-manual/index.html)
