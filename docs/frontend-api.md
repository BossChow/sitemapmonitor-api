# 前端接口文档

## 通用请求头

除 `GET /health` 外，接口都需要：

```text
X-Owner-User-Id: <user_id>
```

本地测试可使用：

```text
X-Owner-User-Id: test-user
```

所有 `id`、`site_id`、`check_id`、`url_id` 都是 UUID 字符串。

## 枚举值

`check_frequency`：

```text
six_hours
twelve_hours
daily
weekly
```

`status`：

```text
initializing
active
paused
failed
```

`change_type` / `tracked_change_types`：

```text
added
removed
updated
```

`check.status`：

```text
queued
running
completed
failed
skipped
```

## GET /health

入参：无

出参：

```json
{
  "status": "ok"
}
```

## POST /sites

入参 Body：

```json
{
  "root_url": "https://example.com",
  "check_frequency": "daily",
  "tracked_change_types": ["added", "removed", "updated"],
  "name": "Example",
  "sitemap_url": "https://example.com/sitemap.xml"
}
```

出参：

```json
{
  "id": "uuid",
  "owner_user_id": "test-user",
  "name": "Example",
  "root_url": "https://example.com",
  "sitemap_url": null,
  "status": "initializing",
  "check_frequency": "daily",
  "tracked_change_types": ["added", "removed", "updated"],
  "baseline_started_at": null,
  "baseline_completed_at": null,
  "baseline_error_message": null,
  "error_message": null,
  "last_checked_at": null,
  "checking_started_at": null,
  "next_check_at": null,
  "created_at": "2026-07-15T00:00:00Z",
  "updated_at": "2026-07-15T00:00:00Z"
}
```

## GET /sites

入参 Query：

```text
limit: number，可选，默认 50，范围 1-200
offset: number，可选，默认 0，最小 0
```

出参：

```json
[
  {
    "id": "uuid",
    "owner_user_id": "test-user",
    "name": "Example",
    "root_url": "https://example.com",
    "sitemap_url": "https://example.com/sitemap.xml",
    "status": "active",
    "check_frequency": "daily",
    "tracked_change_types": ["added", "removed", "updated"],
    "baseline_started_at": "2026-07-15T00:00:00Z",
    "baseline_completed_at": "2026-07-15T00:00:00Z",
    "baseline_error_message": null,
    "error_message": null,
    "last_checked_at": null,
    "checking_started_at": null,
    "next_check_at": "2026-07-16T00:00:00Z",
    "created_at": "2026-07-15T00:00:00Z",
    "updated_at": "2026-07-15T00:00:00Z"
  }
]
```

## GET /sites/{site_id}

入参 Path：

```text
site_id: string
```

出参：同 `POST /sites`

## PATCH /sites/{site_id}

入参 Path：

```text
site_id: string
```

入参 Body，字段均可选：

```json
{
  "name": "Example Blog",
  "root_url": "https://example.com",
  "sitemap_url": "https://example.com/sitemap.xml",
  "status": "active",
  "check_frequency": "twelve_hours",
  "tracked_change_types": ["added"]
}
```

出参：同 `POST /sites`

## DELETE /sites/{site_id}

入参 Path：

```text
site_id: string
```

出参：

```json
{
  "message": "Site deleted"
}
```

## POST /sites/{site_id}/checks

入参 Path：

```text
site_id: string
```

出参：

```json
{
  "task_id": "celery-task-id"
}
```

## GET /sites/{site_id}/checks

入参 Path：

```text
site_id: string
```

入参 Query：

```text
change_type: string，可选，added | removed | updated
limit: number，可选，默认 50，范围 1-200
offset: number，可选，默认 0，最小 0
```

出参：

```json
[
  {
    "id": "uuid",
    "site_id": "uuid",
    "status": "completed",
    "started_at": "2026-07-15T00:00:00Z",
    "finished_at": "2026-07-15T00:01:00Z",
    "url_count": 100,
    "added_count": 2,
    "removed_count": 1,
    "updated_count": 3,
    "error_message": null,
    "change_count": 1,
    "changes": [
      {
        "id": "uuid",
        "change_type": "added",
        "url": "https://example.com/a",
        "old_lastmod": null,
        "new_lastmod": "2026-07-15",
        "created_at": "2026-07-15T00:01:00Z"
      }
    ]
  }
]
```

## GET /checks/{check_id}

入参 Path：

```text
check_id: string
```

入参 Query：

```text
change_type: string，可选，added | removed | updated
```

出参：

```json
{
  "id": "uuid",
  "site_id": "uuid",
  "status": "completed",
  "started_at": "2026-07-15T00:00:00Z",
  "finished_at": "2026-07-15T00:01:00Z",
  "url_count": 100,
  "added_count": 2,
  "removed_count": 1,
  "updated_count": 3,
  "error_message": null,
  "change_count": 1,
  "changes": [
    {
      "id": "uuid",
      "change_type": "added",
      "url": "https://example.com/a",
      "old_lastmod": null,
      "new_lastmod": "2026-07-15",
      "created_at": "2026-07-15T00:01:00Z"
    }
  ]
}
```

## GET /sites/{site_id}/urls

入参 Path：

```text
site_id: string
```

入参 Query：

```text
include_removed: boolean，可选，默认 false
limit: number，可选，默认 100，范围 1-500
offset: number，可选，默认 0，最小 0
```

出参：

```json
{
  "items": [
    {
      "id": "uuid",
      "site_id": "uuid",
      "url_hash": "hash",
      "url": "https://example.com/a",
      "lastmod": "2026-07-15",
      "first_seen_at": "2026-07-15T00:00:00Z",
      "last_seen_at": "2026-07-15T00:01:00Z",
      "last_seen_check_id": "uuid",
      "removed_at": null,
      "created_at": "2026-07-15T00:00:00Z",
      "updated_at": "2026-07-15T00:01:00Z"
    }
  ],
  "total": 100,
  "limit": 100,
  "offset": 0
}
```
