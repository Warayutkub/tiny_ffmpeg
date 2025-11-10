# 🗂️ File Management Test

This document shows how the automatic file management works.

## Current Status

Check current file status:
```bash
curl http://localhost:8000/info
```

Example response:
```json
{
  "storage_status": "2/10 files",
  "max_output_files": 10,
  "output_files": 2,
  "features": {
    "auto_cleanup": "Automatically keeps only 10 latest files"
  }
}
```

## Test File Limits

### 1. Change limit to 3 files
```bash
curl -X POST "http://localhost:8000/config/max-files?max_files=3"
```

### 2. Process some videos
- Upload and process 5+ videos
- Watch automatic cleanup in action
- Only 3 newest files will remain

### 3. Manual cleanup
```bash
curl -X POST "http://localhost:8000/cleanup"
```

Response:
```json
{
  "status": "success",
  "files_before": 5,
  "files_after": 3,
  "files_deleted": 2,
  "max_files_limit": 3
}
```

## File Lifecycle

1. **Upload & Process** → Video saved to `/output/`
2. **Check Count** → If > max_files limit
3. **Auto Cleanup** → Delete oldest files
4. **Task Cleanup** → Remove corresponding task records
5. **Log Results** → Cleanup activity logged

## Benefits

- **No manual management** - Automatic storage control
- **Prevents disk full** - Always maintains space
- **Configurable limits** - Adjust based on needs
- **Latest files preserved** - Most recent work kept
- **Task consistency** - Tasks and files stay in sync

## Monitoring

Watch the logs during cleanup:
```bash
docker-compose logs -f
```

You'll see messages like:
```
INFO: Deleted old output file: merged_abc-123.mp4
INFO: Deleted corresponding task file: abc-123.json  
INFO: Cleanup completed. Kept 3 latest files, deleted 2 old files
```