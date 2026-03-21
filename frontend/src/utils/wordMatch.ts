/**
 * Normalize a word: lowercase, strip punctuation
 */
function normalize(word: string): string {
  return word.toLowerCase().replace(/[^a-z0-9]/g, '');
}

/**
 * Levenshtein edit distance between two strings
 */
function editDistance(a: string, b: string): number {
  const matrix: number[][] = [];
  for (let i = 0; i <= a.length; i++) {
    matrix[i] = [i];
  }
  for (let j = 0; j <= b.length; j++) {
    matrix[0][j] = j;
  }
  for (let i = 1; i <= a.length; i++) {
    for (let j = 1; j <= b.length; j++) {
      const cost = a[i - 1] === b[j - 1] ? 0 : 1;
      matrix[i][j] = Math.min(
        matrix[i - 1][j] + 1,      // deletion
        matrix[i][j - 1] + 1,      // insertion
        matrix[i - 1][j - 1] + cost // substitution
      );
    }
  }
  return matrix[a.length][b.length];
}

/**
 * Compare a spoken word against a target word.
 * Uses exact match first, then fuzzy matching with edit distance.
 * Threshold scales with word length to be forgiving for young readers.
 */
export function compareWords(spoken: string, target: string): boolean {
  const s = normalize(spoken);
  const t = normalize(target);

  // Exact match
  if (s === t) return true;

  // Empty check
  if (!s || !t) return false;

  // For very short words (1-2 chars), require exact match
  if (t.length <= 2) return false;

  // Edit distance threshold: allow 1 edit for words 3-5 chars, 2 for longer
  const maxDistance = t.length <= 5 ? 1 : 2;
  return editDistance(s, t) <= maxDistance;
}
