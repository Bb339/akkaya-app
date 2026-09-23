# Monthly constraint roles

Exact verified monthly supply and delivery have consumer role `POST_RUN_VALIDATION` in S1 and S2. The accepted S2 engine’s existing approximate monthly mechanism is separately labelled `approximate_s2_monthly_optimizer = OPTIMIZER_CONSTRAINT`. Fix 2 does not alter GA, ACO, or ABC mathematics and does not claim optimization under exact verified monthly delivery constraints.

An exact calendar profile can therefore mark a selected plan infeasible after optimization even when another profile would fit a July limit. This is a validation effect, not proof that the optimizer changed its plan. Preview, readiness, result provenance, and the controlled effect matrix preserve that distinction.
