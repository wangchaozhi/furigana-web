import { useCallback, useReducer } from "react";

import type { AnnotatedLine } from "@/lib/types";

const HISTORY_LIMIT = 50;

export type RubyHistoryState = {
  present: AnnotatedLine[];
  past: AnnotatedLine[][];
  future: AnnotatedLine[][];
};

type RubyHistoryAction =
  | { type: "reset"; lines: AnnotatedLine[] }
  | { type: "replace"; update: AnnotatedLine[] | ((current: AnnotatedLine[]) => AnnotatedLine[]) }
  | { type: "commit"; lines: AnnotatedLine[] }
  | { type: "undo" }
  | { type: "redo" };

export const EMPTY_RUBY_HISTORY: RubyHistoryState = { present: [], past: [], future: [] };

export function rubyHistoryReducer(state: RubyHistoryState, action: RubyHistoryAction): RubyHistoryState {
  switch (action.type) {
    case "reset":
      return { present: action.lines, past: [], future: [] };
    case "replace":
      return {
        ...state,
        present: typeof action.update === "function" ? action.update(state.present) : action.update,
      };
    case "commit":
      if (action.lines === state.present) return state;
      return {
        present: action.lines,
        past: [...state.past.slice(-(HISTORY_LIMIT - 1)), state.present],
        future: [],
      };
    case "undo": {
      const previous = state.past.at(-1);
      if (!previous) return state;
      return {
        present: previous,
        past: state.past.slice(0, -1),
        future: [state.present, ...state.future].slice(0, HISTORY_LIMIT),
      };
    }
    case "redo": {
      const next = state.future[0];
      if (!next) return state;
      return {
        present: next,
        past: [...state.past.slice(-(HISTORY_LIMIT - 1)), state.present],
        future: state.future.slice(1),
      };
    }
  }
}

export function useRubyHistory() {
  const [state, dispatch] = useReducer(rubyHistoryReducer, EMPTY_RUBY_HISTORY);
  const resetLines = useCallback((lines: AnnotatedLine[]) => dispatch({ type: "reset", lines }), []);
  const replaceLines = useCallback(
    (update: AnnotatedLine[] | ((current: AnnotatedLine[]) => AnnotatedLine[])) =>
      dispatch({ type: "replace", update }),
    [],
  );
  const commitLines = useCallback((lines: AnnotatedLine[]) => dispatch({ type: "commit", lines }), []);
  const undo = useCallback(() => dispatch({ type: "undo" }), []);
  const redo = useCallback(() => dispatch({ type: "redo" }), []);
  return {
    lines: state.present,
    canUndo: state.past.length > 0,
    canRedo: state.future.length > 0,
    resetLines,
    replaceLines,
    commitLines,
    undo,
    redo,
  };
}
