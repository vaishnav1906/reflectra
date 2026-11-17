/**
 * Words that show up in more than one of the quotes behind a reflection: the thread
 * that makes it a pattern. Content words only, compared loosely (plurals, -ing, -ed).
 */

const STOP = new Set(
  `about after again also always been before being cant could didnt does doesnt doing dont down even every from
  going gonna have having here into just know like make more most much need never only other over really same
  should some still such than that thats their them then there these they thing things think this those through
  very want wanna were what when where which while will with would your youre yeah okay feel feeling today time`.split(/\s+/),
);

export function stem(word: string): string {
  let w = word.toLowerCase().replace(/[^a-z']/g, "").replace(/'.*$/, "");
  for (const suffix of ["ing", "ed", "es", "s"]) {
    if (w.endsWith(suffix) && w.length - suffix.length >= 3) {
      w = w.slice(0, -suffix.length);
      break;
    }
  }
  return w;
}

export function sharedWords(quotes: string[]): Set<string> {
  const counts = new Map<string, number>();
  for (const quote of quotes) {
    const seen = new Set<string>();
    for (const raw of quote.split(/\s+/)) {
      const clean = raw.toLowerCase().replace(/[^a-z']/g, "");
      if (clean.length < 4 || STOP.has(clean)) continue;
      const key = stem(clean);
      if (key.length < 3 || seen.has(key)) continue;
      seen.add(key);
      counts.set(key, (counts.get(key) ?? 0) + 1);
    }
  }
  return new Set([...counts].filter(([, n]) => n >= 2).map(([word]) => word));
}

/** Split a quote into plain text and the shared words, in order. */
export function markShared(quote: string, shared: Set<string>): { text: string; shared: boolean }[] {
  if (!shared.size) return [{ text: quote, shared: false }];
  return quote.split(/(\s+)/).map((part) => {
    const clean = part.toLowerCase().replace(/[^a-z']/g, "");
    return { text: part, shared: clean.length >= 4 && !STOP.has(clean) && shared.has(stem(clean)) };
  });
}
