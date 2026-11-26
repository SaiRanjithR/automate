"""Print the OpenAPI schema as JSON (used by `pnpm gen:api`; no server needed)."""

import json

from app.main import app

if __name__ == "__main__":
    print(json.dumps(app.openapi(), indent=2))
