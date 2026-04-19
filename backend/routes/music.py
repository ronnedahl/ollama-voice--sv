"""Music library REST endpoints."""

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from state import music_library

router = APIRouter(prefix="/api/music", tags=["music"])


@router.get("/list")
async def list_music():
    """List all indexed music tracks."""
    return {"tracks": [t.to_dict() for t in music_library.tracks]}


@router.get("/file/{track_id}")
async def get_music_file(track_id: str):
    """Stream a music file by track ID."""
    track = music_library.get(track_id)
    if not track:
        raise HTTPException(status_code=404, detail="Track not found")
    return FileResponse(track.path, filename=track.filename)


@router.post("/rescan")
async def rescan_music():
    """Re-scan the music directory."""
    count = music_library.scan()
    return {"count": count}
