# Video Audio Merger API

A FastAPI application running in Docker that merges video and audio files using MoviePy with **async task processing**.

## ✨ Features

- 🎥 **Async video/audio merging** - Non-blocking processing
- 🔄 **Replace audio tracks** in videos asynchronously
- 🔁 **Smart duration matching** - Automatically loops video when audio is longer
- 🎬 **Video looping** - Dedicated endpoint for precise video looping
-  **Task-based system** - Get task ID immediately, check status later
- 📥 **Download by task ID** - Retrieve completed videos
- 🗂️ **Auto file management** - Keeps only 10 latest files, deletes older ones
- ⚙️ **Configurable storage** - Adjust file limits dynamically
- 🧹 **Manual cleanup** - Trigger cleanup on demand
- 🐳 **Fully containerized** with Docker
- 📝 **Interactive API documentation**
- 🏥 **Health check endpoints**
- 📊 **CORS support** for web applications
- 📈 **Task monitoring** - List and filter tasks by status

## Quick Start

### Prerequisites

- Docker
- Docker Compose

### Running the Application

1. **Clone or download the project files to your directory**

2. **Build and run with Docker Compose:**
   ```bash
   docker-compose up --build
   ```

3. **The API will be available at:**
   - API: http://localhost:8000
   - Interactive docs: http://localhost:8000/docs
   - Alternative docs: http://localhost:8000/redoc

## API Endpoints

### 🚀 Main Endpoints

**Task Creation (Returns Task ID immediately):**
- **POST /merge** - Smart merge with automatic duration matching
- **POST /merge-replace-audio** - Smart audio replacement with duration matching
- **POST /loop-video-to-audio** - Loop video to match audio duration exactly

**Task Management:**
- **GET /task/{task_id}/status** - Check processing status
- **GET /task/{task_id}/download** - Download completed video
- **GET /tasks** - List recent tasks with filtering

**File Management:**
- **POST /cleanup** - Manually clean up old files
- **POST /config/max-files** - Change maximum files limit

**System:**
- **GET /health** - Health check
- **GET /info** - API information and statistics
- **GET /** - API welcome message

### Supported File Formats

**Video Formats:**
- .mp4, .avi, .mov, .mkv, .wmv, .flv

**Audio Formats:**
- .mp3, .wav, .aac, .m4a, .ogg, .flac

### 📊 Task Status Types

- **`pending`** - Task created, waiting to start
- **`processing`** - Currently processing video
- **`success`** - Completed successfully, ready to download
- **`failed`** - Processing failed, check error message

### 🎯 Processing Modes

**1. Smart Merge (`/merge`)**
- Audio longer → Video loops automatically
- Video longer → Video trimmed to audio length
- Perfect for general merging needs

**2. Audio Replacement (`/merge-replace-audio`)**
- Replaces existing audio with new audio
- Smart duration matching applies
- Keeps original video quality

**3. Video Looping (`/loop-video-to-audio`)**
- Specifically for looping short videos to long audio
- Video repeats seamlessly until audio ends
- Perfect for background music videos

### 🗂️ Automatic File Management

**Storage Control:**
- **Default limit**: 10 latest files
- **Auto cleanup**: Runs after each successful processing
- **Oldest first**: Deletes oldest files when limit exceeded
- **Task cleanup**: Removes corresponding task records

**Configuration:**
- **Dynamic limits**: Change max files (1-100) via API
- **Manual cleanup**: Trigger cleanup anytime
- **Storage status**: View current usage in `/info`

### 🔄 Async Workflow

### How It Works:

1. **📤 Upload files** → Get task ID immediately
2. **⏳ Check status** → Monitor progress with task ID  
3. **✅ Download result** → Get processed video when ready

### 🎬 Smart Duration Matching:

- **Audio longer than video** → Video loops automatically to match
- **Video longer than audio** → Video trimmed to match audio  
- **Same duration** → No adjustment needed

### Using curl

**Step 1: Start merge task (returns task ID)**
```bash
curl -X POST "http://localhost:8000/merge" \
  -H "Content-Type: multipart/form-data" \
  -F "video_file=@your_video.mp4" \
  -F "audio_file=@your_audio.mp3"

# Response: {"task_id": "abc-123-def", "status": "pending", ...}
```

**Step 2: Check task status**
```bash
curl "http://localhost:8000/task/abc-123-def/status"

# Response: {"status": "processing", "message": "Writing merged video file", ...}
```

**Step 3: Download when complete**
```bash
curl "http://localhost:8000/task/abc-123-def/download" --output merged_video.mp4
```

**Loop video to match audio duration:**
```bash
curl -X POST "http://localhost:8000/loop-video-to-audio" \
  -H "Content-Type: multipart/form-data" \
  -F "video_file=@short_video.mp4" \
  -F "audio_file=@long_audio.mp3"

# Response: {"task_id": "xyz-789-abc", "message": "Video will be looped to match audio duration"}
```

**File management:**
```bash
# Manual cleanup (keeps 10 latest files)
curl -X POST "http://localhost:8000/cleanup"

# Change file limit to 5
curl -X POST "http://localhost:8000/config/max-files?max_files=5"

# Check current storage status
curl "http://localhost:8000/info"
```

**List all tasks:**
```bash
# All tasks
curl "http://localhost:8000/tasks"

# Filter by status
curl "http://localhost:8000/tasks?status=success&limit=5"
```

### Using the Interactive Documentation

1. Go to http://localhost:8000/docs
2. Click on any endpoint to expand it
3. Click "Try it out"
4. Upload your files
5. Click "Execute"
6. Download the processed file

## Docker Commands

**Build the image:**
```bash
docker build -t video-merger-api .
```

**Run the container:**
```bash
docker run -p 8000:8000 video-merger-api
```

**Run with volume mounts for persistent storage:**
```bash
docker run -p 8000:8000 \
  -v $(pwd)/output:/app/output \
  -v $(pwd)/temp:/app/temp \
  -v $(pwd)/logs:/app/logs \
  video-merger-api
```

**Using Docker Compose (recommended):**
```bash
# Start the application
docker-compose up -d

# View logs
docker-compose logs -f

# Stop the application
docker-compose down

# Rebuild and start
docker-compose up --build
```

## Project Structure

```
tiny_api_ffmpeg/
├── main.py              # FastAPI application with async tasks
├── requirements.txt     # Python dependencies
├── Dockerfile          # Docker configuration
├── docker-compose.yml  # Docker Compose configuration
├── .gitignore          # Git ignore rules
├── README.md           # This file
├── temp/               # Temporary files (created automatically)
├── output/             # Processed videos (created automatically)
├── tasks/              # Task status storage (created automatically)
└── logs/               # Application logs (created automatically)
```

## Environment Variables

- `PYTHONPATH=/app` - Python path
- `LOG_LEVEL=info` - Logging level

## Health Check

The application includes health checks:
- Endpoint: `GET /health`
- Docker health check runs every 30 seconds
- Returns API status and timestamp

## Logging

- Application logs are written to `logs/app.log`
- Console output is also available
- Includes request tracking and error logging

## Development

To modify the application:

1. Edit `main.py` for API changes
2. Update `requirements.txt` for new dependencies
3. Modify `Dockerfile` for system-level changes
4. Rebuild with `docker-compose up --build`

## Troubleshooting

**Common Issues:**

1. **Port already in use:**
   ```bash
   # Change port in docker-compose.yml or stop conflicting service
   docker-compose down
   ```

2. **Permission issues with volumes:**
   ```bash
   # On Linux/Mac, ensure proper permissions
   chmod -R 755 temp output logs
   ```

3. **Memory issues with large files:**
   - Increase Docker memory limits
   - Process smaller files
   - Monitor container resources

4. **FFmpeg errors:**
   - All FFmpeg dependencies are included in the Docker image
   - Check file format compatibility

## API Response Format

**Success Response:**
- Returns the processed video file as download
- Content-Type: video/mp4

**Error Response:**
```json
{
  "detail": "Error message description"
}
```

## Performance Notes

- Processing time depends on file size and system resources
- Large files may take several minutes to process
- Monitor Docker container resources for optimal performance
- Temporary files are automatically cleaned up after processing

## License

This project is open source and available under the MIT License.