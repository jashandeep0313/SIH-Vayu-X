# templates/

Message templates, one per channel per language.

```
sms_en.txt      sms_hi.txt      sms_or.txt
email_en.html   email_hi.html
push_en.json    push_hi.json
```

## Placeholders

| Token | Meaning |
|---|---|
| `{{severity}}` | GREEN / YELLOW / ORANGE / RED |
| `{{category_full}}` | e.g. "Very Severe Cyclonic Storm" |
| `{{region}}` | Nearest landfall region |
| `{{eta}}` | Local-time landfall estimate |
| `{{wind_kmph}}` | Expected maximum wind |
| `{{primary_action}}` | The single most important instruction |
| `{{affected_districts}}` | Comma-separated district list |
| `{{issued_at}}` | Issue timestamp (IST) |

## Writing rules

1. **Lead with the action, not the meteorology.** "Move to shelter" before "980 hPa".
2. **Name a specific place and time.** Vague warnings do not move people.
3. **SMS stays under 160 characters** — one segment, no jargon, no abbreviations a
   non-specialist would have to decode.
4. **Regional language matters more than English** for citizen-facing channels. Add
   `_or` (Odia), `_bn` (Bengali), `_ta` (Tamil), `_te` (Telugu) for the coastal states
   most exposed to North Indian Ocean cyclones.
5. **Never include a raw model confidence number in a public message.** It invites
   second-guessing an evacuation order. Confidence belongs in the analyst and
   district-admin templates.
