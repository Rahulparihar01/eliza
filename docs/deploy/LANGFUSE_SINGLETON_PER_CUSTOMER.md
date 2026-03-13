# Langfuse Singleton Per Customer

This project standard is:

- Exactly **one Langfuse deployment per customer environment**.
- All enabled applets in that customer environment share the same Langfuse instance.

## Why

- Consistent trace visibility across applets.
- Lower operational overhead than per-applet observability stacks.
- Simpler secrets and endpoint management.

## Required Deployment Rules

1. Deploy one `langfuse-web` + one `langfuse-worker` stack per customer environment.
2. Configure all app/celery services in that environment with the same:
   - `LANGFUSE_HOST`
   - `LANGFUSE_PROJECT_ID`
3. Do not provision additional Langfuse stacks per applet.
4. If Langfuse keys are absent, application should degrade gracefully with tracing disabled.

## Checklist

- [ ] One Langfuse stack exists in the environment.
- [ ] `app` and `celery-worker` point to the same `LANGFUSE_HOST`.
- [ ] Applet-specific overrides do not redefine separate Langfuse hosts.
- [ ] Startup logs show either healthy Langfuse init or explicit graceful disable.

## Local Verification

```bash
docker compose -f docker/docker-compose.yml ps langfuse-web langfuse-worker
docker compose -f docker/docker-compose.yml logs --tail=50 app celery-worker
```
