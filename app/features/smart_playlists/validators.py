"""Validators for Navidrome smart playlist fields and operators."""
from typing import Any, Set

NAVIDROME_FIELDS: Set[str] = {
    "title", "album", "artist", "albumartist", "genre", "hascoverart",
    "tracknumber", "discnumber", "year", "date", "originalyear",
    "originaldate", "releaseyear", "releasedate", "size", "compilation",
    "dateadded", "datemodified", "discsubtitle", "comment", "lyrics",
    "sorttitle", "sortalbum", "sortartist", "sortalbumartist",
    "albumtype", "albumcomment", "catalognumber", "filepath", "filetype",
    "grouping", "duration", "bitrate", "bitdepth", "bpm", "channels",
    "loved", "dateloved", "lastplayed", "daterated", "playcount",
    "rating", "averagerating", "albumrating", "albumloved",
    "albumplaycount", "albumlastplayed", "albumdateloved", "albumdaterated",
    "artistrating", "artistloved", "artistplaycount",
    "mbz_album_id", "mbz_album_artist_id", "mbz_artist_id",
    "mbz_recording_id", "mbz_release_track_id", "mbz_release_group_id",
    "library_id",
}

STRING_OPERATORS: Set[str] = {
    "is", "isNot", "contains", "notContains", "startsWith", "endsWith",
}
NUMBER_OPERATORS: Set[str] = {
    "is", "isNot", "gt", "lt", "inTheRange",
}
BOOLEAN_OPERATORS: Set[str] = {"is", "isNot"}
DATE_OPERATORS: Set[str] = {
    "is", "isNot", "gt", "lt", "inTheRange", "before", "after",
    "inTheLast", "notInTheLast",
}
PLAYLIST_OPERATORS: Set[str] = {"inPlaylist", "notInPlaylist"}

BOOLEAN_FIELDS: Set[str] = {"loved", "hascoverart", "compilation", "albumloved", "artistloved"}
DATE_FIELDS: Set[str] = {
    "date", "originaldate", "releasedate", "dateadded", "datemodified",
    "dateloved", "lastplayed", "daterated", "albumlastplayed",
    "albumdateloved", "albumdaterated",
}
NUMBER_FIELDS: Set[str] = {
    "tracknumber", "discnumber", "year", "originalyear", "releaseyear",
    "size", "duration", "bitrate", "bitdepth", "bpm", "channels",
    "playcount", "rating", "averagerating", "albumrating", "albumplaycount",
    "artistrating", "artistplaycount", "library_id",
}


def validate_field(field: str) -> None:
    if field not in NAVIDROME_FIELDS:
        raise ValueError(f"Invalid field: {field!r}. Allowed: {sorted(NAVIDROME_FIELDS)}")


def validate_operator_for_field(operator: str, field: str, value: Any) -> None:
    validate_field(field)

    if operator in {"inPlaylist", "notInPlaylist"}:
        if not isinstance(value, str):
            raise ValueError(f"{operator} requires a playlist id string")
        return

    if field in BOOLEAN_FIELDS:
        allowed = BOOLEAN_OPERATORS
    elif field in DATE_FIELDS:
        allowed = DATE_OPERATORS
    elif field in NUMBER_FIELDS:
        allowed = NUMBER_OPERATORS
    else:
        allowed = STRING_OPERATORS

    if operator not in allowed:
        raise ValueError(
            f"Operator {operator!r} not allowed for field {field!r}. "
            f"Allowed: {sorted(allowed)}"
        )
