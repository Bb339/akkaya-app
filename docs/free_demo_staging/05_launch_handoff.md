# Free Render Blueprint launch handoff

## Dashboard steps

1. Sign in to Render and choose **New → Blueprint**.
2. Connect `Bb339/akkaya-app` without selecting or modifying an existing production service.
3. Select branch `v2-free-demo-staging-launch` and the root `render.yaml`.
4. Confirm that Render proposes exactly one new web service: `crop-kds-v2-free-demo`, plan **Free**.
5. Confirm there is no disk, database, background worker, or other resource.
6. Enter private values for `KDS_BASIC_AUTH_USERNAME` and `KDS_BASIC_AUTH_PASSWORD` only in Render's secret prompts. Never copy them into Git, evidence, screenshots, or chat.
7. Create the separate Blueprint. Do not add a disk or upgrade the plan.
8. After deployment, verify `/healthz`, authentication, the accepted 20-file workflow, pinned preview, GA seed 123 result, unified decision return, and the explicit ephemeral-data warning.

## Expected free-tier behavior

Render free web services can spin down after inactivity and can restart at any time. The local filesystem is ephemeral, so `/tmp/crop-kds/projects` is expected to be erased after spin-down, restart, or redeploy. A cold start can take about a minute. Free instance hours, bandwidth, and build-pipeline allowances apply.

## Rollback

This branch is isolated. Rollback requires no source rewrite: remove or suspend only the `crop-kds-v2-free-demo` Render service/Blueprint and return to the accepted local tag `v2-local-staging-deployment-hardening-complete`. Do not modify the production service or the private-staging branch.

