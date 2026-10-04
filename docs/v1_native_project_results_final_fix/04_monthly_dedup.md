# Monthly violation de-duplication

The backend monthly supply and delivery validation objects remain unchanged. The presentation layer builds the visible violation-month label with a `Set` and then sorts it. A month present in both lists appears once in the summary while its table row retains both statuses as `ARZ AŞILDI + KAPASİTE AŞILDI`.

The real Chromium run asserted that the visible comma-separated violation-month list contains no duplicate values.
