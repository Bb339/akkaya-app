# Missing-value semantics

Known missing states are explicit:

| Context | Display |
|---|---|
| Current/input water absent | `Mevcut su değeri sağlanmadı` |
| Current/input profit absent | `Mevcut kâr değeri sağlanmadı` |
| Current/input efficiency absent | `Mevcut etkinlik değeri sağlanmadı` |
| Unit efficiency absent from backend presentation contract | `Bu çıktı için sağlanmadı` |
| Missing result metric | `SAĞLANMADI / NOT PROVIDED` |
| Missing annual validation | explicit backend-not-provided message |
| Missing monthly series | explicit backend-not-provided message |

Zero remains a numeric zero. It is not converted to a missing state. Current uploaded inputs and optimized stored results retain separate labels.
