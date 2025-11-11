from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import tempfile
import os
from moviepy.editor import VideoFileClip, AudioFileClip
import uuid
from pathlib import Path
import shutil
import logging
from datetime import datetime
import json
import asyncio
from typing import Dict, Optional
from enum import Enum
import aiofiles

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/app.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Task status enum
class TaskStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"

# In-memory task storage (in production, use Redis or database)
tasks: Dict[str, Dict] = {}

app = FastAPI(
    title="Video Audio Merger API", 
    description="API to merge video and audio files using MoviePy and Docker",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create temp directories
TEMP_DIR = Path("temp")
OUTPUT_DIR = Path("output")
LOGS_DIR = Path("logs")
TASKS_DIR = Path("tasks")
TEMP_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)
TASKS_DIR.mkdir(exist_ok=True)

# Configuration
MAX_OUTPUT_FILES = 10  # Maximum number of output files to keep

# Helper functions for task management
def save_task(task_id: str, task_data: dict):
    """Save task data to file"""
    task_file = TASKS_DIR / f"{task_id}.json"
    with open(task_file, 'w') as f:
        json.dump(task_data, f)
    tasks[task_id] = task_data

def get_task(task_id: str) -> Optional[dict]:
    """Get task data"""
    if task_id in tasks:
        return tasks[task_id]
    
    task_file = TASKS_DIR / f"{task_id}.json"
    if task_file.exists():
        with open(task_file, 'r') as f:
            task_data = json.load(f)
            tasks[task_id] = task_data
            return task_data
    return None

def update_task_status(task_id: str, status: TaskStatus, **kwargs):
    """Update task status"""
    task_data = get_task(task_id)
    if task_data:
        task_data['status'] = status
        task_data['updated_at'] = datetime.now().isoformat()
        task_data.update(kwargs)
        save_task(task_id, task_data)

def cleanup_old_files():
    """Keep only the latest MAX_OUTPUT_FILES files, delete older ones"""
    try:
        # Get all output files with their creation times
        output_files = []
        for file_path in OUTPUT_DIR.glob("*"):
            if file_path.is_file():
                output_files.append((file_path, file_path.stat().st_ctime))
        
        # Sort by creation time (newest first)
        output_files.sort(key=lambda x: x[1], reverse=True)
        
        # If we have more than MAX_OUTPUT_FILES, delete the oldest
        if len(output_files) > MAX_OUTPUT_FILES:
            files_to_delete = output_files[MAX_OUTPUT_FILES:]
            
            for file_path, _ in files_to_delete:
                try:
                    file_path.unlink()
                    logger.info(f"Deleted old output file: {file_path.name}")
                    
                    # Also try to find and delete corresponding task file
                    # Extract task_id from filename (e.g., merged_task-id.mp4 -> task-id)
                    filename = file_path.stem
                    if filename.startswith(('merged_', 'replaced_audio_')):
                        task_id = filename.split('_', 1)[1]
                        task_file = TASKS_DIR / f"{task_id}.json"
                        if task_file.exists():
                            task_file.unlink()
                            logger.info(f"Deleted corresponding task file: {task_id}.json")
                            # Remove from memory cache if exists
                            if task_id in tasks:
                                del tasks[task_id]
                                
                except Exception as e:
                    logger.warning(f"Failed to delete old file {file_path}: {e}")
            
            logger.info(f"Cleanup completed. Kept {MAX_OUTPUT_FILES} latest files, deleted {len(files_to_delete)} old files")
        else:
            logger.info(f"No cleanup needed. Current files: {len(output_files)}/{MAX_OUTPUT_FILES}")
            
    except Exception as e:
        logger.error(f"Error during file cleanup: {e}")

# Background processing functions
def process_merge_video_audio(task_id: str, video_path: Path, audio_path: Path):
    """Background task to merge video and audio"""
    try:
        update_task_status(task_id, TaskStatus.PROCESSING, message="Loading video and audio files")
        
        # Load video and audio clips
        video_clip = VideoFileClip(str(video_path))
        audio_clip = AudioFileClip(str(audio_path))
        
        # Handle duration matching - loop video if audio is longer
        video_duration = video_clip.duration
        audio_duration = audio_clip.duration
        logger.info(f"Task {task_id}: Video duration: {video_duration}s, Audio duration: {audio_duration}s")
        
        if audio_duration > video_duration:
            update_task_status(task_id, TaskStatus.PROCESSING, message="Audio is longer - looping video to match")
            # Calculate how many times to loop the video
            loops_needed = int(audio_duration / video_duration) + 1
            logger.info(f"Task {task_id}: Looping video {loops_needed} times to match audio duration")
            
            # Loop the video and trim to exact audio duration
            video_clip = video_clip.loop(loops_needed).subclip(0, audio_duration)
        elif video_duration > audio_duration:
            update_task_status(task_id, TaskStatus.PROCESSING, message="Video is longer - trimming to match audio")
            # Trim video to match audio duration
            video_clip = video_clip.subclip(0, audio_duration)
        else:
            update_task_status(task_id, TaskStatus.PROCESSING, message="Video and audio durations match")
        
        # Set the audio of the video clip
        final_clip = video_clip.set_audio(audio_clip)
        
        # Output path
        output_path = OUTPUT_DIR / f"merged_{task_id}.mp4"
        
        update_task_status(task_id, TaskStatus.PROCESSING, message="Writing merged video file")
        
        # Write the result to output file
        final_clip.write_videofile(
            str(output_path),
            codec='libx264',
            audio_codec='aac',
            temp_audiofile='temp-audio.m4a',
            remove_temp=True,
            verbose=False,
            logger=None
        )
        
        # Close clips to free memory
        video_clip.close()
        audio_clip.close()
        final_clip.close()
        
        # Update task as completed
        update_task_status(
            task_id, 
            TaskStatus.SUCCESS, 
            message="Video merge completed successfully",
            output_file=f"merged_{task_id}.mp4",
            file_size=output_path.stat().st_size if output_path.exists() else 0
        )
        
        logger.info(f"Task {task_id}: Merge operation completed successfully")
        
        # Cleanup old files to maintain storage limit
        cleanup_old_files()
        
    except Exception as e:
        error_msg = f"Error processing merge: {str(e)}"
        logger.error(f"Task {task_id}: {error_msg}")
        update_task_status(task_id, TaskStatus.FAILED, message=error_msg, error=str(e))
    
    finally:
        # Clean up temporary files
        try:
            if video_path.exists():
                video_path.unlink()
            if audio_path.exists():
                audio_path.unlink()
        except Exception as e:
            logger.warning(f"Task {task_id}: Error cleaning up temp files: {str(e)}")

async def process_replace_audio(task_id: str, video_path: Path, audio_path: Path):
    """Background task to replace audio in video"""
    try:
        update_task_status(task_id, TaskStatus.PROCESSING, message="Loading video and audio files")
        
        # Load video and audio clips
        video_clip = VideoFileClip(str(video_path))
        audio_clip = AudioFileClip(str(audio_path))
        
        # Handle duration matching - prioritize audio duration, loop video if needed
        video_duration = video_clip.duration
        audio_duration = audio_clip.duration
        logger.info(f"Task {task_id}: Video duration: {video_duration}s, Audio duration: {audio_duration}s")
        
        if audio_duration > video_duration:
            update_task_status(task_id, TaskStatus.PROCESSING, message="Audio is longer - looping video to match")
            # Loop video to match audio duration
            loops_needed = int(audio_duration / video_duration) + 1
            logger.info(f"Task {task_id}: Looping video {loops_needed} times to match audio duration")
            video_clip = video_clip.loop(loops_needed).subclip(0, audio_duration)
        elif video_duration > audio_duration:
            update_task_status(task_id, TaskStatus.PROCESSING, message="Video is longer - looping audio to match")
            # Loop audio to match video duration
            loops_needed = int(video_duration / audio_duration) + 1
            logger.info(f"Task {task_id}: Looping audio {loops_needed} times to match video duration")
            audio_clip = audio_clip.loop(loops_needed).subclip(0, video_duration)
        else:
            update_task_status(task_id, TaskStatus.PROCESSING, message="Video and audio durations match")
        
        # Replace the audio of the video clip
        final_clip = video_clip.set_audio(audio_clip)
        
        # Output path
        output_path = OUTPUT_DIR / f"replaced_audio_{task_id}.mp4"
        
        update_task_status(task_id, TaskStatus.PROCESSING, message="Writing video with replaced audio")
        
        # Write the result to output file
        final_clip.write_videofile(
            str(output_path),
            codec='libx264',
            audio_codec='aac',
            temp_audiofile='temp-audio.m4a',
            remove_temp=True,
            verbose=False,
            logger=None
        )
        
        # Close clips to free memory
        video_clip.close()
        audio_clip.close()
        final_clip.close()
        
        # Update task as completed
        update_task_status(
            task_id, 
            TaskStatus.SUCCESS, 
            message="Audio replacement completed successfully",
            output_file=f"replaced_audio_{task_id}.mp4",
            file_size=output_path.stat().st_size if output_path.exists() else 0
        )
        
        logger.info(f"Task {task_id}: Audio replacement completed successfully")
        
        # Cleanup old files to maintain storage limit
        cleanup_old_files()
        
    except Exception as e:
        error_msg = f"Error processing audio replacement: {str(e)}"
        logger.error(f"Task {task_id}: {error_msg}")
        update_task_status(task_id, TaskStatus.FAILED, message=error_msg, error=str(e))
    
    finally:
        # Clean up temporary files
        try:
            if video_path.exists():
                video_path.unlink()
            if audio_path.exists():
                audio_path.unlink()
        except Exception as e:
            logger.warning(f"Task {task_id}: Error cleaning up temp files: {str(e)}")

@app.get("/")
async def root():
    return {
        "message": "Video Audio Merger API is running!",
        "version": "2.1.0",
        "endpoints": {
            "merge": "POST /merge - Start merge video and audio files (smart duration matching)",
            "merge_replace": "POST /merge-replace-audio - Start replace audio in video (smart duration matching)",
            "loop_video": "POST /loop-video-to-audio - Loop video to match audio duration exactly",
            "task_status": "GET /task/{task_id}/status - Get task status",
            "task_download": "GET /task/{task_id}/download - Download completed video",
            "cleanup": "POST /cleanup - Manually clean up old files",
            "health": "GET /health - Health check",
            "docs": "GET /docs - API documentation"
        },
        "features": {
            "smart_duration_matching": "Videos loop automatically when audio is longer",
            "async_processing": "Non-blocking task-based processing",
            "multiple_formats": "Support for various video and audio formats",
            "auto_cleanup": f"Keeps only {MAX_OUTPUT_FILES} latest files automatically"
        }
    }

@app.post("/merge")
async def merge_video_audio(
    background_tasks: BackgroundTasks,
    video_file: UploadFile = File(..., description="Video file to merge"),
    audio_file: UploadFile = File(..., description="Audio file to merge")
    
):
    """
    Start merging a video file with an audio file.
    
    - **video_file**: Upload a video file (mp4, avi, mov, etc.)
    - **audio_file**: Upload an audio file (mp3, wav, aac, etc.)
    
    Returns task ID for tracking progress.
    """
    
    # Generate unique task ID
    task_id = str(uuid.uuid4())
    
    logger.info(f"Starting merge task {task_id} for video: {video_file.filename}, audio: {audio_file.filename}")
    
    # Validate file types
    video_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv']
    audio_extensions = ['.mp3', '.wav', '.aac', '.m4a', '.ogg', '.flac']
    
    # Force .mp4 for video and .mp3 for audio if no extension or unsupported
    # Handle filename and extension
    if not video_file.filename or '.' not in video_file.filename:
        # If no extension, add .mp4
        video_ext = '.mp4'
        video_file.filename = (video_file.filename or 'video') + '.mp4'
    else:
        video_ext = Path(video_file.filename).suffix.lower()
        # If extension exists but not .mp4, replace with .mp4
        if video_ext not in video_extensions:
            video_ext = '.mp4'
            video_file.filename = Path(video_file.filename).stem + '.mp4'
    
    if not audio_file.filename or '.' not in audio_file.filename:
        # If no extension, add .mp3
        audio_ext = '.mp3'
        audio_file.filename = (audio_file.filename or 'audio') + '.mp3'
    else:
        audio_ext = Path(audio_file.filename).suffix.lower()
        # If extension exists but not supported, replace with .mp3
        if audio_ext not in audio_extensions:
            audio_ext = '.mp3'
            audio_file.filename = Path(audio_file.filename).stem + '.mp3'
    audio_ext = Path(audio_file.filename).suffix.lower()
    
    if video_ext not in video_extensions:
        logger.error(f"Unsupported video format: {video_ext}")
        raise HTTPException(status_code=400, detail=f"Unsupported video format. Supported formats: {video_extensions}")
    
    if audio_ext not in audio_extensions:
        logger.error(f"Unsupported audio format: {audio_ext}")
        raise HTTPException(status_code=400, detail=f"Unsupported audio format. Supported formats: {audio_extensions}")
    
    # Create temporary file paths
    temp_video_path = TEMP_DIR / f"video_{task_id}{video_ext}"
    temp_audio_path = TEMP_DIR / f"audio_{task_id}{audio_ext}"
    
    try:
        # # Save uploaded files temporarily
        # with open(temp_video_path, "wb") as buffer:
        #     shutil.copyfileobj(video_file.file, buffer)
        
        # with open(temp_audio_path, "wb") as buffer:
        #     shutil.copyfileobj(audio_file.file, buffer)
        # 1. บันทึกไฟล์วิดีโอแบบ Asynchronous 
        # Save uploaded files asynchronously with optimized chunk size
        async with aiofiles.open(temp_video_path, "wb") as buffer:
            # Use larger chunk size (1MB) for better performance on larger files
            while chunk := await video_file.read(1024 * 1024):
                await buffer.write(chunk)

        async with aiofiles.open(temp_audio_path, "wb") as buffer:
            # Use larger chunk size (1MB) for better performance
            while chunk := await audio_file.read(1024 * 1024):
                await buffer.write(chunk)
        
        # Create task record
        task_data = {
            "task_id": task_id,
            "type": "merge",
            "status": TaskStatus.PENDING,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "video_filename": video_file.filename,
            "audio_filename": audio_file.filename,
            "message": "Task created, waiting to start processing"
        }
        save_task(task_id, task_data)
        
        # Start background processing
        background_tasks.add_task(process_merge_video_audio, task_id, temp_video_path, temp_audio_path)
        
        logger.info(f"Task {task_id} created and queued for processing")
        
        return {
            "task_id": task_id,
            "status": TaskStatus.PENDING,
            "message": "Task created successfully. Use /task/{task_id}/status to check progress.",
            "created_at": task_data["created_at"]
        }
        
    except Exception as e:
        # Clean up on error
        try:
            if temp_video_path.exists():
                temp_video_path.unlink()
            if temp_audio_path.exists():
                temp_audio_path.unlink()
        except:
            pass
        
        logger.error(f"Error creating task {task_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error creating task: {str(e)}")

@app.post("/merge-replace-audio")
async def merge_replace_audio(
    background_tasks: BackgroundTasks,
    video_file: UploadFile = File(..., description="Video file"),
    audio_file: UploadFile = File(..., description="Audio file to replace existing audio")
):
    """
    Start replacing the audio track of a video file with a new audio file.
    
    - **video_file**: Upload a video file
    - **audio_file**: Upload an audio file that will replace the existing audio
    
    Returns task ID for tracking progress.
    """
    
    # Generate unique task ID
    task_id = str(uuid.uuid4())
    
    logger.info(f"Starting audio replacement task {task_id} for video: {video_file.filename}, audio: {audio_file.filename}")
    
    # Validate file types
    video_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv']
    audio_extensions = ['.mp3', '.wav', '.aac', '.m4a', '.ogg', '.flac']
    
    video_ext = Path(video_file.filename).suffix.lower()
    audio_ext = Path(audio_file.filename).suffix.lower()
    
    if video_ext not in video_extensions:
        logger.error(f"Unsupported video format: {video_ext}")
        raise HTTPException(status_code=400, detail=f"Unsupported video format. Supported formats: {video_extensions}")
    
    if audio_ext not in audio_extensions:
        logger.error(f"Unsupported audio format: {audio_ext}")
        raise HTTPException(status_code=400, detail=f"Unsupported audio format. Supported formats: {audio_extensions}")
    
    # Create temporary file paths
    temp_video_path = TEMP_DIR / f"video_{task_id}{video_ext}"
    temp_audio_path = TEMP_DIR / f"audio_{task_id}{audio_ext}"
    
    try:
        # Save uploaded files temporarily
        with open(temp_video_path, "wb") as buffer:
            shutil.copyfileobj(video_file.file, buffer)
        
        with open(temp_audio_path, "wb") as buffer:
            shutil.copyfileobj(audio_file.file, buffer)
        
        # Create task record
        task_data = {
            "task_id": task_id,
            "type": "replace_audio",
            "status": TaskStatus.PENDING,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "video_filename": video_file.filename,
            "audio_filename": audio_file.filename,
            "message": "Task created, waiting to start processing"
        }
        save_task(task_id, task_data)
        
        # Start background processing
        background_tasks.add_task(process_replace_audio, task_id, temp_video_path, temp_audio_path)
        
        logger.info(f"Task {task_id} created and queued for processing")
        
        return {
            "task_id": task_id,
            "status": TaskStatus.PENDING,
            "message": "Task created successfully. Use /task/{task_id}/status to check progress.",
            "created_at": task_data["created_at"]
        }
        
    except Exception as e:
        # Clean up on error
        try:
            if temp_video_path.exists():
                temp_video_path.unlink()
            if temp_audio_path.exists():
                temp_audio_path.unlink()
        except:
            pass
        
        logger.error(f"Error creating task {task_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error creating task: {str(e)}")

@app.post("/loop-video-to-audio")
async def loop_video_to_audio(
    background_tasks: BackgroundTasks,
    video_file: UploadFile = File(..., description="Video file to loop"),
    audio_file: UploadFile = File(..., description="Audio file that determines the duration")
):
    """
    Loop video to match audio duration exactly.
    
    - **video_file**: Upload a video file that will be looped
    - **audio_file**: Upload an audio file that determines the final duration
    
    The video will be looped as many times as needed to match or exceed the audio duration,
    then trimmed to exact audio duration.
    
    Returns task ID for tracking progress.
    """
    
    # Generate unique task ID
    task_id = str(uuid.uuid4())
    
    logger.info(f"Starting loop video task {task_id} for video: {video_file.filename}, audio: {audio_file.filename}")
    
    # Validate file types
    video_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv']
    audio_extensions = ['.mp3', '.wav', '.aac', '.m4a', '.ogg', '.flac']
    
    video_ext = Path(video_file.filename).suffix.lower()
    audio_ext = Path(audio_file.filename).suffix.lower()
    
    if video_ext not in video_extensions:
        logger.error(f"Unsupported video format: {video_ext}")
        raise HTTPException(status_code=400, detail=f"Unsupported video format. Supported formats: {video_extensions}")
    
    if audio_ext not in audio_extensions:
        logger.error(f"Unsupported audio format: {audio_ext}")
        raise HTTPException(status_code=400, detail=f"Unsupported audio format. Supported formats: {audio_extensions}")
    
    # Create temporary file paths
    temp_video_path = TEMP_DIR / f"video_{task_id}{video_ext}"
    temp_audio_path = TEMP_DIR / f"audio_{task_id}{audio_ext}"
    
    try:
        # Save uploaded files temporarily
        with open(temp_video_path, "wb") as buffer:
            shutil.copyfileobj(video_file.file, buffer)
        
        with open(temp_audio_path, "wb") as buffer:
            shutil.copyfileobj(audio_file.file, buffer)
        
        # Create task record
        task_data = {
            "task_id": task_id,
            "type": "loop_video",
            "status": TaskStatus.PENDING,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "video_filename": video_file.filename,
            "audio_filename": audio_file.filename,
            "message": "Task created, waiting to start video looping"
        }
        save_task(task_id, task_data)
        
        # Start background processing (reuse merge function as it now handles looping)
        background_tasks.add_task(process_merge_video_audio, task_id, temp_video_path, temp_audio_path)
        
        logger.info(f"Task {task_id} created and queued for video looping processing")
        
        return {
            "task_id": task_id,
            "status": TaskStatus.PENDING,
            "message": "Video looping task created successfully. The video will be looped to match audio duration.",
            "created_at": task_data["created_at"]
        }
        
    except Exception as e:
        # Clean up on error
        try:
            if temp_video_path.exists():
                temp_video_path.unlink()
            if temp_audio_path.exists():
                temp_audio_path.unlink()
        except:
            pass
        
        logger.error(f"Error creating loop video task {task_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error creating task: {str(e)}")

@app.get("/task/{task_id}/status")
async def get_task_status(task_id: str):
    """
    Get the status of a processing task.
    
    - **task_id**: The task ID returned from merge endpoints
    
    Returns current status, progress, and details.
    """
    
    task_data = get_task(task_id)
    if not task_data:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return {
        "task_id": task_id,
        "status": task_data["status"],
        "type": task_data["type"],
        "message": task_data.get("message", ""),
        "created_at": task_data["created_at"],
        "updated_at": task_data["updated_at"],
        "video_filename": task_data.get("video_filename"),
        "audio_filename": task_data.get("audio_filename"),
        "output_file": task_data.get("output_file"),
        "file_size": task_data.get("file_size"),
        "error": task_data.get("error")
    }

@app.get("/task/{task_id}/download")
async def download_task_result(task_id: str):
    """
    Download the processed video file or get task status.
    
    - **task_id**: The task ID returned from merge endpoints
    
    Returns the processed video file if task is completed successfully,
    or returns the current task status if still processing.
    """
    
    task_data = get_task(task_id)
    if not task_data:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # If task is not completed, return status instead of file
    if task_data["status"] != TaskStatus.SUCCESS:
        return {
            "task_id": task_id,
            "status": task_data["status"],
            "type": task_data["type"],
            "message": task_data.get("message", ""),
            "created_at": task_data["created_at"],
            "updated_at": task_data["updated_at"],
            "video_filename": task_data.get("video_filename"),
            "audio_filename": task_data.get("audio_filename"),
            "error": task_data.get("error")
        }
    
    # Task completed successfully, return the file
    output_file = task_data.get("output_file")
    if not output_file:
        raise HTTPException(status_code=500, detail="Output file not found in task data")
    
    output_path = OUTPUT_DIR / output_file
    if not output_path.exists():
        raise HTTPException(status_code=404, detail="Output file not found on disk")
    
    return FileResponse(
        path=output_path,
        media_type='video/mp4',
        filename=output_file
    )

@app.get("/tasks")
async def list_tasks(limit: int = 10, status: Optional[TaskStatus] = None):
    """
    List recent tasks with optional status filtering.
    
    - **limit**: Maximum number of tasks to return (default: 10)
    - **status**: Filter by task status (pending, processing, success, failed)
    """
    
    # Get all task files
    task_files = list(TASKS_DIR.glob("*.json"))
    all_tasks = []
    
    for task_file in task_files:
        try:
            with open(task_file, 'r') as f:
                task_data = json.load(f)
                if not status or task_data.get("status") == status:
                    all_tasks.append({
                        "task_id": task_data["task_id"],
                        "type": task_data["type"],
                        "status": task_data["status"],
                        "created_at": task_data["created_at"],
                        "updated_at": task_data["updated_at"],
                        "message": task_data.get("message", "")
                    })
        except Exception as e:
            logger.warning(f"Error reading task file {task_file}: {e}")
    
    # Sort by creation time (newest first) and limit
    all_tasks.sort(key=lambda x: x["created_at"], reverse=True)
    
    return {
        "tasks": all_tasks[:limit],
        "total": len(all_tasks),
        "limit": limit,
        "filter_status": status
    }

@app.post("/cleanup")
async def manual_cleanup():
    """
    Manually trigger cleanup of old files.
    
    Keeps only the latest files according to MAX_OUTPUT_FILES limit and deletes older ones.
    """
    
    try:
        # Get file count before cleanup
        files_before = len(list(OUTPUT_DIR.glob("*")))
        
        # Run cleanup
        cleanup_old_files()
        
        # Get file count after cleanup
        files_after = len(list(OUTPUT_DIR.glob("*")))
        deleted_count = files_before - files_after
        
        return {
            "status": "success",
            "message": "Cleanup completed successfully",
            "files_before": files_before,
            "files_after": files_after,
            "files_deleted": deleted_count,
            "max_files_limit": MAX_OUTPUT_FILES,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Manual cleanup failed: {e}")
        raise HTTPException(status_code=500, detail=f"Cleanup failed: {str(e)}")

@app.post("/config/max-files")
async def update_max_files(max_files: int):
    """
    Update the maximum number of output files to keep.
    
    - **max_files**: New maximum number of files to keep (minimum: 1, maximum: 100)
    
    This will trigger an immediate cleanup if current files exceed the new limit.
    """
    
    global MAX_OUTPUT_FILES
    
    # Validate input
    if max_files < 1:
        raise HTTPException(status_code=400, detail="max_files must be at least 1")
    if max_files > 100:
        raise HTTPException(status_code=400, detail="max_files cannot exceed 100")
    
    old_limit = MAX_OUTPUT_FILES
    MAX_OUTPUT_FILES = max_files
    
    try:
        # Get current file count
        current_files = len(list(OUTPUT_DIR.glob("*")))
        
        # Trigger cleanup if needed
        cleanup_triggered = current_files > MAX_OUTPUT_FILES
        if cleanup_triggered:
            cleanup_old_files()
            files_after_cleanup = len(list(OUTPUT_DIR.glob("*")))
        else:
            files_after_cleanup = current_files
        
        logger.info(f"Updated MAX_OUTPUT_FILES from {old_limit} to {MAX_OUTPUT_FILES}")
        
        return {
            "status": "success",
            "message": f"Maximum files limit updated from {old_limit} to {MAX_OUTPUT_FILES}",
            "old_limit": old_limit,
            "new_limit": MAX_OUTPUT_FILES,
            "current_files": files_after_cleanup,
            "cleanup_triggered": cleanup_triggered,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        # Rollback on error
        MAX_OUTPUT_FILES = old_limit
        logger.error(f"Failed to update max files limit: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update limit: {str(e)}")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy", 
        "message": "API is running",
        "timestamp": datetime.now().isoformat(),
        "version": "2.1.0"
    }

@app.get("/info")
async def get_info():
    """Get API information and statistics"""
    temp_files = len(list(TEMP_DIR.glob('*'))) if TEMP_DIR.exists() else 0
    output_files = len(list(OUTPUT_DIR.glob('*'))) if OUTPUT_DIR.exists() else 0
    task_files = len(list(TASKS_DIR.glob('*.json'))) if TASKS_DIR.exists() else 0
    
    # Count tasks by status
    task_counts = {"pending": 0, "processing": 0, "success": 0, "failed": 0}
    if TASKS_DIR.exists():
        for task_file in TASKS_DIR.glob("*.json"):
            try:
                with open(task_file, 'r') as f:
                    task_data = json.load(f)
                    status = task_data.get("status", "unknown")
                    if status in task_counts:
                        task_counts[status] += 1
            except:
                pass
    
    return {
        "api": "Video Audio Merger API",
        "version": "2.1.0",
        "mode": "Async Task Processing with Smart Duration Matching & Auto Cleanup",
        "temp_files": temp_files,
        "output_files": output_files,
        "max_output_files": MAX_OUTPUT_FILES,
        "storage_status": f"{output_files}/{MAX_OUTPUT_FILES} files",
        "total_tasks": task_files,
        "task_status_counts": task_counts,
        "supported_video_formats": ['.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv'],
        "supported_audio_formats": ['.mp3', '.wav', '.aac', '.m4a', '.ogg', '.flac'],
        "features": {
            "smart_duration_matching": "Automatically loops video when audio is longer",
            "video_looping": "Dedicated endpoint for video looping to audio duration",
            "async_processing": "Non-blocking background task processing",
            "task_tracking": "Real-time status updates and progress monitoring",
            "auto_cleanup": f"Automatically keeps only {MAX_OUTPUT_FILES} latest files",
            "storage_management": "Deletes oldest files when limit exceeded"
        },
        "endpoints": {
            "create_merge_task": "POST /merge - Smart merge with duration matching",
            "create_replace_audio_task": "POST /merge-replace-audio - Smart audio replacement", 
            "create_loop_video_task": "POST /loop-video-to-audio - Loop video to audio duration",
            "check_task_status": "GET /task/{task_id}/status",
            "download_result": "GET /task/{task_id}/download",
            "list_tasks": "GET /tasks",
            "manual_cleanup": "POST /cleanup - Manually trigger file cleanup"
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)