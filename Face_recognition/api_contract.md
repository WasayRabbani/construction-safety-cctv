# API Contract: Video Processing

This document serves as the "Blueprint" or "Menu" for the Video Analysis feature. 
Both the Frontend Javascript and the Backend Python script MUST follow these exact rules to communicate successfully.

## 1. The Endpoint (The Address)
- **URL:** `http://127.0.0.1:5002/api/process-video`
- **HTTP Method:** `POST`
- **Purpose:** Receives a raw MP4 video file, runs it through the YOLO AI model, and returns compliance statistics along with a link to the annotated video.

## 2. Request Payload (The Input)
When Javascript sends the `POST` request, it must use a `multipart/form-data` format (which is the standard way to send files). 

The Python script will look inside the "box" for a specific label:
- **Key:** `video`
- **Value:** `[The actual .mp4 file]`

## 3. Response Payload (The Output Receipt)
Once Python successfully processes the video, it must reply with a JSON object exactly matching this structure so the Frontend knows how to update the UI.

```json
{
  "status": "success",
  "safe_count": 14,
  "viol_count": 2,
  "processing_time_sec": 4.2,
  "processed_video_url": "http://127.0.0.1:5002/processed/video1_annotated.mp4"
}
```

## 4. Error Response (If something goes wrong)
If the user uploads an invalid file, or the AI crashes, Python should reply with an error message so the Javascript can show an alert to the user.

```json
{
  "status": "error",
  "message": "Failed to process video. Invalid file format."
}
```
