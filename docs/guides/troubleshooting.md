# Troubleshooting

Common issues and solutions.

## Common Issues

### No Media Found

**Symptom:** `process-new-media` finds no files

**Solutions:**
1. Verify download paths in `.env`:
   ```bash
   grep DOWNLOAD_PATH .env
   ```

2. Check files exist:
   ```bash
   ls -la /path/to/downloads/music
   ```

3. Check file extensions are supported:
   ```bash
   # Supported audio: .mp3, .flac, .wav, .m4a, .ogg, .opus, .aac, .wma, .m4b
   ```

### Hardlink Fails

**Symptom:** `OSError: Invalid cross-device link`

**Cause:** Source and destination on different filesystems

**Solution:** This is expected - the system falls back to copying files.

### Database Locked

**Symptom:** `DatabaseError: database is locked`

**Solutions:**
1. Check no other instance is running:
   ```bash
   ps aux | grep media-organizer
   ```

2. Kill stale processes:
   ```bash
   pkill -f media-organizer
   ```

### Genre Validation Failures

**Symptom:** Files skipped due to invalid genre

**Solutions:**
1. Check genre quality report:
   ```bash
   ./run.sh stats --genre-quality
   ```

2. Add genre to exceptions:
   ```bash
   ./run.sh edit-genre-catalog
   # Select: [4] Manage exceptions
   ```

3. Run genre backfill:
   ```bash
   ./run.sh music-genre-backfill --execute
   ```

### Navidrome Connection Fails

**Symptom:** `NavidromeClientError: connection refused`

**Solutions:**
1. Verify Navidrome is running:
   ```bash
   curl http://localhost:4533
   ```

2. Check credentials in `.env`:
   ```bash
   grep NAVIDROME .env
   ```

3. Test connection:
   ```bash
   ./run.sh navidrome-test
   ```

### Metadata Enrichment Timeout

**Symptom:** Online enrichment takes too long

**Solution:** Increase delay between API calls:
```bash
echo "MUSIC_METADATA_API_DELAY_SECONDS=2.0" >> .env
```

## Debug Mode

Enable verbose logging:

```bash
export LOG_LEVEL=DEBUG
./run.sh process-new-media
```

## Reset Database

To reset the organization database:

```bash
# Backup first!
cp data/organization.json data/organization.json.backup

# Reset
rm data/organization.json
./run.sh process-new-media --dry-run
```

## Get Help

- Check logs: `tail -f logs/organizer.log`
- Run tests: `./run.sh test`
- Open issue on GitHub
