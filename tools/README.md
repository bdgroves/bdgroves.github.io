# tools

Development scripts for the games under `/games/`. Not deployed —
these are for running locally before a push.

## audit-dice.js

Walks every game module, enumerates every character build, and
checks each skill check against the die it rolls.

```
npm install --no-save jsdom      # one time
node tools/audit-dice.js
node tools/audit-dice.js --verbose
```

Reports four things:

| flag | meaning | is it a bug? |
|---|---|---|
| `IMPOSSIBLE` | best possible roll cannot reach the DC | **yes** |
| `AUTOPASS` | worst possible roll cannot fail | **yes** |
| `BRUTAL` | only the highest face passes | judgement call |
| `CERTAIN` | only a natural 1 fails | judgement call |

Exits non-zero if it finds an `IMPOSSIBLE` or `AUTOPASS`, so it can
gate a commit if you ever want it to.

### Why this exists

A d8 has eight faces. If one character build sits at −2 on a stat
and another sits at +5, the modifier spread is wider than the die,
and some DC will land outside what the die can express — producing a
button that can never succeed, or a roll that can never fail. That
shipped three separate times before this tool existed.

The rule of thumb it enforces: **keep the total modifier spread for a
stat narrower than its die.** A d8 stat wants roughly a −1..+3 range,
a d20 stat can take much more.
