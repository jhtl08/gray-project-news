import { createContext, useContext } from "react";

const noop = () => {};

export const AnnounceContext = createContext(noop);

/** Announces a message through the app's always-mounted live regions. */
export function useAnnounce() {
  return useContext(AnnounceContext);
}
