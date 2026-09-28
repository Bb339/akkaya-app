# Private staging launch baseline

- Accepted hardening tag: `v2-local-staging-deployment-hardening-complete^{}`
- Accepted hardening target: `0726ac7b50a0a70dd29e3cd6b238776e51dcc321`
- Launch branch: `v2-private-staging-launch-smoke-test`
- Manifest-only successor: `6d0b8ddeb31e83359dd87cfdb101f539afa28983`

The successor changes only `autoDeploy: false` to the current schema-valid `autoDeployTrigger: 'off'`. Runtime and scientific behavior are unchanged.

