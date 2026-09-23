# Analysis-run snapshot

At run start the application records:

- execution profile, authority label and result classification;
- project ID and planning year;
- dataset IDs, versions, authorities, confirmation times and sources;
- candidate/current-pattern import batch IDs and file hashes;
- engine Git commit and scientific source hash;
- scenario, algorithm, seed, objective and canonical configuration;
- the complete dry-run/readiness selection.

The snapshot is embedded in run provenance and copied into the result contract. Later active-pointer changes do not rewrite historical runs.
