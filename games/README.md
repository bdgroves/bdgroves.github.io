# 🎲 games

Four playable adventures, one shared engine, and a tool that refuses to let me ship a die roll you can't win.

It started because someone posted a photo of the 1983 *Star Frontiers* Referee's Screen and I wanted to roll percentile dice again. It has since become a small pile of infrastructure.

Live at [brooksgroves.com/games](https://brooksgroves.com/games.html).

---

## The games

### 🚀 [Kellath's Drift](https://brooksgroves.com/games/kellaths-drift.html)
Percentile roll-under, in the spirit of the old TSR boxes. Your survey skiff is a smoking wedge in red scrub and there's a relay tower eleven kilometres north. Roll 2d10, try to roll *under* your target. That's the whole system and it's beautiful.

### 🛰️ [Offline Protocol](https://brooksgroves.com/games/offline-protocol.html)
You're a security construct escorting a survey crew to a rig that isn't as dead as the paperwork says, and you quietly disabled your own governor module a while back. Seven acts, five crew who can die, an old guard construct you can fight *or talk down*, and a transport intelligence called Latitude who works out your secret in the first hour and remembers it between contracts.

### 🗂️ [Adjuster's Report](https://brooksgroves.com/games/adjusters-report.html)
No combat at all. You're an insurance loss adjuster on a station where a death is already ruled accidental, and clause 3.1 pays eleven million if it stays that way. Five facts, three suspects, one liar, and a culprit redrawn every run. The policy wording is readable in-game and it is the entire moral engine.

### 🏜️ [Railroad Valley: Nine Litres](https://brooksgroves.com/games/stay-with-the-vehicle.html)
Real USGS terrain in Nye County, Nevada. Your Jeep stops on a two-track with nine litres of water. Search and rescue finds *vehicles*, not people — but the advice assumes a search, and a search assumes somebody noticed you were gone. Each trip rolls whether anyone is expecting you and tells you at the start.

Somewhere out there is a geocache nobody has signed since 2004.

### 📖 The stories

Two of the four have stories worth telling outside the game. Both are complete spoilers — play first.

- **[Forty-One Entries](forty-one-entries.md)** — the man who kept the logbook in Railroad Valley, in the order it actually happened.
- **[Clause 15.2](clause-15-2.md)** — what really happened on Corvid-9, and the piece of administrative housekeeping that catches it.

### 📋 [The Referee's Screen](https://brooksgroves.com/games/reference.html)
Every mechanic in all four games, in panels, in the layout the old GM screens used. Prints cleanly if you want it on paper.

---

## How it works

```
games/
  engine.js          ← dice, audio, history, sheet, saves, chrome
  engine.css         ← everything visual, shared
  <module>.html      ← one game: content + a config object
tools/
  audit-dice.js      ← refuses to let a broken check ship
```

### The engine owns the boring parts

Dice (percentile roll-under **and** an ascending d4–d20 ladder), synthesized audio, scene history and the Back button, the character sheet, the status bar, page chrome, cross-run saves, and persistent panels for anything expensive like a Leaflet map.

A module supplies content and calls:

```js
Engine.init({
  id: 'adjusters-report',
  title: "ADJUSTER'S REPORT",
  mode: 'over',              // roll high vs DC; 'under' = percentile
  state: () => freshState(),
  status: statusFields,      // the status bar
  sheet: sheetHTML,          // the character sheet
  start: startCase
});
```

### A scene is a function

```js
function theHatch(){
  Engine.badge('ACT 2');
  Engine.render(`…prose… <button id="h1">HACK THE LOCK</button>`);
  document.getElementById('h1').onclick = ()=>{
    Engine.check({die:10, mod:player.stats.ANALYSIS, dc:DC.lock}, (ok)=>{
      Engine.render(ok ? `…it opens clean…` : `…feedback spike…`);
      Engine.wire(interior);   // next scene
    });
  };
}
```

`Engine.check` handles the dice panel, the tumbling faces, the sounds, the verdict banner and the Continue button, then calls you back with true or false. You never touch a timer.

Scenes go through `Engine.go(fn)` rather than being called directly — that's what makes Back work, and it's where the dice cleanup lives.

### The dice look like dice

Each die gets its own silhouette via CSS `clip-path` — d4 a triangle, d8 a rhombus, d10 the classic kite, d20 the hexagonal profile — with faint SVG facet lines so it reads as a solid rather than a badge with a number on it.

### The sound is synthesized

No audio files. A dice tick is a filtered noise burst with a randomized bandpass so it doesn't loop-sound; landing adds a low triangle sweep; success is a rising two-note chime; failure a falling sawtooth through a lowpass. About a hundred lines of Web Audio.

---

## 🔧 tools/audit-dice.js

```bash
npm install --no-save jsdom     # once
node tools/audit-dice.js
node tools/audit-dice.js --verbose
```

Boots every module headlessly, enumerates every character build, resolves every DC including per-run jitter, and flags four things:

| flag | meaning | bug? |
|---|---|---|
| `IMPOSSIBLE` | best possible roll can't reach the DC | **yes** |
| `AUTOPASS` | worst possible roll can't fail | **yes** |
| `BRUTAL` | only the top face passes | judgement call |
| `CERTAIN` | only a natural 1 fails | judgement call |

Exits non-zero on a real bug.

### Why it exists

A d8 has eight faces. If one build sits at −2 on a stat and another at +5, the modifier spread is **wider than the die**, and some DC will inevitably land outside what the die can express — producing a button that can never work.

I shipped that three separate times before writing this. Each time I fixed the DC. The DC was never the problem.

> **The rule it enforces: keep a stat's total modifier spread narrower than its die.** A d8 stat wants about −1..+3. A d20 stat can take much more.

It has caught five real bugs, two of which were already live, and it found one *in the same session I wrote it*.

---

## Things I learned the hard way

**Atmosphere is only for things the player already understands.** I wrote "a carrier" about forty times without defining it. A friend — who is *studying for his ham licence* — said he had no idea what it meant or what to do with it. Anything the player must act on gets said plainly, at least once.

**A game can be ambiguous about anything except how long you have to live and what a button costs.** Running dry in Railroad Valley doesn't kill you instantly — you get about nine effective hours. Correct physiology, invisible to the player, so dying felt arbitrary. Now the status bar switches from litres to a countdown.

**Don't put the lesson in the title.** The desert game was called *Stay With the Vehicle*, which answered its own question before you pressed a button. It's now *Railroad Valley: Nine Litres*, and the advice is conditional — because in real life it is.

**A secondary story must pay the primary system, not compete with it.** The mystery in Railroad Valley was ignorable until finding it yielded sixteen litres of water. Now ignoring it kills you about six times in seven.

**Automated testing catches bugs; it cannot catch confusion.** I've run hundreds of headless playthroughs. Not one of them ever had to *understand* anything.

---

## Adding a module

1. Copy an existing game as a skeleton.
2. Write content. Scenes are functions.
3. Call `Engine.init()` with your state, status, sheet and start.
4. Run the audit before you push.
5. Add a card to `games.html` and a panel set to `games/reference.html`.

The third game was written entirely as content with **zero** engine changes, which is when I believed the abstraction was drawn in the right place. The fourth one broke it — a Leaflet map can't survive `Engine.render()` wiping the DOM every scene — so the engine grew persistent panels. Thirty lines, and every future module gets them.

---

## Credits and honesty

All mechanics are original. Nothing is reproduced from any published rulebook.

Coordinates in Railroad Valley are real. The two-track, the breakdown point, and everyone in the story are fiction. **It's a game, not a route guide.** Don't drive into Nye County on the strength of it.

Built with an embarrassing amount of enthusiasm by [Brooks Groves](https://brooksgroves.com), who mostly makes maps.
