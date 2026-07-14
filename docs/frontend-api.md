# Frontend API Guide

This document describes the minimum API flow the frontend needs for the Sitemap Monitor MVP.

## Base URL

Local development:

```text
http://127.0.0.1:8000
```

VPS Docker deployment:

```text
http://YOUR_VPS_IP:5010
```

## Authentication Header

Most APIs require an external user id header:

```text
X-Owner-User-Id: <current-user-id>
```

The backend does not manage users. The frontend or upstream auth service should provide this value.

For local testing, use:

```text
X-Owner-User-Id: test-user
```

`GET /health` is the only MVP endpoint that does not require this header.

## Recommended Call Flow

### 1. Health Check

Use this to confirm the API is reachable.

```http
GET /health
```

Response:

```json
{
  "status": "ok"
}
```

### 2. Create Site

Create a monitored site before triggering checks.

```http
POST /sites
```

Headers:

```text
Content-Type: application/json
X-Owner-User-Id: test-user
```

Body:

```json
{
  "name": "Example",
  "root_url": "https://example.com",
  "sitemap_url": "https://example.com/sitemap.xml",
  "check_frequency": "daily"
}
```

Supported `check_frequency` values:

```text
six_hours
twelve_hours
daily
weekly
```

Response contains the site `id`. Save it as `site_id`.

### 3. List Sites

Use this for the dashboard site list.

```http
GET /sites?limit=50&offset=0
```

Headers:

```text
X-Owner-User-Id: test-user
```

### 4. Get Site Detail

Use this for a site detail page.

```http
GET /sites/{site_id}
```

Headers:

```text
X-Owner-User-Id: test-user
```

### 5. Update Site

Use this for editing name, sitemap URL, status, or frequency.

```http
PATCH /sites/{site_id}
```

Body example:

```json
{
  "name": "Example Blog",
  "check_frequency": "twelve_hours",
  "status": "active"
}
```

Supported `status` values:

```text
active
paused
```

### 6. Trigger Manual Check

This creates an async Celery task. The response only means the task was queued.

```http
POST /sites/{site_id}/checks
```

Response:

```json
{
  "task_id": "celery-task-id"
}
```

Frontend behavior:

1. Show a checking state.
2. Poll `GET /sites/{site_id}/checks`.
3. Stop polling when the latest check is `completed` or `failed`.

### 7. Poll Check History

```http
GET /sites/{site_id}/checks?limit=20&offset=0
```

Important fields:

```text
id
status
started_at
finished_at
url_count
added_count
removed_count
updated_count
error_message
```

Possible `status` values:

```text
running
completed
failed
```

Recommended polling interval after manual trigger:

```text
2-5 seconds
```

### 8. Get Check Detail

Use this if the frontend has a `check_id`.

```http
GET /checks/{check_id}
```

### 9. List URLs

Use this to display all known URLs for a site.

```http
GET /sites/{site_id}/urls?include_removed=false&limit=100&offset=0
```

Set `include_removed=true` if the UI needs to show removed URLs.

Important fields:

```text
url
lastmod
first_seen_at
last_seen_at
removed_at
```

If `removed_at` is not null, the URL is currently considered removed from the sitemap.

### 10. List Changes

Use this for the main changes feed.

```http
GET /sites/{site_id}/changes?limit=50&offset=0
```

Important fields:

```text
change_type
url
old_lastmod
new_lastmod
created_at
check_id
```

Supported `change_type` values:

```text
added
removed
updated
```

## Common UI States

### Site List Page

Call:

```text
GET /sites
```

Display:

```text
name
root_url
sitemap_url
status
check_frequency
last_checked_at
next_check_at
```

### Site Detail Page

Recommended initial calls:

```text
GET /sites/{site_id}
GET /sites/{site_id}/checks?limit=10
GET /sites/{site_id}/changes?limit=50
GET /sites/{site_id}/urls?limit=100
```

### Manual Check Button

On click:

```text
POST /sites/{site_id}/checks
```

Then poll:

```text
GET /sites/{site_id}/checks?limit=1
```

When latest check becomes `completed`, refresh:

```text
GET /sites/{site_id}
GET /sites/{site_id}/changes
GET /sites/{site_id}/urls
```

When latest check becomes `failed`, show `error_message`.

## Error Handling

Typical status codes:

```text
401: Missing X-Owner-User-Id
404: Site or check not found
422: Invalid request body or query parameter
500: Server error
```

For `401`, make sure the frontend sends:

```text
X-Owner-User-Id
```

For `422`, check URL format and enum values.

## Example Fetch Wrapper

```ts
const API_BASE_URL = 'http://127.0.0.1:8000'

async function apiFetch<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      'X-Owner-User-Id': 'test-user',
      ...options.headers,
    },
  })

  if (!response.ok) {
    const error = await response.text()
    throw new Error(error)
  }

  return response.json() as Promise<T>
}
```

## Example Manual Check Flow

```ts
async function triggerAndPollCheck(siteId: number) {
  await apiFetch<{ task_id: string }>(`/sites/${siteId}/checks`, {
    method: 'POST',
  })

  for (let attempt = 0; attempt < 30; attempt += 1) {
    await new Promise((resolve) => setTimeout(resolve, 3000))

    const checks = await apiFetch<Array<{ status: string; error_message?: string | null }>>(
      `/sites/${siteId}/checks?limit=1`,
    )

    const latestCheck = checks[0]
    if (!latestCheck) {
      continue
    }

    if (latestCheck.status === 'completed') {
      return latestCheck
    }

    if (latestCheck.status === 'failed') {
      throw new Error(latestCheck.error_message || 'Sitemap check failed')
    }
  }

  throw new Error('Sitemap check timed out')
}
```

