"""Shared media extension constants used across scanner, classifier and organizers."""

AUDIO_EXTS = {".mp3", ".flac", ".wav", ".m4a",
              ".ogg", ".opus", ".aac", ".wma", ".m4b"}
LYRICS_EXTS = {".lrc"}
BOOK_EXTS = {".epub", ".pdf", ".mobi", ".azw", ".azw3"}
COMIC_EXTS = {".cbz", ".cbr", ".cb7", ".cbt"}

SUPPORTED_MEDIA_EXTS = AUDIO_EXTS | LYRICS_EXTS | BOOK_EXTS | COMIC_EXTS
