#!/usr/bin/env python3
"""
Second-pass categorization for data/entry.csv.

The first pass was regex-only and dumped ~29% into 'misc'. This applies an
explicit lookup table first, then falls back to the regex rules, then leaves
whatever is genuinely uncategorizable as 'misc'.

Usage:  python reclassify.py       # rewrites data/entry.csv in place
        python build.py            # then rebuild the DB

Edit OVERRIDES freely — it is keyed on lowercased entry text. Adding a line
here is the intended way to correct a call you disagree with.
"""
import csv, re, pathlib, shutil, collections

HERE = pathlib.Path(__file__).parent
CSV = HERE / "data" / "entry.csv"

# ---------------------------------------------------------------------------
# Explicit calls. Keys are lowercase entry text.
# ---------------------------------------------------------------------------
OVERRIDES = {
    # --- music: acts hiding behind nicknames, real names, and puns ---
    "david robert jones": "music",          # David Bowie's birth name
    "bubba skynard": "music",               # Lynyrd Skynyrd
    "peter tork's dork": "music",           # the Monkees
    "peter tosh": "music",
    "debbie harry": "music",
    "john + yoko": "music",
    "air supply": "music",
    "deep fuckin' purple": "music",
    "the the": "music",
    "ten years after": "music",
    "the blue dogs": "music",
    "heavy metal": "music",
    "new york hardcore": "music",
    "long live randy rhoads 1956-1982": "music",
    "crankin' out halen at bikes": "music",
    "nuke the beastie boys and run dmc": "music",
    "sid vicious nite at eckerd college": "music",
    "equidemius": "music",                  # the L.A. band that kept charting
    "cheech + chong": "media",
    "cheech + chong movies": "media",
    "dan the man": "music",
    "sweet daddy": "music",
    "silly ciben": "music",
    "let's work": "music",
    "one anarchettes": "music",
    "hep cat": "music",

    # --- media / TV / print ---
    "gumby": "media",
    "the young ones": "media",
    "g.l.o.w.": "media",
    "spuds mackenzie": "media",
    "fat freddie's cat": "media",
    "hank kimball": "media",
    "mcbuzz bros.": "media",
    "wfmu": "media",
    "compact discs": "media",
    "conan quote on confronting your enemy": "media",
    "asteroids": "media",
    "wonkey + bonkey": "media",
    "squiblibian": "media",
    "subversive, intellectual books": "media",
    "reading in the bathroom": "media",
    "remote controls": "media",
    "allen watts": "media",                 # Alan Watts, the writer
    "atlantis": "media",

    # --- sports (new bucket) ---
    "detroit tigers": "sports",
    "chicago white sox": "sports",
    "the world series": "sports",
    "bowling": "sports",
    "downhill skiing": "sports",
    "shark surfing": "sports",
    "surfin'": "sports",
    "isshinryu karate": "sports",
    "frisbee dogs": "sports",
    "feeding piranhas": "sports",
    "ecu students doing $7,500 damage to n.c. state property": "sports",
    "n.d.s.u.": "sports",
    "east illinois university": "sports",

    # --- religion / spirituality (new bucket) ---
    "jesus": "religion",
    "jesus christ": "religion",
    "god": "religion",
    "nam myo-ho renge kyo": "religion",
    "magick": "religion",
    "ezekiel 23": "religion",
    "the rapture": "religion",
    "sensory deprivation": "religion",

    # --- vehicles (new bucket) ---
    "harleys": "vehicles",
    "harley davidsons": "vehicles",
    "motorcycles": "vehicles",
    "mustang gts": "vehicles",
    "chevy trucks": "vehicles",

    # --- cannabis / drug culture the regex missed ---
    "lighting farts": "cannabis",
    "torchlighting": "cannabis",
    "co2 + negative ion generators": "cannabis",
    "n.y. pot parades": "cannabis",
    "honest dealers": "cannabis",
    "honest, reliable connections": "cannabis",
    "happiness is the bag of pot the cops didn't find": "cannabis",
    "man, this stuff is sticky!!!": "cannabis",
    "no bugs": "cannabis",
    "stoner weapon": "cannabis",
    "nevada bigfoot ale": "drugs",
    "brewtowski": "drugs",
    "no hangovers!": "drugs",
    "post nasal drip": "drugs",
    "vitamin c": "drugs",
    "isolation tanks": "drugs",
    "lava lamps": "misc",
    "crystal prisms": "misc",
    "trippin'": "drugs",
    "groovyness": "drugs",

    # --- people the regex missed ---
    "my son + daughter": "people",
    "my cat, isis": "people",
    "old friends": "people",
    "friends": "people",
    "cats": "people",
    "killing deer": "misc",
    "running over cats": "misc",
    "ashes on my dog": "people",
    "the rasta dog of getaway": "people",
    "rob's place": "people",
    "slick thai slater": "people",
    "hael-ham": "people",

    # --- politics the regex missed ---
    "living outside the ussr": "politics",
    "capitalist space colonies": "politics",
    "cop with a flat tire": "politics",
    "south american airspace": "politics",
    "radar jammers": "politics",
    "trojan water bombs": "sex",

    # --- life events / milestones (new bucket) ---
    "graduating!": "milestones",
    "graduating from monty tech": "milestones",
    "handing in that last term paper": "milestones",
    "turning 21!!!!!": "milestones",
    "halloween parties": "milestones",
    "partying in chicago": "milestones",
    "partying in provincetown": "milestones",
    "money": "milestones",

    # --- experience: first-person stoned moments, the column's native genre ---
    "getting stoned on canoe float trips": "experience",
    "convincing mom that i'm not stoned": "experience",
    "eating food whilst stoned": "experience",
    "leaving your body while flashbacking at a party": "experience",
    "fishing naked": "experience",
    "happiness is being insane": "experience",
    "barf in my boots": "experience",
    "chanting the kama sutra stoned": "experience",
    "it's steamin', it's smokin', my brain is broken": "experience",
    "listening to the stooges dosed": "experience",
    "sex while tripping": "experience",
    "trippin' with the grateful dead": "experience",
    "doin' shrooms with mr. bud man": "experience",
    "tripping out at the northville insane asylum in michigan": "experience",
    "scuba diving with nitrous tanks": "experience",
    "vacation with an 8-ball": "experience",
    "sleeping late": "experience",
    "reading in the bathroom": "experience",
    "sex on the roof": "experience",
    "super psychedelic farking": "experience",
    "horizontal rain": "experience",
    "arguing with my dad over whether the far side is funny": "experience",
    "getting ann to quit drinking + start smoking": "experience",
    "my old beat-up nikes that my mom wants to throw out": "experience",
    "the beach": "experience",
    "calm down!": "experience",
    "fire it up hell!": "experience",

    # --- slang: reader coinages and in-jokes with no referent ---
    "bat shit": "slang",
    "farking": "slang",
    "cranken": "slang",
    "fuckheadddd": "slang",
    "fugly": "slang",
    "groovyness": "slang",
    "frop": "slang",
    "shmee": "slang",
    "juan bonguloid": "slang",
    "atomic flower power": "slang",
    "hael-ham": "slang",
    "squiblibian": "slang",
    "wonkey + bonkey": "slang",
    "dooner bowl": "slang",
    "gubud": "slang",
    "cranken ": "slang",

    # --- sex: missed by the regex ---
    "fat + ugly girls": "sex",
    "hot, raunchy, macho fucking": "sex",
    "getting flashed by a pretty girl": "sex",
    "making men out of little boys": "sex",
    "69": "sex",
    "bodacious ta-tas": "sex",
    "wet monkey love": "sex",
    "no muff is too tuff": "sex",
    "big dicks": "sex",
    "mr. zog's sex wax": "sex",
    "smelly, stinky panties": "sex",
    "hiding the salami": "sex",
    "any tracy lords flick": "sex",
    "husbands who also do drugs": "sex",
    "sex with married women": "sex",
    "losing your virginity": "sex",
    "being married": "sex",
    "romance": "sex",

    # --- politics ---
    "whoever nailed judge maximum john wood": "politics",
    "killing deer": "politics",
    "my favorite thing is death - publish this you sorry twits": "politics",

    # --- food ---
    "7-11 big gulps": "food",
    "chopsticks": "food",

    # --- objects / gear ---
    "lava lamps": "objects",
    "crystal prisms": "objects",
    "tie dyes": "objects",
    "dancing bears": "objects",
    "bilbo + frodo's birthday": "media",
    "being a mammal, dude!": "slang",
    "running over cats": "misc",
    "it's good to be the king": "media",
}

# Fallback regex rules, same order-sensitive logic as the first pass.
RULES = [
    ("politics", r"reagan|raygun|ollie|north|norml|nancy|meese|contra|freedom|"
                 r"bill of rights|politics|greenpeace|peace|kid's rights|capitalism|"
                 r"dixie|women's lib|unliberated|anti-nuke|activist|demonstrat|"
                 r"legaliz|prison|kgb|f\.b\.i|cia|crowley"),
    ("cannabis", r"bong|buds?\b|sinse|shmee|frop|grow|indica|sativa|marijuana|reefer|"
                 r"thai stick|skunk|hydro|phototron|halide|joint|grass|weed|kaya|ganja|"
                 r"homegrown|hemp|panama red|matanuska|gubud|dooner|smok|hits\b|hash"),
    ("drugs",    r"lsd|l\.s\.d|acid|shroom|psychedelic|coke|cocaine|codeine|nitrous|"
                 r"8-ball|blotter|stp|mda|dmt|beer|budweiser|crown royal|vodka|"
                 r"champagne|mountain dew|booze|visine|drugs"),
    ("music",    r"floyd|zeppelin|zep\b|hendrix|dead\b|deadhead|marley|zappa|metallica|"
                 r"motley|maiden|priest|ac/dc|stryper|ramones|anthrax|beefheart|samoans|"
                 r"dickies|bad brains|milkmen|sex pistols|stooges|t\. rex|doors|beatles|"
                 r"mozart|beethoven|joni|paycheck|hank williams|zz top|xtc|genesis|"
                 r"stevie|robert plant|alice cooper|elevators|murphy's law|w\.a\.s\.p|"
                 r"bon jovi|rock|reggae|band|music|guitar|meatmen|roky|mentors|dylan|"
                 r"love\b|judas"),
    ("media",    r"\btv\b|mtv|radio|magazine|high times|lampoon|jetsons|flintstones|"
                 r"brady|gilligan|addams|letterman|stern|goldthwait|movies|film|reruns|"
                 r"comic|far side|cartoon|freak brothers|bloom county|felix|wrasslin|"
                 r"newlywed|vonnegut|blake|analog|tower"),
    ("sex",      r"sex|blow job|oral|bondage|virginity|foreplay|masturbat|panties|muff|"
                 r"ta-tas|blondes|tracy lords|romance|kissing|hard-ons|dicks|salami|"
                 r"russ meyer"),
    ("food",     r"pizza|cookies|coco puffs|oreo|bugles|cherry garcia|gobstopper|spam|"
                 r"bee bim|chocolate|fatties|breakfast|bullfrogs"),
    ("people",   r"vinny|priscilla|gayle martin|damon|mike \+ jeanette|ralph \+ sue|"
                 r"andrea|angie|frank \+ debby|\bbob\b|\bed\b|jeff"),
]


def classify(text, gloss):
    key = text.strip().lower()
    if key in OVERRIDES:
        return OVERRIDES[key]
    blob = f"{text} {gloss or ''}".lower()
    for cat, pat in RULES:
        if re.search(pat, blob):
            return cat
    return "misc"


def main():
    rows = list(csv.DictReader(open(CSV, encoding="utf-8")))
    before = collections.Counter(r["category"] for r in rows)

    shutil.copy(CSV, CSV.with_suffix(".csv.bak"))
    for r in rows:
        r["category"] = classify(r["text"], r.get("gloss"))
    after = collections.Counter(r["category"] for r in rows)

    with open(CSV, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["entry_id", "installment_id", "rank",
                                           "text", "gloss", "last_month",
                                           "amount", "category"])
        w.writeheader()
        w.writerows(rows)

    print(f"backed up to {CSV.with_suffix('.csv.bak').name}\n")
    print(f"{'category':<12} {'before':>7} {'after':>7}")
    for cat in sorted(set(before) | set(after)):
        print(f"{cat:<12} {before.get(cat,0):>7} {after.get(cat,0):>7}")
    total = len(rows)
    print(f"\nmisc: {before['misc']}/{total} -> {after['misc']}/{total} "
          f"({100*after['misc']/total:.1f}%)")
    print("\nStill misc — add to OVERRIDES if you want them placed:")
    for r in sorted({r["text"] for r in rows if r["category"] == "misc"}):
        print(f"  {r}")


if __name__ == "__main__":
    main()
