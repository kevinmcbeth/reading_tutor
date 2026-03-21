interface WordHighlightProps {
  word: string;
  state: 'inactive' | 'active' | 'correct' | 'failed';
  isChallenge: boolean;
}

export default function WordHighlight({ word, state, isChallenge }: WordHighlightProps) {
  let classes = 'inline-block mx-1 text-3xl md:text-4xl font-bold transition-all duration-300 ';

  switch (state) {
    case 'active':
      classes += 'text-blue-600 underline decoration-4 underline-offset-4 scale-110';
      break;
    case 'correct':
      classes += 'text-green-500';
      break;
    case 'failed':
      classes += 'text-red-400 line-through';
      break;
    case 'inactive':
    default:
      classes += isChallenge ? 'text-gray-700' : 'text-gray-400';
      break;
  }

  return <span className={classes}>{word}</span>;
}
