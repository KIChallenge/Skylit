import type { Metadata } from "next";

import { StyleguideView } from "./styleguide-view";

export const metadata: Metadata = {
  title: "Styleguide",
  robots: { index: false },
};

export default function StyleguidePage() {
  return <StyleguideView />;
}
