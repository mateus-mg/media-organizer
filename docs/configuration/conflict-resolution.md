# Conflict Resolution

How Media Organizer handles duplicate files.

## Strategies

| Strategy | Behavior |
|----------|----------|
| `skip` | Skip file if destination exists |
| `rename` | Add numeric suffix to new file |
| `overwrite` | Replace existing file |
| `hardlink` | Use existing file (same inode) |

## Conflict Detection

1. Check if destination path exists
2. Compare file inodes (if hardlinks)
3. Compare file sizes and modification times
4. Apply configured strategy

## Per-Type Behavior

### Music

Conflicts resolved at track level:
- Same `artist + album + title + track_number` → skip/rename
- Different editions → rename with edition suffix

### Books

Conflicts resolved at book level:
- Same `author + title` → skip/rename
- Different formats (epub vs pdf) → both kept

### Comics

Conflicts resolved at issue level:
- Same `title + year + issue_number` → skip/rename
- Different formats (cbz vs cbr) → both kept

## Hardlink Optimization

When source and destination are on same filesystem:

```python
if is_same_filesystem(source, destination):
    create_hardlink(source, destination)
else:
    copy_file(source, destination)  # Cross-filesystem
```

Same inode detected → skip duplicate organization.
