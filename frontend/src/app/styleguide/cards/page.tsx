import type { Metadata } from "next";
import { CardsPreview } from "./preview";

export const metadata: Metadata = { title: "Ergebnis-Cards", robots: { index: false } };

export default function CardsPage() { return <CardsPreview />; }
