# Media Organizer

A powerful Python-based media file management tool that automatically organizes music, books, and comics from download directories into structured libraries using hardlinks.

## Features

- **Automatic Organization** - Scans download directories and organizes media
- **Multiple Media Types** - Music, Books, Comics, Lyrics, Artwork
- **Metadata Enrichment** - MusicBrainz, Last.fm, OpenLibrary, Google Books
- **Genre Guard** - Intelligent genre validation
- **Hardlink Support** - Saves disk space
- **Navidrome Integration** - Playlist sync via Subsonic API
- **Filename Suggestions** - AI-powered improvements
- **Conflict Resolution** - Multiple strategies

## Quick Links

- [Getting Started](getting-started.md)
- [Architecture Overview](architecture/index.md)
- [Configuration Guide](configuration/index.md)
- [CLI Commands](guides/commands.md)
- [API Reference](reference/cli-commands.md)

## Supported Media Types

| Type | Extensions | Organization Pattern |
|------|------------|---------------------|
| Music | .mp3, .flac, .wav, .m4a, .ogg, .opus, .aac, .wma, .m4b | `Artist/Album/Track.ext` |
| Books | .epub, .pdf, .mobi, .azw, .azw3 | `Author/Title.ext` |
| Comics | .cbz, .cbr, .cb7, .cbt | `Title (Year) - Series #Issue.ext` |
| Lyrics | .lrc | Matched to music tracks |
| Artwork | .jpg, .jpeg, .png, .webp | Matched to albums/books |

## System Requirements

- Python 3.9+
- Linux (with hardlink support)
- 4GB RAM minimum
- 100GB disk space for media library
