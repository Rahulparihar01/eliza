# Docker Container Rebuild Guide

## The Problem We Faced

When developing with Docker, we ran into a critical issue:
1. We rebuilt containers at 3:24 PM
2. Made code changes afterward (fixing the `.value` bug)
3. Copied files into containers with `docker cp`
4. **The code still didn't work!**

### Why Docker CP Doesn't Always Work

When you copy files into a running container:
- ✅ The file is updated on disk
- ❌ Python may have cached `.pyc` bytecode files
- ❌ Already-imported modules stay in memory with old code
- ❌ The running process doesn't reload automatically

## The Solution: Always Rebuild

### Quick Rebuild (Normal Development)
```bash
./scripts/rebuild_containers.sh
```

This rebuilds `app` and `celery-worker` containers with your latest code changes.

### Full Rebuild (After Dependency Changes)
```bash
./scripts/rebuild_containers.sh --no-cache
```

Use this when:
- You modified `requirements.txt`
- Something seems "stuck" with old behavior
- You want to guarantee a completely fresh build

### Rebuild Everything
```bash
./scripts/rebuild_containers.sh --no-cache --all
```

Rebuilds all services (frontend, logstash, etc.). Rarely needed.

## When to Rebuild

### ✅ ALWAYS Rebuild After:
- Changing Python code in `src/`
- Modifying `requirements.txt`
- Updating `Dockerfile`
- Changing shell scripts in `docker/`
- Modifying any code that runs inside containers

### ❌ DON'T Need to Rebuild After:
- Changing `.env` files (just restart: `docker-compose restart`)
- Updating database schemas (just run migrations)
- Modifying files that are volume-mounted (like `logs/`)

## Manual Rebuild Commands

If you prefer to do it manually:

```bash
# 1. Build containers
docker-compose -f docker/docker-compose.yml build app celery-worker

# 2. Restart with new images
docker-compose -f docker/docker-compose.yml up -d app celery-worker

# 3. Wait for health checks
sleep 15

# 4. Check status
docker-compose -f docker/docker-compose.yml ps
```

## How Docker Builds Work

1. **Build Stage**: Docker creates an image with your code
   - Installs dependencies
   - Copies source files
   - Creates a filesystem snapshot

2. **Run Stage**: Docker starts containers from the image
   - Containers have their own isolated filesystem
   - Code is frozen at the moment the image was built

3. **Key Point**: Containers use the image's filesystem, not your local files
   - Your local changes don't automatically appear in containers
   - You must rebuild the image to include new changes

## Why We Built the Helper Script

The helper script (`rebuild_containers.sh`):
- ✅ Ensures correct rebuild sequence
- ✅ Waits for health checks
- ✅ Shows clear status
- ✅ Prevents "I thought I rebuilt but used old code" errors
- ✅ Saves time with clear options

## Debugging Tips

### Container has old code?
```bash
# Check when the image was built
docker image inspect docker-app:latest --format='{{.Created}}'

# Compare to your last code change
git log -1 --format="%ai" src/tasks/data_analyst_tasks.py

# If image is older → REBUILD!
```

### Not sure if rebuild worked?
```bash
# Check a specific file inside the container
docker exec docker-celery-worker-1 cat /app/src/tasks/data_analyst_tasks.py | grep "data_source_type.value"

# If you see ".value" → rebuild didn't work
# Should see just "data_source_type" after our fix
```

### Want to force complete rebuild?
```bash
# Nuclear option: delete everything and rebuild
docker-compose down
docker system prune -a  # WARNING: Removes ALL unused images
./scripts/rebuild_containers.sh --no-cache --all
```

## Best Practices

1. **After ANY Python code change**: Run `./scripts/rebuild_containers.sh`
2. **Check logs immediately**: `docker-compose logs -f celery-worker`
3. **Verify changes**: Test your fix to confirm the new code is running
4. **Use --no-cache** when in doubt (adds ~2 minutes but guarantees freshness)

## Summary

**The Golden Rule**: When you change code that runs in Docker, REBUILD the containers. Don't just restart, don't just copy files—rebuild.

Use the helper script to make this painless:
```bash
./scripts/rebuild_containers.sh
```

This ensures your code changes are always reflected in the running containers.

