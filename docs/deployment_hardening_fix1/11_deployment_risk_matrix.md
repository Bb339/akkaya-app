# Deployment risk matrix

| Context | Supported state | Remaining risk |
|---|---|---|
| Local development | Supported with `py app.py`; filesystem persistence follows the selected local path | Debug server is local tooling; no server auth in explicit local mode |
| Private single-instance staging | Fix1 configuration ready for independent review | Edge/proxy request timeout must be confirmed; disk backup/restore and monitoring are operational tasks; one long analysis occupies the sole worker |
| Public production | Not ready | Basic Auth is insufficient as a full identity system; no distributed store/queue, horizontal scale, immutable upload archive, production backup/SLO, rate limiting, or full security assessment |
| Process termination during analysis | Recovered on next protected access | Work is not resumed; it is truthfully terminalized as interrupted |
| Persistent disk loss | Project state can be lost | No database, object archive, or repository-managed backup policy |
| Multiple instances/workers | Unsupported | File-backed coordination and process-scoped recovery are intentionally single-instance |
| Git unavailable | Analysis continues with explicit unavailable provenance | Commit attribution is unavailable rather than inferred |

The hosting provider's external HTTP timeout remains the main staging validation risk because the repository can configure Gunicorn's timeout but not every upstream proxy.

