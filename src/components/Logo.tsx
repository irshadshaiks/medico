export function Logo({ size = 24 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" aria-hidden className="block">
      <rect x="2.6" y="2.6" width="18.8" height="18.8" rx="6" stroke="#4FD8E4" strokeOpacity=".55" strokeWidth="1.2" />
      <path
        d="M4.8 12.6h3.1l1.6-4.1 2.4 7.6 1.9-5 1.1 2.4h4.3"
        stroke="#4FD8E4"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
