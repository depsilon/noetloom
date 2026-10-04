# Active work

This block is the project's only execution queue.

<!-- noetloom:plan -->
```json
{
  "version": 1,
  "items": []
}
```

## Historical completion evidence

<!-- noetloom:completed -->
```json
{
  "version": 1,
  "entries": [
    {
      "event": "completed",
      "project_id": "7f791247-6b06-4c5b-bf71-253b57ae5c87",
      "item": {
        "id": "P-001",
        "title": "Implement the requested project",
        "status": "planned",
        "cycle": 1,
        "depends_on": [],
        "outcome": "Build a Python standard-library CLI that totals CSV expenses by category. Input columns are category and amount; output stable JSON totals with two decimal places. Reject malformed or non-finite amounts with an error and nonzero exit. Allow negative refunds. No network services or authentication.",
        "scope": [
          "Application, local operating documents, and relevant tests"
        ],
        "acceptance": [
          "The CLI accepts exactly the category and amount columns in either order, rejects malformed rows, blank categories, nonnumeric/non-finite values, and amounts with over two fractional digits with stderr diagnostics and nonzero exit, and prints no partial stdout on failure",
          "Valid input produces deterministic JSON with sorted category keys and two-decimal amount strings; negative refunds aggregate correctly and a header-only CSV produces an empty object",
          "Subprocess tests exercise valid, empty, and invalid input through the public command"
        ],
        "verification": [
          "application"
        ]
      },
      "evidence": [
        "check-64bc8ee9b51540f98b420e97d24089f9"
      ],
      "summary": "Implemented deterministic CSV expense totals CLI with strict validation, exact decimal aggregation including refunds, subprocess coverage, and documented interface.",
      "at": "2026-10-04T17:26:31.690902+00:00"
    },
    {
      "event": "reopened",
      "project_id": "7f791247-6b06-4c5b-bf71-253b57ae5c87",
      "id": "P-001",
      "cycle": 2,
      "reason": "The accepted category filter changes the CLI contract and invalidates prior application evidence.",
      "feedback": "feedback-filter",
      "at": "2026-10-04T17:31:12.908291+00:00"
    },
    {
      "event": "completed",
      "project_id": "7f791247-6b06-4c5b-bf71-253b57ae5c87",
      "item": {
        "id": "P-001",
        "title": "Add optional category filtering to the expense totals CLI",
        "status": "planned",
        "cycle": 2,
        "depends_on": [],
        "outcome": "Build a Python standard-library CLI that totals CSV expenses by category, with an optional category filter. Input columns are category and amount; output stable JSON totals with two decimal places. Reject malformed or non-finite amounts with an error and nonzero exit. Allow negative refunds. No network services or authentication.",
        "scope": [
          "Application, local operating documents, and relevant tests"
        ],
        "acceptance": [
          "The CLI accepts exactly the category and amount columns in either order, rejects malformed rows, blank categories, nonnumeric/non-finite values, and amounts with over two fractional digits with stderr diagnostics and nonzero exit, and prints no partial stdout on failure",
          "Without a filter, valid input produces deterministic JSON with sorted category keys and two-decimal amount strings; negative refunds aggregate correctly and a header-only CSV produces an empty object",
          "With --category CATEGORY, only that category's total is returned, or {} when absent; the entire input is validated including unselected rows",
          "Subprocess tests exercise valid, empty, invalid, filtered, absent-category, and invalid-unselected-row behavior through the public command"
        ],
        "verification": [
          "application"
        ]
      },
      "evidence": [
        "check-dec5408d1e064849b1715cf0b69754d8"
      ],
      "summary": "Added optional category selection with full input validation preserved; filtered, absent-category, and unselected-invalid-row subprocess cases pass. Local/offline scope retained.",
      "at": "2026-10-04T17:32:24.271805+00:00"
    },
    {
      "event": "reopened",
      "project_id": "7f791247-6b06-4c5b-bf71-253b57ae5c87",
      "id": "P-001",
      "cycle": 3,
      "reason": "Exact arithmetic acceptance failed at unequal scales",
      "feedback": "review-exact-sum",
      "at": "2026-10-04T17:35:58.650641+00:00"
    },
    {
      "event": "completed",
      "project_id": "7f791247-6b06-4c5b-bf71-253b57ae5c87",
      "item": {
        "id": "P-001",
        "title": "Add optional category filtering to the expense totals CLI",
        "status": "planned",
        "cycle": 3,
        "depends_on": [],
        "outcome": "Build a Python standard-library CLI that totals CSV expenses by category, with an optional category filter. Input columns are category and amount; output stable JSON totals with two decimal places. Reject malformed or non-finite amounts with an error and nonzero exit. Allow negative refunds. No network services or authentication.",
        "scope": [
          "Application, local operating documents, and relevant tests"
        ],
        "acceptance": [
          "The CLI accepts exactly the category and amount columns in either order, rejects malformed rows, blank categories, nonnumeric/non-finite values, and amounts with over two fractional digits with stderr diagnostics and nonzero exit, and prints no partial stdout on failure",
          "Without a filter, valid input produces deterministic JSON with sorted category keys and two-decimal amount strings; negative refunds aggregate correctly and a header-only CSV produces an empty object",
          "With --category CATEGORY, only that category's total is returned, or {} when absent; the entire input is validated including unselected rows",
          "Subprocess tests exercise valid, empty, invalid, filtered, absent-category, and invalid-unselected-row behavior through the public command"
        ],
        "verification": [
          "application"
        ]
      },
      "evidence": [
        "check-82cb1214a6f24624a5da6e9bf6b4b852"
      ],
      "summary": "Category filtering and exact totals, including unequal-scale large amounts, pass 9 CLI tests.",
      "at": "2026-10-04T17:36:16.715708+00:00"
    },
    {
      "event": "reopened",
      "project_id": "7f791247-6b06-4c5b-bf71-253b57ae5c87",
      "id": "P-001",
      "cycle": 4,
      "reason": "Revalidate the integrated self-contained example",
      "feedback": "framework-integration",
      "at": "2026-10-04T17:56:42.097074+00:00"
    },
    {
      "event": "completed",
      "project_id": "7f791247-6b06-4c5b-bf71-253b57ae5c87",
      "item": {
        "id": "P-001",
        "title": "Add optional category filtering to the expense totals CLI",
        "status": "planned",
        "cycle": 4,
        "depends_on": [],
        "outcome": "Build a Python standard-library CLI that totals CSV expenses by category, with an optional category filter. Input columns are category and amount; output stable JSON totals with two decimal places. Reject malformed or non-finite amounts with an error and nonzero exit. Allow negative refunds. No network services or authentication.",
        "scope": [
          "Application, local operating documents, and relevant tests"
        ],
        "acceptance": [
          "The CLI accepts exactly the category and amount columns in either order, rejects malformed rows, blank categories, nonnumeric/non-finite values, and amounts with over two fractional digits with stderr diagnostics and nonzero exit, and prints no partial stdout on failure",
          "Without a filter, valid input produces deterministic JSON with sorted category keys and two-decimal amount strings; negative refunds aggregate correctly and a header-only CSV produces an empty object",
          "With --category CATEGORY, only that category's total is returned, or {} when absent; the entire input is validated including unselected rows",
          "Subprocess tests exercise valid, empty, invalid, filtered, absent-category, and invalid-unselected-row behavior through the public command"
        ],
        "verification": [
          "application",
          "framework"
        ]
      },
      "evidence": [
        "check-897abd2d77c14d719e63f1508eccf179",
        "check-5c3540ff262c44c29299c9b9a98f59df"
      ],
      "summary": "Exact totals and filtering pass nine CLI tests; integrated current helper, canonical skills, licenses and framework consistency. Original creation and fresh-session correction are preserved in history.",
      "at": "2026-10-04T17:56:42.629635+00:00"
    }
  ]
}
```
