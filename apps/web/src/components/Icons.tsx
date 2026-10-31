import type { SVGProps } from "react";

const base = (p: SVGProps<SVGSVGElement>) => ({ width: 18, height: 18, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: 1.8, strokeLinecap: "round" as const, strokeLinejoin: "round" as const, "aria-hidden": true, ...p });

export const IconHome = (p: SVGProps<SVGSVGElement>) => <svg {...base(p)}><path d="M3 11l9-7 9 7v9a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z" /></svg>;
export const IconFolder = (p: SVGProps<SVGSVGElement>) => <svg {...base(p)}><path d="M3 6a1 1 0 0 1 1-1h5l2 2h9a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1z" /></svg>;
export const IconBook = (p: SVGProps<SVGSVGElement>) => <svg {...base(p)}><path d="M4 5a2 2 0 0 1 2-2h13v16H6a2 2 0 0 0-2 2z" /><path d="M4 19V5" /></svg>;
export const IconNet = (p: SVGProps<SVGSVGElement>) => <svg {...base(p)}><circle cx="5" cy="7" r="2" /><circle cx="5" cy="17" r="2" /><circle cx="12" cy="12" r="2" /><circle cx="19" cy="7" r="2" /><circle cx="19" cy="17" r="2" /><path d="M7 7.6 10.2 11M7 16.4l3.2-3.4M13.8 11 17 7.6M13.8 13 17 16.4" /></svg>;
export const IconShield = (p: SVGProps<SVGSVGElement>) => <svg {...base(p)}><path d="M12 3 4 6v6c0 5 3.5 8 8 9 4.5-1 8-4 8-9V6z" /></svg>;
export const IconMenu = (p: SVGProps<SVGSVGElement>) => <svg {...base(p)}><path d="M4 6h16M4 12h16M4 18h16" /></svg>;
export const IconPlus = (p: SVGProps<SVGSVGElement>) => <svg {...base(p)}><path d="M12 5v14M5 12h14" /></svg>;
export const IconDownload = (p: SVGProps<SVGSVGElement>) => <svg {...base(p)}><path d="M12 4v11M7 10l5 5 5-5M5 20h14" /></svg>;
export const IconStop = (p: SVGProps<SVGSVGElement>) => <svg {...base(p)}><rect x="6" y="6" width="12" height="12" rx="2" /></svg>;
export const IconPlay = (p: SVGProps<SVGSVGElement>) => <svg {...base(p)}><path d="M7 5v14l12-7z" /></svg>;
export const IconUp = (p: SVGProps<SVGSVGElement>) => <svg {...base(p)}><path d="M12 19V5M6 11l6-6 6 6" /></svg>;
export const IconDown = (p: SVGProps<SVGSVGElement>) => <svg {...base(p)}><path d="M12 5v14M6 13l6 6 6-6" /></svg>;
export const IconTrash = (p: SVGProps<SVGSVGElement>) => <svg {...base(p)}><path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13" /></svg>;
export const IconOut = (p: SVGProps<SVGSVGElement>) => <svg {...base(p)}><path d="M15 4h4v16h-4M10 12h10M6 8l-4 4 4 4" transform="scale(-1,1) translate(-24,0)" /></svg>;
